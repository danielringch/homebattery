from ...core.types import MODE_CHARGE, TYPE_CHARGER
from ..devices import Devices
from .anyclass import AnyClass

class Charger(AnyClass):
    def __init__(self, config: dict, devices: Devices):
        super().__init__(TYPE_CHARGER, devices, lambda x: x.on_charger_data, lambda x: x.get_charger_data())

    async def set_mode(self, mode: str):
        async with self._lock:
            shall_on = (mode == MODE_CHARGE)
            for charger in self._devices:
                await charger.switch_charger(shall_on)
