from time import ticks_ms, ticks_diff

class ValueAggregator:
    def __init__(self):
        self.__last_value = 0
        self.__last_ticks = None
        self.clear()

    def add(self, value):
        now = ticks_ms()
        if value is None:
            value = self.__last_value
        if self.__last_ticks is not None:
            time_span = ticks_diff(now, self.__last_ticks)
            self.__sum += self.__last_value * time_span
            self.__total_timespan += time_span
        self.__last_value = value
        self.__last_ticks = now

    def clear(self):
        self.__sum = 0
        self.__total_timespan = 0

    def average(self, clear_afterwards=False):
        if self.__total_timespan == 0:
            result = 0
        else:
            result = self.__sum / self.__total_timespan
        if clear_afterwards:
            self.clear()
        return result
    
    def integral(self, clear_afterwards=False):
        result = self.__sum / 1000 # aggregation is done in ms for better accuracy, but the integral is in s
        if clear_afterwards:
            self.clear()
        return result
        
        