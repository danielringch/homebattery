
class DriverInterface():
    @property
    def device_types(self):
        raise NotImplementedError()
    
    @property
    def name(self):
        raise NotImplementedError()