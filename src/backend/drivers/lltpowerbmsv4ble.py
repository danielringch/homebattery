from asyncio import create_task, sleep
from bluetooth import UUID as BT_UUID
from ubinascii import unhexlify
from struct import unpack
from sys import print_exception
from .interfaces.batteryinterface import BatteryInterface
from ..core.devicetools import print_battery
from ..core.microblecentral import MicroBleCentral, MicroBleDevice, MicroBleTimeoutError, MicroBleBuffer
from ..core.types import BatteryData, CallbackCollection

# ressources:
# https://blog.ja-ke.tech/2020/02/07/ltt-power-bms-chinese-protocol.html
# https://www.lithiumbatterypcb.com/smart-bms-software-download/
# https://www.lithiumbatterypcb.com/wp-content/uploads/2023/05/RS485-UART-RS232-Communication-protocol.pdf

class LltPowerBmsV4Ble(BatteryInterface):
    class DataBundle:
        def __init__(self):
            self.__general_blob = None
            self.__cells_blob = None

        def add(self, decoder):
            if decoder.command == 3:
                self.__general_blob = decoder.data
            elif decoder.command == 4:
                self.__cells_blob = decoder.data

        @property
        def complete(self):
            return self.__general_blob is not None and self.__cells_blob is not None
        
        def parse(self, battery_data: BatteryData):
            if not self.complete:
                return None
            g = self.__general_blob
            c = self.__cells_blob
            number_of_temperatures = (len(g) - 23) // 2
            temp_format_string = '!' + ('H' * number_of_temperatures)
            temps = tuple((x - 2731) / 10 for x in unpack(temp_format_string, g[23:23 +  (2 * number_of_temperatures)]))
            number_of_cells = len(c) // 2
            cell_format_string = '!' + ('H' * number_of_cells)
            cells = tuple(x / 1000 for x in unpack(cell_format_string, c[0:(2 * number_of_cells)]))

            battery_data.update(
                v=unpack('!H', g[0:2])[0] / 100.0,
                i=unpack('!h', g[2:4])[0] / 100.0,
                soc=unpack('!B', g[19:20])[0],
                c=unpack('!H', g[4:6])[0] / 100.0,
                c_full=unpack('!H', g[6:8])[0] / 100.0,
                n=unpack('!H', g[8:10])[0],
                temps=temps,
                cells=cells
            )

    class MesssageDecoder:
        def __init__(self, log):
            self.__log = log
            self.__length = None
            self.__data = None
            self.__command = None
            self.__success = None

        def read(self, blob):
            if self.__success is not None:
                return
            self.__success = False
            if self.__data is None:
                if len(blob) < 5: # at least one byte payload
                    self.__log.error('Dropping unknown packet: too short.')
                    return
                if blob[0] != 0xdd:
                    self.__log.error('Dropping unknown packet: wrong start byte.')
                    return
                if blob[2] != 0:
                    self.__log.error('Dropping packet: error indication.')
                    return
                self.__command = unpack('!B', blob[1:2])[0]
                self.__length = unpack('!B', blob[3:4])[0] + 3 # 2 bytes checksum + 1 byte end byte
                self.__data = bytearray(blob[4:])
            else:
                self.__data += bytearray(blob)

            if len(self.__data) < self.__length: # type: ignore
                self.__success = None
            else:
                if self.__data[-1] != 0x77:
                    self.__log.error('Dropping packet: wrong end byte.')
                    return
                self.__success = True

        @property
        def success(self):
            return self.__success
        
        @property
        def command(self):
            return self.__command
        
        @property
        def data(self):
            return memoryview(self.__data)[:-3] if self.__data is not None else None

    def __init__(self, name, config):
        from ..core.singletons import Singletons
        from ..core.types import TYPE_BATTERY
        self.__name = name
        self.__device_types = (TYPE_BATTERY,)
        self.__mac = config['mac']

        self.__ble = Singletons.ble
        self.__log = Singletons.log.create_logger(name)

        self.__on_data = CallbackCollection()

        self.__device = None
        self.__data = BatteryData(name)
        self.__current_bundle = None
        self.__current_decoder = None

    async def read_battery(self):
        rx_characteristic = None
        try:
            self.__ble.activate()
            self.__data.invalidate()
            self.__current_bundle = self.DataBundle()

            if self.__device is None:
                self.__device = MicroBleDevice(self.__ble)
                await self.__device.connect(self.__mac, 0, timeout=10000)
            else:
                await self.__device.reconnect(timeout=10000)

            service = await self.__device.service(BT_UUID(0xff00))
            tx_characteristic = await service.characteristic(BT_UUID(0xff02))
            rx_characteristic = await service.characteristic(BT_UUID(0xff01))
            rx_descriptor = await rx_characteristic.descriptor()

            rx_characteristic.enable_rx(self.__handle_blob)

            await rx_descriptor.write(unhexlify('01'), is_request=True)
            await sleep(1.0)

            success = await self.__send(tx_characteristic, unhexlify('dda50300fffd77'))
            if success:
                self.__current_bundle.add(self.__current_decoder)
                success = await self.__send(tx_characteristic, unhexlify('dda50400fffc77'))
                if success:
                    self.__current_bundle.add(self.__current_decoder)

            if self.__current_bundle.complete:
                self.__current_bundle.parse(self.__data)
                print_battery(self.__log, self.__data)
                self.__on_data.run_all(self.__data)
            else:
                self.__log.error(f'Failed to receive battery data.')

        except MicroBleTimeoutError as e:
            self.__log.error(str(e))
        except Exception as e:
            self.__log.error(f'BLE error: {e}')
            from ..core.singletons import Singletons
            print_exception(e, Singletons.log.trace)
        finally:
            if rx_characteristic is not None:
                rx_characteristic.disable_rx()
            if self.__device is not None:
                await self.__device.disconnect()
            self.__current_decoder = None
            self.__current_bundle = None
            self.__ble.deactivate()

    @property
    def on_battery_data(self):
        return self.__on_data

    @property
    def name(self):
        return self.__name

    @property
    def device_types(self):
        return self.__device_types

    def __handle_blob(self, blob):
        if self.__current_decoder is not None:
            self.__current_decoder.read(blob)

    async def __send(self, characteristic, data):
        for i in range(5):
            self.__current_decoder = self.MesssageDecoder(self.__log)
            await characteristic.write(data)
            for _ in range(20):
                await sleep(0.1)
                if self.__current_decoder.success == True:
                    return True
            self.__log.error(f'Attempt {i} for command {data} failed.')
        return False