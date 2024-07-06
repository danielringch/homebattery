from gc import collect as gc_collect
from micropython import const

_AHOY_DTU = const('ahoyDtu')
_DALY_8S_24V_60A = const('daly8S24V60A')
_GROWATT_INVERTER_MODBUS = const('growattinvertermodbus')
_JK_BMS_BD4 = const('jkBmsBd4')
_LLT_POWER_BMS_V4_BLE = const('lltPowerBmsV4Ble')
_MQTT_BATTERY = const('mqttBattery')
_MQTT_CONSUMPTION = const('mqttConsumption')
_SHELLY_CHARGER = const('shellyCharger')
_VICTRON_MPPT = const('victronMppt')

class Devices:
    def __init__(self, config, mqtt):
        config = config['devices']
        self.__devices = []

        from ..core.singletons import Singletons
        log = Singletons.log

        for name, meta in config.items():
            driver_name = meta['driver']
            if driver_name == _AHOY_DTU:
                from ..drivers.ahoydtu import AhoyDtu
                gc_collect()
                self.__load_device(log, name, AhoyDtu, meta)
            elif driver_name == _DALY_8S_24V_60A:
                from ..drivers.daly8s24v60a import Daly8S24V60A
                gc_collect()
                self.__load_device(log, name, Daly8S24V60A, meta)
            elif driver_name == _GROWATT_INVERTER_MODBUS:
                from ..drivers.growattinvertermodbus import GrowattInverterModbus
                gc_collect()
                self.__load_device(log, name, GrowattInverterModbus, meta)
            elif driver_name == _JK_BMS_BD4:
                from ..drivers.jkbmsbd4 import JkBmsBd4
                gc_collect()
                self.__load_device(log, name, JkBmsBd4, meta)
            elif driver_name == _LLT_POWER_BMS_V4_BLE:
                from ..drivers.lltpowerbmsv4ble import LltPowerBmsV4Ble
                gc_collect()
                self.__load_device(log, name, LltPowerBmsV4Ble, meta)
            elif driver_name == _MQTT_BATTERY:
                from ..drivers.mqttbattery import MqttBattery
                gc_collect()
                self.__load_device(log, name, MqttBattery, meta, mqtt)
            elif driver_name == _MQTT_CONSUMPTION:
                from ..drivers.mqttconsumption import MqttConsumption
                gc_collect()
                self.__load_device(log, name, MqttConsumption, meta, mqtt)
            elif driver_name == _SHELLY_CHARGER:
                from ..drivers.shellycharger import ShellyCharger
                gc_collect()
                self.__load_device(log, name, ShellyCharger, meta)
            elif driver_name == _VICTRON_MPPT:
                from ..drivers.victronmppt import VictronMppt
                gc_collect()
                self.__load_device(log, name, VictronMppt, meta)
            else:
                log.error('Unknown driver for device ', name, ': ', driver_name)

    def get_by_type(self, type: str):
        return tuple(x for x in self.__devices if type in x.device_types)

    @property
    def devices(self):
        return self.__devices
    
    def __load_device(self, log, name, driver, config, *args):
        try:
            log.send('devices', 'Loading device ', name, ' with driver ', driver.__name__)
            instance = driver(name, config, *args)
            self.__devices.append(instance)
            gc_collect()
        except Exception as e:
            from sys import print_exception
            from ..core.singletons import Singletons
            log.error('Failed to initialize device ', name, ': ', e)
            print_exception(e, Singletons.log.trace)