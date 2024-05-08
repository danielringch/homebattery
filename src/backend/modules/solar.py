from asyncio import Lock, sleep
from collections import deque
from sys import print_exception
from time import localtime, time
from ..core.backendmqtt import Mqtt
from ..core.types import OperationMode, CallbackCollection, CommandBundle
from .devices import Devices

class Solar:
    def __init__(self, config: dict, devices: Devices, mqtt: Mqtt):
        self.__lock = Lock()
        self.__commands = deque((), 10)

        self.__mqtt = mqtt

        from ..core.userinterface_singleton import display
        self.__display = display
        from ..core.types_singletons import operationmode
        self.__mode_protect = operationmode.protect
        from ..core.logging_singleton import log
        self.__log = log

        self.__on_energy = CallbackCollection()

        from ..core.types_singletons import devicetype
        self.__devices = []
        for device in devices.devices:
            if devicetype.solar not in device.device_types:
                continue
            self.__devices.append(device)
            device.on_solar_status_change.add(self.__on_status_change)
            device.on_solar_power_change.add(self.__on_power_change)

        self.__last_status = None
        self.__last_power = None

        self.__set_next_energy_execution()

    async def run(self):
        while True:
            try:
                now = time()
                async with self.__lock:
                    while len(self.__commands) > 0:
                        await self.__commands.popleft().run()
                    if now >= self.__next_energy_execution:
                        await self.__get_energy()
                        self.__set_next_energy_execution()
            except Exception as e:
                self.__log.error(f'Solar cycle failed: {e}')
                print_exception(e, self.__log.trace)
            await sleep(0.1)

    async def is_on(self):
        async with self.__lock:
            return self.__last_status

    async def set_mode(self, mode: OperationMode):
        async with self.__lock:
            on = mode != self.__mode_protect
            is_on = self.__get_status()
            if is_on != on:
                for device in self.__devices:
                    await device.switch_solar(on)
            else:
                await self.__mqtt.send_solar_state(is_on)

    @property
    def on_energy(self):
        return self.__on_energy
    
    async def __get_status(self):
        combined_status = None
        states = tuple(x.get_solar_status() for x in self.__devices)
        if True not in states: # also fallback for no solar
            combined_status = False
        elif False not in states:
            combined_status = True

        if combined_status != self.__last_status:
            await self.__mqtt.send_solar_state(combined_status)
            self.__last_status = combined_status

    async def __get_power(self):
        power = sum(x.get_solar_power() for x in self.__devices, 0)

        if power != self.__last_power:
            self.__display.update_solar_power(power)
            self.__last_power = power

    async def __get_energy(self):
        energy = 0.0
        for device in self.__devices:
            device_energy = await device.get_solar_energy()
            if device_energy is not None:
                energy += device_energy
        self.__on_energy.run_all(round(energy))

    def __set_next_energy_execution(self):
        now = localtime()
        now_seconds = time()
        minutes = now[4]
        seconds = now[5]
        extra_seconds = (minutes % 15) * 60 + seconds
        seconds_to_add = (15 * 60) - extra_seconds
        self.__next_energy_execution = now_seconds + seconds_to_add

    def __on_status_change(self, _):
        self.__commands.append(CommandBundle(self.__get_status, ()))

    def __on_power_change(self, _):
        self.__commands.append(CommandBundle(self.__get_power, ()))