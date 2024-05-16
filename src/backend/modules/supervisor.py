from asyncio import create_task, sleep
from sys import print_exception
from time import time
from ..core.backendmqtt import Mqtt
from ..core.types import TYPE_CHARGER, TYPE_INVERTER, TYPE_SOLAR
from ..core.watchdog import Watchdog
from .inverter import Inverter
from .charger import Charger
from .battery import Battery
from .modeswitcher import ModeSwitcher
from .supervisorchecks import BatteryOfflineChecker, CellLowChecker, CellHighChecker
from .supervisorchecks import TempLowChargeChecker, TempLowDischargeChecker, TempHighChargeChecker, TempHighDischargeChecker
from .supervisorchecks import LiveDataOfflineChargeChecker, LiveDataOfflineDischargeChecker, MqttOfflineChecker
from .supervisorchecks import StartupChecker, LockedReason, PRIO_INTERNAL

class Supervisor:
    def __init__(self, config: dict, watchdog: Watchdog, mqtt: Mqtt, modeswitcher: ModeSwitcher, inverter: Inverter, charger: Charger, battery: Battery):
        from ..core.singletons import Singletons
        config = config['supervisor']

        self.__log = Singletons.log.create_logger('supervisor')
        self.__display = Singletons.display
        self.__leds = Singletons.leds

        self.__watchdog = watchdog
        self.__modeswitcher = modeswitcher

        self.__mqtt = mqtt

        self.__check_interval = int(config['check_interval'])
        self.__next_check = 0

        self.__internal_error = self.internal = LockedReason(
                name='internal',
                priority=PRIO_INTERNAL,
                locked_devices=(TYPE_CHARGER, TYPE_SOLAR, TYPE_INVERTER),
                fatal=True)

        self.__locks = set()
        self.__checkers = (
                BatteryOfflineChecker(config, battery),
                CellLowChecker(config, battery),
                CellHighChecker(config, battery),
                TempLowChargeChecker(config, battery),
                TempLowDischargeChecker(config, battery),
                TempHighChargeChecker(config, battery),
                TempHighDischargeChecker(config, battery),
                LiveDataOfflineChargeChecker(config, mqtt),
                LiveDataOfflineDischargeChecker(config, mqtt),
                MqttOfflineChecker(config, mqtt),
                StartupChecker(config, self.__locks))

        self.__health_check_passed = time()

    def run(self):
        self.__task = create_task(self.__run())
    
    async def __run(self):
        while True:
            try:
                await self.__tick()
            except Exception as e:
                self.__log.error('Supervisor cycle failed: ', e)
                from ..core.singletons import Singletons
                print_exception(e, Singletons.log.trace)
            
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
            self.__log.error('Cycle failed: ', e)
            self.__locks.add(self.__internal_error)

        locked_devices = set()
        for lock in self.__locks:
            self.__log.info('System lock: ', lock.name)
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
