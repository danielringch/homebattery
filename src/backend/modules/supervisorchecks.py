from micropython import const
from time import time
from ..core.types import EnumEntry, TYPE_CHARGER, TYPE_INVERTER, TYPE_SOLAR

_DEFAULT_HIGH = const(999)
_DEFAULT_LOW = const(-999)

_PRIO_BATTERY_OFFLINE = const(30)
_PRIO_CELL_LOW = const(32)
_PRIO_CELL_HIGH = const(31)
_PRIO_TEMP_LOW_CHARGE = const(33)
_PRIO_TEMP_LOW_DISCHARGE = const(34)
_PRIO_TEMP_HIGH_CHARGE = const(35)
_PRIO_TEMP_HIGH_DISCHARGE = const(36)
_PRIO_LIVE_DATA_LOST_CHARGE = const(11)
_PRIO_LIVE_DATA_LOST_DISCHARGE = const(10)
_PRIO_MQTT_OFFLINE = const(5)
_PRIO_STARTUP = const(2)
PRIO_INTERNAL = const(0)



class LockedReason(EnumEntry):
    def __init__(self, name, priority, locked_devices, fatal=False):
        super().__init__(name, None)
        self.priority = priority
        self.locked_devices = locked_devices
        self.fatal = fatal

    def __lt__(self, other):
        return self.priority < other.priority 
    
class SubChecker:
    def __init__(self, config, name, priority, locked_devices, fatal=False):
        self.__name = name
        if config[self.__name]['enabled']:
            self._lock = LockedReason(
                    name=name,
                    priority=priority,
                    locked_devices=locked_devices,
                    fatal=fatal)
        else:
            self._lock = None

class BatteryOfflineChecker(SubChecker):
    def __init__(self, config, battery):
        super().__init__(config, 'battery_offline', _PRIO_BATTERY_OFFLINE, (TYPE_CHARGER, TYPE_SOLAR, TYPE_INVERTER))
        self.__threshold = int(config[self.__name]['threshold'])
        self.__last_data = dict()
        self.__battery = battery
        for name in self.__battery.battery_data.keys():
            self.__on_battery_data(name)
        battery.on_battery_data.append(self.__on_battery_data)

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

class CellLowChecker(SubChecker):
    def __init__(self, config, battery):
        super().__init__(config, 'cell_low', _PRIO_CELL_LOW, (TYPE_INVERTER,))
        self.__threshold = float(config[self.__name]['threshold'])
        self.__hysteresis = float(config[self.__name]['hysteresis'])
        self.__threshold_exceeded = False
        self.__battery = battery

    def check(self, now):
        if self._lock is None:
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
        return (self.__threshold_exceeded, self._lock)
        
class CellHighChecker(SubChecker):
    def __init__(self, config, battery):
        super().__init__(config, 'cell_high', _PRIO_CELL_HIGH, (TYPE_CHARGER, TYPE_SOLAR))
        self.__threshold = float(config[self.__name]['threshold'])
        self.__hysteresis = float(config[self.__name]['hysteresis'])
        self.__threshold_exceeded = False
        self.__battery = battery

    def check(self, now):
        if self._lock is None:
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
        return (self.__threshold_exceeded, self._lock)

class TempLowChargeChecker(SubChecker):
    def __init__(self, config, battery):
        super().__init__(config, 'temp_low_charge', _PRIO_TEMP_LOW_CHARGE, (TYPE_CHARGER, TYPE_SOLAR))
        self.__threshold = float(config[self.__name]['threshold'])
        self.__hysteresis = float(config[self.__name]['hysteresis'])
        self.__threshold_exceeded = False
        self.__battery = battery

    def check(self, now):
        if self._lock is None:
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
        return (self.__threshold_exceeded, self._lock)

class TempLowDischargeChecker(SubChecker):
    def __init__(self, config, battery):
        super().__init__(config, 'temp_low_discharge', _PRIO_TEMP_LOW_DISCHARGE, (TYPE_INVERTER,))
        self.__threshold = float(config[self.__name]['threshold'])
        self.__hysteresis = float(config[self.__name]['hysteresis'])
        self.__threshold_exceeded = False
        self.__battery = battery

    def check(self, now):
        if self._lock is None:
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
        return (self.__threshold_exceeded, self._lock)
    
class TempHighChargeChecker(SubChecker):
    def __init__(self, config, battery):
        super().__init__(config, 'temp_high_charge', _PRIO_TEMP_HIGH_CHARGE, (TYPE_CHARGER, TYPE_SOLAR,))
        self.__threshold = float(config[self.__name]['threshold'])
        self.__hysteresis = float(config[self.__name]['hysteresis'])
        self.__threshold_exceeded = False
        self.__battery = battery

    def check(self, now):
        if self._lock is None:
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
        return (self.__threshold_exceeded, self._lock)
    
class TempHighDischargeChecker(SubChecker):
    def __init__(self, config, battery):
        super().__init__(config, 'temp_high_discharge', _PRIO_TEMP_HIGH_DISCHARGE, (TYPE_INVERTER,))
        self.__threshold = float(config[self.__name]['threshold'])
        self.__hysteresis = float(config[self.__name]['hysteresis'])
        self.__threshold_exceeded = False
        self.__battery = battery

    def check(self, now):
        if self._lock is None:
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
        return (self.__threshold_exceeded, self._lock)
        
class LiveDataOfflineChargeChecker(SubChecker):
    def __init__(self, config, consumption):
        super().__init__(config, 'live_data_lost_charge', _PRIO_LIVE_DATA_LOST_CHARGE, (TYPE_CHARGER,))
        self.__threshold = int(config[self.__name]['threshold'])
        self.__consumption = consumption

    def check(self, now):
        if self._lock is None:
            return None
        active = bool((now - self.__consumption.last_seen) > self.__threshold)
        return (active, self._lock)

class LiveDataOfflineDischargeChecker(SubChecker):
    def __init__(self, config, consumption):
        super().__init__(config, 'live_data_lost_discharge', _PRIO_LIVE_DATA_LOST_DISCHARGE, (TYPE_INVERTER,))
        self.__threshold = int(config[self.__name]['threshold'])
        self.__consumption = consumption

    def check(self, now):
        if self._lock is None:
            return None
        active = bool((now - self.__consumption.last_seen) > self.__threshold)
        return (active, self._lock)

class MqttOfflineChecker(SubChecker):
    def __init__(self, config, mqtt):
        super().__init__(config, 'mqtt_offline', _PRIO_MQTT_OFFLINE, (TYPE_CHARGER, TYPE_INVERTER), True)
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
        super().__init__(config, 'startup', _PRIO_STARTUP, (TYPE_INVERTER, TYPE_SOLAR, TYPE_CHARGER))
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
