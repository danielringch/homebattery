from asyncio import Lock, TimeoutError, wait_for
from time import time
from ..core.devicetools import merge_driver_statuses
from ..core.logging import CustomLogger
from ..core.types import CommandFiFo, MODE_PROTECT, run_callbacks, STATUS_ON, STATUS_OFF, STATUS_OFFLINE, STATUS_SYNCING
from ..core.types import MEASUREMENT_STATUS, MEASUREMENT_POWER, MEASUREMENT_ENERGY
from .devices import Devices

class Solar:
    def __init__(self, config: dict, devices: Devices):
        from ..core.singletons import Singletons
        self.__lock = Lock()
        self.__commands = CommandFiFo(16)

        self.__log: CustomLogger = Singletons.log.create_logger('solar')

        self.__summary_callbacks = list()

        from ..core.types import TYPE_SOLAR
        self.__devices = devices.get_by_type(TYPE_SOLAR)
        for device in self.__devices:
            device.on_solar_data.append(self.__on_device_data)

        self.__last_status_tx = 0
        self.__last_power_tx = 0

        self.__last_status = STATUS_OFFLINE if self.__devices else STATUS_OFF
        self.__last_power = 0

    async def run(self):
        while True:
            try:
                now = time()
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

    async def set_mode(self, mode: str):
        async with self.__lock:
            on = mode != MODE_PROTECT
            for device in self.__devices:
                   await device.switch_solar(on)

    @property
    def on_summary_data(self):
        return self.__summary_callbacks
    
    def get_summary_data(self):
        return {
            MEASUREMENT_STATUS: self.__last_status,
            MEASUREMENT_POWER: self.__last_power
        }

    async def __get_status(self):
        now = time()
        driver_statuses = tuple(x.get_solar_data()[MEASUREMENT_STATUS] for x in self.__devices)
        status = merge_driver_statuses(driver_statuses)

        if (status != self.__last_status) or ((now - self.__last_status_tx) > 270):
            run_callbacks(self.__summary_callbacks, {MEASUREMENT_STATUS: status})
            self.__last_status = status
            self.__last_status_tx = now

    async def __get_power(self):
        now = time()
        power = sum((x.get_solar_data().get(MEASUREMENT_POWER, 0) for x in self.__devices), 0)
        if (power != self.__last_power) or ((now - self.__last_power_tx) > 270):
            run_callbacks(self.__summary_callbacks, {MEASUREMENT_POWER: power})
            self.__last_power = power
            self.__last_power_tx = now

    def __on_device_data(self, sender, data):
        if MEASUREMENT_STATUS in data:
            self.__commands.append(self.__get_status)
        if MEASUREMENT_POWER in data:
            self.__commands.append(self.__get_power)
        if MEASUREMENT_ENERGY in data:
            run_callbacks(self.__summary_callbacks, {MEASUREMENT_ENERGY: data[MEASUREMENT_ENERGY]})
