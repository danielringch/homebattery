from time import time
from .devices import Devices
from ..core.types import run_callbacks
from ..drivers.interfaces.consumptioninterface import ConsumptionInterface

class Consumption:
    class DataBundle:
        def __init__(self):
            self.power = 0
            self.last_seen = 0

    def __init__(self, devices: Devices):
        from ..core.singletons import Singletons
        self.__log = Singletons.log.create_logger('consumption')

        self.__power_callbacks = list()

        self.__last_seen = 0

        self.__powers = dict()
        from ..core.types import TYPE_CONSUMPTION
        self.__devices = devices.get_by_type(TYPE_CONSUMPTION)
        for device in self.__devices:
            device.on_power.append(self.__on_power)
            self.__powers[device.name] = self.DataBundle()

    @property
    def on_power(self):
        return self.__power_callbacks
    
    @property
    def last_seen(self):
        return self.__last_seen

    def __on_power(self, sender: ConsumptionInterface, power: int):
        bundle = self.__powers[sender.name]
        bundle.power = power
        bundle.last_seen = time()

        total_power = 0
        oldest = time()
        for device in self.__powers.values():
            total_power += device.power
            oldest = min(oldest, device.last_seen)
        self.__last_seen = oldest

        self.__log.info('Total power consumption: ', total_power, ' W')

        run_callbacks(self.__power_callbacks, total_power)
