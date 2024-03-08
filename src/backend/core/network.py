import network, ntptime, time
from time import sleep

from uerrno import ETIMEDOUT
from .logging import log

class Network():
    def __init__(self, config: dict):
        self.__config = config["network"]

    def connect(self):
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        wlan.config(pm=0xA11140)
        wlan.connect(self.__config['ssid'], self.__config['password'])

        for _ in range(int(self.__config['timeout'])):
            log.debug('Waiting for connection...')
            sleep(1)
            if wlan.isconnected():
                break
        else:
            return False

        log.debug('Network connected.')

        log.debug('Synchronizing clock...')
        for _ in range(int(self.__config['ntp_timeout']) // 2):
            try:
                ntptime.settime()
                break
            except OSError as e:
                if e.args[0] != ETIMEDOUT:
                    raise
                log.debug(f'Waiting for network time...')
                sleep(2)
        else:
            return False
    
        log.debug(f'Clock synchronized.')
        return True
