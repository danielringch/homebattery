import asyncio, bluetooth, ubinascii, struct, sys
from .interfaces.batteryinterface import BatteryInterface
from ..core.microblecentral import MicroBleCentral, MicroBleDevice, MicroBleTimeoutError, ble_instance
from ..core.logging import log
from ..core.types import BatteryData, devicetype

# ressources:
# https://blog.ja-ke.tech/2020/02/07/ltt-power-bms-chinese-protocol.html
# https://www.lithiumbatterypcb.com/smart-bms-software-download/
# https://www.lithiumbatterypcb.com/wp-content/uploads/2023/05/RS485-UART-RS232-Communication-protocol.pdf

class LltPowerBmsV4Ble(BatteryInterface):
    class DataBundle(BatteryData):
        def __init__(self):
            super().__init__()
            self.__general_present = False
            self.__cells_present = False
        
        @property
        def complete(self):
            return self.__general_present and self.__cells_present
        
        def parse(self, decoder):
            if decoder.command == 3:
                self.__parse_general(decoder)
            elif decoder.command == 4:
                self.__parse_cells(decoder)

        def __parse_general(self, decoder):
            view = decoder.data
            self.voltage = struct.unpack('!H', view[0:2])[0] / 100.0
            self.current = struct.unpack('!h', view[2:4])[0] / 100.0
            self.capacity_remaining = struct.unpack('!H', view[4:6])[0] / 100.0
            self.capacity_full = struct.unpack('!H', view[6:8])[0] / 100.0
            self.cycles = struct.unpack('!H', view[8:10])[0]
            # bytes 10+11 are production date
            # bytes 12+13 are balance low
            # bytes 14+15 are balance high
            # bytes 16+17 are protection
            # byte 18 is version
            self.soc = struct.unpack('!B', view[19:20])[0]
            # byte 20 is MOS status
            # byte 21 is number of cells
            # byte 22 is number of temperature probes
            number_of_temperatures = (len(view) - 23) // 2
            format_string = '!' + ('H' * number_of_temperatures)
            self.temperatures = tuple((x - 2731) / 10 for x in struct.unpack(format_string, view[23:23 +  (2 * number_of_temperatures)]))
            self.__general_present = True

        def __parse_cells(self, decoder):
            view = decoder.data
            number_of_cells = len(view) // 2
            format_string = '!' + ('H' * number_of_cells)
            self.cell_voltages = tuple(x / 1000 for x in struct.unpack(format_string, view[0:(2 * number_of_cells)]))
            self.__cells_present = True

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
        self.__device_types = (devicetype.battery,)
        self.__mac = config['mac']

        self.__log = log.get_custom_logger(name)

        self.__device = None
        self.__receive_task = None
        self.__data = None
        self.__current_decoder = None

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
                                         ubinascii.unhexlify('dda50300fffd77'))
            if success:
                self.__data.parse(self.__current_decoder)
                success = await self.__send(send_characteristic,
                                             ubinascii.unhexlify('dda50400fffc77'))
                if success:
                    self.__data.parse(self.__current_decoder)

            if self.__data.complete:
                self.__log.send(f'Voltage: {self.__data.voltage} V | Current: {self.__data.current} A')
                self.__log.send(f'SoC: {self.__data.soc} % | Capacity: {self.__data.capacity_remaining}/{self.__data.capacity_full} Ah')
                temperatues_str = ' ; '.join(f'{x:.1f}' for x in self.__data.temperatures)
                self.__log.send(f'Cycles: {self.__data.cycles} Temperatures [°C]: {temperatues_str}')
                cells_str = ' ; '.join(f'{x:.3f}' for x in self.__data.cell_voltages)
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
            self.__current_decoder = None
            self.__data = None

    @property
    def device_types(self):
        return self.__device_types

    async def __receive(self, characteristic):
        characteristic.enable_rx()
        while True:
            response = await characteristic.notified()
            if self.__data is None or self.__current_decoder is None:
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