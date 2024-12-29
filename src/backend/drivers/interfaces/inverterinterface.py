from .driverinterface import DriverInterface

class InverterInterface(DriverInterface):
    async def switch_inverter(self, on):
        raise NotImplementedError()
    
    async def set_inverter_power(self, power):
        raise NotImplementedError()
    
    @property
    def min_power(self):
        raise NotImplementedError()

    @property
    def max_power(self):
        raise NotImplementedError()
    
    @property
    def on_inverter_data(self):
        raise NotImplementedError()
    
    def get_inverter_data(self):
        raise NotImplementedError()
