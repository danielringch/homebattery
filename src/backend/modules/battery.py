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

        self.__next_run = time.time()

        self.__batteries = list()
        for device in devices.devices:
            if devicetype.battery not in device.device_types:
                continue
            self.__batteries.append(self.BatteryBundle(device))

        self.__battery_data = list()


    async def run(self):
        if len(self.__batteries) == 0:
            log.battery('No batteries found.')
            return

        while True:
            await asyncio.sleep(0.1)
            if time.time() < self.__next_run:
                continue

            ble_instance.activate()

            try:
                success = True
                self.__battery_data.clear()
                for battery in sorted(self.__batteries, key=lambda x: x.online):
                    success &= await self.__read_battery(battery)
                    if not success:
                        break
            
                if not success:
                    log.battery('Not all batteries responsed.')
                    self.__battery_data.clear()
                    self.__next_run = time.time() + random.randrange(2, 5, 1)
                else:
                    self.__on_battery_data.run_all()
                    self.__next_run = time.time() + 60
            finally:
                ble_instance.deactivate()
    
    @property
    def battery_data(self):
        return self.__battery_data

    @property
    def on_battery_data(self):
        return self.__on_battery_data


    async def __read_battery(self, battery: BatteryBundle):
        try:
            battery_data = await battery.battery.read_battery()
            if battery_data is None:
                battery.online = False
                raise Exception('Battery did not response.')
            battery.online = True
            self.__battery_data.append(battery_data)
            return True
        except Exception as e:
            log.battery(f'Battery query failed: {e}') 
            return False
