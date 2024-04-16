import asyncio, bluetooth, ubinascii, struct, sys
from .interfaces.batteryinterface import BatteryInterface
from ..core.microblecentral import MicroBleCentral, MicroBleDevice, MicroBleTimeoutError, ble_instance
from ..core.logging import log
from ..core.types import BatteryData, devicetype

class Daly8S24V60A(BatteryInterface):
    class DataBundle(BatteryData):
        def __init__(self):
            super().__init__()
            self.__complete = False

        @property
        def complete(self):
            return self.__complete

        def parse(self, data):
            self.__complete = True
            view = memoryview(data)
            self.voltage = struct.unpack('!H', view[79:81])[0] / 10.0
            self.current = None
            self.soc = struct.unpack('!H', view[87:89])[0] / 10.0
            self.capacity_remaining = struct.unpack('!H', view[99:101])[0] / 10.0
            self.capacity_full = None
            self.cycles = struct.unpack('!H', view[105:107])[0]
            for i in range(8):
                position = 3 + (2 * i)
                voltage = struct.unpack('!H', view[position: position + 2])[0] / 1000.0
                self.cell_voltages.append(voltage)

    def __init__(self, name, config):
        self.__device_types = (devicetype.battery,)
        self.__mac = config['mac']

        self.__log = log.get_custom_logger(name)

        self.__device = None
        self.__receive_task = None
        self.__data = None

    async def read_battery(self):
        try:
            self.__data = self.DataBundle()

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

            await tx_characteristic.write(ubinascii.unhexlify('d2030000003ed7b9'))

            for _ in range(50):
                await asyncio.sleep(0.1)
                if self.__data.complete:
                    break
            else:
                self.__log.send(f'Failed to receive battery data.')
                return None
            
            self.__log.send(f'Voltage: {self.__data.voltage} V | Current: {self.__data.current} A')
            self.__log.send(f'SoC: {self.__data.soc} % | {self.__data.capacity_remaining} / {self.__data.capacity_full} Ah')
            self.__log.send(f'Cycles: {self.__data.cycles}')
            cells_str = ' | '.join(f'{x:.3f}' for x in self.__data.cell_voltages)
            self.__log.send(f'Cells [V]: {cells_str}')
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
            self.__data = None

    @property
    def device_types(self):
        return self.__device_types

    async def __receive(self, characteristic):
        characteristic.enable_rx()
        while True:
            response = await characteristic.notified()
            if self.__data is None:
                continue
            if len(response) < 128:
                self.__log.send(f'Dropping too short bluetooth packet, mac={self.__mac}, len={len(response)}.')
                continue
            if response[0] == 0xd2 and response[1] == 0x03 and response[2] == 0x7c:
                self.__data.parse(response)
                continue
                    
            self.__log.send(f'Dropping unknown bluetooth packet, mac={self.__mac}, data={response} .')
