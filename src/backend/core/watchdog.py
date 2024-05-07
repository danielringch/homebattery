from machine import Pin, WDT
from .logging_singleton import log

class Watchdog:
    class Stub:
        def feed(self):
            pass

    def __init__(self):
        enabled = bool(Pin(9, Pin.IN).value())
        log.info(f'Watchdog enabled={enabled}')
        self.__wdt = WDT(timeout=5000) if enabled else self.Stub()

    def feed(self):
        self.__wdt.feed()
