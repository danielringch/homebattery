from .driverinterface import DriverInterface

class InverterInterface(DriverInterface):
    async def switch_inverter(self, on):
        raise NotImplementedError()
    
    def get_inverter_status(self):
        raise NotImplementedError()
    
    @property
    def on_inverter_status_change(self):
        raise NotImplementedError()
    
    async def set_inverter_power(self, power):
        raise NotImplementedError()
    
    def get_inverter_power(self):
        raise NotImplementedError()
    
    @property
    def min_power(self):
        raise NotImplementedError()

    @property
    def max_power(self):
        raise NotImplementedError()
    
    @property
    def on_inverter_power_change(self):
        raise NotImplementedError()
    
    def get_inverter_energy(self):
        raise NotImplementedError()
