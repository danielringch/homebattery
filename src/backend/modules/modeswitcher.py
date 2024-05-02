import asyncio, sys
from collections import deque
from ..core.types import CommandBundle, devicetype, OperationMode, operationmode
from ..core.logging import log
from ..core.backendmqtt import Mqtt
from ..core.display import display
from ..core.leds import leds
from .inverter import Inverter
from .charger import Charger
from .solar import Solar


class ModeSwitcher:
    def __init__(self, config: dict, mqtt: Mqtt, inverter: Inverter, charger: Charger, solar: Solar):
        #config = config['modeswitcher']
        self.__commands = deque((), 10)
        self.__task = None
        self.__event = asyncio.Event()

        self.__inverter = inverter
        self.__charger = charger
        self.__solar = solar

        self.__locked_devices = set()

        self.__mqtt = mqtt
        self.__mqtt.on_mode.add(self.__on_mode)
    
        self.__requested_mode = operationmode.idle
        self.__current_modes = (operationmode.protect, operationmode.protect, operationmode.protect)

    def run(self):
        self.__task = asyncio.create_task(self.__run())

    async def __run(self):
        while True:
            await self.__event.wait()
            self.__event.clear()
            #await asyncio.sleep(0.1)
            try:
                while len(self.__commands) > 0:
                    await self.__commands.popleft().run()
            except Exception as e:
                log.error(f'ModeSwitcher cycle failed: {e}')
                sys.print_exception(e, log.trace)

    def update_locked_devices(self, devices: set):
        if devices == self.__locked_devices:
            return
        self.__locked_devices.clear()
        self.__locked_devices.update(devices)
        leds.switch_charger_locked(devicetype.charger in self.__locked_devices)
        leds.switch_inverter_locked(devicetype.inverter in self.__locked_devices)
        leds.switch_solar_locked(devicetype.solar in self.__locked_devices)
        self.__commands.append(CommandBundle(self.__update, (None,)))
        self.__event.set()

    async def __try_set_mode(self, mode: OperationMode):
        self.__requested_mode = mode
        effective_modes = self.__get_effective_mode(mode)
        await self.__update(effective_modes)

    async def __update(self, modes):
        if modes is None:
            modes = self.__get_effective_mode(self.__requested_mode)
        if modes == self.__current_modes:
            return
        self.__current_modes = modes
        await self.__switch_charger(modes[0])
        await self.__switch_inverter(modes[1])
        await self.__switch_solar(modes[2])
        display.update_mode(self.__get_displayed_mode(modes))

    def __get_effective_mode(self, mode: OperationMode):
        charger_mode = operationmode.protect if devicetype.charger in self.__locked_devices else mode
        inverter_mode = operationmode.protect if devicetype.inverter in self.__locked_devices else mode
        solar_mode = operationmode.protect if devicetype.solar in self.__locked_devices else mode

        return charger_mode, inverter_mode, solar_mode
    
    def __get_displayed_mode(self, modes):
        charger_mode, inverter_mode, solar_mode = modes
        if inverter_mode == operationmode.discharge:
            return operationmode.discharge
        if charger_mode == operationmode.charge:
            return operationmode.charge
        if solar_mode == operationmode.idle:
            return operationmode.idle
        return operationmode.protect

    async def __switch_charger(self, mode: OperationMode):
        log.modeswitch(f'Switching charger to mode {mode}.')
        await self.__charger.set_mode(mode)

    async def __switch_solar(self, mode: OperationMode):
        log.modeswitch(f'Switching solar to mode {mode}.')
        await self.__solar.set_mode(mode)
            
    async def __switch_inverter(self, mode: OperationMode):
        log.modeswitch(f'Switching inverter to mode {mode}.')
        await self.__inverter.set_mode(mode)

    def __on_mode(self, mode):
        self.__commands.append(CommandBundle(self.__try_set_mode, (mode,)))
        self.__event.set()
