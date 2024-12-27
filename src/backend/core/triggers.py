from asyncio import create_task, sleep_ms
from .types import run_callbacks
from micropython import const
from time import ticks_ms, ticks_diff, time

TRIGGER_6S = const('trigger_6s')
TRIGGER_300S = const('trigger_300s')

class Triggers:
    def __init__(self):
        self.__worker = None
        self.__subscribers = []

    def start(self):
        from .singletons import Singletons # logger might not be initialised in ctor
        self.__log = Singletons.log.create_logger('triggers')
        self.__worker = create_task(self.__run())

    def add_subscriber(self, callback):
        self.__subscribers.append(callback)

    async def __run(self):
        self.__last_5min = time()
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
        delta = now - self.__last_5min
        if delta > 297:
            self.__last_5min = now
            return TRIGGER_300S
        return TRIGGER_6S
    
triggers = Triggers()
