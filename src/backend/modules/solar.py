import asyncio, time
from ..drivers.shelly import *
from ..core.types import OperationMode, operationmode, CallbackCollection, devicetype
from ..core.logging import *
from .devices import Devices

class Solar:
    def __init__(self, config: dict, devices: Devices,):
        self.__lock = asyncio.Lock()

        self.__on_energy = CallbackCollection()

        self.__devices = []
        for device in devices.devices:
            if devicetype.solar not in device.device_types:
                continue
            self.__devices.append(device)

        self.__set_next_energy_execution()

    async def run(self):
        while True:
            try:
                now = time.time()
                async with self.__lock:
                    for device in self.__devices:
                        await device.tick()
                    if now >= self.__next_energy_execution:
                        await self.__get_energy()
                        self.__set_next_energy_execution()
            except Exception as e:
                log.error(f'Solar cycle failed: {e}')
            await asyncio.sleep(0.1)

    async def is_on(self):
        return False

    async def set_mode(self, mode: OperationMode):
        async with self.__lock:
            pass

    @property
    def on_energy(self):
        return self.__on_energy

    async def __get_energy(self):
        energy = 0.0
        self.__on_energy.run_all(round(energy))

    def __set_next_energy_execution(self):
        now = time.localtime()
        now_seconds = time.time()
        minutes = now[4]
        seconds = now[5]
        extra_seconds = (minutes % 15) * 60 + seconds
        seconds_to_add = (15 * 60) - extra_seconds
        self.__next_energy_execution = now_seconds + seconds_to_add