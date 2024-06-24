from asyncio import create_task, sleep
from sys import print_exception
from time import time
from ..core.backendmqtt import Mqtt
from ..core.types import TYPE_CHARGER, TYPE_INVERTER, TYPE_SOLAR
from ..core.watchdog import Watchdog
from .consumption import Consumption
from .battery import Battery
from .modeswitcher import ModeSwitcher
from .supervisorchecks import BatteryOfflineChecker, CellLowChecker, CellHighChecker
from .supervisorchecks import TempLowChargeChecker, TempLowDischargeChecker, TempHighChargeChecker, TempHighDischargeChecker
from .supervisorchecks import LiveDataOfflineChargeChecker, LiveDataOfflineDischargeChecker, MqttOfflineChecker
from .supervisorchecks import StartupChecker, LockedReason

class Supervisor:
    def __init__(self, \
                 config: dict, watchdog: Watchdog,\
                 mqtt: Mqtt, modeswitcher: ModeSwitcher,\
                 consumption: Consumption, battery: Battery):
        from ..core.singletons import Singletons
        config = config['supervisor']

        self.__log = Singletons.log.create_logger('supervisor')
        self.__ui = Singletons.ui

        self.__watchdog = watchdog
        self.__modeswitcher = modeswitcher

        self.__mqtt = mqtt

        self.__task = None

        self.__internal_error = self.internal = LockedReason(
                name='internal',
                locked_devices=(TYPE_CHARGER, TYPE_SOLAR, TYPE_INVERTER),
                fatal=True)

        self.__locks = list()
        self.__checkers = (
                BatteryOfflineChecker(config, battery),
                CellLowChecker(config, battery),
                CellHighChecker(config, battery),
                TempLowChargeChecker(config, battery),
                TempLowDischargeChecker(config, battery),
                TempHighChargeChecker(config, battery),
                TempHighDischargeChecker(config, battery),
                LiveDataOfflineChargeChecker(config, consumption),
                LiveDataOfflineDischargeChecker(config, consumption),
                MqttOfflineChecker(config, mqtt),
                StartupChecker(config, self.__locks))

    def run(self):
        self.__task = create_task(self.__run())
    
    async def __run(self):
        while True:
            try:
                await self.__tick()
            except Exception as e:
                self.__log.error('Cycle failed: ', e)
                from ..core.singletons import Singletons
                print_exception(e, Singletons.log.trace) 
            await sleep(1)

    async def __tick(self):
        now = time()

        previous_locked = self.__locks[-1] if len(self.__locks) else None

        try:
            for checker in self.__checkers:
                result = checker.check(now)
                if result is None:
                    continue
                self.__update_lock(result[0], result[1])
            self.__update_lock(False, self.__internal_error)

        except Exception as e:
            self.__log.error('Checker failed: ', e)
            self.__update_lock.add(True, self.__internal_error)

        locked_devices = set()
        for lock in self.__locks:
            locked_devices.update(lock.locked_devices)
        latest_lock = self.__locks[-1] if len(self.__locks) > 0 else None

        if previous_locked != latest_lock:
            for lock in self.__locks:
                self.__log.info('System lock: ', lock.name)
            if len(self.__locks) == 0:
                self.__log.info('System lock: none')
            await self.__mqtt.send_locked(latest_lock.name if latest_lock is not None else None)
            self.__ui.update_locks(self.__locks)

        self.__modeswitcher.update_locked_devices(locked_devices)

        if not any(x.fatal for x in self.__locks):
            self.__watchdog.feed()
            self.__ui.notify_watchdog()

    def __update_lock(self, active, lock):
        if lock in self.__locks:
            if not active:
                self.__locks.remove(lock)
        else:
            if active:
                self.__locks.append(lock)
