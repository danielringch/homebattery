import asyncio, bluetooth, ubinascii, struct, sys
from .interfaces import BatteryInterface
from ..core.microblecentral import MicroBleCentral, MicroBleDevice, MicroBleTimeoutError, ble_instance
from ..core.logging import log
from ..core.types import BatteryData, devicetype

class AccuratT6024V(BatteryInterface):
    class DataBundle(BatteryData):
        def __init__(self):
            super().__init__()
            self.__burst_1_present = False
            self.__burst_2_present = False
            self.__burst_3_present = False

        @property
        def command_1_complete(self):
            return self.__burst_1_present and self.__burst_2_present
        
        @property
        def command_2_complete(self):
            return self.__burst_3_present
        
        @property
        def complete(self):
            return self.__burst_1_present and self.__burst_2_present and self.__burst_3_present
        
        def parse_burst_1(self, data):
            self.__burst_1_present = True
            view = memoryview(data)
            self.voltage = struct.unpack('!H', view[4:6])[0] / 100.0
            self.current = struct.unpack('!h', view[6:8])[0] / 100.0
            self.capacity_remaining = struct.unpack('!H', view[8:10])[0] / 100.0
            self.capacity_full = struct.unpack('!H', view[10:12])[0] / 100.0
            self.cycles = struct.unpack('!H', view[12:14])[0]

        def parse_burst_2(self, data):
            self.__burst_2_present = True
            view = memoryview(data)
            self.soc = struct.unpack('!B', view[3:4])[0]

        def parse_burst_3(self, data):
            self.__burst_3_present = True
            view = memoryview(data)
            for i in range(8):
                position = 4 + (2 * i)
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
                                         ubinascii.unhexlify('dda50300fffd77'), 
                                         lambda : self.__data.command_1_complete)
            if success:
                success = await self.__send(send_characteristic,
                                             ubinascii.unhexlify('dda50400fffc77'),
                                             lambda : self.__data.command_2_complete)

            if self.__data.complete:
                self.__log.send(f'Voltage: {self.__data.voltage} V | Current: {self.__data.current} A')
                self.__log.send(f'SoC: {self.__data.soc} % | {self.__data.capacity_remaining} / {self.__data.capacity_full} Ah')
                self.__log.send(f'Cycles: {self.__data.cycles}')
                cells_str = ' | '.join(f'{x:.3f}' for x in self.__data.cell_voltages)
                self.__log.send(f'Cells [V]: {cells_str}')
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
            if len(response) < 3:
                self.__log.send(f'Dropping too short bluetooth packet, mac={self.__mac}, len={len(response)}.')
                continue
            if response[0] == 0xdd:
                if response[1] == 0x03 and len(response) == 20:
                    self.__data.parse_burst_1(response)
                    continue
                elif response[1] == 0x04 and len(response) == 20:
                    self.__data.parse_burst_3(response)
                    continue
            elif response[0] == 0x00 and response[1] == 0x00 and response[2] == 0x16 and len(response) == 14:
                self.__data.parse_burst_2(response)
                continue
            elif len(response) == 3:
                continue
                    
            self.__log.send(f'Dropping unknown bluetooth packet, mac={self.__mac}, data={response} .')

    async def __send(self, characteristic, data, complete_callback):
        for i in range(5):
            await characteristic.write(data)
            for _ in range(20):
                await asyncio.sleep(0.1)
                if complete_callback():
                    return True
            self.__log.send(f'Attempt {i} for command {data} failed.')
        return False