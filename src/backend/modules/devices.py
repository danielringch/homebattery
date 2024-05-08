import sys
from micropython import const

from ..drivers.ahoydtu import AhoyDtu
from ..drivers.daly8s24v60a import Daly8S24V60A
from ..drivers.jkbmsbd4 import JkBmsBd4
from ..drivers.lltpowerbmsv4ble import LltPowerBmsV4Ble
from ..drivers.mqttbattery import MqttBattery
from ..drivers.shelly import Shelly
from ..drivers.victronmppt import VictronMppt

_AHOY_DTU = const('ahoydtu')
_DALY_8S_24V_60A = const('daly8S24V60A')
_JK_BMS_BD4 = const('jkBmsBd4')
_LLT_POWER_BMS_V4_BLE = const('lltPowerBmsV4Ble')
_MQTT_BATTERY = const('mqttBattery')
_SHELLY = const('shelly')
_VICTRON_MPPT = const('victronmppt')

drivers = {
    _AHOY_DTU: AhoyDtu,
    _DALY_8S_24V_60A: Daly8S24V60A,
    _JK_BMS_BD4: JkBmsBd4,
    _LLT_POWER_BMS_V4_BLE: LltPowerBmsV4Ble,
    _MQTT_BATTERY : MqttBattery,
    _SHELLY: Shelly,
    _VICTRON_MPPT: VictronMppt
}

class Devices:
    def __init__(self, config, mqtt):
        config = config['devices']
        self.__devices = []

        from ..core.logging_singleton import log

        for name, meta in config.items():
            try:
                driver_name = meta['driver']
                driver = drivers[driver_name]
                log.debug(f'Loading device {name} with driver {driver.__name__}.')
                if driver_name == _MQTT_BATTERY:
                    instance = driver(name, meta, mqtt) 
                else:
                    instance = driver(name, meta)
                self.__devices.append(instance)
            except Exception as e:
                log.error(f'Failed to initialize device {name}: {e}')
                sys.print_exception(e, log.trace)

    @property
    def devices(self):
        return self.__devices