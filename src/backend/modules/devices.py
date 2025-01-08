from gc import collect as gc_collect
from micropython import const

from ..core.logging import CustomLogger

_AHOY_DTU = const('ahoyDtu')
_DALY_8S_24V_60A = const('daly8S24V60A')
_GENERIC_SOLAR = const('genericSolar')
_GROWATT_INVERTER_MODBUS = const('growattinvertermodbus')
_HEIDELBERG_WALLBOX = const('heidelbergWallbox')
_HTTP_CONSUMPTION = const('httpConsumption')
_JK_BMS_BD = const('jkBmsBd')
_LLT_POWER_BMS_V4_BLE = const('lltPowerBmsV4Ble')
_MQTT_BATTERY = const('mqttBattery')
_MQTT_CONSUMPTION = const('mqttConsumption')
_OPEN_DTU = const('openDtu')
_PYLON_LV = const('pylonLv')
_SHELLY_CHARGER = const('shellyCharger')
_SHELLY_HEATER = const('shellyHeater')
_VICTRON_MPPT = const('victronMppt')

class Devices:
    def __init__(self, config, mqtt):
        config = config['devices']
        self.__devices = []

        from ..core.singletons import Singletons
        self.__log: CustomLogger = Singletons.log.create_logger('devices')

        for name, meta in config.items():
            driver_name = meta['driver']
            if driver_name == _AHOY_DTU:
                from ..drivers.hoymiles.ahoydtuadapter import AhoyDtu
                gc_collect()
                self.__load_device(name, AhoyDtu, meta)
            elif driver_name == _DALY_8S_24V_60A:
                from ..drivers.daly.daly8s24v60a import Daly8S24V60A
                gc_collect()
                self.__load_device(name, Daly8S24V60A, meta)
            elif driver_name == _GENERIC_SOLAR:
                from ..drivers.generic.genericsolar import GenericSolar
                gc_collect()
                self.__load_device(name, GenericSolar, meta)
            elif driver_name == _GROWATT_INVERTER_MODBUS:
                from ..drivers.growatt.growattinvertermodbus import GrowattInverterModbus
                gc_collect()
                self.__load_device(name, GrowattInverterModbus, meta)
            elif driver_name == _HEIDELBERG_WALLBOX:
                from ..drivers.heidelberg.heidelbergwallbox import HeidelbergWallbox
                gc_collect()
                self.__load_device(name, HeidelbergWallbox, meta)
            elif driver_name == _HTTP_CONSUMPTION:
                from ..drivers.generic.httpconsumption import HttpConsumption
                gc_collect()
                self.__load_device(name, HttpConsumption, meta)
            elif driver_name == _JK_BMS_BD:
                from ..drivers.jkbms.jkbmsbd import JkBmsBd
                gc_collect()
                self.__load_device(name, JkBmsBd, meta)
            elif driver_name == _LLT_POWER_BMS_V4_BLE:
                from ..drivers.lltpower.lltpowerbmsv4ble import LltPowerBmsV4Ble
                gc_collect()
                self.__load_device(name, LltPowerBmsV4Ble, meta)
            elif driver_name == _MQTT_BATTERY:
                from ..drivers.generic.mqttbattery import MqttBattery
                gc_collect()
                self.__load_device(name, MqttBattery, meta, mqtt)
            elif driver_name == _MQTT_CONSUMPTION:
                from ..drivers.generic.mqttconsumption import MqttConsumption
                gc_collect()
                self.__load_device(name, MqttConsumption, meta, mqtt)
            elif driver_name == _OPEN_DTU:
                from ..drivers.hoymiles.opendtuadapter import OpenDtu
                gc_collect()
                self.__load_device(name, OpenDtu, meta)
            elif driver_name == _PYLON_LV:
                from ..drivers.pylontech.pylonlv import PylonLv
                gc_collect()
                self.__load_device(name, PylonLv, meta)
            elif driver_name == _SHELLY_CHARGER:
                from ..drivers.shelly.shellycharger import ShellyCharger
                gc_collect()
                self.__load_device(name, ShellyCharger, meta)
            elif driver_name == _SHELLY_HEATER:
                from ..drivers.shelly.shellyheater import ShellyHeater
                gc_collect()
                self.__load_device(name, ShellyHeater, meta)
            elif driver_name == _VICTRON_MPPT:
                from ..drivers.victron.victronmppt import VictronMppt
                gc_collect()
                self.__load_device(name, VictronMppt, meta)
            else:
                self.__log.error('Unknown driver for device ', name, ': ', driver_name)

    def get_by_type(self, type: str):
        return tuple(x for x in self.__devices if type in x.device_types)

    @property
    def devices(self):
        return self.__devices
    
    def __load_device(self, name, driver, config, *args):
        try:
            self.__log.info('Loading device ', name, ' with driver ', driver.__name__)
            instance = driver(name, config, *args)
            self.__devices.append(instance)
            gc_collect()
        except Exception as e:
            self.__log.error('Failed to initialize device ', name, ': ', e)
            self.__log.trace(e)