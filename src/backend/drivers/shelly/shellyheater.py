from ..interfaces.heaterinterface import HeaterInterface
from ...core.logging import CustomLogger
from ...core.types import TYPE_HEATER
from .anyshelly import AnyShelly

class ShellyHeater(HeaterInterface):
    def __init__(self, name, config):
        super().__init__()
        from ...core.singletons import Singletons
        self.__name = name
        self.__device_types = (TYPE_HEATER,)
        self.__log: CustomLogger = Singletons.log.create_logger(name)
        self.__driver = AnyShelly(self, config, self.__log)

    @property
    def name(self):
        return self.__name

    @property
    def device_types(self):
        return self.__device_types

    async def switch_heater(self, on):
        await self.__driver.switch(on)

    @property
    def on_heater_data(self):
        return self.__driver.on_data
    
    def get_heater_data(self):
        return self.__driver.get_data()
        