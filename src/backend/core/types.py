from asyncio import Event
from micropython import const
from struct import pack_into, unpack_from
from time import time

MODE_CHARGE = const('charge')
MODE_DISCHARGE = const('discharge')
MODE_IDLE = const('idle')
MODE_PROTECT = const('protect')

TYPE_BATTERY = const('battery')
TYPE_CHARGER = const('charger')
TYPE_CONSUMPTION = const('consumption')
TYPE_INVERTER = const('inverter')
TYPE_SOLAR = const('solar')

STATUS_ON = const('on')
STATUS_SYNCING = const('syncing')
STATUS_OFF = const('off')
STATUS_FAULT = const('fault')

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

class BatteryData:
    def __init__(self, name, is_forwarded=False):
        self.name = name
        self.is_forwarded = is_forwarded
        self.v = 0
        self.i = 0
        self.soc = 0
        self.c = 0
        self.c_full = 0
        self.n = 0
        self.temps = tuple()
        self.cells = tuple()
        self.timestamp = 0

    def update(self, v, i, soc, c, c_full, n, temps, cells):
        self.v = v # voltage [V]
        self.i = i # current [A]
        self.soc = soc # state of charge [%]
        self.c = c # capacity remaining [Ah]
        self.c_full = c_full # capacity full [Ah]
        self.n = n # cycles
        self.temps = temps # cell temperatures [°C]
        self.cells = cells # cell voltages [V]
        self.timestamp = time()

    def invalidate(self):
        self.timestamp = 0

    @property
    def valid(self):
        return self.timestamp > 0
    
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
    
class SimpleFiFo:
    class Item:
        def __init__(self, payload):
            self.payload = payload
            self.newer = None

    class Iter:
        def __init__(self, start):
            self.__item = start

        def __iter__(self):
            return self
        
        def __next__(self):
            if self.__item is None:
                raise StopIteration
            payload = self.__item.payload
            self.__item = self.__item.newer
            return payload

    def __init__(self):
        self.__newest = None
        self.__oldest = None
        self.__length = 0

    def __len__(self):
        return self.__length
    
    def __iter__(self):
        return self.Iter(self.__oldest)

    @property
    def empty(self):
        return self.__oldest is None
    
    def clear(self):
        self.__length = 0
        if self.__oldest is not None:
            item = self.__oldest
            while item is not None:
                next = item.newer
                item.newer = None
                item = next
        self.__newest = None
        self.__oldest = None
    
    def append(self, payload):
        self.__length += 1
        item = self.Item(payload)
        if self.__newest is not None:
            self.__newest.newer = item
        self.__newest = item
        if self.__oldest is None:
            self.__oldest = item

    def peek(self):
        assert self.__oldest is not None
        return self.__oldest.payload

    def pop(self):
        assert self.__oldest is not None
        self.__length -= 1
        item = self.__oldest
        self.__oldest = item.newer
        if item.newer is None:
            self.__newest = None
        item.newer = None
        return item.payload
    
class CommandFiFo(SimpleFiFo):
    def __init__(self):
        super().__init__()
        self.event = Event()

    def append(self, payload):
        self.event.set()
        super().append(payload)

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
