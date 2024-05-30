from .driverinterface import DriverInterface

class ConsumptionInterface(DriverInterface):
    @property
    def on_power(self):
        raise NotImplementedError()
