from asyncio import create_task, sleep
from time import time
from ..core.backendmqtt import Mqtt
from ..core.logging import CustomLogger
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

        self.__log: CustomLogger = Singletons.log.create_logger('supervisor')
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
        self.__previous_top_lock = None
        self.__checkers = (
                # order represents priority, low to high
                LiveDataOfflineChargeChecker(config, consumption),
                LiveDataOfflineDischargeChecker(config, consumption),
                TempLowChargeChecker(config, battery),
                TempLowDischargeChecker(config, battery),
                TempHighChargeChecker(config, battery),
                TempHighDischargeChecker(config, battery),
                CellLowChecker(config, battery),
                CellHighChecker(config, battery),
                BatteryOfflineChecker(config, battery),
                MqttOfflineChecker(config, mqtt),
                StartupChecker(config, self.__locks)) # must always be last check, otherwise content of self.__locks would be incorrect

    def run(self):
        self.__task = create_task(self.__run())
    
    async def __run(self):
        while True:
            try:
                await self.__tick()
            except Exception as e:
                self.__log.error('Cycle failed: ', e)
                self.__log.trace(e)
            await sleep(1)

    async def __tick(self):
        now = time()
        try:
            self.__locks.clear()
            for checker in self.__checkers:
                lock = checker.check(now)
                if lock is not None:
                    self.__locks.append(lock)
        except Exception as e:
            self.__log.error('Checker failed: ', e)
            self.__locks.append(self.__internal_error)

        locked_devices = set()
        for lock in self.__locks:
            locked_devices.update(lock.locked_devices)
        top_prio_lock = self.__locks[-1] if len(self.__locks) > 0 else None

        if top_prio_lock != self.__previous_top_lock:
            self.__previous_top_lock = top_prio_lock
            for lock in self.__locks:
                self.__log.info('System lock: ', lock.name)
            if len(self.__locks) == 0:
                self.__log.info('System lock: none')
            self.__ui.update_locks(self.__locks)
            try: # if MQTT is offline, sending data results in an exception
                await self.__mqtt.send_locked(top_prio_lock.name if top_prio_lock is not None else None)
            except:
                self.__log.error('Failed to send lock information over MQTT')
                self.__previous_top_lock = None # ensure lock is sent over MQTT in next cycle

        self.__modeswitcher.update_locked_devices(locked_devices)

        if not any(x.fatal for x in self.__locks):
            self.__watchdog.feed()
            self.__ui.notify_watchdog()
