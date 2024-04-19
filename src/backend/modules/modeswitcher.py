import asyncio, sys
from collections import deque
from ..core.types import CommandBundle, devicetype, OperationMode, operationmode
from ..core.logging import log
from ..core.backendmqtt import Mqtt
from ..core.display import display
from .inverter import Inverter
from .charger import Charger


class ModeSwitcher:
    def __init__(self, config: dict, mqtt: Mqtt, inverter: Inverter, charger: Charger):
        #config = config['modeswitcher']
        self.__commands = deque((), 10)
        self.__task = None
        self.__event = asyncio.Event()

        self.__inverter = inverter
        self.__charger = charger

        self.__locked_devices = set()

        self.__mqtt = mqtt
        self.__mqtt.on_mode.add(self.__on_mode)
    
        self.__requested_mode = operationmode.idle
        self.__operation_mode = operationmode.idle

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
        self.__commands.append(CommandBundle(self.__update, ()))
        self.__event.set()

    async def __try_set_mode(self, mode: OperationMode):
        self.__requested_mode = mode
        effective_mode, solar_on = self.__get_effective_mode(mode)
        if effective_mode != mode:
            log.modeswitch(f'Switch to mode {mode.name} suppressed.')
            # TODO send mode
            return
        await self.__update(effective_mode, solar_on)

    async def __update(self, mode = None, solar_on = True):
        if mode is None:
            mode, solar_on = self.__get_effective_mode(self.__requested_mode)
        if mode == self.__operation_mode:
            return
        self.__operation_mode = mode
        await self.__switch_charger(mode)
        await self.__switch_solar(solar_on)
        await self.__switch_inverter(mode)
        display.update_mode(mode)

    def __get_effective_mode(self, mode: OperationMode):
        effective_mode = operationmode.idle
        if mode == operationmode.charge:
            effective_mode = operationmode.idle if devicetype.charger in self.__locked_devices else mode
        elif mode == operationmode.discharge:
            effective_mode = operationmode.idle if devicetype.inverter in self.__locked_devices else mode
        else:
            effective_mode = operationmode.idle

        return effective_mode, bool(devicetype.solar in self.__locked_devices)

    async def __switch_charger(self, mode: OperationMode):
        log.modeswitch(f'Switching charger to mode {mode}.')
        await self.__charger.set_mode(mode)

    async def __switch_solar(self, on: bool):
        pass
            
    async def __switch_inverter(self, mode: OperationMode):
        log.modeswitch(f'Switching inverter to mode {mode}.')
        await self.__inverter.set_mode(mode)

    def __on_mode(self, mode):
        self.__commands.append(CommandBundle(self.__try_set_mode, (mode,)))
        self.__event.set()
