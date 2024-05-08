from machine import Pin, WDT

class Watchdog:
    class Stub:
        def feed(self):
            pass

    def __init__(self):
        from .logging_singleton import log
        enabled = bool(Pin(8, Pin.IN).value())
        log.info(f'Watchdog enabled={enabled}')
        self.__wdt = WDT(timeout=5000) if enabled else self.Stub()

    def feed(self):
        self.__wdt.feed()
