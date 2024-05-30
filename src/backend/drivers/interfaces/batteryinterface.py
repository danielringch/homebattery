from .driverinterface import DriverInterface

class BatteryInterface(DriverInterface):
    async def read_battery(self):
        raise NotImplementedError()
    
    @property
    def on_battery_data(self):
        raise NotImplementedError()