from .driverinterface import DriverInterface

class SolarInterface(DriverInterface):
    async def switch_solar(self, on):
        raise NotImplementedError
    
    def get_solar_status(self):
        raise NotImplementedError
    
    @property
    def on_solar_status_change(self):
        raise NotImplementedError
    
    def get_solar_power(self):
        raise NotImplementedError
    
    @property
    def on_solar_power_change(self):
        raise NotImplementedError
    
    async def get_solar_energy(self):
        raise NotImplementedError