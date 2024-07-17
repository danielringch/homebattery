from micropython import const
from time import time
from ..core.types import EnumEntry, TYPE_CHARGER, TYPE_INVERTER, TYPE_SOLAR

_DEFAULT_HIGH = const(999)
_DEFAULT_LOW = const(-999)

class LockedReason(EnumEntry):
    def __init__(self, name, locked_devices, fatal=False):
        super().__init__(name, None)
        self.locked_devices = locked_devices
        self.fatal = fatal
    
class SubChecker:
    def __init__(self, config, name, locked_devices, fatal=False):
        self.__name = name
        if self.__name in config:
            self._lock = LockedReason(
                    name=name,
                    locked_devices=locked_devices,
                    fatal=fatal)
        else:
            self._lock = None

    @property
    def active(self):
        return self._lock is not None

    def _return_lock(self, active):
        return self._lock if active else None

class BatteryOfflineChecker(SubChecker):
    def __init__(self, config, battery):
        super().__init__(config, 'battery_offline', (TYPE_CHARGER, TYPE_SOLAR, TYPE_INVERTER))
        if not self.active:
            return
        self.__threshold = int(config[self.__name]['threshold'])
        self.__last_data = dict()
        self.__battery = battery
        for name in self.__battery.battery_data.keys():
            self.__on_battery_data(name)
        battery.on_battery_data.append(self.__on_battery_data)

    def check(self, now):
        if not self.active:
            return None
        oldest_timestamp = min(self.__last_data.values()) if len(self.__last_data) > 0 else 0
        return self._return_lock(bool((now - oldest_timestamp) > self.__threshold))
        
    def __on_battery_data(self, name):
        data = self.__battery.battery_data[name]
        if data is None:
            self.__last_data[name] = 0
        else:
            self.__last_data[name] = data.timestamp

class CellLowChecker(SubChecker):
    def __init__(self, config, battery):
        super().__init__(config, 'cell_low', (TYPE_INVERTER,))
        if not self.active:
            return
        self.__threshold = float(config[self.__name]['threshold'])
        self.__hysteresis = float(config[self.__name]['hysteresis'])
        self.__threshold_exceeded = False
        self.__battery = battery

    def check(self, now):
        if not self.active:
            return None
        lowest_cell = _DEFAULT_HIGH
        for battery in self.__battery.battery_data.values():
            if battery is None or not battery.valid:
                continue
            for cell in battery.cells:
                lowest_cell = min(lowest_cell, cell)

        if lowest_cell == _DEFAULT_HIGH:
            return None

        threshold = self.__threshold
        if self.__threshold_exceeded:
            threshold += self.__hysteresis

        self.__threshold_exceeded = lowest_cell < threshold
        return self._return_lock(self.__threshold_exceeded)
        
class CellHighChecker(SubChecker):
    def __init__(self, config, battery):
        super().__init__(config, 'cell_high', (TYPE_CHARGER, TYPE_SOLAR))
        if not self.active:
            return
        self.__threshold = float(config[self.__name]['threshold'])
        self.__hysteresis = float(config[self.__name]['hysteresis'])
        self.__threshold_exceeded = False
        self.__battery = battery

    def check(self, now):
        if not self.active:
            return None
        highest_cell = _DEFAULT_LOW
        for battery in self.__battery.battery_data.values():
            if battery is None or not battery.valid:
                continue
            for cell in battery.cells:
                highest_cell = max(highest_cell, cell)
                
        if highest_cell == _DEFAULT_LOW:
            return None

        threshold = self.__threshold
        if self.__threshold_exceeded:
            threshold -= self.__hysteresis

        self.__threshold_exceeded = highest_cell > threshold
        return self._return_lock(self.__threshold_exceeded)

class TempLowChargeChecker(SubChecker):
    def __init__(self, config, battery):
        super().__init__(config, 'temp_low_charge', (TYPE_CHARGER, TYPE_SOLAR))
        if not self.active:
            return
        self.__threshold = float(config[self.__name]['threshold'])
        self.__hysteresis = float(config[self.__name]['hysteresis'])
        self.__threshold_exceeded = False
        self.__battery = battery

    def check(self, now):
        if not self.active:
            return None
        lowest_temp = _DEFAULT_HIGH
        for battery in self.__battery.battery_data.values():
            if battery is None or not battery.valid:
                continue
            for temperature in battery.temps:
                lowest_temp = min(lowest_temp, temperature)

        if lowest_temp == _DEFAULT_HIGH:
            return None

        threshold = self.__threshold
        if self.__threshold_exceeded:
            threshold += self.__hysteresis

        self.__threshold_exceeded = lowest_temp < threshold
        return self._return_lock(self.__threshold_exceeded)

