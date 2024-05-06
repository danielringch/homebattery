import asyncio, bluetooth, ubinascii, struct, sys
from micropython import const
from .interfaces.batteryinterface import BatteryInterface
from ..core.microblecentral import MicroBleCentral, MicroBleDevice, MicroBleTimeoutError, ble_instance
from ..core.logging import log
from ..core.types import BatteryData, devicetype

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
                    self.__data = bytearray(blob[6:])
                else:
                    self.__success = None
                    return
            else:
                self.__data += blob

            if len(self.__data) < self.__length: # type: ignore
                self.__success = None
            else:
                if False: #TODO: crc
                    self.__log.send('Dropping packet: wrong checksum.')
                    return
                self.__success = True

        @property
        def success(self):
            return self.__success
        
        @property
        def data(self):
            return memoryview(self.__data) if self.__data is not None else None

    def __init__(self, name, config):
        self.__name = name
        self.__device_types = (devicetype.battery,)
        self.__mac = config['mac']

        self.__log = log.get_custom_logger(name)

        self.__device = None
        self.__receive_task = None
        self.__data = BatteryData(name)
        self.__current_decoder = None

    async def read_battery(self):
        try:
            ble_instance.activate()
            self.__data.invalidate()

            if self.__device is None:
                self.__device = MicroBleDevice(ble_instance)
                await self.__device.connect(self.__mac, 0, timeout=10000)
            else:
                await self.__device.reconnect(timeout=10000)

            service = await self.__device.service(bluetooth.UUID(0xffe0))
            characteristic = await service.characteristic(bluetooth.UUID(0xffe1))
            descriptor = await characteristic.descriptor()

            self.__receive_task = asyncio.create_task(self.__receive(characteristic))

            await descriptor.write(ubinascii.unhexlify('0100'))
            await asyncio.sleep(0.2)
            
            await characteristic.write(ubinascii.unhexlify('aa5590eb9700a397a25553bef1fcf9796b521483'))

            await asyncio.sleep(1.0)

            success = await self.__send(characteristic,
                                         ubinascii.unhexlify('aa5590eb960013e9e22d518e1f56085727a705a1'))
            if success:
                self.__parse(self.__current_decoder.data)

            if self.__data.valid:
                for line in str(self.__data).split('\n'):
                    self.__log.send(line)
                return self.__data
            else:
                self.__log.send(f'Failed to receive battery data.')
                return None

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
            ble_instance.deactivate()

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
            for _ in range(100):
                await asyncio.sleep(0.1)
                if self.__current_decoder.success == True:
                    return True
            self.__log.send(f'Attempt {i} for command failed.')
        return False
    
    def __parse(self, data):
        temps = tuple(x / 10 for x in struct.unpack('<HH', data[156:160]))
        cells = tuple(x / 1000 for x in struct.unpack(_JK_CELL_FORMAT_STR, data[0:64]) if x > 0)

        self.__data.update(
            v=struct.unpack('<I', data[144:148])[0] / 1000,
            i=struct.unpack('<i', data[152:156])[0] / 1000,
            soc=struct.unpack('!B', data[167:168])[0],
            c=struct.unpack('<I', data[168:172])[0] / 1000,
            c_full=struct.unpack('<I', data[172:176])[0] / 1000,
            n=struct.unpack('<I', data[176:180])[0],
            temps=temps,
            cells=cells
        )
