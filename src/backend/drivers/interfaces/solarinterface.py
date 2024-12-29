from .driverinterface import DriverInterface

class SolarInterface(DriverInterface):
    async def switch_solar(self, on):
        raise NotImplementedError()
    
    @property
    def on_solar_data(self):
        raise NotImplementedError()
    
    def get_solar_data(self):
        raise NotImplementedError()