from asyncio import Lock, TimeoutError, wait_for
from time import time
from ..core.devicetools import merge_driver_statuses
from ..core.logging import CustomLogger
from ..core.types import CommandFiFo, MODE_DISCHARGE, run_callbacks, STATUS_FAULT, STATUS_OFF, STATUS_OFFLINE, STATUS_ON, STATUS_SYNCING
from ..core.types import MEASUREMENT_STATUS, MEASUREMENT_POWER, MEASUREMENT_ENERGY
from .consumption import Consumption
from .devices import Devices
from .netzero import NetZero

class Inverter:
    def __init__(self, config: dict, devices: Devices, consumption: Consumption):
        from ..core.singletons import Singletons
        self.__lock = Lock()
        self.__commands = CommandFiFo(16)

        self.__log: CustomLogger = Singletons.log.create_logger('inverter')

        config = config['inverter']
        self.__default_power = int(config['power'])
        self.__reduce_power_during_fault = bool(config['reduce_power_during_fault'])
        if 'netzero' in config:
            self.__netzero = NetZero(config['netzero'])
            consumption.on_power.append(self.__on_live_consumption)
        else:
            self.__log.info('Netzero disabled.')
            self.__netzero = None

        self.__summary_callbacks = list()

        self.__last_status_tx = 0
        self.__last_power_tx = 0

        from ..core.types import TYPE_INVERTER
        self.__inverters = devices.get_by_type(TYPE_INVERTER)
        self.__last_status = STATUS_OFFLINE if self.__inverters else STATUS_OFF
        self.__last_power = 0

        for device in self.__inverters:
            device.on_inverter_data.append(self.__on_device_data)

    async def run(self):
        while True:
            try:
                async with self.__lock:
                    while self.__commands:
                        await self.__commands.popleft()()
            except Exception as e:
                self.__log.error('Cycle failed: ', e)
                self.__log.trace(e)
            try:
                await wait_for(self.__commands.wait_and_clear(), timeout=1)
            except TimeoutError:
                pass

    def get_status(self):
        return self.__last_status if self.__last_status is not None else STATUS_SYNCING

    async def __get_status(self):
        now = time()
        driver_statuses = tuple(x.get_inverter_data()[MEASUREMENT_STATUS] for x in self.__inverters)
        status = merge_driver_statuses(driver_statuses)

        if status != self.__last_status :
            self.__commands.append(self.__handle_state_change)
            if status != STATUS_ON:
                run_callbacks(self.__summary_callbacks, {MEASUREMENT_POWER: 0})
                if self.__netzero is not None:
                    self.__netzero.clear()

        if (status != self.__last_status) or ((now - self.__last_status_tx) > 270):
            run_callbacks(self.__summary_callbacks, {MEASUREMENT_STATUS: status})
            self.__last_status = status
            self.__last_status_tx = now
        return status

    async def set_mode(self, mode: str):
        async with self.__lock:
            shall_on = mode == MODE_DISCHARGE
            for inverter in self.__inverters:
                await inverter.switch_inverter(shall_on)

    @property
    def on_summary_data(self):
        return self.__summary_callbacks
    
    def get_summary_data(self):
        return {
            MEASUREMENT_STATUS: self.__last_status,
            MEASUREMENT_POWER: self.__last_power
        }
    
    async def __handle_state_change(self):
        if self.__last_status == STATUS_FAULT and self.__reduce_power_during_fault:
            await self.__set_power(0)
        elif self.__last_status == STATUS_ON and self.__netzero is None:
            await self.__set_power(self.__default_power)

    async def __update_netzero(self):
        if len(self.__inverters) == 0:
            return
        status = await self.__get_status()
        power = await self.__get_power()
        if status != STATUS_ON or power is None:
            return
        delta = self.__netzero.evaluate() # type: ignore
        if delta != 0:
            await self.__set_power(power + delta)

    async def __get_power(self):
        now = time()
        power = 0
        for inverter in self.__inverters:
            inverter_power = inverter.get_inverter_data().get(MEASUREMENT_POWER, None)
            if inverter_power is None:
                return None
            power += inverter_power

        if power != self.__last_power:
            if self.__netzero is not None:
                self.__netzero.clear()
        if (power != self.__last_power) or ((now - self.__last_power_tx) > 270):
            run_callbacks(self.__summary_callbacks, {MEASUREMENT_POWER: power})
            self.__last_power = power
            self.__last_power_tx = now
        return power
    
    async def __set_power(self, power):
        last_inverter = self.__inverters[-1]

        max_power = sum((x.max_power for x in self.__inverters), 0)
        relative_power = power / max_power if max_power > 0 else 0
        remaining_power = power
        new_power = 0

        for inverter in self.__inverters:
            power_per_inverter = round(inverter.max_power * relative_power) if inverter is not last_inverter else remaining_power
            actual_power = await inverter.set_inverter_power(power_per_inverter)
            new_power += actual_power
            remaining_power -= actual_power

    def __on_device_data(self, sender, data):
        if MEASUREMENT_STATUS in data:
            self.__commands.append(self.__get_status)
        if MEASUREMENT_POWER in data:
            self.__commands.append(self.__get_power)
        if MEASUREMENT_ENERGY in data:
            run_callbacks(self.__summary_callbacks, {MEASUREMENT_ENERGY: data[MEASUREMENT_ENERGY]})

    def __on_live_consumption(self, power):
        if self.__last_status == STATUS_ON:
            self.__netzero.update(time(), power) # type: ignore
        self.__commands.append(self.__update_netzero)
