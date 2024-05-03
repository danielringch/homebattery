import struct

class BatteryData:
    def __init__(self):
        self.v = None
        self.i = None
        self.soc = None
        self.c = None
        self.c_full = None
        self.n = None
        self.temps = tuple()
        self.cells = tuple()
        self.valid = False

    def update(self, v, i, soc, c, c_full, n, temps, cells):
        self.v = v # voltage [V]
        self.i = i # current [A]
        self.soc = soc # state of charge [%]
        self.c = c # capacity remaining [Ah]
        self.c_full = c_full # capacity full [Ah]
        self.n = n # cycles
        self.temps = temps # cell temperatures [°C]
        self.cells = cells # cell voltages [V]
        self.valid = True

    def invalidate(self):
        self.valid = False

    def __str__(self) -> str:
        temperatues_str = ' ; '.join(f'{x:.1f}' for x in self.temps)
        cells_str = ' | '.join(f'{x:.3f}' for x in self.cells)
        return f'Voltage: {self.v} V | Current: {self.i} A\nSoC: {self.soc} % | {self.c} / {self.c_full} Ah\nCycles: {self.n} | Temperatures [°C]: {temperatues_str}\nCells [V]: {cells_str}'

class BatterySummary:
    def __init__(self):
        self.capacity_remaining = None
        self.min_cell_voltage = None
        self.max_cell_voltage = None
        self.timestamp = None

    def merge(self, battery: BatteryData):
        if self.capacity_remaining is None:
            self.capacity_remaining = 0.0
        self.capacity_remaining += battery.c

        if self.min_cell_voltage is None:
            self.min_cell_voltage = min(battery.cells)
        else:
            self.min_cell_voltage = min(self.min_cell_voltage, min(battery.cells))

        if self.max_cell_voltage is None:
            self.max_cell_voltage = max(battery.cells)
        else:
            self.max_cell_voltage = max(self.max_cell_voltage, max(battery.cells))

bool2string = {True: 'true', False: 'false', None: 'none'}

bool2on = {True: 'on', False: 'off', None: 'unknown'}

class CallbackCollection:
    def __init__(self):
        self.__callbacks = list()

    def add(self, callback):
        self.__callbacks.append(callback)

    def run_all(self, *args, **kwargs):
        for callback in self.__callbacks:
            callback(*args, **kwargs)

    @property
    def items(self):
        return tuple(self.__callbacks)

class CommandBundle:
    def __init__(self, callback, parameters):
        self.__callback = callback
        self.__parameters = parameters

    async def run(self):
        await self.__callback(*self.__parameters)

class EnergyIntegral:
    def __init__(self):
        self.__value = 0.0

    def get(self):
        return self.__value
    
    def add(self, value):
        self.__value += value

    def merge(self, other):
        self.__value += other.__value

    def reset(self):
        self.__value = 0.0

class EnumEntry:
    def __init__(self, name, dict):
        self.name = name
        if dict is not None:
            dict[name] = self

    def __lt__(self, other):
        return self.name < other.name

    def __eq__(self, other):
        return isinstance(other, EnumEntry) and self.name == other.name
    
    def __hash__(self):
        return hash(self.name)
    
    def __str__(self) -> str:
        return self.name
    
class OperationMode(EnumEntry):
    pass

class OperationModeValues:
    def __init__(self):
        self.__dict = {}
        self.charge = OperationMode('charge', self.__dict)
        self.discharge = OperationMode('discharge', self.__dict)
        self.idle = OperationMode('idle', self.__dict)
        self.protect = OperationMode('protect', self.__dict)

    def from_string(self, str):
        return self.__dict[str]
    
operationmode = OperationModeValues()

class DeviceType(EnumEntry):
    pass

class DeviceTypeValues:
    def __init__(self):
        self.__dict = {}
        self.battery = DeviceType('battery', self.__dict)
        self.charger = DeviceType('charger', self.__dict)
        self.inverter = DeviceType('inverter', self.__dict)
        self.solar = DeviceType('solar', self.__dict)

devicetype = DeviceTypeValues()

class InverterStatus(EnumEntry):
    pass

class InverterStatusValues:
    def __init__(self):
        self.__dict = {}
        self.off = InverterStatus('off', self.__dict)
        self.syncing = InverterStatus('syncing', self.__dict)
        self.on = InverterStatus('on', self.__dict)
        self.fault = InverterStatus('fault', self.__dict)

    def from_string(self, str):
        return self.__dict[str]
    
inverterstatus = InverterStatusValues()

class PowerLut:
    def __init__(self, path):
        self.__lut = None
        self.__lut_length = 0
        self.__min_percent = 100
        self.__min_power = 65535
        self.__max_power = 0
        with open(path, 'r') as file:
            for line in file:
                line = line.strip().strip('{},')
                if not line:
                    continue
                self.__lut_length += 1
            file.seek(0)

            self.__lut = bytearray(3 * self.__lut_length)
            lut_index = 0

            for line in file:
                line = line.strip().strip('{},')
                if not line:
                    continue

                key, value = line.split(':')
                percent = int(key.strip(' "'))
                power = int(value.strip())
                self.__min_percent = min(self.__min_percent, percent)
                self.__min_power = min(self.__min_power, power)
                self.__max_power = max(self.__max_power, power)
                struct.pack_into('@HB', self.__lut, lut_index, power, percent)
                lut_index += 3

    def get_power(self, percent):
        for i in range(self.__lut_length):
            power_entry, percent_entry = struct.unpack_from('@HB', self.__lut, 3 * i)
            # if percent is smaller than supported, this returns the smallest power possible
            if percent <= percent_entry:
                return power_entry, percent_entry
        else:
            # if percent is higher than supported, this returns the biggest power possible
            return power_entry, percent_entry
                
    def get_percent(self, power):
        previous_power, previous_percent = struct.unpack_from('@HB', self.__lut, 0)
        power = max(self.__min_power, min(self.__max_power, power))
        for i in range(self.__lut_length):
            power_entry, percent_entry = struct.unpack_from('@HB', self.__lut, 3 * i)
            if power_entry > power:
                return previous_percent, previous_power
            previous_percent = percent_entry
            previous_power = power_entry
        else:
            return previous_percent, previous_power
                
    @property
    def min_percent(self):
        return self.__min_percent

    @property
    def min_power(self):
        return self.__min_power

    @property
    def max_power(self):
        return self.__max_power
