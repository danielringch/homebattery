from ...core.types import MODE_PROTECT, TYPE_SOLAR
from ..devices import Devices
from .anyclass import AnyClass

class Solar(AnyClass):
    def __init__(self, config: dict, devices: Devices):
        super().__init__(TYPE_SOLAR, devices, lambda x: x.on_solar_data, lambda x: x.get_solar_data())

    async def set_mode(self, mode: str):
        async with self._lock:
            on = (mode != MODE_PROTECT)
            for device in self._devices:
                   await device.switch_solar(on)
