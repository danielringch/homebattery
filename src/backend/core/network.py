from network import WLAN, STA_IF
from ntptime import settime as setntptime
from time import sleep
from uerrno import ETIMEDOUT
from .watchdog import Watchdog

class Network():
    def __init__(self, config: dict):
        from .logging_singleton import log
        self.__log = log
        self.__config = config["network"]

    def connect(self, watchdog: Watchdog):
        watchdog.feed()
        wlan = WLAN(STA_IF)
        wlan.active(True)
        wlan.config(pm=0xA11140)
        wlan.connect(self.__config['ssid'], self.__config['password'])
        countdown = int(self.__config['timeout'])
        while True:
            self.__log.debug('Waiting for connection...')
            if countdown > 0:
                watchdog.feed()
                countdown -= 1
            sleep(1)
            if wlan.isconnected():
                break
        self.__log.debug('Network connected.')

    def get_network_time(self, watchdog: Watchdog):
        self.__log.debug('Synchronizing clock...')
        countdown = int(self.__config['ntp_timeout']) // 2
        while True:
            try:
                if countdown > 0:
                    watchdog.feed()
                setntptime()
                break
            except OSError as e:
                if e.args[0] != ETIMEDOUT:
                    raise
                self.__log.debug(f'Waiting for network time...')
                if countdown > 0:
                    watchdog.feed()
                    countdown -= 1
                sleep(2)
        self.__log.debug(f'Clock synchronized.')
