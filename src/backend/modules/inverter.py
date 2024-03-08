import asyncio
from collections import deque
from ..drivers.opendtu import *
from ..core.commandbundle import CommandBundle
from ..core.types import OperationMode, operationmode, CallbackCollection, devicetype
from ..core.logging import *
from ..core.backendmqtt import Mqtt
from ..core.display import display
from .devices import Devices
from .netzero import *

class Inverter:
    def __init__(self, config: dict, devices: Devices, mqtt: Mqtt):
        self.__lock = asyncio.Lock()
        self.__commands = deque((), 10)

        self.__mqtt = mqtt
        self.__mqtt.on_live_consumption.add(self.__on_live_consumption)

        self.__state = None
        self.__netzero = NetZero(config)
        self.__on_energy = CallbackCollection()

        self.__inverters = []
        for device in devices.devices:
            if devicetype.inverter not in device.device_types:
                continue
            self.__inverters.append(device)

        self.__set_next_energy_execution()


    async def run(self):
        while True:
            try:
                now = time.time()
                async with self.__lock:
                    while len(self.__commands) > 0:
                        await self.__commands.popleft().run()
                    for inverter in self.__inverters:
                        await inverter.tick()
                    if now >= self.__next_energy_execution:
                        await self.__get_energy()
                        self.__set_next_energy_execution()
            except Exception as e:
                log.error(f'Inverter cycle failed: {e}')
            await asyncio.sleep(0.1)

    
    async def is_on(self, cached=False):
        async with self.__lock:
            return await self.__is_on(cached=cached)


    async def set_mode(self, mode: OperationMode):
        async with self.__lock:
            if len(self.__inverters) == 0:
                return False
            on = mode == operationmode.discharge
            await self.__set_power(0)
            for inverter in self.__inverters:
                await inverter.switch_inverter(on)
            state_confirmed, state = await self.__confirm_state(on)
            if not state_confirmed:
                log.alert(f'Not all inverters are confirmed in new state on={on}.')
            self.__netzero.clear()
            if state != True:
                display.update_inverter_power(0)
            self.__mqtt.send_inverter_state(state)
            return state
        

    @property
    def on_energy(self):
        return self.__on_energy


    async def __update_netzero(self, timestamp, consumption):
        display.update_consumption(consumption)
        if await self.__is_on(cached=True) != True:
            return
        self.__netzero.evaluate(timestamp, consumption)
        if self.__netzero.delta != 0:
            await self.__change_power(self.__netzero.delta)


    async def __change_power(self, delta):
        current_power = 0
        for inverter in self.__inverters:
            current_power += await inverter.get_inverter_power()
        await self.__set_power(current_power + delta)


    async def __set_power(self, power):
        power_per_inverter = power // len(self.__inverters)
        last_inverter = self.__inverters[-1]
        actual_power = 0
        power_changed = False
        for inverter in self.__inverters:
            new_power, inverter_delta = await inverter.set_inverter_power((power - actual_power) if inverter is last_inverter else power_per_inverter)
            if inverter_delta != 0:
                self.__netzero.clear()
                power_changed = True
            actual_power += new_power
        if power_changed:
            display.update_inverter_power(actual_power)
            self.__mqtt.send_inverter_power(actual_power)


    async def __confirm_state(self, on, retries=15):
        for _ in range(retries):
            is_on = await self.__is_on()
            if on == is_on:
                return True, is_on
            await asyncio.sleep(2.0)
        else:
            return False, is_on
        
    
    async def __is_on(self, cached=False):
        if cached:
            return self.__state
        if len(self.__inverters) == 0:
            self.__state = False
        else:
            self.__state = None
            for inverter in self.__inverters:
                is_on = await inverter.is_inverter_on()
                if is_on is None or (self.__state is not None and is_on != self.__state):
                    self.__state = None
                    break
                self.__state = is_on
        return self.__state
    

    async def __get_energy(self):
        energy = 0.0
        for inverter in self.__inverters:
            inverter_energy = await inverter.get_inverter_energy()
            if inverter_energy is not None:
                energy += inverter_energy
        self.__on_energy.run_all(round(energy))
    

    def __set_next_energy_execution(self):
        now = time.localtime()
        now_seconds = time.time()
        minutes = now[4]
        seconds = now[5]
        extra_seconds = (minutes % 15) * 60 + seconds
        seconds_to_add = (15 * 60) - extra_seconds
        self.__next_energy_execution = now_seconds + seconds_to_add


    def __on_live_consumption(self, power):
        self.__commands.append(CommandBundle(self.__update_netzero, (time.time(), power)))
