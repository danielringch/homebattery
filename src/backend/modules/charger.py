import asyncio, sys, time
from collections import deque
from ..core.types import CommandBundle, OperationMode, CallbackCollection
from ..core.types_singletons import bool2on, operationmode, devicetype
from ..core.logging_singleton import log
from ..core.backendmqtt import Mqtt
from .devices import Devices

class Charger:
    def __init__(self, config: dict, devices: Devices, mqtt: Mqtt):
        self.__lock = asyncio.Lock()
        self.__commands = deque((), 10)
        self.__mqtt = mqtt

        self.__last_state = None

        self.__on_energy = CallbackCollection()

        self.__chargers = []
        for device in devices.devices:
            if devicetype.charger not in device.device_types:
                continue
            self.__chargers.append(device)
            device.on_charger_status_change.add(self.__on_charger_status)

        self.__set_next_energy_execution()

    async def run(self):
        while True:
            try:
                now = time.time()
                async with self.__lock:
                    while len(self.__commands) > 0:
                        await self.__commands.popleft().run()
                    if now >= self.__next_energy_execution:
                        await self.__get_energy()
                        self.__set_next_energy_execution()
            except Exception as e:
                log.error(f'Charger cycle failed: {e}')
                sys.print_exception(e, log.trace)
            await asyncio.sleep(0.1)

    async def is_on(self):
        async with self.__lock:
            return await self.__get_state()

    async def set_mode(self, mode: OperationMode):
        async with self.__lock:
            shall_on = mode == operationmode.charge
            if shall_on == self.__last_state:
                # mode request must be answered
                self.__mqtt.send_charger_state(self.__last_state)
            for charger in self.__chargers:
                await charger.switch_charger(shall_on)

    @property
    def on_energy(self):
        return self.__on_energy

    async def __get_state(self):
        if len(self.__chargers) == 0:
            return False
        mode = None
        for charger in self.__chargers:
            on = charger.get_charger_status()
            if on is None:
                mode = None
                break
            if mode is None:
                mode = on
            elif on != mode:
                mode = None
                break
        if self.__last_state != on:
            self.__mqtt.send_charger_state(on)
            self.__last_state = on
        return on

    async def __get_energy(self):
        energy = 0.0
        for charger in self.__chargers:
            charger_energy = await charger.get_charger_energy()
            if charger_energy is not None:
                energy += charger_energy
        self.__on_energy.run_all(round(energy))

    def __set_next_energy_execution(self):
        now = time.localtime()
        now_seconds = time.time()
        minutes = now[4]
        seconds = now[5]
        extra_seconds = (minutes % 15) * 60 + seconds
        seconds_to_add = (15 * 60) - extra_seconds
        self.__next_energy_execution = now_seconds + seconds_to_add

    def __on_charger_status(self, status):
        self.__commands.append(CommandBundle(self.__get_state, ()))
