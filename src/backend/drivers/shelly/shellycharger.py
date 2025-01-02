from ..interfaces.chargerinterface import ChargerInterface
from ...core.logging import CustomLogger
from ...core.types import TYPE_CHARGER
from .anyshelly import AnyShelly

class ShellyCharger(ChargerInterface):
    def __init__(self, name, config):
        super(ShellyCharger, self).__init__()
        from ...core.singletons import Singletons
        self.__name = name
        self.__device_types = (TYPE_CHARGER,)
        self.__log: CustomLogger = Singletons.log.create_logger(name)
        self.__driver = AnyShelly(self, config, self.__log)

    @property
    def name(self):
        return self.__name

    @property
    def device_types(self):
        return self.__device_types

    async def switch_charger(self, on):
        await self.__driver.switch(on)

    @property
    def on_charger_data(self):
        return self.__driver.on_data
    
    def get_charger_data(self):
        return self.__driver.get_data()
        