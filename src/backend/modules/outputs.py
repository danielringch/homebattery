from asyncio import create_task
from ..core.backendmqtt import Mqtt
from ..core.logging import CustomLogger
from ..core.types import CommandFiFo, STATUS_ON, MEASUREMENT_CAPACITY, MEASUREMENT_CURRENT, MEASUREMENT_POWER, MEASUREMENT_STATUS
from ..core.types import TYPE_CHARGER, TYPE_INVERTER, TYPE_SOLAR
from .supervisor import Supervisor
from .consumption import Consumption
from .battery import Battery
from .charger import Charger
from .devices import Devices
from .inverter import Inverter
from .solar import Solar

class Outputs:
    def __init__(self, mqtt: Mqtt, supervisor: Supervisor, devices: Devices, consumption: Consumption, \
                 battery: Battery, charger: Charger, inverter: Inverter, solar: Solar):
        from ..core.singletons import Singletons
        self.__commands = CommandFiFo(128)
        self.__log: CustomLogger = Singletons.log.create_logger('output')
        self.__mqtt = mqtt
        self.__supervisor = supervisor
        self.__consumption = consumption
        self.__battery = battery
        self.__charger = charger
        self.__inverter = inverter
        self.__solar = solar

        for charger_device in devices.get_by_type(TYPE_CHARGER):
            charger_device.on_charger_data.append(self.__on_charger_device_data)
        for inverter_device in devices.get_by_type(TYPE_INVERTER):
            inverter_device.on_inverter_data.append(self.__on_inverter_device_data)
        for solar_device in devices.get_by_type(TYPE_SOLAR):
            solar_device.on_solar_data.append(self.__on_solar_device_data)

        self.__charger.on_summary_data.append(self.__on_charger_summary_data)
        self.__inverter.on_summary_data.append(self.__on_inverter_summary_data)
        self.__solar.on_summary_data.append(self.__on_solar_summary_data)

        self.__ui = Singletons.ui

        self.__mqtt.on_connect.append(self.__on_mqtt_connect)
        
        self.__battery.on_battery_data.append(self.__on_battery_data)

        self.__consumption.on_power.append(self.__on_consumption_power)

        self.__task = create_task(self.__run())

    async def __run(self):
        while True:
            try:
                await self.__commands.wait_and_clear()
                while self.__commands:
                    await self.__commands.popleft()()
            except Exception as e:
                self.__log.error('Cycle failed: ', e)
                self.__log.trace(e)

# charger

    async def __send_charger_summary_data(self):
        data = self.__commands.popleft()
        if MEASUREMENT_STATUS in data:
            self.__ui.switch_charger_on(data[MEASUREMENT_STATUS] == STATUS_ON)
        await self.__mqtt.send_charger_summary(data)

    async def __send_charger_device_data(self):
        name = self.__commands.popleft()
        data = self.__commands.popleft()
        await self.__mqtt.send_charger_device(name, data)

# inverter

    async def __send_inverter_summary_data(self):
        data = self.__commands.popleft()
        if MEASUREMENT_STATUS in data:
            self.__ui.switch_inverter_on(data[MEASUREMENT_STATUS] == STATUS_ON)
        if MEASUREMENT_POWER in data:
            self.__ui.update_inverter_power(data[MEASUREMENT_POWER])
        await self.__mqtt.send_inverter_summary(data)

    async def __send_inverter_device_data(self):
        name = self.__commands.popleft()
        data = self.__commands.popleft()
        await self.__mqtt.send_inverter_device(name, data)

# solar

    async def __send_solar_summary_data(self):
        data = self.__commands.popleft()
        if MEASUREMENT_STATUS in data:
            self.__ui.switch_solar_on(data[MEASUREMENT_STATUS] == STATUS_ON)
        if MEASUREMENT_POWER in data:
            self.__ui.update_solar_power(data[MEASUREMENT_POWER])
        await self.__mqtt.send_solar_summary(data)

    async def __send_solar_device_data(self):
        name = self.__commands.popleft()
        data = self.__commands.popleft()
        await self.__mqtt.send_solar_device(name, data)

# battery

    async def __send_battery_summary(self):
        capacity = self.__commands.popleft()
        current = self.__commands.popleft()
        data = {
            MEASUREMENT_CAPACITY: float(capacity),
            MEASUREMENT_CURRENT: float(current)
        }
        await self.__mqtt.send_battery_summary(data)

    async def __send_battery_device(self):
        name = self.__commands.popleft()
        changed_battery = self.__battery.battery_data[name]
        if changed_battery is not None and changed_battery.valid and not changed_battery.is_forwarded:
            await self.__mqtt.send_battery_device(changed_battery)

#consumption

    async def __send_consumption_power(self):
        power = self.__commands.popleft()
        self.__ui.update_consumption(power)
        data = {MEASUREMENT_POWER: int(power)}
        await self.__mqtt.send_sensor_device('grid', data)

# other

    async def __send_all_summary(self):
        await self.__mqtt.send_inverter_summary(self.__inverter.get_summary_data())
        await self.__mqtt.send_solar_summary(self.__solar.get_summary_data())
        await self.__mqtt.send_charger_summary(self.__charger.get_summary_data())

# callback handlers

    def __on_mqtt_connect(self):
        self.__commands.append(self.__send_all_summary)

    def __on_charger_summary_data(self, data):
        self.__commands.append(self.__send_charger_summary_data)
        self.__commands.append(data)

    def __on_inverter_summary_data(self, data):
        self.__commands.append(self.__send_inverter_summary_data)
        self.__commands.append(data)

    def __on_solar_summary_data(self, data):
        self.__commands.append(self.__send_solar_summary_data)
        self.__commands.append(data)

    def __on_charger_device_data(self, sender, data):
        self.__commands.append(self.__send_charger_device_data)
        self.__commands.append(sender.name)
        self.__commands.append(data)

    def __on_inverter_device_data(self, sender, data):
        self.__commands.append(self.__send_inverter_device_data)
        self.__commands.append(sender.name)
        self.__commands.append(data)

    def __on_solar_device_data(self, sender, data):
        self.__commands.append(self.__send_solar_device_data)
        self.__commands.append(sender.name)
        self.__commands.append(data)

    def __on_battery_data(self, name):
        self.__commands.append(self.__send_battery_device)
        self.__commands.append(name)

        total_current = 0
        total_capacity = 0
        for battery in self.__battery.battery_data.values():
            if battery is None or not battery.valid:
                break
            total_current += battery.i
            total_capacity += battery.c
        else:
            self.__ui.update_battery_capacity(total_capacity)
            self.__commands.append(self.__send_battery_summary)
            self.__commands.append(total_capacity)
            self.__commands.append(total_current)

    def __on_consumption_power(self, power):
        self.__commands.append(self.__send_consumption_power)
        self.__commands.append(power)
