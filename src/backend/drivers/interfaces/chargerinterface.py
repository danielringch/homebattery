from .driverinterface import DriverInterface

class ChargerInterface(DriverInterface):
    async def switch_charger(self, on):
        raise NotImplementedError
    
    def get_charger_status(self):
        raise NotImplementedError
    
    @property
    def on_charger_status_change(self):
        raise NotImplementedError
    
    async def get_charger_energy(self):
        raise NotImplementedError