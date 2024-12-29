from asyncio import Event
from micropython import const
from struct import pack_into, unpack_from
from collections import deque

MODE_CHARGE = const('charge')
MODE_DISCHARGE = const('discharge')
MODE_IDLE = const('idle')
MODE_PROTECT = const('protect')

TYPE_BATTERY = const('battery')
TYPE_CHARGER = const('charger')
TYPE_CONSUMPTION = const('consumption')
TYPE_INVERTER = const('inverter')
TYPE_SOLAR = const('solar')
TYPE_SENSOR = const('sensor')

STATUS_ON = const('on')
STATUS_SYNCING = const('syncing')
STATUS_OFF = const('off')
STATUS_FAULT = const('fault')
STATUS_OFFLINE = const('offline')

MEASUREMENT_CAPACITY = const('capacity')
MEASUREMENT_CURRENT = const('current')
MEASUREMENT_ENERGY = const('energy')
MEASUREMENT_POWER = const('power')
MEASUREMENT_SOC = const('soc')
MEASUREMENT_STATUS = const('status')
MEASUREMENT_TEMPERATURE = const('temperature')
MEASUREMENT_VOLTAGE = const('voltage')

def to_operation_mode(str):
    if str == MODE_CHARGE:
        return MODE_CHARGE
    elif str == MODE_DISCHARGE:
        return MODE_DISCHARGE
    elif str == MODE_IDLE:
        return MODE_IDLE
    else:
        return MODE_PROTECT
    
def to_port_id(str):
    if str == "ext1":
        return 0
    elif str == "ext2":
        return 1
    else:
        raise Exception(f'Unknown port: {str}')
    
def run_callbacks(list, *args, **kwargs):
    for callback in list:
        callback(*args, **kwargs)

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
    
class CommandFiFo(deque):
    def __init__(self, size: int):
        super().__init__(tuple(), size)
        self.event = Event()

    def append(self, payload):
        self.event.set()
        super().append(payload)

    def appendleft(self, payload):
        self.event.set()
        super().appendleft(payload)

    async def wait_and_clear(self):
        await self.event.wait()
        self.event.clear()
    
class PowerLut:
    def __init__(self, path):
        self.__lut_length = 0
        self.__min_percent = 100
        self.__min_power = 65535
        self.__max_power = 0
        with open(path, 'r') as file:
            for line in file:
                valid, _ = self.__read_line(line)
                if valid is not None:
                    self.__lut_length += 1
            file.seek(0)

            self.__lut = bytearray(3 * self.__lut_length)
            lut_index = 0

            for line in file:
                percent, power = self.__read_line(line)
                if percent is None or power is None:
                    continue
                self.__min_percent = min(self.__min_percent, percent)
                self.__min_power = min(self.__min_power, power)
                self.__max_power = max(self.__max_power, power)
                pack_into('@HB', self.__lut, lut_index, power, percent)
                lut_index += 3

    def get_power(self, percent):
        for i in range(self.__lut_length):
            power_entry, percent_entry = unpack_from('@HB', self.__lut, 3 * i)
            # if percent is smaller than supported, this returns the smallest power possible
            if percent <= percent_entry:
                return power_entry, percent_entry
        else:
            # if percent is higher than supported, this returns the biggest power possible
            return power_entry, percent_entry
                
    def get_percent(self, power):
        previous_power, previous_percent = unpack_from('@HB', self.__lut, 0)
        power = max(self.__min_power, min(self.__max_power, power))
        for i in range(self.__lut_length):
            power_entry, percent_entry = unpack_from('@HB', self.__lut, 3 * i)
            if power_entry > power:
                return previous_percent, previous_power
            previous_percent = percent_entry
            previous_power = power_entry
        else:
            return previous_percent, previous_power
        
    def __read_line(self, line):
        try:
            percent, power = line.split(';')
            return int(percent.strip()), int(power.strip())
        except:
            return None, None
                
    @property
    def min_percent(self):
        return self.__min_percent

    @property
    def min_power(self):
        return self.__min_power

    @property
    def max_power(self):
        return self.__max_power
