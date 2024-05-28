from micropython import const
from time import time
from ..core.types import SimpleFiFo

_MAX_EVALUATION_TIME = const(120)
_MIN_ITEMS = const(5)

class NetZero:
    def __init__(self, config):
        config = config['netzero']

        from ..core.singletons import Singletons
        self.__log = Singletons.log.create_logger('netzero')
        
        self.__time_span = min(_MAX_EVALUATION_TIME, int(config['evaluated_time_span']))
        self.__data = SimpleFiFo() 
        self.__last_data = 0

        self.__unsigned = not bool(config['signed'])
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
            return

        if self.__last_data == timestamp and len(self.__data) > 0:
            self.__log.info('More than one data point for timestamp, dropping the newer one.')
        else:
            self.__data.append((timestamp, consumption))

        while True:
            item = self.__data.peek()
            if item[0] + self.__time_span <= timestamp:
                _ = self.__data.pop()
            else:
                break

        self.__last_data = timestamp

    def evaluate(self):
        now = time()
        smallest = None
        second_smallest = None
        oldest_age = 0

        for item in self.__data:
            consumption = item[1]
            timestamp = item[0]
            
            oldest_age = max(oldest_age, now - timestamp)
            if smallest is None or consumption < smallest:
                second_smallest = smallest
                smallest = consumption
            elif second_smallest is None or consumption < second_smallest:
                second_smallest = consumption

        if second_smallest is None: # not enough data point to do any evaluation
            result = 0
        elif self.__unsigned and second_smallest == 0: # overproduction
            result = self.__step_down
        elif second_smallest < (self.__offset - self.__hysteresis): # reduce
            result = -(min(self.__step_down, self.__offset - second_smallest))
        elif len(self.__data) < _MIN_ITEMS or oldest_age < self.__mature_interval: # wait
            result = 0
        elif second_smallest > (self.__offset + self.__hysteresis): # increase
            result = min(self.__step_up, second_smallest - self.__offset) 
        else:
            result = 0

        self.__log.info('Delta: ', result, ' W | Min: ', second_smallest, ' W | ', len(self.__data), ' / ', _MIN_ITEMS, ' data points | ', oldest_age, ' / ', self.__mature_interval, ' s time span')
        return result
