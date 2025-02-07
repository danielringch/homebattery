from .driverinterface import DriverInterface

class HeaterInterface(DriverInterface):
    async def switch_heater(self, on):
        raise NotImplementedError()
    
    @property
    def on_heater_data(self):
        raise NotImplementedError()
    
    def get_heater_data(self):
        raise NotImplementedError()