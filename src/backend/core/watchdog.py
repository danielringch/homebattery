from machine import Pin, WDT

class Watchdog:
    class Stub:
        def feed(self):
            pass

    def __init__(self):
        enabled = bool(Pin(8, Pin.IN).value())
        from .singletons import Singletons
        Singletons.log.info(f'Watchdog enabled={enabled}')
        self.__wdt = WDT(timeout=5000) if enabled else self.Stub()

    def feed(self):
        self.__wdt.feed()
