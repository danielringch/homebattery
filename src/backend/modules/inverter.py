import asyncio, sys
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

        self.__operation_mode = operationmode.idle
        self.__netzero = NetZero(config)
        self.__on_energy = CallbackCollection()

        self.__inverter = None

        for device in devices.devices:
            if devicetype.inverter not in device.device_types:
                continue
            if self.__inverter is not None:
                log.inverter(f'Only one inverter drive at once is supported, ignoring additional drivers.')
            else:
                self.__inverter = device
                self.__inverter.on_inverter_status_change.add(self.__on_inverter_status)
        if self.__inverter is None:
            log.inverter(f'No inverter driver present.')

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

    async def is_on(self):
        async with self.__lock:
            if self.__inverter is None:
                return False
            return await self.__inverter.is_inverter_on()

    async def set_mode(self, mode: OperationMode):
        async with self.__lock:
            self.__operation_mode = mode
            if self.__inverter is None:
                return False
            on = mode == operationmode.discharge
            await self.__inverter.switch_inverter(on)
            if await self.__inverter.is_inverter_on() == on:
                # if not synced yet, it will be sent later via __on_inverter_status
                self.__mqtt.send_inverter_state(on)
        
    @property
    def on_energy(self):
        return self.__on_energy

    async def __update_netzero(self, timestamp, consumption):
        display.update_consumption(consumption)
        if self.__inverter is None:
            return
        state = await self.__inverter.is_inverter_on()
        if self.__operation_mode != operationmode.discharge or state in (False, None):
            self.__netzero.clear()
            return
        self.__netzero.evaluate(timestamp, consumption)
        if self.__netzero.delta != 0:
            current_power = await self.__inverter.get_inverter_power()
            await self.__set_power(current_power + self.__netzero.delta)

    async def __set_power(self, power):
        if self.__inverter is not None:
            actual_power, power_delta = await self.__inverter.set_inverter_power(power)
            if power_delta != 0:
                self.__netzero.clear()
                display.update_inverter_power(actual_power)
                self.__mqtt.send_inverter_power(actual_power)

    async def __get_energy(self):
        energy = 0.0
        if self.__inverter is not None:
            energy = self.__inverter.get_inverter_energy()
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
        if status != True:
            display.update_inverter_power(0)
        self.__mqtt.send_inverter_state(status)

    def __on_live_consumption(self, power):
        self.__commands.append(CommandBundle(self.__update_netzero, (time.time(), power)))
