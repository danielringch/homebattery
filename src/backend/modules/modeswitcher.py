from asyncio import create_task, Event
from collections import deque
from sys import print_exception
from ..core.types import CommandBundle, OperationMode
from ..core.backendmqtt import Mqtt
from .inverter import Inverter
from .charger import Charger
from .solar import Solar

class ModeSwitcher:
    def __init__(self, config: dict, mqtt: Mqtt, inverter: Inverter, charger: Charger, solar: Solar):
        #config = config['modeswitcher']
        self.__commands = deque((), 10)
        self.__task = None
        self.__event = Event()

        from ..core.types_singletons import devicetype
        self.__devicetype = devicetype
        from ..core.types_singletons import operationmode
        self.__operationmode = operationmode
        from ..core.logging_singleton import log
        self.__log = log
        from ..core.userinterface_singleton import display
        self.__display = display
        from ..core.userinterface_singleton import leds
        self.__leds = leds

        self.__inverter = inverter
        self.__charger = charger
        self.__solar = solar

        self.__locked_devices = set()

        self.__mqtt = mqtt
        self.__mqtt.on_mode.add(self.__on_mode)
    
        self.__requested_mode = operationmode.idle
        self.__current_modes = (operationmode.protect, operationmode.protect, operationmode.protect)
        self.__displayed_mode = None

    def run(self):
        self.__task = create_task(self.__run())

    async def __run(self):
        while True:
            await self.__event.wait()
            self.__event.clear()
            #await asyncio.sleep(0.1)
            try:
                while len(self.__commands) > 0:
                    await self.__commands.popleft().run()
            except Exception as e:
                self.__log.error(f'ModeSwitcher cycle failed: {e}')
                print_exception(e, self.__log.trace)

    def update_locked_devices(self, devices: set):
        if devices == self.__locked_devices:
            return
        self.__locked_devices.clear()
        self.__locked_devices.update(devices)
        self.__leds.switch_charger_locked(self.__devicetype.charger in self.__locked_devices)
        self.__leds.switch_inverter_locked(self.__devicetype.inverter in self.__locked_devices)
        self.__leds.switch_solar_locked(self.__devicetype.solar in self.__locked_devices)
        self.__commands.append(CommandBundle(self.__update, (None,)))
        self.__event.set()

    async def __try_set_mode(self, mode: OperationMode):
        self.__requested_mode = mode
        self.__displayed_mode = None # force sending the mode over MQTT even if nothing changes
        effective_modes = self.__get_effective_mode(mode)
        await self.__update(effective_modes)

    async def __update(self, modes):
        if modes is None:
            modes = self.__get_effective_mode(self.__requested_mode)
        if modes != self.__current_modes:
            self.__current_modes = modes
            await self.__switch_charger(modes[0])
            await self.__switch_inverter(modes[1])
            await self.__switch_solar(modes[2])
        displayed_mode = self.__get_displayed_mode(modes)
        if displayed_mode != self.__displayed_mode:
            self.__displayed_mode = displayed_mode
            self.__display.update_mode(self.__displayed_mode)
            await self.__mqtt.send_mode(self.__displayed_mode)

    def __get_effective_mode(self, mode: OperationMode):
        charger_mode = self.__operationmode.protect if self.__devicetype.charger in self.__locked_devices else mode
        inverter_mode = self.__operationmode.protect if self.__devicetype.inverter in self.__locked_devices else mode
        solar_mode = self.__operationmode.protect if self.__devicetype.solar in self.__locked_devices else mode

        return charger_mode, inverter_mode, solar_mode
    
    def __get_displayed_mode(self, modes):
        charger_mode, inverter_mode, solar_mode = modes
        if inverter_mode == self.__operationmode.discharge:
            return self.__operationmode.discharge
        if charger_mode == self.__operationmode.charge:
            return self.__operationmode.charge
        if solar_mode == self.__operationmode.idle:
            return self.__operationmode.idle
        return self.__operationmode.protect

    async def __switch_charger(self, mode: OperationMode):
        self.__log.modeswitch(f'Switching charger to mode {mode}.')
        await self.__charger.set_mode(mode)

    async def __switch_solar(self, mode: OperationMode):
        self.__log.modeswitch(f'Switching solar to mode {mode}.')
        await self.__solar.set_mode(mode)
            
    async def __switch_inverter(self, mode: OperationMode):
        self.__log.modeswitch(f'Switching inverter to mode {mode}.')
        await self.__inverter.set_mode(mode)

    def __on_mode(self, mode):
        self.__commands.append(CommandBundle(self.__try_set_mode, (mode,)))
        self.__event.set()
