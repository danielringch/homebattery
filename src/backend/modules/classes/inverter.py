from time import time
from ...core.devicetools import merge_driver_statuses
from ...core.types import MODE_DISCHARGE, run_callbacks, STATUS_FAULT, STATUS_ON, TYPE_INVERTER
from ...core.types import MEASUREMENT_STATUS, MEASUREMENT_POWER
from ..consumption import Consumption
from ..devices import Devices
from ..netzero import NetZero
from .anyclass import AnyClass

class Inverter(AnyClass):
    def __init__(self, config: dict, devices: Devices, consumption: Consumption):
        super().__init__(TYPE_INVERTER, devices, lambda x: x.on_inverter_data, lambda x: x.get_inverter_data())

        config = config['inverter']
        self.__default_power = int(config['power'])
        self.__reduce_power_during_fault = bool(config['reduce_power_during_fault'])
        if 'netzero' in config:
            self.__netzero = NetZero(config['netzero'])
            consumption.on_power.append(self.__on_live_consumption)
        else:
            self._log.info('Netzero disabled.')
            self.__netzero = None

    async def set_mode(self, mode: str):
        async with self._lock:
            shall_on = (mode == MODE_DISCHARGE)
            for inverter in self._devices:
                await inverter.switch_inverter(shall_on)

    async def _get_status(self):
        driver_statuses = tuple(x.get_inverter_data()[MEASUREMENT_STATUS] for x in self._devices)
        status = merge_driver_statuses(driver_statuses)

        if status != self._last_status :
            self._commands.append(self._handle_state_change)
            if status != STATUS_ON:
                run_callbacks(self._summary_callbacks, {MEASUREMENT_POWER: 0})
                if self.__netzero is not None:
                    self.__netzero.clear()

        if status != self._last_status:
            run_callbacks(self._summary_callbacks, {MEASUREMENT_STATUS: status})
            self._last_status = status
        return status

    async def _handle_state_change(self):
        if self._last_status == STATUS_FAULT and self.__reduce_power_during_fault:
            await self.__set_power(0)
        elif self._last_status == STATUS_ON and self.__netzero is None:
            await self.__set_power(self.__default_power)

    async def _update_netzero(self):
        if len(self._devices) == 0:
            return
        status = await self._get_status()
        power = await self._get_power()
        if status != STATUS_ON or power is None:
            return
        delta = self.__netzero.evaluate() # type: ignore
        if delta != 0:
            await self.__set_power(power + delta)

    async def _get_power(self):
        power = 0
        for inverter in self._devices:
            inverter_power = inverter.get_inverter_data().get(MEASUREMENT_POWER, None)
            if inverter_power is None:
                return None
            power += inverter_power

        if power != self._last_power:
            if self.__netzero is not None:
                self.__netzero.clear()
        if power != self._last_power:
            run_callbacks(self._summary_callbacks, {MEASUREMENT_POWER: power})
            self._last_power = power
        return power
    
    async def __set_power(self, power):
        last_inverter = self._devices[-1]

        max_power = sum((x.max_power for x in self._devices), 0)
        relative_power = power / max_power if max_power > 0 else 0
        remaining_power = power
        new_power = 0

        for inverter in self._devices:
            power_per_inverter = round(inverter.max_power * relative_power) if inverter is not last_inverter else remaining_power
            actual_power = await inverter.set_inverter_power(power_per_inverter)
            new_power += actual_power
            remaining_power -= actual_power

    def __on_live_consumption(self, power):
        if self._last_status == STATUS_ON:
            self.__netzero.update(time(), power) # type: ignore
        self._commands.append(self._update_netzero)
