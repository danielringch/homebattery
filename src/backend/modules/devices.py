import sys
from ..core.logging import *

from ..drivers.accuratt6024v import AccuratT6024V
from ..drivers.ahoydtu import AhoyDtu
from ..drivers.daly8s24v60a import Daly8S24V60A
from ..drivers.shelly import Shelly

drivers = {
    'accuratT6024V': AccuratT6024V,
    'ahoydtu': AhoyDtu,
    'daly8S24V60A': Daly8S24V60A,
    'shelly': Shelly
}

class Devices:
    def __init__(self, config):
        config = config['devices']
        self.__devices = []

        for name, meta in config.items():
            try:
                driver = drivers[meta['driver']]
                log.debug(f'Loading device {name} with driver {driver.__name__}.')
                instance = driver(name, meta)
                self.__devices.append(instance)
            except Exception as e:
                log.error(f'Failed to initialize device {name}: {e}')
                sys.print_exception(e, log.trace)

    @property
    def devices(self):
        return self.__devices