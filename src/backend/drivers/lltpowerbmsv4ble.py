import asyncio, bluetooth, ubinascii, struct, sys
from .interfaces.batteryinterface import BatteryInterface
from ..core.microblecentral import MicroBleCentral, MicroBleDevice, MicroBleTimeoutError
from ..core.microblecentral_singleton import ble_instance
from ..core.logging_singleton import log
from ..core.types import BatteryData, CallbackCollection
from ..core.types_singletons import devicetype

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
            temps = tuple((x - 2731) / 10 for x in struct.unpack(temp_format_string, g[23:23 +  (2 * number_of_temperatures)]))
            number_of_cells = len(c) // 2
            cell_format_string = '!' + ('H' * number_of_cells)
            cells = tuple(x / 1000 for x in struct.unpack(cell_format_string, c[0:(2 * number_of_cells)]))

            battery_data.update(
                v=struct.unpack('!H', g[0:2])[0] / 100.0,
                i=struct.unpack('!h', g[2:4])[0] / 100.0,
                soc=struct.unpack('!B', g[19:20])[0],
                c=struct.unpack('!H', g[4:6])[0] / 100.0,
                c_full=struct.unpack('!H', g[6:8])[0] / 100.0,
                n=struct.unpack('!H', g[8:10])[0],
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
                    self.__log.send('Dropping unknown packet: too short.')
                    return
                if blob[0] != 0xdd:
                    self.__log.send('Dropping unknown packet: wrong start byte.')
                    return
                if blob[2] != 0:
                    self.__log.send('Dropping packet: error indication.')
                    return
                self.__command = struct.unpack('!B', blob[1:2])[0]
                self.__length = struct.unpack('!B', blob[3:4])[0] + 3 # 2 bytes checksum + 1 byte end byte
                self.__data = bytearray(blob[4:])
            else:
                self.__data += blob

            if len(self.__data) < self.__length: # type: ignore
                self.__success = None
            else:
                if self.__data[-1] != 0x77:
                    self.__log.send('Dropping packet: wrong end byte.')
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
        self.__name = name
        self.__device_types = (devicetype.battery,)
        self.__mac = config['mac']

        self.__log = log.get_custom_logger(name)

        self.__on_data = CallbackCollection()

        self.__device = None
        self.__receive_task = None
        self.__data = BatteryData(name)
        self.__current_bundle = None
        self.__current_decoder = None

    async def read_battery(self):
        try:
            ble_instance.activate()
            self.__data.invalidate()
            self.__current_bundle = self.DataBundle()

            if self.__device is None:
                self.__device = MicroBleDevice(ble_instance)
                await self.__device.connect(self.__mac, 0, timeout=10000)
            else:
                await self.__device.reconnect(timeout=10000)

            service = await self.__device.service(bluetooth.UUID(0xff00))
            send_characteristic = await service.characteristic(bluetooth.UUID(0xff02))
            receive_characteristic = await service.characteristic(bluetooth.UUID(0xff01))
            receive_descriptor = await receive_characteristic.descriptor()

            self.__receive_task = asyncio.create_task(self.__receive(receive_characteristic))

            await receive_descriptor.write(ubinascii.unhexlify('01'), is_request=True)
            await asyncio.sleep(1.0)

            success = await self.__send(send_characteristic,
                                         ubinascii.unhexlify('dda50300fffd77'))
            if success:
                self.__current_bundle.add(self.__current_decoder)
                success = await self.__send(send_characteristic,
                                             ubinascii.unhexlify('dda50400fffc77'))
                if success:
                    self.__current_bundle.add(self.__current_decoder)

            if self.__current_bundle.complete:
                self.__current_bundle.parse(self.__data)
                for line in str(self.__data).split('\n'):
                    self.__log.send(line)
                self.__on_data.run_all(self.__data)
            else:
                self.__log.send(f'Failed to receive battery data.')

        except MicroBleTimeoutError as e:
            self.__log.send(str(e))
        except Exception as e:
            self.__log.send(f'BLE error: {e}')
            sys.print_exception(e, log.trace)
        finally:
            if self.__receive_task is not None:
                self.__receive_task.cancel()
            if self.__device is not None:
                await self.__device.disconnect()
            self.__current_decoder = None
            self.__current_bundle = None
            ble_instance.deactivate()

    @property
    def on_battery_data(self):
        return self.__on_data

    @property
    def name(self):
        return self.__name

    @property
    def device_types(self):
        return self.__device_types

    async def __receive(self, characteristic):
        characteristic.enable_rx()
        while True:
            response = await characteristic.notified()
            if self.__current_decoder is None:
                continue
            self.__current_decoder.read(response)

    async def __send(self, characteristic, data):
        for i in range(5):
            self.__current_decoder = self.MesssageDecoder(self.__log)
            await characteristic.write(data)
            for _ in range(20):
                await asyncio.sleep(0.1)
                if self.__current_decoder.success == True:
                    return True
            self.__log.send(f'Attempt {i} for command {data} failed.')
        return False