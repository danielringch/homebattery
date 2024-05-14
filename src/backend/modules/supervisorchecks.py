from time import time
from ..core.types import EnumEntry, TYPE_CHARGER, TYPE_INVERTER, TYPE_SOLAR

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
