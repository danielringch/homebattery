from asyncio import create_task, sleep
from bluetooth import UUID as BT_UUID
from micropython import const
from ubinascii import unhexlify
from struct import unpack
from sys import print_exception
from .interfaces.batteryinterface import BatteryInterface
from ..core.devicetools import print_battery
from ..core.microblecentral import MicroBleCentral, MicroBleDevice, MicroBleTimeoutError, MicroBleBuffer
from ..core.types import BatteryData, run_callbacks

# ressources:


_JK_CELL_FORMAT_STR = const('<HHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHH')

class JkBmsBd4(BatteryInterface):
    class MesssageDecoder:
        def __init__(self, log):
            self.__log = log
            self.__length = 294 # 300 bytes - 6 bytes header
            self.__data = None
            self.__success = None

        def read(self, blob):
            if self.__success is not None:
                return
            self.__success = False
            if self.__data is None:
                if len(blob) >= 7 \
                        and blob[0] == 0x55 and blob[1] == 0xaa and blob[2] == 0xeb and blob[3] == 0x90 \
                        and blob[4] == 0x02:
                    self.__data = blob[6:]
                else:
                    self.__success = None
                    return
            else:
                self.__data += bytearray(blob)

            if len(self.__data) < self.__length: # type: ignore
                self.__success = None
            else:
                if False: #TODO: crc
                    self.__log.error('Dropping packet: wrong checksum.')
                    return
                self.__success = True

        @property
        def success(self):
            return self.__success
        
        @property
        def data(self):
            return memoryview(self.__data) if self.__data is not None else None

    def __init__(self, name, config):
        from ..core.singletons import Singletons
        from ..core.types import TYPE_BATTERY
        self.__name = name
        self.__device_types = (TYPE_BATTERY,)
        self.__mac = config['mac']

        self.__ble = Singletons.ble
        self.__log = Singletons.log.create_logger(name)

        self.__on_data = list()

        self.__device = None
        self.__data = BatteryData(name)
        self.__current_decoder = None

    async def read_battery(self):
        characteristic = None
        try:
            self.__ble.activate()
            self.__data.invalidate()

            if self.__device is None:
                self.__device = MicroBleDevice(self.__ble)
                await self.__device.connect(self.__mac, 0, timeout=10000)
            else:
                await self.__device.reconnect(timeout=10000)

            service = await self.__device.service(BT_UUID(0xffe0))
            characteristic = await service.characteristic(BT_UUID(0xffe1))
            descriptor = await characteristic.descriptor()

            characteristic.enable_rx(self.__handle_blob)

            await descriptor.write(unhexlify('0100'))
            await sleep(0.2)
            
            await characteristic.write(unhexlify('aa5590eb9700a397a25553bef1fcf9796b521483'))

            await sleep(1.0)

            success = await self.__send(characteristic,
                                         unhexlify('aa5590eb960013e9e22d518e1f56085727a705a1'))
            if success:
                self.__parse(self.__current_decoder.data)

            if self.__data.valid:
                print_battery(self.__log, self.__data)
                run_callbacks(self.__on_data, self.__data)
            else:
                self.__log.error('Failed to receive battery data.')

        except MicroBleTimeoutError as e:
            self.__log.error(str(e))
        except Exception as e:
            self.__log.error('BLE error: ', e)
            from ..core.singletons import Singletons
            print_exception(e, Singletons.log.trace)
        finally:
            if characteristic is not None:
                characteristic.disable_rx()
            if self.__device is not None:
                await self.__device.disconnect()
            self.__current_decoder = None
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

    def __handle_blob(self, data):
        if self.__current_decoder is not None:
            self.__current_decoder.read(data)

    async def __send(self, characteristic, data):
        for i in range(5):
            self.__current_decoder = self.MesssageDecoder(self.__log)
            await characteristic.write(data)
            for _ in range(100):
                await sleep(0.1)
                if self.__current_decoder.success == True:
                    return True
            self.__log.error('Attempt ', i, ' for command failed.')
        return False
    
    def __parse(self, data):
        temps = tuple(x / 10 for x in unpack('<HH', data[156:160]))
        cells = tuple(x / 1000 for x in unpack(_JK_CELL_FORMAT_STR, data[0:64]) if x > 0)

        self.__data.update(
            v=unpack('<I', data[144:148])[0] / 1000,
            i=unpack('<i', data[152:156])[0] / 1000,
            soc=unpack('!B', data[167:168])[0],
            c=unpack('<I', data[168:172])[0] / 1000,
            c_full=unpack('<I', data[172:176])[0] / 1000,
            n=unpack('<I', data[176:180])[0],
            temps=temps,
            cells=cells
        )
