from asyncio import sleep
from collections import deque
from micropython import const
from random import randrange
from time import time
from ..core.types import CallbackCollection, CommandBundle
from .devices import Devices

_BATTERY_LOG_NAME = const('battery')

class Battery:
    class BatteryBundle:
            def __init__(self, battery):
                self.online = True
                self.battery = battery


    def __init__(self, config: dict, devices: Devices):
        self.__commands = deque((), 10)

        self.__on_battery_data = CallbackCollection()

        self.__battery_data = dict()
        self.__batteries = list()
        from ..core.types_singletons import devicetype
        for device in devices.devices:
            if devicetype.battery not in device.device_types:
                continue
            device.on_battery_data.add(self.__on_device_data)
            self.__batteries.append(device)
            self.__battery_data[device.name] = None



    async def run(self):
        if len(self.__batteries) == 0:
            from ..core.logging_singleton import log
            log.send(_BATTERY_LOG_NAME, 'No batteries found.')
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
        self.__on_battery_data.run_all(data.name)
                    
    @property
    def battery_data(self):
        return self.__battery_data

    @property
    def on_battery_data(self):
        return self.__on_battery_data
