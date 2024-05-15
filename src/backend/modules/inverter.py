from asyncio import Event, Lock, TimeoutError, wait_for
from collections import deque
from micropython import const
from sys import print_exception
from time import time
from ..core.backendmqtt import Mqtt
from ..core.devicetools import get_energy_execution_timestamp, merge_driver_statuses
from ..core.types import CallbackCollection, CommandBundle, MODE_DISCHARGE, STATUS_FAULT, STATUS_OFF, STATUS_ON, STATUS_SYNCING
from .devices import Devices
from .netzero import NetZero

_INVERTER_LOG_NAME = const('inverter')

class Inverter:
    def __init__(self, config: dict, devices: Devices, mqtt: Mqtt):
        from ..core.singletons import Singletons
        self.__lock = Lock()
        self.__commands = deque((), 10)

        self.__log = Singletons.log.create_logger(_INVERTER_LOG_NAME)
        self.__event = Event()

        self.__mqtt = mqtt
        self.__mqtt.on_live_consumption.add(self.__on_live_consumption)

        self.__netzero = NetZero(config)
        self.__on_energy = CallbackCollection()
        self.__on_power = CallbackCollection()
        self.__on_status = CallbackCollection()

        self.__last_status = None
        self.__last_power = None

        from ..core.types import TYPE_INVERTER
        self.__inverters = devices.get_by_type(TYPE_INVERTER)
        for device in self.__inverters:
            device.on_inverter_status_change.add(self.__on_inverter_status)
            device.on_inverter_power_change.add(self.__on_inverter_power)

        self.__max_power = sum((x.max_power for x in self.__inverters), 0)

        if len(self.__inverters) == 0:
            self.__last_status = STATUS_OFF

        self.__next_energy_execution = get_energy_execution_timestamp()

    async def run(self):
        while True:
            try:
                now = time()
                async with self.__lock:
                    while len(self.__commands) > 0:
                        await self.__commands.popleft().run()
                    if now >= self.__next_energy_execution:
                        await self.__get_energy()
                        self.__next_energy_execution = get_energy_execution_timestamp()
            except Exception as e:
                self.__log.error('Inverter cycle failed: ', e)
                from ..core.singletons import Singletons
                print_exception(e, Singletons.log.trace)
            try:
                await wait_for(self.__event.wait(), timeout=1)
            except TimeoutError:
                pass
            self.__event.clear()

    def get_status(self):
        return self.__last_status if self.__last_status is not None else STATUS_SYNCING

    async def __get_status(self):
        driver_statuses = tuple(x.get_inverter_status() for x in self.__inverters)
        status = merge_driver_statuses(driver_statuses)

        if status != self.__last_status :
            self.__commands.append(CommandBundle(self.__handle_state_change, (status,)))
            self.__event.set()
            if status != STATUS_ON:
                self.__on_power.run_all(0)
                self.__netzero.clear()
            self.__on_status.run_all(status)
            self.__last_status = status
        return status

    async def set_mode(self, mode: str):
        async with self.__lock:
            shall_on = mode == MODE_DISCHARGE
            for inverter in self.__inverters:
                await inverter.switch_inverter(shall_on)

    @property
    def on_energy(self):
        return self.__on_energy
    
    @property
    def on_power(self):
        return self.__on_power
    
    @property
    def on_status(self):
        return self.__on_status
    
    async def __handle_state_change(self, new_status):
        if new_status == STATUS_FAULT:
            # fault recovery has better chances if other inverters produce minimal power
            await self.__set_power(0)

    async def __update_netzero(self, timestamp, consumption):
        if len(self.__inverters) == 0:
            return
        status = await self.__get_status()
        power = await self.__get_power()
        if status != STATUS_ON or power is None:
            return
        delta = self.__netzero.evaluate(timestamp, consumption)
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
            self.__netzero.clear()
            self.__on_power.run_all(power)
            self.__last_power = power
        return power
    
    async def __set_power(self, power):
        last_inverter = self.__inverters[-1]

        relative_power = power / self.__max_power
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
            energy += inverter.get_inverter_energy()
        self.__on_energy.run_all(round(energy))

    def __on_inverter_status(self, status):
        self.__commands.append(CommandBundle(self.__get_status, ()))
        self.__event.set()

    def __on_inverter_power(self, power):
        self.__commands.append(CommandBundle(self.__get_power, ()))
        self.__event.set()

    def __on_live_consumption(self, power):
        self.__commands.append(CommandBundle(self.__update_netzero, (time(), power)))
        self.__event.set()
