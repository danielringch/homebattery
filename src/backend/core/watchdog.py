from machine import Pin, WDT

class Watchdog:
    class Stub:
        def feed(self):
            pass

    def __init__(self):
        from .singletons import Singletons
        enabled = not Singletons.ui.sw2
        Singletons.log.info('Watchdog enabled=', enabled)
        self.__wdt = WDT(timeout=5000) if enabled else self.Stub()

    def feed(self):
        self.__wdt.feed()
