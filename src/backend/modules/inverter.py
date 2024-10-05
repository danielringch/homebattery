from asyncio import Lock, TimeoutError, wait_for
from sys import print_exception
from time import time
from ..core.devicetools import get_energy_execution_timestamp, merge_driver_statuses
from ..core.types import CommandFiFo, MODE_DISCHARGE, run_callbacks, STATUS_FAULT, STATUS_OFF, STATUS_ON, STATUS_SYNCING
from .consumption import Consumption
from .devices import Devices
from .netzero import NetZero

class Inverter:
    def __init__(self, config: dict, devices: Devices, consumption: Consumption):
        from ..core.singletons import Singletons
        self.__lock = Lock()
        self.__commands = CommandFiFo()

        self.__log = Singletons.log.create_logger('inverter')

        config = config['inverter']
        self.__default_power = int(config['power'])
        self.__reduce_power_during_fault = bool(config['reduce_power_during_fault'])
        if 'netzero' in config:
            self.__netzero = NetZero(config['netzero'])
            consumption.on_power.append(self.__on_live_consumption)
        else:
            self.__log.info('Netzero disabled.')
            self.__netzero = None

        self.__status_callbacks = list()
        self.__power_callbacks = list()
        self.__device_power_callbacks = list()
        self.__energy_callbacks = list()
        self.__device_energy_callbacks = list()

        self.__last_status = None
        self.__last_power = None

        from ..core.types import TYPE_INVERTER
        self.__inverters = devices.get_by_type(TYPE_INVERTER)
        for device in self.__inverters:
            device.on_inverter_status_change.append(self.__on_inverter_status)
            device.on_inverter_power_change.append(self.__on_inverter_power)

        if len(self.__inverters) == 0:
            self.__last_status = STATUS_OFF

        self.__next_energy_execution = get_energy_execution_timestamp()

    async def run(self):
        while True:
            try:
                now = time()
                async with self.__lock:
                    while not self.__commands.empty:
                        await self.__commands.pop()()
                    if now >= self.__next_energy_execution:
                        await self.__get_energy()
                        self.__next_energy_execution = get_energy_execution_timestamp()
            except Exception as e:
                self.__log.error('Cycle failed: ', e)
                from ..core.singletons import Singletons
                print_exception(e, Singletons.log.trace)
            try:
                await wait_for(self.__commands.wait_and_clear(), timeout=1)
            except TimeoutError:
                pass

    def get_status(self):
        return self.__last_status if self.__last_status is not None else STATUS_SYNCING

    async def __get_status(self):
        driver_statuses = tuple(x.get_inverter_status() for x in self.__inverters)
        status = merge_driver_statuses(driver_statuses)

        if status != self.__last_status :
            self.__commands.append(self.__handle_state_change)
            if status != STATUS_ON:
                run_callbacks(self.__power_callbacks, 0)
                if self.__netzero is not None:
                    self.__netzero.clear()
            run_callbacks(self.__status_callbacks, status)
            self.__last_status = status
        return status

    async def set_mode(self, mode: str):
        async with self.__lock:
            shall_on = mode == MODE_DISCHARGE
            for inverter in self.__inverters:
                await inverter.switch_inverter(shall_on)

    @property
    def on_status(self):
        return self.__status_callbacks
    
    @property
    def on_power(self):
        return self.__power_callbacks
    
    @property
    def on_device_power(self):
        return self.__device_power_callbacks
    
    @property
    def on_energy(self):
        return self.__energy_callbacks
    
    @property
    def on_device_energy(self):
        return self.__device_energy_callbacks
    
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
        power = 0
        for inverter in self.__inverters:
            inverter_power = inverter.get_inverter_power()
            if inverter_power is None:
                return None
            power += inverter_power

        if power != self.__last_power:
            if self.__netzero is not None:
                self.__netzero.clear()
            run_callbacks(self.__power_callbacks, power)
            self.__last_power = power
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

    async def __get_energy(self):
        energy = 0.0
        for inverter in self.__inverters:
            device_energy = inverter.get_inverter_energy()
            energy += device_energy
            run_callbacks(self.__device_energy_callbacks, inverter.name, round(device_energy))
        run_callbacks(self.__energy_callbacks, round(energy))

    def __on_inverter_status(self, sender, status):
        self.__commands.append(self.__get_status)

    def __on_inverter_power(self, sender, power):
        self.__commands.append(self.__get_power)
        run_callbacks(self.__device_power_callbacks, sender.name, power)

    def __on_live_consumption(self, power):
        if self.__last_status == STATUS_ON:
            self.__netzero.update(time(), power) # type: ignore
        self.__commands.append(self.__update_netzero)
