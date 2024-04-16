from .driverinterface import DriverInterface

class BatteryInterface(DriverInterface):
    async def read_battery(self):
        raise NotImplementedError