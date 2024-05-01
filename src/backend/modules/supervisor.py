import asyncio, sys, time
from ..core.types import devicetype, EnumEntry
from ..core.logging import log
from ..core.backendmqtt import Mqtt
from ..core.display import display
from ..core.leds import leds
from ..core.watchdog import Watchdog
from .inverter import Inverter
from .charger import Charger
from .battery import Battery
from .modeswitcher import ModeSwitcher


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
        config = config['supervisor']

        self.__watchdog = watchdog
        self.__modeswitcher = modeswitcher

        self.__mqtt = mqtt

        self.__check_interval = int(config['check_interval'])
        self.__next_check = 0

        self.__internal_error = self.internal = Supervisor.LockedReason(
                name='internal',
                priority=0,
                locked_devices=(devicetype.charger, devicetype.solar, devicetype.inverter),
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

        self.__health_check_passed = time.time()

    def run(self):
        self.__task = asyncio.create_task(self.__run())
    
    async def __run(self):
        while True:
            try:
                self.__tick()
            except Exception as e:
                log.error(f'Supervisor cycle failed: {e}')
                sys.print_exception(e, log.trace)
            
            deadline = 3 * self.__check_interval
            now = time.time()
            if self.__health_check_passed + deadline > now:
                self.__watchdog.feed()
                leds.notify_watchdog()
            await asyncio.sleep(0.5)

    def __tick(self):
        now = time.time()
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
            log.supervisor(f'Cycle failed: {e}')
            self.__locks.add(self.__internal_error)

        locked_devices = set()
        for lock in self.__locks:
            log.supervisor(f'System lock: {lock.name}')
            locked_devices.update(lock.locked_devices)

        top_priority_lock = sorted(self.__locks)[0] if len(self.__locks) else None

        if previous_locked != top_priority_lock:
            self.__mqtt.send_locked(top_priority_lock.name if top_priority_lock is not None else None)
            display.update_lock(top_priority_lock.name if top_priority_lock is not None else None)
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
            super().__init__(config, 'battery_offline', 30, (devicetype.charger, devicetype.solar, devicetype.inverter))
            self.__threshold = int(config[self.__name]['threshold'])
            self.__last_data = 0
            battery.on_battery_data.add(self.__on_battery_data)

        def check(self, now):
            if self._lock is None:
                return None
            active = bool((now - self.__last_data) > self.__threshold)
            return (active, self._lock)
        
        def __on_battery_data(self):
            self.__last_data = time.time()
        
    class CellHighChecker(SubChecker):
        def __init__(self, config, battery):
            super().__init__(config, 'cell_high', 31, (devicetype.charger, devicetype.solar))
            self.__threshold = float(config[self.__name]['threshold'])
            self.__hysteresis = float(config[self.__name]['hysteresis'])
            self.__threshold_exceeded = False
            self.__battery = battery

        def check(self, now):
            if self._lock is None:
                return None
            battery_data = self.__battery.data
            if battery_data is None or battery_data.max_cell_voltage is None:
                return None

            threshold = self.__threshold
            if self.__threshold_exceeded:
                threshold -= self.__hysteresis

            self.__threshold_exceeded = battery_data.max_cell_voltage > threshold
            return (self.__threshold_exceeded, self._lock)
        
    class CellLowChecker(SubChecker):
        def __init__(self, config, battery):
            super().__init__(config, 'cell_low', 32, (devicetype.inverter,))
            self.__threshold = float(config[self.__name]['threshold'])
            self.__hysteresis = float(config[self.__name]['hysteresis'])
            self.__threshold_exceeded = False
            self.__battery = battery

        def check(self, now):
            if self._lock is None:
                return None
            battery_data = self.__battery.data
            if battery_data is None or battery_data.max_cell_voltage is None:
                return None

            threshold = self.__threshold
            if self.__threshold_exceeded:
                threshold += self.__hysteresis

            self.__threshold_exceeded = battery_data.max_cell_voltage < threshold
            return (self.__threshold_exceeded, self._lock)
        
    class LiveDataOfflineChargeChecker(SubChecker):
        def __init__(self, config, mqtt):
            super().__init__(config, 'live_data_lost_charge', 11, (devicetype.charger,))
            self.__threshold = int(config[self.__name]['threshold'])
            self.__last_data = 0
            mqtt.on_live_consumption.add(self.__on_live_consumption)

        def check(self, now):
            if self._lock is None:
                return None
            active = bool((now - self.__last_data) > self.__threshold)
            return (active, self._lock)
        
        def __on_live_consumption(self, _):
            self.__last_data = time.time()

    class LiveDataOfflineDischargeChecker(SubChecker):
        def __init__(self, config, mqtt):
            super().__init__(config, 'live_data_lost_discharge', 10, (devicetype.inverter,))
            self.__threshold = int(config[self.__name]['threshold'])
            self.__last_data = 0
            mqtt.on_live_consumption.add(self.__on_live_consumption)

        def check(self, now):
            if self._lock is None:
                return None
            active = bool((now - self.__last_data) > self.__threshold)
            return (active, self._lock)
        
        def __on_live_consumption(self, _):
            self.__last_data = time.time()

    class MqttOfflineChecker(SubChecker):
        def __init__(self, config, mqtt):
            super().__init__(config, 'mqtt_offline', 5, (devicetype.charger, devicetype.inverter), True)
            self.__threshold = int(config[self.__name]['threshold'])
            self.__last_online = 0
            self.__mqtt = mqtt

        def check(self, now):
            if self._lock is None:
                return None
            if self.__mqtt.connected:
                self.__last_online = time.time()
            active = bool((now - self.__last_online) > self.__threshold)
            return (active, self._lock)

    class StartupChecker(SubChecker):
        def __init__(self, config, locks):
            config = {'startup': {'enabled': True}}
            super().__init__(config, 'startup', 2, (devicetype.inverter, devicetype.solar, devicetype.charger))
            self.__mature_timestamp = time.time() + 60
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
