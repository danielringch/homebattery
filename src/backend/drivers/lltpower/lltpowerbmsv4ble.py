from asyncio import sleep
from bluetooth import UUID as BT_UUID
from ubinascii import unhexlify
from ..interfaces.batteryinterface import BatteryInterface
from ...core.devicetools import print_battery
from ...core.microblecentral import MicroBleCentral, MicroBleDevice, MicroBleTimeoutError
from ...core.logging import CustomLogger
from ...core.types import run_callbacks
from ...helpers.batterydata import BatteryData
from ...helpers.streamreader import read_big_uint8, read_big_uint16, read_big_int16

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

            battery_data.v=read_big_uint16(g, 0) / 100
            battery_data.i=read_big_int16(g, 2) / 100
            battery_data.c=read_big_uint16(g, 4) / 100
            battery_data.c_full=read_big_uint16(g, 6) / 100
            battery_data.n=read_big_uint16(g, 8)
            battery_data.soc=read_big_uint8(g, 19)
            battery_data.temps = tuple((read_big_uint16(g, i) - 2731) / 10 for i in range(23, len(g), 2))
            battery_data.cells = tuple(read_big_uint16(c, i) / 1000 for i in range(0, len(c), 2))
            battery_data.validate()

    class MesssageDecoder:
        def __init__(self, log):
            self.__log = log
            self.__length = None
            self.__data = None
            self.__command = None
            self.__checksum = 0x10000
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
                self.__command = read_big_uint8(blob, 1)
                self.__length = read_big_uint8(blob, 3) + 3 # 2 bytes checksum + 1 byte end byte
                self.__data = bytearray(blob[4:])
                for i in range(2, len(blob)):
                    self.__checksum -= blob[i]
            else:
                self.__data += bytearray(blob)
                for i in range(0, len(blob) - 3):
                    self.__checksum -= blob[i]

            if len(self.__data) < self.__length: # type: ignore
                self.__success = None
            else:
                received_checksum = read_big_uint16(self.__data, -3)
                if received_checksum != self.__checksum:
                    self.__log.error('Dropping packet: wrong checksum.')
                    return

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
        from ...core.singletons import Singletons
        from ...core.types import TYPE_BATTERY
        self.__name = name
        self.__device_types = (TYPE_BATTERY,)
        self.__mac = config['mac']

        self.__ble = Singletons.ble
        self.__log: CustomLogger = Singletons.log.create_logger(name)

        self.__on_data = list()

        self.__device = None
        self.__data = BatteryData(name)
        self.__current_bundle = None
        self.__current_decoder = None

    async def read_battery(self):
        rx_characteristic = None
        try:
            self.__ble.activate()
            self.__data.reset()
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
                run_callbacks(self.__on_data, self.__data)
            else:
                self.__log.error('Failed to receive battery data.')

        except MicroBleTimeoutError as e:
            self.__log.error(str(e))
        except Exception as e:
            self.__log.error('BLE error: ', e)
            self.__log.trace(e)
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
            self.__log.error('Attempt ', i, ' for command ', data, ' failed.')
        return False