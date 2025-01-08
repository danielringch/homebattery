from ...core.types import STATUS_OFF, STATUS_ON
from ...core.types import TYPE_HEATER, TYPE_BATTERY
from ..devices import Devices
from ..battery import Battery
from .anyclass import AnyClass

_MAGIC_NONE = 999

_SUPPORTED_CLASSES = (TYPE_BATTERY,)

class Heater(AnyClass):
    def __init__(self, config: dict, devices: Devices, battery: Battery):
        super().__init__(TYPE_HEATER, devices, lambda x: x.on_heater_data, lambda x: x.get_heater_data())

        self.__battery = battery

        self.__temps = {
            TYPE_BATTERY: _MAGIC_NONE
        }

        self.__activate_thresholds = {}
        self.__deactivate_thresholds = {}

        if 'heater' in config:
            config = config['heater']
            for name, threshold in config['activate'].items():
                if not name in _SUPPORTED_CLASSES:
                    self._log.error('Unknown device class or sensor: ', name)
                else:
                    self.__activate_thresholds[name] = threshold
            for name, threshold in config['deactivate'].items():
                if not name in _SUPPORTED_CLASSES:
                    self._log.error('Unknown device class or sensor: ', name)
                else:
                    self.__deactivate_thresholds[name] = threshold

        battery.on_battery_data.append(self.__on_battery_data)

    async def _evaluate(self):
        if not self._devices:
            return

        activators = list()
        deactivators = list()

        for name, threshold in self.__activate_thresholds.items():
            temp = self.__temps.get(name, _MAGIC_NONE)
            if temp == _MAGIC_NONE:
                continue
            if temp <= threshold:
                activators.append(name)

        for name, threshold in self.__deactivate_thresholds.items():
            temp = self.__temps.get(name, _MAGIC_NONE)
            if temp == _MAGIC_NONE:
                continue
            if temp >= threshold:
                deactivators.append(name)

        if activators:
            self._log.info('Sensors under activation threshold: ', ', '.join(activators))
            if self._last_status != STATUS_ON:
                self._log.info('Activating heater')
                await self.__switch(True)
        elif deactivators:
            self._log.info('Sensors over deactivation threshold: ', ', '.join(deactivators))
            if self._last_status != STATUS_OFF:
                self._log.info('Deactivating heater')
                await self.__switch(False)

    async def __switch(self, on: bool):
        for heater in self._devices:
            await heater.switch_heater(on)

    def __on_battery_data(self, _):
        min_temp = _MAGIC_NONE
        for battery in self.__battery.battery_data.values():
            if battery and battery.temps:
                min_temp = min(min_temp, min(battery.temps))
        self.__temps[TYPE_BATTERY] = min_temp
        self._commands.append(self._evaluate)
