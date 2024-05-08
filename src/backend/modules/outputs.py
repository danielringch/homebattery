from asyncio import create_task, Event
from collections import deque
from sys import print_exception
from ..core.backendmqtt import Mqtt
from ..core.types import CommandBundle
from .supervisor import Supervisor
from .battery import Battery
from .charger import Charger
from .inverter import Inverter
from .solar import Solar

class Outputs:
    def __init__(self, mqtt: Mqtt, supervisor: Supervisor, battery: Battery, charger: Charger, inverter: Inverter, solar: Solar):
        self.__commands = deque((), 10)
        self.__command_event = Event()
        from ..core.logging_singleton import log
        self.__log = log.get_custom_logger('output')
        self.__trace = log.trace
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

        self.__task = create_task(self.__run())

    async def __run(self):
        while True:
            try:
                await self.__command_event.wait()
                self.__command_event.clear()
                while len(self.__commands) > 0:
                    await self.__commands.popleft().run()
            except Exception as e:
                self.__log.send(f'Charger cycle failed: {e}')
                print_exception(e, self.__trace)

    async def __send_battery_data(self, name):
        changed_battery = self.__battery.battery_data[name]
        if changed_battery is not None and changed_battery.valid and not changed_battery.is_forwarded:
            await self.__mqtt.send_battery(changed_battery)

    async def __send_charger_energy(self, energy):
        await self.__mqtt.send_charger_energy(energy)

    async def __send_inverter_energy(self, energy):
        await self.__mqtt.send_inverter_energy(energy)

    async def __send_solar_energy(self, energy):
        await self.__mqtt.send_solar_energy(energy)

    def __on_battery_data(self, name):
        self.__commands.append(CommandBundle(self.__send_battery_data, (name,)))
        self.__command_event.set()

        total_capacity = 0
        for battery in self.__battery.battery_data.values():
            if battery is None or not battery.valid:
                break
            total_capacity += battery.c
        else:
            self.__display.update_battery_capacity(total_capacity)

    def __on_charger_energy(self, energy):
        self.__commands.append(CommandBundle(self.__send_charger_energy, (energy,)))
        self.__command_event.set()

    def __on_inverter_energy(self, energy):
        self.__commands.append(CommandBundle(self.__send_inverter_energy, (energy,)))
        self.__command_event.set()

    def __on_solar_energy(self, energy):
        self.__commands.append(CommandBundle(self.__send_solar_energy, (energy,)))
        self.__command_event.set()
