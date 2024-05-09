from asyncio import create_task, Event
from collections import deque
from micropython import const
from sys import print_exception
from ..core.backendmqtt import Mqtt
from ..core.types import CommandBundle, MODE_CHARGE, MODE_DISCHARGE, MODE_IDLE, MODE_PROTECT, TYPE_CHARGER, TYPE_INVERTER, TYPE_SOLAR
from .inverter import Inverter
from .charger import Charger
from .solar import Solar

_MODESWITCHER_LOG_NAME = const('modeswitcher')

class ModeSwitcher:
    def __init__(self, config: dict, mqtt: Mqtt, inverter: Inverter, charger: Charger, solar: Solar):
        from ..core.singletons import Singletons
        #config = config['modeswitcher']
        self.__commands = deque((), 10)
        self.__task = None
        self.__event = Event()

        self.__trace = Singletons.log.trace
        self.__log = Singletons.log.create_logger(_MODESWITCHER_LOG_NAME)
        self.__display = Singletons.display
        self.__leds = Singletons.leds

        self.__inverter = inverter
        self.__charger = charger
        self.__solar = solar

        self.__locked_devices = set()

        self.__mqtt = mqtt
        self.__mqtt.on_mode.add(self.__on_mode)
    
        self.__requested_mode = MODE_IDLE
        self.__current_modes = (MODE_PROTECT, MODE_PROTECT, MODE_PROTECT)
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
                print_exception(e, self.__trace)

    def update_locked_devices(self, devices: set):
        if devices == self.__locked_devices:
            return
        self.__locked_devices.clear()
        self.__locked_devices.update(devices)
        self.__leds.switch_charger_locked(TYPE_CHARGER in self.__locked_devices)
        self.__leds.switch_inverter_locked(TYPE_INVERTER in self.__locked_devices)
        self.__leds.switch_solar_locked(TYPE_SOLAR in self.__locked_devices)
        self.__commands.append(CommandBundle(self.__update, (None,)))
        self.__event.set()

    async def __try_set_mode(self, mode: str):
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

    def __get_effective_mode(self, mode: str):
        charger_mode = MODE_PROTECT if TYPE_CHARGER in self.__locked_devices else mode
        inverter_mode = MODE_PROTECT if TYPE_INVERTER in self.__locked_devices else mode
        solar_mode = MODE_PROTECT if TYPE_SOLAR in self.__locked_devices else mode

        return charger_mode, inverter_mode, solar_mode
    
    def __get_displayed_mode(self, modes):
        charger_mode, inverter_mode, solar_mode = modes
        if inverter_mode == MODE_DISCHARGE:
            return MODE_DISCHARGE
        if charger_mode == MODE_CHARGE:
            return MODE_CHARGE
        if solar_mode == MODE_IDLE:
            return MODE_IDLE
        return MODE_PROTECT

    async def __switch_charger(self, mode: str):
        self.__log.info(f'Switching charger to mode {mode}.')
        await self.__charger.set_mode(mode)

    async def __switch_solar(self, mode: str):
        self.__log.info(f'Switching solar to mode {mode}.')
        await self.__solar.set_mode(mode)
            
    async def __switch_inverter(self, mode: str):
        self.__log.info(f'Switching inverter to mode {mode}.')
        await self.__inverter.set_mode(mode)

    def __on_mode(self, mode):
        self.__commands.append(CommandBundle(self.__try_set_mode, (mode,)))
        self.__event.set()
