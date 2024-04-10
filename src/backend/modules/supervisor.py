import asyncio, sys, time
from collections import deque
from machine import WDT
from ..core.commandbundle import CommandBundle
from ..core.types import EnumEntry, OperationMode, operationmode, CallbackCollection
from ..core.logging import *
from ..core.backendmqtt import Mqtt
from ..core.display import display
from ..core.leds import leds
from .inverter import Inverter
from .charger import Charger
from .battery import Battery
from .netzero import *


class Supervisor:
    class LockedReason(EnumEntry):
        def __init__(self, name, message, priority, blocks_charge, blocks_solar, blocks_inverter):
            super().__init__(name, None)
            self.message = message
            self.priority = priority
            self.blocks_charge = blocks_charge
            self.blocks_solar = blocks_solar
            self.blocks_inverter = blocks_inverter

        def __lt__(self, other):
            return self.priority < other.priority
        
    class LockedReasons():
        def __init__(self):
            self.battery_data = Supervisor.LockedReason(
                    name='battery_data', 
                    message='Battery data lost.', 
                    priority=30,
                    blocks_charge=True,
                    blocks_solar=True,
                    blocks_inverter=True)
            self.cell_high = Supervisor.LockedReason(
                    name='cell_high',
                    message='Battery cell voltage high.',
                    priority=31,
                    blocks_charge=True,
                    blocks_solar=True,
                    blocks_inverter=False)
            self.cell_low = Supervisor.LockedReason(
                    name='cell_low',
                    message='Battery cell voltage low.',
                    priority=32,
                    blocks_charge=False,
                    blocks_solar=False,
                    blocks_inverter=True)
            self.internal = Supervisor.LockedReason(
                    name='internal',
                    message='Internal supervisor error.',
                    priority=0,
                    blocks_charge=True,
                    blocks_solar=True,
                    blocks_inverter=True)
            self.live_data = Supervisor.LockedReason(
                    name='live_data',
                    message='Live data lost.',
                    priority=10,
                    blocks_charge=True,
                    blocks_solar=False,
                    blocks_inverter=True)
            self.mqtt = Supervisor.LockedReason(
                    name='mqtt',
                    message='MQTT connection lost.',
                    priority=5,
                    blocks_charge=True,
                    blocks_solar=False,
                    blocks_inverter=True)
            self.startup = Supervisor.LockedReason(
                    name='startup',
                    message='System startup.',
                    priority=2,
                    blocks_charge=True,
                    blocks_solar=True,
                    blocks_inverter=True)

    def __init__(self, config: dict, watchdog: WDT, mqtt: Mqtt, inverter: Inverter, charger: Charger, battery: Battery):
        self.__locked_reasons = self.LockedReasons()

        self.__commands = deque((), 10)

        self.__on_cycle_finished = CallbackCollection()

        self.__watchdog = watchdog
        self.__inverter = inverter
        self.__charger = charger
        self.__battery = battery

        self.__battery.on_battery_data.add(self.__on_battery_data)

        self.__mqtt = mqtt
        self.__mqtt.on_mode.add(self.__on_mode)
        self.__mqtt.on_live_consumption.add(self.__on_live_consumption)

        self.__check_interval = int(config['supervisor']['check_interval'])
        self.__next_check = 0

        self.__mature_timestamp = time.time() + 60

        self.__live_data_timestamp = time.time()
        self.__live_data_tolerance = int(config['supervisor']['live_data_tolerance'])

        self.__battery_data_timestamp = time.time()
        self.__battery_data_tolerance = int(config['supervisor']['battery_data_tolerance'])
        self.__minimum_cell_voltage = float(config['supervisor']['minimum_cell_voltage'])
        self.__minimum_cell_voltage_hysteresis = float(config['supervisor']['minimum_cell_voltage_hysteresis'])
        self.__maximum_cell_voltage = float(config['supervisor']['maximum_cell_voltage'])
        self.__maximum_cell_voltage_hysteresis = float(config['supervisor']['maximum_cell_voltage_hysteresis'])

        self.__requested_mode = operationmode.idle
        self.__operation_mode = operationmode.idle
        self.__locks = set()
        self.__locks.add(self.__locked_reasons.startup)
        self.__unhealty = False

        self.__health_check_passed = time.time()

    async def run(self):
        self.__watchdog_task = asyncio.create_task(self.__run_watchdog())
        while True:
            try:
                while len(self.__commands) > 0:
                    await self.__commands.popleft().run()
                self.__on_cycle_finished.run_all()
            except Exception as e:
                log.error(f'Supervisor cycle failed: {e}')
                sys.print_exception(e, log.trace)
            await asyncio.sleep(0.1)

    @property
    def on_cycle_finished(self):
        return self.__on_cycle_finished
    
    async def __run_watchdog(self):
        while True:
            try:
                self.__tick()
            except Exception as e:
                log.error(f'Supervisor check failed: {e}')
                sys.print_exception(e, log.trace)
            
            deadline = 3 * self.__check_interval
            now = time.time()
            if self.__health_check_passed + deadline > now:
                self.__watchdog.feed()
                leds.notify_watchdog()
            await asyncio.sleep(0.5)

    async def __try_set_mode(self, mode: OperationMode):
        self.__requested_mode = mode
        effective_mode, solar_on = self.__get_effective_mode(mode)
        if effective_mode != mode:
            log.supervisor(f'Switch to mode {mode.name} suppressed.')
            if len(self.__locks) > 0:
                self.__mqtt.send_locked(sorted(self.__locks)[0].message)
            return
        await self.__set_mode(effective_mode, solar_on)

    async def __set_mode(self, mode: OperationMode, solar_on: bool):
        self.__operation_mode = mode
        await self.__switch_charger(mode)
        await self.__switch_solar(solar_on)
        await self.__switch_inverter(mode)
        display.update_mode(mode)

    def __get_effective_mode(self, mode: OperationMode):
        solar_on = not any(x.blocks_solar for x in self.__locks)
        effective_mode = operationmode.idle
        if mode in (operationmode.charge, operationmode.quickcharge):
            effective_mode = operationmode.idle if any(x.blocks_charge for x in self.__locks) else mode
        elif mode == operationmode.discharge:
            effective_mode = operationmode.idle if any(x.blocks_inverter for x in self.__locks) else mode
        else:
            effective_mode = operationmode.idle

        return effective_mode, solar_on

    async def __switch_charger(self, mode: OperationMode):
        log.supervisor(f'Switching charger to mode {mode}.')
        await self.__charger.set_mode(mode)

    async def __switch_solar(self, on: bool):
        pass
            
    async def __switch_inverter(self, mode: OperationMode):
        log.supervisor(f'Switching inverter to mode {mode}.')
        await self.__inverter.set_mode(mode)

    def __tick(self):
        now = time.time()
        if now < self.__next_check:
            return
        self.__set_next_check(now)

        previous_locked = sorted(self.__locks)[0] if len(self.__locks) else None

        self.__unhealty = False

        try:
            self.__check_battery_online(now)
            self.__check_battery_min_voltage()
            self.__check_battery_max_voltage()
            self.__check_live_data(now)
            self.__check_mqtt_connected()
            self.__check_startup(now)

        except Exception as e:
            log.supervisor(f'Cycle failed: {e}')
            self.__locks.add(self.__locked_reasons.internal)

        for lock in self.__locks:
            log.supervisor(f'System lock: {lock.message}')

        top_priority_lock = sorted(self.__locks)[0] if len(self.__locks) else None

        if previous_locked != top_priority_lock:
            self.__mqtt.send_locked(top_priority_lock.message if top_priority_lock is not None else None)
            display.update_lock(top_priority_lock.name if top_priority_lock is not None else None)

        effective_mode, effective_solar = self.__get_effective_mode(self.__requested_mode)
        #TODO: handle solar
        if effective_mode != self.__operation_mode:
            self.__commands.append(CommandBundle(self.__set_mode, (effective_mode, effective_solar)))

        if not self.__unhealty:
            self.__health_check_passed = now

    def __check_battery_online(self, now):
        if (now - self.__battery_data_timestamp) > self.__battery_data_tolerance:
            self.__locks.add(self.__locked_reasons.battery_data)
        else:
            self.__clear_lock(self.__locked_reasons.battery_data)

    def __check_battery_min_voltage(self):
        battery_data = self.__battery.data
        if battery_data is None or battery_data.min_cell_voltage is None:
            return

        treshold = self.__minimum_cell_voltage
        if self.__locked_reasons.cell_low in self.__locks:
            treshold += self.__minimum_cell_voltage_hysteresis

        if battery_data.min_cell_voltage < treshold:
            self.__locks.add(self.__locked_reasons.cell_low)
        else:
            self.__clear_lock(self.__locked_reasons.cell_low)

    def __check_battery_max_voltage(self):
        battery_data = self.__battery.data
        if battery_data is None or battery_data.max_cell_voltage is None:
            return

        treshold = self.__maximum_cell_voltage
        if self.__locked_reasons.cell_high in self.__locks:
            treshold += self.__maximum_cell_voltage_hysteresis

        if battery_data.max_cell_voltage > treshold:
            self.__locks.add(self.__locked_reasons.cell_high)
        else:
            self.__clear_lock(self.__locked_reasons.cell_high)

    def __check_live_data(self, now):
        if (now - self.__live_data_timestamp) > self.__live_data_tolerance:
            self.__locks.add(self.__locked_reasons.live_data)
        else:
            self.__clear_lock(self.__locked_reasons.live_data)

    def __check_mqtt_connected(self):
        if not self.__mqtt.connected:
            self.__locks.add(self.__locked_reasons.mqtt)
            self.__unhealty = True
        else:
            self.__clear_lock(self.__locked_reasons.mqtt)

    def __check_startup(self, now):
        if len(self.__locks) == 0:
            return
        if len(self.__locks) == 1 and self.__locked_reasons.startup in self.__locks:
            self.__clear_lock(self.__locked_reasons.startup)
            return
        if now > self.__mature_timestamp:
            self.__clear_lock(self.__locked_reasons.startup)

    def __clear_lock(self, lock):
        try:
            self.__locks.remove(lock)
        except KeyError:
            pass

    def __set_next_check(self, now):
        self.__next_check = now + self.__check_interval

    def __on_battery_data(self):
        self.__battery_data_timestamp = time.time()

    def __on_live_consumption(self, _):
        self.__live_data_timestamp = time.time()

    def __on_mode(self, mode):
        self.__commands.append(CommandBundle(self.__try_set_mode, (mode,)))
