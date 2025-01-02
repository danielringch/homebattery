from asyncio import Lock, TimeoutError, wait_for
from ...core.devicetools import merge_driver_statuses
from ...core.logging import CustomLogger
from ...core.triggers import triggers, TRIGGER_300S
from ...core.types import CommandFiFo, run_callbacks, STATUS_OFF, STATUS_OFFLINE, MEASUREMENT_STATUS, MEASUREMENT_ENERGY, MEASUREMENT_POWER
from ..devices import Devices

class AnyClass:
    def __init__(self, class_name: str, devices: Devices, data_event, data_getter):
        from ...core.singletons import Singletons
        self._lock = Lock()
        self._commands = CommandFiFo(16)

        self._log: CustomLogger = Singletons.log.create_logger(class_name)

        self._summary_callbacks = list()

        self._devices = devices.get_by_type(class_name)
        self._last_status = STATUS_OFFLINE if self._devices else STATUS_OFF
        self._last_power = 0

        self.__data_getter = data_getter

        for device in self._devices:
            data_event(device).append(self.__on_device_data)

        triggers.add_subscriber(self.__on_trigger)

    async def run(self):
        while True:
            try:
                async with self._lock:
                    while self._commands:
                        await self._commands.popleft()()
            except Exception as e:
                self._log.error('Cycle failed: ', e)
                self._log.trace(e)
            try:
                await wait_for(self._commands.wait_and_clear(), timeout=1)
            except TimeoutError:
                pass

    def __on_trigger(self, trigger_type):
        try:
            if trigger_type == TRIGGER_300S:
                run_callbacks(self._summary_callbacks, self.get_summary_data())
        except Exception as e:
            self._log.error('Trigger cycle failed: ', e)
            self._log.trace(e)

    def get_status(self):
        return self._last_status

    @property
    def on_summary_data(self):
        return self._summary_callbacks
    
    def get_summary_data(self):
        return {
            MEASUREMENT_STATUS: self._last_status,
            MEASUREMENT_POWER: self._last_power
        }

    async def _get_status(self):
        driver_statuses = tuple(self.__data_getter(x)[MEASUREMENT_STATUS] for x in self._devices)
        status = merge_driver_statuses(driver_statuses)

        if status != self._last_status:
            run_callbacks(self._summary_callbacks, {MEASUREMENT_STATUS: status})
            self._last_status = status

    async def _get_power(self):
        power = sum((self.__data_getter(x).get(MEASUREMENT_POWER, 0) for x in self._devices), 0)
        if power != self._last_power:
            run_callbacks(self._summary_callbacks, {MEASUREMENT_POWER: power})
            self._last_power = power

    def __on_device_data(self, sender, data):
        if MEASUREMENT_STATUS in data:
            self._commands.append(self._get_status)
        if MEASUREMENT_POWER in data:
            self._commands.append(self._get_power)
        if MEASUREMENT_ENERGY in data:
            run_callbacks(self._summary_callbacks, {MEASUREMENT_ENERGY: data[MEASUREMENT_ENERGY]})
