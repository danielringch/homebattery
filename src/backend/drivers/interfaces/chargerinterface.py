from .driverinterface import DriverInterface

class ChargerInterface(DriverInterface):
    async def switch_charger(self, on):
        raise NotImplementedError()
    
    @property
    def on_charger_data(self):
        raise NotImplementedError()
    
    def get_charger_data(self):
        raise NotImplementedError()