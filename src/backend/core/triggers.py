from asyncio import create_task, sleep_ms
from .types import run_callbacks
from micropython import const
from time import ticks_ms, ticks_diff, time, localtime

TRIGGER_6S = const('trigger_6s')
TRIGGER_300S = const('trigger_300s')

class Triggers:
    def __init__(self):
        self.__worker = None
        self.__subscribers = []
        self.__next_300s = get_timestamp_of_next_interval(5)

    def start(self):
        from .singletons import Singletons # logger might not be initialised in ctor
        self.__log = Singletons.log.create_logger('triggers')
        self.__worker = create_task(self.__run())

    def add_subscriber(self, callback):
        self.__subscribers.append(callback)

    async def __run(self):
        wait_time = 6000
        while True:
            try:
                await sleep_ms(wait_time)
                ts_start = ticks_ms()
                run_callbacks(self.__subscribers, self.__get_trigger_type())
                wait_time = 6000 - ticks_diff(ticks_ms(), ts_start)
            except Exception as e:
                self.__log.error('Worker cycle failed: ', e)
                self.__log.trace(e)

    def __get_trigger_type(self):
        now = time()
        trigger = TRIGGER_6S
        if now > self.__next_300s:
            self.__next_300s = get_timestamp_of_next_interval(5)
            trigger = TRIGGER_300S
        return trigger
    
def get_timestamp_of_next_interval(interval: int):
    now = localtime()
    now_seconds = time()
    minutes = now[4]
    seconds = now[5]
    extra_seconds = (minutes % interval) * 60 + seconds
    seconds_to_add = (interval * 60) - extra_seconds
    return now_seconds + seconds_to_add
    
triggers = Triggers()
