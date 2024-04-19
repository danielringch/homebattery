import time
from collections import namedtuple
from ..core.logging import *
from ..core.microdeque import MicroDeque, MicroDequeOverflowError

class NetZero:
    PowerElement = namedtuple("PowerElement", "timestamp power")

    def __init__(self, config):
        config = config['netzero']
        
        self.__time_span = int(config['evaluated_time_span'])

        self.__power_data = MicroDeque(50)

        self.__offset = int(config['power_offset'])
        self.__hysteresis = int(config['power_hysteresis'])
        self.__step_up = int(config['power_change_upwards'])
        self.__step_down = -int(config['power_change_downwards'])
        self.__mature_interval = int(config['maturity_time_span'])
        self.__data_deadline = time.time()

        self.__delta = 0

    def evaluate(self, timestamp, consumption):
        self.__update_data(timestamp, consumption)
        self.__delta = self.__evaluate_power()

    def clear(self):
        self.__delta = 0
        self.__power_data.clear()
        self.__data_deadline = time.time()

    @property
    def delta(self):
        return self.__delta

    def __update_data(self, timestamp, consumption):
        if timestamp < self.__data_deadline:
            log.netzero('Omitting data consumption data, too old.')
        self.__data_deadline = timestamp
        element = self.PowerElement(timestamp, consumption)
        try:
            self.__power_data.append(element)
        except MicroDequeOverflowError:
            pass # losing some old data is not critical
        delete_threshold = timestamp - self.__time_span
        while self.__power_data[0].timestamp < delete_threshold:
            self.__power_data.popleft()

    def __evaluate_power(self):
        oldest_element = self.__power_data[0]
        current_element = self.__power_data[-1]
        if sum(1 for i in self.__power_data if i.power < 1) > 1:
            log.netzero('Overproduction.')
            return self.__step_down
        if (len(self.__power_data) < 5) or (current_element.timestamp - oldest_element.timestamp < self.__mature_interval):
            log.netzero(f'Not enough data.')
            return 0
        values = [x.power for x in self.__power_data]
        values.sort()
        start_index = len(values) // 5
        upper_values = values[start_index:]
        min_power = min(upper_values)
        log.netzero(f'Minimum power: {min_power}W | {len(values)} data points.')
        if min_power < self.__offset:
            value = -(self.__offset - min_power)
            return value
        if min_power > (self.__offset + self.__hysteresis):
            value = min(self.__step_up, min_power - self.__offset - (self.__hysteresis / 2)) 
            return value
        return 0
