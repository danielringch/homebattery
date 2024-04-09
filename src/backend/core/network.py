import network, ntptime
from time import sleep
from machine import WDT

from uerrno import ETIMEDOUT
from .logging import log

class Network():
    def __init__(self, config: dict):
        self.__config = config["network"]

    def connect(self, watchdog: WDT):
        watchdog.feed()
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        wlan.config(pm=0xA11140)
        wlan.connect(self.__config['ssid'], self.__config['password'])
        countdown = int(self.__config['timeout'])
        while True:
            log.debug('Waiting for connection...')
            if countdown > 0:
                watchdog.feed()
                countdown -= 1
            sleep(1)
            if wlan.isconnected():
                break
        log.debug('Network connected.')

    def get_network_time(self, watchdog: WDT):
        log.debug('Synchronizing clock...')
        countdown = int(self.__config['ntp_timeout']) // 2
        while True:
            try:
                if countdown > 0:
                    watchdog.feed()
                ntptime.settime()
                break
            except OSError as e:
                if e.args[0] != ETIMEDOUT:
                    raise
                log.debug(f'Waiting for network time...')
                if countdown > 0:
                    watchdog.feed()
                    countdown -= 1
                sleep(2)
        log.debug(f'Clock synchronized.')
