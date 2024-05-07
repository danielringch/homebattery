from machine import Pin, WDT
from .logging_singleton import log

class Watchdog:
    class Stub:
        def feed(self):
            pass

    def __init__(self):
        self.__pin = Pin(9, Pin.IN)
        self.__enabled = bool(self.__pin.value())
        log.info(f'Watchdog enabled={self.__enabled}')
        self.__wdt = WDT(timeout=5000) if self.__enabled else self.Stub()

    def feed(self):
        self.__wdt.feed()
