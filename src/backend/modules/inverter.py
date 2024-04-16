import asyncio, sys
from collections import deque
from ..core.commandbundle import CommandBundle
from ..core.types import OperationMode, operationmode, CallbackCollection, devicetype, inverterstatus
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

        self.__netzero = NetZero(config)
        self.__on_energy = CallbackCollection()

        self.__last_status = None
        self.__last_power = None
        self.__inverters = []

        for device in devices.devices:
            if devicetype.inverter not in device.device_types:
                continue
            self.__inverters.append(device)
            device.on_inverter_status_change.add(self.__on_inverter_status)
            device.on_inverter_power_change.add(self.__on_inverter_power)

        self.__max_power = sum((x.max_power for x in self.__inverters), 0)

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
                log.error(f'Inverter cycle failed: {e}')
                sys.print_exception(e, log.trace)
            await asyncio.sleep(0.1)

    async def get_status(self):
        async with self.__lock:
            return self.__get_status()

    async def __get_status(self):
        status = None
        for inverter in self.__inverters:
            inverter_status = inverter.get_inverter_status()
            if inverter_status in (inverterstatus.on, inverterstatus.off):
                if status is None:
                    status = inverter_status
                elif status != inverter_status:
                    status = inverterstatus.syncing
            elif inverterstatus == inverterstatus.syncing:
                status = inverterstatus.syncing
            else:
                status = inverterstatus.fault
                break

        if status != self.__last_status :
            self.__commands.append(CommandBundle(self.__handle_state_change, (status,)))
            if status != inverterstatus.on:
                display.update_inverter_power(0)
                self.__netzero.clear()
            self.__mqtt.send_inverter_state(status == inverterstatus.on)
            self.__last_status = status
        return status

    async def set_mode(self, mode: OperationMode):
        async with self.__lock:
            shall_on = mode == operationmode.discharge
            shall_status = inverterstatus.on if shall_on else inverterstatus.off
            for inverter in self.__inverters:
                await inverter.switch_inverter(shall_on)
            actual_status = await self.__get_status()
            if actual_status == shall_status:
                # Operation mode requests must be answered, but since we are
                # already in target state, __get_status() will not send anything, so
                # we need to do it manually here.
                self.__mqtt.send_inverter_state(actual_status == inverterstatus.on)

    @property
    def on_energy(self):
        return self.__on_energy
    
    async def __handle_state_change(self, new_status):
        if new_status == inverterstatus.fault:
            # fault recovery has better chances if other inverters produce minimal power
            await self.__set_power(0)

    async def __update_netzero(self, timestamp, consumption):
        display.update_consumption(consumption)
        if len(self.__inverters) == 0:
            return
        status = await self.__get_status()
        power = await self.__get_power()
        if status != inverterstatus.on or power is None:
            return
        self.__netzero.evaluate(timestamp, consumption)
        if self.__netzero.delta != 0:
            await self.__set_power(power + self.__netzero.delta)


    async def __get_power(self):
        power = 0
        for inverter in self.__inverters:
            inverter_power = inverter.get_inverter_power()
            if inverter_power is None:
                return None
            power += inverter_power

        if power != self.__last_power:
            self.__netzero.clear()
            display.update_inverter_power(power)
            self.__mqtt.send_inverter_power(power)
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

    def __set_next_energy_execution(self):
        now = time.localtime()
        now_seconds = time.time()
        minutes = now[4]
        seconds = now[5]
        extra_seconds = (minutes % 15) * 60 + seconds
        seconds_to_add = (15 * 60) - extra_seconds
        self.__next_energy_execution = now_seconds + seconds_to_add

    def __on_inverter_status(self, status):
        self.__commands.append(CommandBundle(self.__get_status, ()))

    def __on_inverter_power(self, power):
        self.__commands.append(CommandBundle(self.__get_power, ()))

    def __on_live_consumption(self, power):
        self.__commands.append(CommandBundle(self.__update_netzero, (time.time(), power)))
