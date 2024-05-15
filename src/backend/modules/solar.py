from asyncio import Event, Lock, TimeoutError, wait_for
from collections import deque
from micropython import const
from sys import print_exception
from time import time
from ..core.devicetools import get_energy_execution_timestamp, merge_driver_statuses
from ..core.types import CallbackCollection, CommandBundle, MODE_PROTECT, STATUS_ON, STATUS_OFF, STATUS_SYNCING
from .devices import Devices

_SOLAR_LOG_NAME = const('solar')

class Solar:
    def __init__(self, config: dict, devices: Devices):
        from ..core.singletons import Singletons
        self.__lock = Lock()
        self.__commands = deque((), 10)

        self.__log = Singletons.log.create_logger(_SOLAR_LOG_NAME)
        self.__event = Event()

        self.__on_energy = CallbackCollection()
        self.__on_power = CallbackCollection()
        self.__on_status = CallbackCollection()

        from ..core.types import TYPE_SOLAR
        self.__devices = devices.get_by_type(TYPE_SOLAR)
        for device in self.__devices:
            device.on_solar_status_change.add(self.__on_status_change)
            device.on_solar_power_change.add(self.__on_power_change)

        self.__last_status = None
        self.__last_power = None

        if len(self.__devices) == 0:
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
                self.__log.error('Solar cycle failed: ', e)
                from ..core.singletons import Singletons
                print_exception(e, Singletons.log.trace)
            try:
                await wait_for(self.__event.wait(), timeout=1)
            except TimeoutError:
                pass
            self.__event.clear()

    def get_status(self):
        return self.__last_status if self.__last_status is not None else STATUS_SYNCING

    async def set_mode(self, mode: str):
        async with self.__lock:
            on = mode != MODE_PROTECT
            for device in self.__devices:
                   await device.switch_solar(on)

    @property
    def on_energy(self):
        return self.__on_energy
    
    @property
    def on_power(self):
        return self.__on_power
    
    @property
    def on_status(self):
        return self.__on_status
    
    async def __get_status(self):
        driver_statuses = tuple(x.get_solar_status() for x in self.__devices)
        status = merge_driver_statuses(driver_statuses)

        if status != self.__last_status:
            self.__on_status.run_all(status)
            self.__last_status = status

    async def __get_power(self):
        power = sum((x.get_solar_power() for x in self.__devices), 0)
        if power != self.__last_power:
            self.__on_power.run_all(power)
            self.__last_power = power

    async def __get_energy(self):
        energy = 0.0
        for device in self.__devices:
            device_energy = await device.get_solar_energy()
            if device_energy is not None:
                energy += device_energy
        self.__on_energy.run_all(round(energy))

    def __on_status_change(self, _):
        self.__commands.append(CommandBundle(self.__get_status, ()))

    def __on_power_change(self, _):
        self.__commands.append(CommandBundle(self.__get_power, ()))