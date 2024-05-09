from asyncio import create_task, sleep
from micropython import const
from sys import print_exception
from time import time
from ..core.backendmqtt import Mqtt
from ..core.types import EnumEntry, TYPE_CHARGER, TYPE_INVERTER, TYPE_SOLAR
from ..core.watchdog import Watchdog
from .inverter import Inverter
from .charger import Charger
from .battery import Battery
from .modeswitcher import ModeSwitcher

_SUPERVISOR_LOG_NAME = const('supervisor')

class Supervisor:
    class LockedReason(EnumEntry):
        def __init__(self, name, priority, locked_devices, fatal=False):
            super().__init__(name, None)
            self.priority = priority
            self.locked_devices = locked_devices
            self.fatal = fatal

        def __lt__(self, other):
            return self.priority < other.priority            

    def __init__(self, config: dict, watchdog: Watchdog, mqtt: Mqtt, modeswitcher: ModeSwitcher, inverter: Inverter, charger: Charger, battery: Battery):
        from ..core.singletons import Singletons
        config = config['supervisor']

        self.__trace = Singletons.log.trace
        self.__log = Singletons.log.create_logger(_SUPERVISOR_LOG_NAME)
        self.__display = Singletons.display
        self.__leds = Singletons.leds

        self.__watchdog = watchdog
        self.__modeswitcher = modeswitcher

        self.__mqtt = mqtt

        self.__check_interval = int(config['check_interval'])
        self.__next_check = 0

        self.__internal_error = self.internal = Supervisor.LockedReason(
                name='internal',
                priority=0,
                locked_devices=(TYPE_CHARGER, TYPE_SOLAR, TYPE_INVERTER),
                fatal=True)

        self.__locks = set()
        self.__checkers = (
                self.BatteryOfflineChecker(config, battery),
                self.CellHighChecker(config, battery),
                self.CellLowChecker(config, battery),
                self.LiveDataOfflineChargeChecker(config, mqtt),
                self.LiveDataOfflineDischargeChecker(config, mqtt),
                self.MqttOfflineChecker(config, mqtt),
                self.StartupChecker(config, self.__locks))

        self.__health_check_passed = time()

    def run(self):
        self.__task = create_task(self.__run())
    
    async def __run(self):
        while True:
            try:
                await self.__tick()
            except Exception as e:
                self.__log.error(f'Supervisor cycle failed: {e}')
                print_exception(e, self.__trace)
            
            deadline = 3 * self.__check_interval
            now = time()
            if self.__health_check_passed + deadline > now:
                self.__watchdog.feed()
                self.__leds.notify_watchdog()
            await sleep(0.5)

    async def __tick(self):
        now = time()
        if now < self.__next_check:
            return
        self.__next_check = now + self.__check_interval

        previous_locked = sorted(self.__locks)[0] if len(self.__locks) else None

        try:
            for checker in self.__checkers:
                result = checker.check(now)
                if result is None:
                    continue
                if result[0]:
                    self.__locks.add(result[1])
                else:
                    self.__clear_lock(result[1])
            self.__clear_lock(self.__internal_error)

        except Exception as e:
            self.__log.error(f'Cycle failed: {e}')
            self.__locks.add(self.__internal_error)

        locked_devices = set()
        for lock in self.__locks:
            self.__log.info(f'System lock: {lock.name}')
            locked_devices.update(lock.locked_devices)

        top_priority_lock = sorted(self.__locks)[0] if len(self.__locks) else None

        if previous_locked != top_priority_lock:
            await self.__mqtt.send_locked(top_priority_lock.name if top_priority_lock is not None else None)
            self.__display.update_lock(top_priority_lock.name if top_priority_lock is not None else None)
        self.__modeswitcher.update_locked_devices(locked_devices)

        if not any(x.fatal for x in self.__locks):
            self.__health_check_passed = now

    def __clear_lock(self, lock):
        try:
            self.__locks.remove(lock)
        except KeyError:
            pass

    class SubChecker:
        def __init__(self, config, name, priority, locked_devices, fatal=False):
            self.__name = name
            if config[self.__name]['enabled']:
                self._lock = Supervisor.LockedReason(
                        name=name,
                        priority=priority,
                        locked_devices=locked_devices,
                        fatal=fatal)
            else:
                self._lock = None

    class BatteryOfflineChecker(SubChecker):
        def __init__(self, config, battery):
            super().__init__(config, 'battery_offline', 30, (TYPE_CHARGER, TYPE_SOLAR, TYPE_INVERTER))
            self.__threshold = int(config[self.__name]['threshold'])
            self.__last_data = dict()
            self.__battery = battery
            for name in self.__battery.battery_data.keys():
                self.__on_battery_data(name)
            battery.on_battery_data.add(self.__on_battery_data)

        def check(self, now):
            if self._lock is None:
                return None
            oldest_timestamp = min(self.__last_data.values()) if len(self.__last_data) > 0 else 0
            active = bool((now - oldest_timestamp) > self.__threshold)
            return (active, self._lock)
        
        def __on_battery_data(self, name):
            data = self.__battery.battery_data[name]
            if data is None:
                self.__last_data[name] = 0
            else:
                self.__last_data[name] = data.timestamp
        
    class CellHighChecker(SubChecker):
        def __init__(self, config, battery):
            super().__init__(config, 'cell_high', 31, (TYPE_CHARGER, TYPE_SOLAR))
            self.__threshold = float(config[self.__name]['threshold'])
            self.__hysteresis = float(config[self.__name]['hysteresis'])
            self.__threshold_exceeded = False
            self.__battery = battery

        def check(self, now):
            if self._lock is None:
                return None
            highest_cell = 0
            for battery in self.__battery.battery_data.values():
                if battery is None or not battery.valid:
                    continue
                for cell in battery.cells:
                    highest_cell = max(highest_cell, cell)
                
            if highest_cell == 0:
                return None

            threshold = self.__threshold
            if self.__threshold_exceeded:
                threshold -= self.__hysteresis

            self.__threshold_exceeded = highest_cell > threshold
            return (self.__threshold_exceeded, self._lock)
        
    class CellLowChecker(SubChecker):
        def __init__(self, config, battery):
            super().__init__(config, 'cell_low', 32, (TYPE_INVERTER,))
            self.__threshold = float(config[self.__name]['threshold'])
            self.__hysteresis = float(config[self.__name]['hysteresis'])
            self.__threshold_exceeded = False
            self.__battery = battery

        def check(self, now):
            if self._lock is None:
                return None
            lowest_cell = 999
            for battery in self.__battery.battery_data.values():
                if battery is None or not battery.valid:
                    continue
                for cell in battery.cells:
                    lowest_cell = min(lowest_cell, cell)

            if lowest_cell == 999:
                return None

            threshold = self.__threshold
            if self.__threshold_exceeded:
                threshold += self.__hysteresis

            self.__threshold_exceeded = lowest_cell < threshold
            return (self.__threshold_exceeded, self._lock)
        
    class LiveDataOfflineChargeChecker(SubChecker):
        def __init__(self, config, mqtt):
            super().__init__(config, 'live_data_lost_charge', 11, (TYPE_CHARGER,))
            self.__threshold = int(config[self.__name]['threshold'])
            self.__last_data = 0
            mqtt.on_live_consumption.add(self.__on_live_consumption)

        def check(self, now):
            if self._lock is None:
                return None
            active = bool((now - self.__last_data) > self.__threshold)
            return (active, self._lock)
        
        def __on_live_consumption(self, _):
            self.__last_data = time()

    class LiveDataOfflineDischargeChecker(SubChecker):
        def __init__(self, config, mqtt):
            super().__init__(config, 'live_data_lost_discharge', 10, (TYPE_INVERTER,))
            self.__threshold = int(config[self.__name]['threshold'])
            self.__last_data = 0
            mqtt.on_live_consumption.add(self.__on_live_consumption)

        def check(self, now):
            if self._lock is None:
                return None
            active = bool((now - self.__last_data) > self.__threshold)
            return (active, self._lock)
        
        def __on_live_consumption(self, _):
            self.__last_data = time()

    class MqttOfflineChecker(SubChecker):
        def __init__(self, config, mqtt):
            super().__init__(config, 'mqtt_offline', 5, (TYPE_CHARGER, TYPE_INVERTER), True)
            self.__threshold = int(config[self.__name]['threshold'])
            self.__last_online = 0
            self.__mqtt = mqtt

        def check(self, now):
            if self._lock is None:
                return None
            if self.__mqtt.connected:
                self.__last_online = time()
            active = bool((now - self.__last_online) > self.__threshold)
            return (active, self._lock)

    class StartupChecker(SubChecker):
        def __init__(self, config, locks):
            config = {'startup': {'enabled': True}}
            super().__init__(config, 'startup', 2, (TYPE_INVERTER, TYPE_SOLAR, TYPE_CHARGER))
            self.__mature_timestamp = time() + 60
            self.__locks = locks

        def check(self, now):
            if len(self.__locks) > 0 \
                and self._lock not in self.__locks \
                and now < self.__mature_timestamp:
                return (True, self._lock)
            elif (len(self.__locks) == 1 and self._lock in self.__locks) \
                    or (now >= self.__mature_timestamp):
                self.__mature_timestamp = now
                return (False, self._lock)
