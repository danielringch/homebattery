from asyncio import sleep
from random import randrange
from time import time
from ..core.types import run_callbacks
from .devices import Devices

class Battery:
    class BatteryBundle:
            def __init__(self, battery):
                self.online = True
                self.battery = battery


    def __init__(self, config: dict, devices: Devices):
        self.__on_battery_data = list()

        self.__battery_data = dict()
        from ..core.types import TYPE_BATTERY
        self.__batteries = devices.get_by_type(TYPE_BATTERY)
        for battery in self.__batteries:
            self.__battery_data[battery.name] = None
            battery.on_battery_data.append(self.__on_device_data)

    async def run(self):
        from ..core.singletons import Singletons
        if len(self.__batteries) == 0:
            Singletons.log.send('battery', 'No batteries found.')
            return

        while True:
            now = time()
            for device in self.__batteries:
                data = self.__battery_data[device.name]
                if data is None or data.timestamp + 60 < now:
                    await device.read_battery()
            await sleep(randrange(2, 5, 1))

    def __on_device_data(self, data):
        self.__battery_data[data.name] = data
        run_callbacks(self.__on_battery_data, data.name)
                    
    @property
    def battery_data(self):
        return self.__battery_data

    @property
    def on_battery_data(self):
        return self.__on_battery_data
