
class BatteryData:
    def __init__(self):
        self.voltage = None
        self.current = None
        self.capacity_remaining = None
        self.capacity_full = None
        self.cycles = None
        self.soc = None
        self.cell_voltages = list()

class BatterySummary:
    def __init__(self):
        self.capacity_remaining = None
        self.min_cell_voltage = None
        self.max_cell_voltage = None
        self.timestamp = None

    def merge(self, battery: BatteryData, reserved_capacity: float):
        if self.capacity_remaining is None:
            self.capacity_remaining = 0.0
        self.capacity_remaining += max(0.0, battery.capacity_remaining - reserved_capacity)

        if self.min_cell_voltage is None:
            self.min_cell_voltage = min(battery.cell_voltages)
        else:
            self.min_cell_voltage = min(self.min_cell_voltage, min(battery.cell_voltages))

        if self.max_cell_voltage is None:
            self.max_cell_voltage = max(battery.cell_voltages)
        else:
            self.max_cell_voltage = max(self.max_cell_voltage, max(battery.cell_voltages))


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
        self.quickcharge = OperationMode('quickcharge', self.__dict)

    def from_string(self, str):
        return self.__dict[str]
    
operationmode = OperationModeValues()

class ChargeMode(EnumEntry):
    pass

class ChargeModeValues:
    def __init__(self):
        self.__dict = {}
        self.off = ChargeMode('off', self.__dict)
        self.charge = ChargeMode('charge', self.__dict)
        self.quickcharge = ChargeMode('quickcharge', self.__dict)

    def from_string(self, str):
        return self.__dict[str]
    
chargemode = ChargeModeValues()

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
