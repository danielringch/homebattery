from asyncio import create_task, sleep
from ubinascii import unhexlify, hexlify
from micropython import const
from sys import print_exception
from .interfaces.batteryinterface import BatteryInterface
from ..core.devicetools import print_battery
from ..core.addonrs485 import AddOnRs485
from ..core.types import to_port_id, run_callbacks
from ..helpers.batterydata import BatteryData
from ..helpers.streamreader import AsciiHexStreamReader

# ressources:



class PylonLvDeviceInfo:
    def __init__(self, serial: str, group_id: int, slave_id: int, alias: str):
        self.serial = serial
        self.group_id = group_id
        self.slave_id = slave_id
        self.alias = alias
    
class PythonLvAlarmLock:
    def __init__(self, logger):
        self.__logger = logger
        self.__charge_locked = False
        self.__discharge_locked = False

    def add(self, name, value, normal, no_charge, no_discharge):
        if value == normal:
            return
        if value == no_charge:
            self.__charge_locked = True
            self.__logger.info(f'{name}: alarm, no charge possible')
        elif value == no_discharge:
            self.__discharge_locked = True
            self.__logger.info(f'{name}: alarm, no discharge possible')
        else:
            self.__charge_locked = True
            self.__discharge_locked = True
            self.__logger.info(f'{name}: alarm, no operation possible')

    @property
    def charge_locked(self):
        return self.__charge_locked
    
    @property
    def discharge_locked(self):
        return self.__discharge_locked

