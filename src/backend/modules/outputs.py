from asyncio import create_task, Event
from micropython import const
from sys import print_exception
from ..core.backendmqtt import Mqtt
from ..core.types import CommandFiFo, STATUS_ON
from .supervisor import Supervisor
from .battery import Battery
from .charger import Charger
from .inverter import Inverter
from .solar import Solar

_OUTPUT_LOG_NAME = const('output')

class Outputs:
    def __init__(self, mqtt: Mqtt, supervisor: Supervisor, battery: Battery, charger: Charger, inverter: Inverter, solar: Solar):
        from ..core.singletons import Singletons
        self.__commands = CommandFiFo()
        self.__log = Singletons.log.create_logger(_OUTPUT_LOG_NAME)
        self.__mqtt = mqtt
        self.__supervisor = supervisor
        self.__battery = battery
        self.__charger = charger
        self.__inverter = inverter
        self.__solar = solar

        self.__display = Singletons.display
        self.__leds = Singletons.leds

        self.__mqtt.on_live_consumption.add(self.__on_live_consumption)
        self.__mqtt.on_connect.add(self.__on_mqtt_connect)
        self.__battery.on_battery_data.add(self.__on_battery_data)
        self.__charger.on_energy.add(self.__on_charger_energy)
        self.__charger.on_status.add(self.__on_charger_status)
        self.__inverter.on_energy.add(self.__on_inverter_energy)
        self.__inverter.on_power.add(self.__on_inverter_power)
        self.__inverter.on_status.add(self.__on_inverter_status)
        self.__solar.on_energy.add(self.__on_solar_energy)
        self.__solar.on_power.add(self.__on_solar_power)
        self.__solar.on_status.add(self.__on_solar_status)

        self.__task = create_task(self.__run())

    async def __run(self):
        while True:
            try:
                await self.__commands.wait_and_clear()
                while not self.__commands.empty:
                    await self.__commands.popleft()()
            except Exception as e:
                self.__log.error('Charger cycle failed: ', e)
                from ..core.singletons import Singletons
                print_exception(e, Singletons.log.trace)

    async def __send_battery_data(self):
        name = self.__commands.popleft()
        changed_battery = self.__battery.battery_data[name]
        if changed_battery is not None and changed_battery.valid and not changed_battery.is_forwarded:
            await self.__mqtt.send_battery(changed_battery)

    async def __send_charger_energy(self):
        energy = self.__commands.popleft()
        await self.__mqtt.send_charger_energy(energy)

    async def __send_charger_status(self):
        status = self.__commands.popleft()
        await self.__mqtt.send_charger_status(status)

    async def __send_inverter_energy(self):
        energy = self.__commands.popleft()
        await self.__mqtt.send_inverter_energy(energy)

    async def __send_inverter_power(self):
        power = self.__commands.popleft()
        self.__display.update_inverter_power(power)
        await self.__mqtt.send_inverter_power(power)

    async def __send_inverter_status(self):
        status = self.__commands.popleft()
        await self.__mqtt.send_inverter_status(status)

    async def __send_solar_energy(self):
        energy = self.__commands.popleft()
        await self.__mqtt.send_solar_energy(energy)

    async def __send_solar_power(self):
        power = self.__commands.popleft()
        self.__display.update_solar_power(power)

    async def __send_solar_status(self):
        status = self.__commands.popleft()
        await self.__mqtt.send_solar_status(status)

    async def __send_all_status(self):
        await self.__mqtt.send_inverter_status(self.__inverter.get_status())
        await self.__mqtt.send_solar_status(self.__solar.get_status())
        await self.__mqtt.send_charger_status(self.__charger.get_status())

    def __on_mqtt_connect(self):
        self.__commands.append(self.__send_all_status)

    def __on_live_consumption(self, power):
        self.__display.update_consumption(power)

    def __on_battery_data(self, name):
        self.__commands.append(self.__send_battery_data)
        self.__commands.append(name)

        total_capacity = 0
        for battery in self.__battery.battery_data.values():
            if battery is None or not battery.valid:
                break
            total_capacity += battery.c
        else:
            self.__display.update_battery_capacity(total_capacity)

    def __on_charger_energy(self, energy):
        self.__commands.append(self.__send_charger_energy)
        self.__commands.append(energy)

    def __on_charger_status(self, status):
        self.__leds.switch_charger_on(status == STATUS_ON)
        self.__commands.append(self.__send_charger_status)
        self.__commands.append(status)

    def __on_inverter_energy(self, energy):
        self.__commands.append(self.__send_inverter_energy)
        self.__commands.append(energy)

    def __on_inverter_power(self, power):
        self.__commands.append(self.__send_inverter_power)
        self.__commands.append(power)

    def __on_inverter_status(self, status):
        self.__leds.switch_inverter_on(status == STATUS_ON)
        self.__commands.append(self.__send_inverter_status)
        self.__commands.append(status)

    def __on_solar_energy(self, energy):
        self.__commands.append(self.__send_solar_energy)
        self.__commands.append(energy)

    def __on_solar_power(self, power):
        self.__commands.append(self.__send_solar_power)
        self.__commands.append(power)

    def __on_solar_status(self, status):
        self.__leds.switch_solar_on(status == STATUS_ON)
        self.__commands.append(self.__send_solar_status)
        self.__commands.append(status)
