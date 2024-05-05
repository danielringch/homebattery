import asyncio, bluetooth, ubinascii, struct, sys
from micropython import const
from .interfaces.batteryinterface import BatteryInterface
from ..core.microblecentral import MicroBleCentral, MicroBleDevice, MicroBleTimeoutError, ble_instance
from ..core.logging import log
from ..core.types import BatteryData, devicetype

_DALY_CELL_FORMAT_STR = const('!HHHHHHHHHHHHHHHH')

class Daly8S24V60A(BatteryInterface):
    def __init__(self, name, config):
        self.__device_types = (devicetype.battery,)
        self.__mac = config['mac']

        self.__log = log.get_custom_logger(name)

        self.__device = None
        self.__receive_task = None
        self.__receiving = False
        self.__data = BatteryData(name)

    async def read_battery(self):
        try:
            self.__data.invalidate()

            if self.__device is None:
                self.__device = MicroBleDevice(ble_instance)
                await self.__device.connect(self.__mac, 1, timeout=10000)
            else:
                await self.__device.reconnect(timeout=10000)
            
            service = await self.__device.service(bluetooth.UUID(0xfff0))
            tx_characteristic = await service.characteristic(bluetooth.UUID(0xfff2))
            rx_characteristic = await service.characteristic(bluetooth.UUID(0xfff1))
            rx_descriptor = await rx_characteristic.descriptor()

            self.__receive_task = asyncio.create_task(self.__receive(rx_characteristic))

            await tx_characteristic.write(b'')
            await rx_descriptor.write(ubinascii.unhexlify('01'), is_request=True)

            self.__receiving = True
            await tx_characteristic.write(ubinascii.unhexlify('d2030000003ed7b9'))

            for _ in range(50):
                await asyncio.sleep(0.1)
                if self.__data.valid:
                    break
            else:
                self.__log.send(f'Failed to receive battery data.')
                return None
            
            for line in str(self.__data).split('\n'):
                self.__log.send(line)
            return self.__data

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

    @property
    def device_types(self):
        return self.__device_types

    async def __receive(self, characteristic):
        characteristic.enable_rx()
        while True:
            response = await characteristic.notified()
            if not self.__receiving:
                continue
            if len(response) < 128:
                self.__log.send(f'Dropping too short bluetooth packet, mac={self.__mac}, len={len(response)}.')
                continue
            if response[0] == 0xd2 and response[1] == 0x03 and response[2] == 0x7c:
                self.__parse(response)
                self.__receiving = False
                continue
                    
            self.__log.send(f'Dropping unknown bluetooth packet, mac={self.__mac}, data={response} .')

    def __parse(self, data):
        temp_1 = struct.unpack('!B', data[94:95])[0] - 40
        temp_2 = struct.unpack('!B', data[96:97])[0] - 40
        temps = (temp_1, temp_2)
        cells = tuple(x / 1000 for x in struct.unpack(_DALY_CELL_FORMAT_STR, memoryview(data)[3:35]) if x > 0)

        self.__data.update(
                v=struct.unpack('!H', data[83:85])[0] / 10,
                i=(struct.unpack('!H', data[85:87])[0] - 30000) / 10,
                soc=struct.unpack('!H', data[87:89])[0] / 10.0,
                c=struct.unpack('!H', data[99:101])[0] / 10.0,
                c_full=0,
                n=struct.unpack('!H', data[105:107])[0],
                temps=temps,
                cells=cells
        )