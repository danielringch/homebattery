import asyncio, random, time
from collections import deque
from ..core.logging import *
from ..core.microblecentral import ble_instance
from ..core.types import CallbackCollection, CommandBundle, devicetype
from .devices import Devices

class Battery:
    class BatteryBundle:
            def __init__(self, battery):
                self.online = True
                self.battery = battery


    def __init__(self, config: dict, devices: Devices):
        self.__commands = deque((), 10)

        self.__on_battery_data = CallbackCollection()

        self.__batteries = list()
        for device in devices.devices:
            if devicetype.battery not in device.device_types:
                continue
            self.__batteries.append(device)

        self.__battery_data = dict()


    async def run(self):
        if len(self.__batteries) == 0:
            log.battery('No batteries found.')
            return

        while True:
            now = time.time()
            for device in self.__batteries:
                data = self.__battery_data.get(device.name, None)
                if data is None or data.timestamp + 60 < now:
                    new_data = await device.read_battery()
                    self.__battery_data[device.name] = new_data
                    if new_data is None:
                        log.battery(f'Failed to read battery {device.name}: did not respond.')
                    else:
                        self.__on_battery_data.run_all(device.name)
            await asyncio.sleep(random.randrange(2, 5, 1))
                    
    @property
    def battery_data(self):
        return self.__battery_data

    @property
    def on_battery_data(self):
        return self.__on_battery_data
