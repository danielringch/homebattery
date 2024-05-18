from micropython import const
from time import time
from ..core.byteringbuffer import ByteRingBuffer

_MAX_EVALUATION_TIME = const(120)
_MIN_ITEMS = const(5)
_NO_DATA = const(0xFF)

class NetZero:
    def __init__(self, config):
        config = config['netzero']

        from ..core.singletons import Singletons
        self.__log = Singletons.log.create_logger('netzero')
        
        self.__time_span = min(_MAX_EVALUATION_TIME, int(config['evaluated_time_span']))
        self.__data = ByteRingBuffer(2 * self.__time_span, ignore_overflow=True)
        self.__last_data = 0

        self.__offset = int(config['power_offset'])
        self.__hysteresis = int(config['power_hysteresis'])
        self.__step_up = int(config['power_change_upwards'])
        self.__step_down = -int(config['power_change_downwards'])
        self.__mature_interval = int(config['maturity_time_span'])

    def clear(self):
        self.__data.clear()
        self.__last_data = time()

    def update(self, timestamp, consumption):
        if timestamp < self.__last_data:
            self.__log.info('Omitting data consumption data, too old.')
        empty_items = min(self.__time_span, timestamp - self.__last_data) - 1
        if empty_items > 0 and len(self.__data) > 0:
            for _ in range(empty_items):
                self.__data.append(0xFF) # no data
                self.__data.append(0xFF)

        if self.__last_data == timestamp and len(self.__data) > 0:
            self.__log.info('More than one data point for timestamp, dropping the newer one.')
        else:
            self.__data.append((consumption >> 8) & 0xFF)
            self.__data.append(consumption & 0xFF)

        self.__last_data = timestamp

    def evaluate(self):
        valid_items = 0
        smallest = _NO_DATA
        second_smallest = _NO_DATA
        oldest_age = 0

        for i in range(0, len(self.__data), 2):
            consumption = (self.__data[i] << 8) + self.__data[i + 1]
            if consumption == _NO_DATA:
                continue

            valid_items += 1
            oldest_age = i // 2

            if consumption < smallest:
                second_smallest = smallest
                smallest = consumption
            elif consumption < second_smallest:
                second_smallest = consumption

        if second_smallest == _NO_DATA: # not enough data point to do any evaluation
            second_smallest = None # prevent misleading log data
            result = 0
        elif second_smallest == 0:
            result = self.__step_down
        elif second_smallest < (self.__offset - self.__hysteresis):
            result = -(self.__offset - second_smallest)
        elif valid_items < 5 or oldest_age < self.__mature_interval:
            result = 0
        elif second_smallest > (self.__offset + self.__hysteresis):
            result = min(self.__step_up, second_smallest - self.__offset) 
        else:
            result = 0

        self.__log.info('Delta: ', result, ' W | Min: ', second_smallest, ' W | ', valid_items, ' / ', _MIN_ITEMS, ' data points | ', oldest_age, ' / ', self.__mature_interval, ' s time span')
        return result