class TempLowDischargeChecker(SubChecker):
    def __init__(self, config, battery):
        super().__init__(config, 'temp_low_discharge', (TYPE_INVERTER,))
        if not self.active:
            return
        self.__threshold = float(config[self.__name]['threshold'])
        self.__hysteresis = float(config[self.__name]['hysteresis'])
        self.__threshold_exceeded = False
        self.__battery = battery

    def check(self, now):
        if not self.active:
            return None
        lowest_temp = _DEFAULT_HIGH
        for battery in self.__battery.battery_data.values():
            if battery is None or not battery.valid:
                continue
            for temperature in battery.temps:
                lowest_temp = min(lowest_temp, temperature)

        if lowest_temp == _DEFAULT_HIGH:
            return None

        threshold = self.__threshold
        if self.__threshold_exceeded:
            threshold += self.__hysteresis

        self.__threshold_exceeded = lowest_temp < threshold
        return self._return_lock(self.__threshold_exceeded)
    
class TempHighChargeChecker(SubChecker):
    def __init__(self, config, battery):
        super().__init__(config, 'temp_high_charge', (TYPE_CHARGER, TYPE_SOLAR,))
        if not self.active:
            return
        self.__threshold = float(config[self.__name]['threshold'])
        self.__hysteresis = float(config[self.__name]['hysteresis'])
        self.__threshold_exceeded = False
        self.__battery = battery

    def check(self, now):
        if not self.active:
            return None
        highest_temp = _DEFAULT_LOW
        for battery in self.__battery.battery_data.values():
            if battery is None or not battery.valid:
                continue
            for temperature in battery.temps:
                highest_temp = max(highest_temp, temperature)

        if highest_temp == _DEFAULT_LOW:
            return None

        threshold = self.__threshold
        if self.__threshold_exceeded:
            threshold -= self.__hysteresis

        self.__threshold_exceeded = highest_temp > threshold
        return self._return_lock(self.__threshold_exceeded)
    
class TempHighDischargeChecker(SubChecker):
    def __init__(self, config, battery):
        super().__init__(config, 'temp_high_discharge', (TYPE_INVERTER,))
        if not self.active:
            return
        self.__threshold = float(config[self.__name]['threshold'])
        self.__hysteresis = float(config[self.__name]['hysteresis'])
        self.__threshold_exceeded = False
        self.__battery = battery

    def check(self, now):
        if not self.active:
            return None
        highest_temp = _DEFAULT_LOW
        for battery in self.__battery.battery_data.values():
            if battery is None or not battery.valid:
                continue
            for temperature in battery.temps:
                highest_temp = max(highest_temp, temperature)

        if highest_temp == _DEFAULT_LOW:
            return None

        threshold = self.__threshold
        if self.__threshold_exceeded:
            threshold -= self.__hysteresis

        self.__threshold_exceeded = highest_temp > threshold
        return self._return_lock(self.__threshold_exceeded)
        
class LiveDataOfflineChargeChecker(SubChecker):
    def __init__(self, config, consumption):
        super().__init__(config, 'live_data_lost_charge', (TYPE_CHARGER,))
        if not self.active:
            return
        self.__threshold = int(config[self.__name]['threshold'])
        self.__consumption = consumption

    def check(self, now):
        if not self.active:
            return None
        return self._return_lock(bool((now - self.__consumption.last_seen) > self.__threshold))

class LiveDataOfflineDischargeChecker(SubChecker):
    def __init__(self, config, consumption):
        super().__init__(config, 'live_data_lost_discharge', (TYPE_INVERTER,))
        if not self.active:
            return
        self.__threshold = int(config[self.__name]['threshold'])
        self.__consumption = consumption

    def check(self, now):
        if not self.active:
            return None
        return self._return_lock(bool((now - self.__consumption.last_seen) > self.__threshold))

class MqttOfflineChecker(SubChecker):
    def __init__(self, config, mqtt):
        super().__init__(config, 'mqtt_offline', (TYPE_CHARGER, TYPE_INVERTER), True)
        if not self.active:
            return
        self.__threshold = int(config[self.__name]['threshold'])
        self.__last_online = 0
        self.__mqtt = mqtt

    def check(self, now):
        if not self.active:
            return None
        if self.__mqtt.connected:
            self.__last_online = time()
        return self._return_lock(bool((now - self.__last_online) > self.__threshold))

class StartupChecker(SubChecker):
    def __init__(self, config, locks):
        config = {'startup': None}
        super().__init__(config, 'startup', (TYPE_INVERTER, TYPE_SOLAR, TYPE_CHARGER))
        self.__mature_timestamp = time() + 60
        self.__locks = locks

    def check(self, now):
        if len(self.__locks) > 0 \
            and self._lock not in self.__locks \
            and now < self.__mature_timestamp:
            return self._lock
        elif (len(self.__locks) == 1 and self._lock in self.__locks) \
                or (now >= self.__mature_timestamp):
            self.__mature_timestamp = now
            return None
