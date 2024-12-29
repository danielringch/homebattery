from asyncio import Lock, TimeoutError, wait_for
from time import time
from ..core.devicetools import merge_driver_statuses
from ..core.logging import CustomLogger
from ..core.types import CommandFiFo, MODE_CHARGE, run_callbacks, STATUS_ON, STATUS_OFF, STATUS_OFFLINE, STATUS_SYNCING, MEASUREMENT_STATUS, MEASUREMENT_ENERGY
from .devices import Devices

class Charger:
    def __init__(self, config: dict, devices: Devices):
        from ..core.singletons import Singletons
        self.__lock = Lock()
        self.__commands = CommandFiFo(16)

        self.__log: CustomLogger = Singletons.log.create_logger('charger')

        self.__last_status_tx = 0
        self.__last_power_tx = 0

        self.__summary_callbacks = list()

        from ..core.types import TYPE_CHARGER
        self.__chargers = devices.get_by_type(TYPE_CHARGER)
        self.__last_status = STATUS_OFFLINE if self.__chargers else STATUS_OFF

        for device in self.__chargers:
            device.on_charger_data.append(self.__on_device_data)

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
        return self.__last_status

    async def set_mode(self, mode: str):
        async with self.__lock:
            shall_on = mode == MODE_CHARGE
            for charger in self.__chargers:
                await charger.switch_charger(shall_on)

    @property
    def on_summary_data(self):
        return self.__summary_callbacks
    
    def get_summary_data(self):
        return {MEASUREMENT_STATUS: self.__last_status}

    async def __get_status(self):
        now = time()
        driver_statuses = tuple(x.get_charger_data()[MEASUREMENT_STATUS] for x in self.__chargers)
        status = merge_driver_statuses(driver_statuses)

        if (status != self.__last_status) or ((now - self.__last_status_tx) > 270):
            run_callbacks(self.__summary_callbacks, {MEASUREMENT_STATUS: status})
            self.__last_status = status
            self.__last_status_tx = now

    def __on_device_data(self, sender, data):
        if MEASUREMENT_STATUS in data:
            self.__commands.append(self.__get_status)
        if MEASUREMENT_ENERGY in data:
            run_callbacks(self.__summary_callbacks, {MEASUREMENT_ENERGY: data[MEASUREMENT_ENERGY]})
