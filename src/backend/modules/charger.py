from asyncio import Event, Lock, TimeoutError, wait_for
from micropython import const
from sys import print_exception
from time import time
from ..core.devicetools import get_energy_execution_timestamp, merge_driver_statuses
from ..core.types import CommandFiFo, MODE_CHARGE, run_callbacks, STATUS_ON, STATUS_OFF, STATUS_SYNCING
from .devices import Devices

_CHARGER_LOG_NAME = const('charger')

class Charger:
    def __init__(self, config: dict, devices: Devices):
        from ..core.singletons import Singletons
        self.__lock = Lock()
        self.__commands = CommandFiFo()

        self.__log = Singletons.log.create_logger(_CHARGER_LOG_NAME)

        self.__last_status = None

        self.__on_energy = list()
        self.__on_status = list()

        from ..core.types import TYPE_CHARGER
        self.__chargers = devices.get_by_type(TYPE_CHARGER)
        for device in self.__chargers:
            device.on_charger_status_change.append(self.__on_charger_status)

        if len(self.__chargers) == 0:
            self.__last_status = STATUS_OFF

        self.__next_energy_execution = get_energy_execution_timestamp()

    async def run(self):
        while True:
            try:
                now = time()
                async with self.__lock:
                    while not self.__commands.empty:
                        await self.__commands.popleft()()
                    if now >= self.__next_energy_execution:
                        await self.__get_energy()
                        self.__next_energy_execution = get_energy_execution_timestamp()
            except Exception as e:
                self.__log.error('Charger cycle failed: ', e)
                from ..core.singletons import Singletons
                print_exception(e, Singletons.log.trace)
            try:
                await wait_for(self.__commands.wait_and_clear(), timeout=1)
            except TimeoutError:
                pass

    def get_status(self):
        return self.__last_status if self.__last_status is not None else STATUS_SYNCING

    async def set_mode(self, mode: str):
        async with self.__lock:
            shall_on = mode == MODE_CHARGE
            for charger in self.__chargers:
                await charger.switch_charger(shall_on)

    @property
    def on_energy(self):
        return self.__on_energy
    
    @property
    def on_status(self):
        return self.__on_status

    async def __get_status(self):
        driver_statuses = tuple(x.get_charger_status() for x in self.__chargers)
        status = merge_driver_statuses(driver_statuses)

        if status != self.__last_status:
            run_callbacks(self.__on_status, status)
            self.__last_status = status

    async def __get_energy(self):
        energy = 0.0
        for charger in self.__chargers:
            charger_energy = await charger.get_charger_energy()
            if charger_energy is not None:
                energy += charger_energy
        run_callbacks(self.__on_energy, round(energy))

    def __on_charger_status(self, status):
        self.__commands.append(self.__get_status)
