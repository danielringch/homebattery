import asyncio, random, time
from collections import deque
from ..core.logging import *
from ..core.backendmqtt import Mqtt
from ..core.microblecentral import ble_instance
from ..core.types import BatterySummary, CallbackCollection, CommandBundle, devicetype
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

        self.__data = None


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
                data = BatterySummary()
                success = True
                for battery in sorted(self.__batteries, key=lambda x: x.online):
                    success &= await self.__read_battery(battery, data)
                    if not success:
                        break
            
                if not success:
                    log.battery('Not all batteries responsed, no combined battery data for this cycle.')
                    self.__data = None
                    self.__next_run = time.time() + random.randrange(2, 5, 1)
                else:
                    data.timestamp = time.time()
                    self.__data = data

                    log.battery(f'Capacity remaining: {data.capacity_remaining:.1f} Ah')
                    log.battery(f'Minimum cell voltage: {data.min_cell_voltage:.3f} V')
                    log.battery(f'Maximum cell voltage: {data.max_cell_voltage:.3f} V')

                    self.__on_battery_data.run_all()
                    self.__next_run = time.time() + 60
            finally:
                ble_instance.deactivate()


    @property
    def data(self):
        return self.__data


    @property
    def on_battery_data(self):
        return self.__on_battery_data


    async def __read_battery(self, battery: BatteryBundle, summary: BatterySummary):
        try:
            battery_data = await battery.battery.read_battery()
            if battery_data is None:
                battery.online = False
                raise Exception('Battery did not response.')
            battery.online = True
            summary.merge(battery_data)
            return True
        except Exception as e:
            log.battery(f'Battery query failed: {e}') 
            return False
