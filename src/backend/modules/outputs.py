from ..core.backendmqtt import Mqtt
from .supervisor import Supervisor
from .battery import Battery
from .charger import Charger
from .inverter import Inverter
from .solar import Solar

class Outputs:
    def __init__(self, mqtt: Mqtt, supervisor: Supervisor, battery: Battery, charger: Charger, inverter: Inverter, solar: Solar):
        self.__mqtt = mqtt
        self.__supervisor = supervisor
        self.__battery = battery
        self.__charger = charger
        self.__inverter = inverter
        self.__solar = solar

        from ..core.userinterface_singleton import display
        self.__display = display

        self.__battery.on_battery_data.add(self.__on_battery_data)
        self.__charger.on_energy.add(self.__on_charger_energy)
        self.__inverter.on_energy.add(self.__on_inverter_energy)
        self.__solar.on_energy.add(self.__on_solar_energy)

    def __on_battery_data(self, name):
        changed_battery = self.__battery.battery_data[name]
        if changed_battery is not None and changed_battery.valid and not changed_battery.is_forwarded:
            self.__mqtt.send_battery(changed_battery)
        total_capacity = 0
        for battery in self.__battery.battery_data.values():
            if battery is None or not battery.valid:
                break
            total_capacity += battery.c
        else:
            self.__display.update_battery_capacity(total_capacity)

    def __on_charger_energy(self, energy):
        self.__mqtt.send_charger_energy(energy)

    def __on_inverter_energy(self, energy):
        self.__mqtt.send_inverter_energy(energy)

    def __on_solar_energy(self, energy):
        self.__mqtt.send_solar_energy(energy)