class PylonLv(BatteryInterface):
    def __init__(self, name, config):
        from ..core.singletons import Singletons
        
        self.__name = name
        self.__log = Singletons.log.create_logger(name)

        self.__serial = config['serial']
        self.__address: int = None
        self.__data = BatteryData(name)

        port = config['port']
        port_id = to_port_id(port)
        self.__port: AddOnRs485 = None 
        if Singletons.ports[port_id] is None:
            self.__port = AddOnRs485(port_id, 115200, 8, None, 1)
            Singletons.ports[port_id] = self.__port
        elif type(Singletons.ports[port_id]) is AddOnRs485:
            self.__port = Singletons.ports[port_id]
            if not self.__port.is_compatible(115200, 8, None, 1):
                raise Exception('Port ', port, ' has incompatible settings')
        else:
            raise Exception('Port ', port, 'is already in use')

        self.__on_data = list()

        self.__background_task = create_task(self.__find_device())

    async def read_battery(self):
        if self.__address is None:
            return
        try:
            self.__data.reset()
            analog_response = await self.__port.send(self.__create_analog_value_request())
            self.__read_analog_value_response(analog_response)

            if self.__data.valid:
                print_battery(self.__log, self.__data)
                run_callbacks(self.__on_data, self.__data)
            alarm_response = await self.__port.send(self.__create_alarm_info_request())
            self.__read_alarm_info_response(alarm_response)
            management_response = await self.__port.send(self.__create_management_info_request())
            self.__read_management_info_response(management_response)

            if None in (analog_response, alarm_response, management_response):
                self.__log.error('Failed to receive battery data.')
        except Exception as e:
            self.__log.error('Reading battery failed: ', e)
            from ..core.singletons import Singletons
            print_exception(e, Singletons.log.trace)

    @property
    def on_battery_data(self):
        return self.__on_data

    @property
    def name(self):
        return self.__name

    @property
    def device_types(self):
        from ..core.types import TYPE_BATTERY
        return (TYPE_BATTERY,)
    
    async def __find_device(self):
        for _ in range(3): # 3 attempts to mitigate communication errors
            for slave_id in range(16):
                async with self.__port.lock:
                    response = await self.__port.send(self.__create_serial_number_request(0, slave_id))
                    # protocol spec says slave address begins with 2, battery datasheets says max. 15 slaves
                    # so we need to try the range between 0 and 2 to check for any battery
                    serial = self.__read_serial_number_response(response, 0, slave_id)
                    if serial != self.__serial:
                        continue
                    self.__address = slave_id # group_id is 0, so we can direct use the slave id
                    self.__log.info('Found battery at address ', hex(self.__address))
                    self.__read_system_parameter_response(await self.__port.send(self.__create_system_parameter_request()))
                    return

    def __to_ascii_hex(self, value: int):
        hex_value = hex(value).upper()
        if len(hex_value) < 4:
            return b'0' + hex_value[-1].encode('utf-8')
        else:
            return hex_value[-2:].encode('utf-8')
        
    def __from_ascii_hex(self, value: bytearray):
        byte_value = value.decode('utf-8')
        int_value = int(byte_value, 16)
        return int_value
    
    def __from_string(self, value: bytearray):
        result = bytearray(len(value) // 2)
        for i in range(len(result)):
            value_index = 2 * i
            result[i] = self.__from_ascii_hex(value[value_index:value_index + 2])
        return result.decode('utf-8')

    def __to_length(self, length: int):
        nibble_1 = length & 0xF
        nibble_2 = (length & 0xF0) >> 4
        nibble_3 = (length & 0xF00) >> 8
        length_checksum = (~((nibble_1 + nibble_2 + nibble_3) & 0xF) + 1) & 0xF

        result = bytearray(4)
        result[0], result[1] = self.__to_ascii_hex((length_checksum << 4) + nibble_3)
        result[2], result[3] = self.__to_ascii_hex((nibble_2 << 4) + nibble_1)
        return result
    
    def __from_length(self, length: bytearray):
        int_value = self.__from_ascii_hex(length)
        nibble_1 = int_value & 0xF
        nibble_2 = (int_value & 0xF0) >> 4
        nibble_3 = (int_value & 0xF00) >> 8
        checksum = (int_value & 0xF000) >> 12

        calculated = (~((nibble_1 + nibble_2 + nibble_3) & 0xF) + 1) & 0xF

        return (int_value & 0xFFF), checksum, calculated
    
    def __to_checksum(self, data: bytearray):
        checksum = 0
        for byte in data:
            checksum += byte
        checksum = (~((checksum) & 0xFFFF) + 1) & 0xFFFF

        result = bytearray(4)
        result[0], result[1] = self.__to_ascii_hex((checksum & 0xFF00) >> 8)
        result[2], result[3] = self.__to_ascii_hex(checksum & 0xFF)
        return result
    
    def __from_checksum(self, data: bytearray, checksum: bytearray):
        int_sum = 0
        for byte in data:
            int_sum += byte
        calculated = (~((int_sum) & 0xFFFF) + 1) & 0xFFFF
        received = self.__from_ascii_hex(checksum)
        return received, calculated

    def __complete_request(self, request: bytearray, group: int, slave: int, payload_length: int):
        # address
        request[3], request[4] = self.__to_ascii_hex((group << 4) + slave)
        # length
        request[9], request[10], request[11], request[12] = self.__to_length(payload_length)
        # checksum
        request[-5], request[-4], request[-3], request[-2] = self.__to_checksum(request[1:-5])

    def __deccode_response(self, response: bytearray, group: int, slave: int, cid: int):
        try:
            if response[0] != 0x7e:
                raise Exception(f'Invalid frame start: {hex(response[0])}')
            # ignore version
            address = self.__from_ascii_hex(response[3:5])
            if address != ((group << 4) + slave):
                raise Exception(f'Invalid client address: {hex(address)}')
            cid = self.__from_ascii_hex(response[5:7])
            if cid != 0x46:
                raise Exception(f'Invalid command identifiert: {hex(cid)}')
            rtn = self.__from_ascii_hex(response[7:9])
            if rtn != 0:
                raise Exception(f'Invalid return code: {hex(rtn)}')
            length, length_chk1, length_chk2 = self.__from_length(response[9:13])
            if length_chk1 != length_chk2:
                raise Exception(f'Invalid length checksum: {hex(length_chk1)}')
            data = response[13:13+length]
            chk_received, chk_calculated = self.__from_checksum(response[1:-5], response[-5:-1])
            if chk_received != chk_calculated:
                raise Exception(f'Invalid checksum: {hex(chk_received)}')
            if response[-1] != 0x0d:
                raise Exception(f'Invalid frame end: {hex(response[-1])}')
            return data
        except Exception as e:
            self.__log.error(f'Invalid response from group={group} slave={slave}: ', e)
            from ..core.singletons import Singletons
            print_exception(e, Singletons.log.trace)
            return None
            

    def __create_protocol_version_request(self, group: int, slave: int):
        #                     SOI VER     ADR     CID LENGTH          INFO    CHK             EOI
        request = bytearray(b'\x7E\x32\x30\x00\x00464F\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x0D')
        request[13], request[14] = self.__to_ascii_hex(slave)
        self.__complete_request(request, group, slave, 0)
        return request
    
    def __create_serial_number_request(self, group: int, slave: int):
        #                     SOI VER     ADR     CID LENGTH          INFO    CHK             EOI
        request = bytearray(b'\x7E\x32\x30\x00\x004693\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x0D')
        request[13], request[14] = self.__to_ascii_hex(slave)
        self.__complete_request(request, group, slave, 2)
        return request

    def __read_serial_number_response(self, response, group: int, slave: int):
        if response is None:
            return None
        data = self.__deccode_response(response, group, slave, 0x46)
        if data is None:
            return None
        return self.__from_string(data[2:]) # first byte is command info
    
    def __create_analog_value_request(self):
        #                     SOI VER     ADR     CID LENGTH          INFO    CHK             EOI
        request = bytearray(b'\x7E\x32\x30\x00\x004642\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x0D')
        request[13], request[14] = self.__to_ascii_hex(self.__address & 0xF)
        self.__complete_request(request, (self.__address & 0xF0) >> 4, self.__address & 0xF, 2)
        return request
    
    def __read_analog_value_response(self, response):
        if response is None:
            return
        raw = self.__deccode_response(response, (self.__address & 0xF0) >> 4, self.__address & 0xF, 0x46)
        if raw is None:
            return

        reader = AsciiHexStreamReader(raw, 4) # first byte is command info, second is info flags

        n_cells = reader.read_uint8()
        cell_voltages = []
        for _ in range(n_cells):
            cell_voltages.append(reader.read_uint16() / 1000)

        n_temps = reader.read_uint8()
        bms_temp = None
        temps = []
        for _ in range(n_temps):
            temps.append((reader.read_uint16() - 2731) / 10)
        if temps:
            bms_temp = temps[0]
            temps.pop(0)

        b = self.__data

        b.temps = tuple(temps)
        b.cells = tuple(cell_voltages)

        b.i = reader.read_int16() / 10
        b.v = reader.read_uint16() / 1000
        b.c = reader.read_uint16() / 1000

        remaining_items = reader.read_uint8()

        if remaining_items >= 2:
            b.c_full = reader.read_uint16() / 1000
            b.n = reader.read_uint16()

        if remaining_items >= 4:
            b.c = reader.read_uint24() / 1000
            b.c_full = reader.read_uint24() / 1000

        self.__data.validate()

    def __create_system_parameter_request(self):
        #                     SOI VER     ADR     CID LENGTH          INFO    CHK             EOI
        request = bytearray(b'\x7E\x32\x30\x00\x004647\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x0D')
        request[13], request[14] = self.__to_ascii_hex(self.__address & 0xF)
        self.__complete_request(request, (self.__address & 0xF0) >> 4, self.__address & 0xF, 2)
        return request
    
    def __read_system_parameter_response(self, response):
        if response is None:
            return
        raw = self.__deccode_response(response, (self.__address & 0xF0) >> 4, self.__address & 0xF, 0x46)
        if raw is None:
            return

        reader = AsciiHexStreamReader(raw, 2) # first byte is info flags

        self.__log.info(f'Cell high voltage limit: {(reader.read_uint16() / 1000):.3f} V')
        self.__log.info(f'Cell low voltage limit: {(reader.read_uint16() / 1000):.3f} V')
        self.__log.info(f'Cell under voltage limit: {(reader.read_uint16() / 1000):.3f} V')
        self.__log.info(f'Charge high temperature limit: {((reader.read_uint16() - 2731) / 10):.1f} °C')
        self.__log.info(f'Charge low temperature limit: {((reader.read_uint16() - 2731) / 10):.1f} °C')
        self.__log.info(f'Charge current limit: {(reader.read_int16() / 10):.1f} A')
        self.__log.info(f'Module high voltage limit: {(reader.read_uint16() / 1000):.3f} V')
        self.__log.info(f'Module low voltage limit: {(reader.read_uint16() / 1000):.3f} V')
        self.__log.info(f'Module under voltage limit: {(reader.read_uint16() / 1000):.3f} V')
        self.__log.info(f'Discharge high temperature limit: {((reader.read_uint16() - 2731) / 10):.1f} °C')
        self.__log.info(f'Discharge low temperature limit: {((reader.read_uint16() - 2731) / 10):.1f} °C')
        self.__log.info(f'Discharge current limit: {(reader.read_int16() / 10):.1f} A')


    def __create_alarm_info_request(self):
        #                     SOI VER     ADR     CID LENGTH          INFO    CHK             EOI
        request = bytearray(b'\x7E\x32\x30\x00\x004644\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x0D')
        request[13], request[14] = self.__to_ascii_hex(self.__address & 0xF)
        self.__complete_request(request, (self.__address & 0xF0) >> 4, self.__address & 0xF, 2)
        return request
    
    def __read_alarm_info_response(self, response):
        if response is None:
            return
        raw = self.__deccode_response(response, (self.__address & 0xF0) >> 4, self.__address & 0xF, 0x46)
        if raw is None:
            return
        
        reader = AsciiHexStreamReader(raw, 4) # first byte is data flags, second is command value
        lock_info = PythonLvAlarmLock(self.__log)

        n_cells = reader.read_uint8()
        for i in range(n_cells):
            lock_info.add(f'Cell {i+1}', reader.read_uint8(), 0, 2, 1)
        n_temps = reader.read_uint8()
        for i in range(n_temps):
            lock_info.add(f'Temperature sensor {i + 1}', reader.read_uint8(), 0, None, None)
        lock_info.add('Charge current', reader.read_uint8(), 0, 2, None)
        lock_info.add('Module voltage', reader.read_uint8(), 0, 2, 1)
        lock_info.add('Discharge current', reader.read_uint8(), 0, 2, None)

        status1 = reader.read_uint8()
        lock_info.add('Module undervoltage', status1 & 0x80, 0, None, 0x80)
        lock_info.add('Charge overtemperature', status1 & 0x40, 0, None, None)
        lock_info.add('Discharge overtemperature', status1 & 0x20, 0, None, None)
        lock_info.add('Discharge overcurrent', status1 & 0x10, 0, None, 0x10)
        lock_info.add('Charge overcurrent', status1 & 0x04, 0, 0x04, None)
        lock_info.add('Cell undervoltage', status1 & 0x02, 0, None, 0x02)
        lock_info.add('Module overvoltage', status1 & 0x01, 0, 0x01, None)

        status2 = reader.read_uint8()
        power_used = bool(status2 & 0x04)
        charge_mosfest_enabled = bool(status2 & 0x03)
        discharge_mosfest_enabled = bool(status2 & 0x02)

        status3 = reader.read_uint8()
        charging_active = bool(status3 & 0x80)
        discharging_active = bool(status3 & 0x20)
        fully_charged = bool(status3 & 0x08)
        buzzer_on = bool(status3 & 0x01)

        status4 = reader.read_uint8()
        lock_info.add('Cell 8 failure', status4 & 0x80, 0, None, None)
        lock_info.add('Cell 7 failure', status4 & 0x40, 0, None, None)
        lock_info.add('Cell 6 failure', status4 & 0x20, 0, None, None)
        lock_info.add('Cell 5 failure', status4 & 0x10, 0, None, None)
        lock_info.add('Cell 4 failure', status4 & 0x08, 0, None, None)
        lock_info.add('Cell 3 failure', status4 & 0x04, 0, None, None)
        lock_info.add('Cell 2 failure', status4 & 0x02, 0, None, None)
        lock_info.add('Cell 1 failure', status4 & 0x01, 0, None, None)

        status5 = reader.read_uint8()
        lock_info.add('Cell 16 failure', status5 & 0x80, 0, None, None)
        lock_info.add('Cell 15 failure', status5 & 0x40, 0, None, None)
        lock_info.add('Cell 14 failure', status5 & 0x20, 0, None, None)
        lock_info.add('Cell 13 failure', status5 & 0x10, 0, None, None)
        lock_info.add('Cell 12 failure', status5 & 0x08, 0, None, None)
        lock_info.add('Cell 11 failure', status5 & 0x04, 0, None, None)
        lock_info.add('Cell 10 failure', status5 & 0x02, 0, None, None)
        lock_info.add('Cell 9 failure', status5 & 0x01, 0, None, None)

        flags = []

        if power_used:
            flags.append('power_used')
        if charge_mosfest_enabled:
            flags.append('charge_enabled')
        if discharge_mosfest_enabled:
            flags.append('discharge_enabled')
        if charging_active:
            flags.append('charging')
        if discharging_active:
            flags.append('discharging')
        if fully_charged:
            flags.append('fully_charged')
        if buzzer_on:
            flags.append('buzzer')

        self.__log.info('Flags: ', ' '.join(flags))
        self.__log.info('Charging locked: ', lock_info.charge_locked)
        self.__log.info('Discharging locked: ', lock_info.discharge_locked)

    def __create_management_info_request(self):
        #                     SOI VER     ADR     CID LENGTH          INFO    CHK             EOI
        request = bytearray(b'\x7E\x32\x30\x00\x004692\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x0D')
        request[13], request[14] = self.__to_ascii_hex(self.__address & 0xF)
        self.__complete_request(request, (self.__address & 0xF0) >> 4, self.__address & 0xF, 2)
        return request
    
    def __read_management_info_response(self, response):
        if response is None:
            return
        raw = self.__deccode_response(response, (self.__address & 0xF0) >> 4, self.__address & 0xF, 0x46)
        if raw is None:
            return

        reader = AsciiHexStreamReader(raw, 2) # first byte is command info

        charge_voltage_limit = reader.read_uint16() / 1000
        discharge_voltage_limit = reader.read_uint16() / 1000
        charge_current_limit = reader.read_int16() / 10
        discharge_current_limit = reader.read_int16() / 10
        status = reader.read_uint8()

        charge_enable = bool(status & 0x80)
        discharge_enable = bool(status & 0x40)
        charge_request = bool(status & 0x30)
        full_charge_request = bool(status & 0x08)

        flags = []
        if charge_enable:
            flags.append('charge_enabled')
        if discharge_enable:
            flags.append('discharge_enabled')
        if charge_request:
            flags.append('charge_request')
        if full_charge_request:
            flags.append('full_charge_request')

        self.__log.info('Voltage limit (charge/ discharge) [V]: ', f'{charge_voltage_limit:.3f}', ' / ', f'{discharge_voltage_limit:.3f}')
        self.__log.info('Current limit (charge/ discharge) [A]: ', f'{charge_current_limit:.1f}', ' / ', f'{discharge_current_limit:.1f}')
        self.__log.info('Flags: ', ' '.join(flags))

