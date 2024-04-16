from .driverinterface import DriverInterface

class ChargerInterface(DriverInterface):
    async def switch_charger(self, on):
        raise NotImplementedError
    
    async def is_charger_on(self):
        raise NotImplementedError
    
    async def get_charger_energy(self):
        raise NotImplementedError