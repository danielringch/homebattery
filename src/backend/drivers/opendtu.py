import asyncio, sys, time

from ..core.microaiohttp import ClientSession, BasicAuth
from ..core.logging import *
from ..core.leds import leds
from ..core.types import bool2string, CallbackCollection, PowerLut
from ..core import devicetype

class OpenDtu:
    class Device:
        def __init__(self, name, serial, lut):
            self.__name = name
            self.__log = log.get_custom_logger(self.__name)
            self.__serial = serial
            self.__power_lut = PowerLut(lut)
            self.__shall_on = False
            self.__is_on = None
            self.__shall_percent = self.__power_lut.min_percent
            self.__current_percent = None
            self.__current_power = None
            self.__last_command = 0
            self.__energy = 0 # unusual unit: Ws , too keep things integer can only divide once by 3600

        @property
        def name(self):
            return self.__name
        
        @property
        def serial(self):
            return self.__serial
        
        @property
        def lut(self):
            return self.__power_lut

        @property
        def status(self):
            return self.__is_on
        
        @property
        def status_synced(self):
            return self.__shall_on == self.__is_on

        def set_status(self, on: bool):
            self.__shall_on = on
            if not self.power_synced:
                self.__log.send(f'New target state: on={bool2string[self.__shall_on]}')

        def get_status_request(self):
            now = time.time()
            delta = now - self.__last_command
            if self.status_synced:
                return None
            if self.__shall_on and delta < 60:
                return None
            if not self.__shall_on and delta < 30:
                return None
            self.__last_command = now
            if self.__shall_on:
                return f'"serial":"{self.__serial}","restart":true'
            return f'"serial":"{self.__serial}","power":false'

        @property
        def power(self):
            return self.__current_power
        
        @property
        def min_power(self):
            return self.lut.min_power

        @property
        def max_power(self):
            return self.lut.max_power
        
        @property
        def power_synced(self):
            return self.__shall_percent == self.__current_percent
        
        def set_power(self, power: int):
            self.__shall_percent, shall_power = self.__power_lut.get_percent(power)
            if not self.power_synced:
                self.__log.send(f'New power target: {self.__shall_percent}% / {shall_power}W.')
            return self.__shall_percent, shall_power
        
        def get_power_request(self):
            now = time.time()
            if self.power_synced or now - self.__last_command < 10:
                return None
            self.__last_command = now
            return f'"serial":"{self.__serial}","limit_type":1, "limit_value":{self.__shall_percent}'

        def update(self, on, power_percent):
            self.__is_on = on
            if power_percent is None:
                self.__current_power = None
                self.__current_percent = None
            else:
                self.__current_power, self.__current_percent = self.__power_lut.get_power(power_percent)
            self.__log.send(f'State: on={bool2string[self.__is_on]} power={self.__current_power}W')

        def add_energy(self, seconds):
            if not self.__is_on or self.__current_power is None:
                return
            self.__energy += self.__current_power * seconds

        def get_energy(self):
            energy = self.__energy / 3600
            self.__energy = 0
            return energy

    def __init__(self, name, config):
        self.__device_types = (devicetype.inverter,)
        self.__log = log.get_custom_logger(name)
        self.__host, self.__port = config['host'].split(':')
        self.__port = int(self.__port)
        self.__auth = BasicAuth("admin", config['password'])

        self.__last_status = None
        self.__on_status_change = CallbackCollection()

        self.__devices = []
        for name, values in config["devices"].items():
            device = self.Device(name, values["serial"], values["power_lut"])
            self.__devices.append(device)
            self.__log.send(f'{device.name} available with {device.lut.min_power} W - {device.lut.max_power} W output power.')

        self.__devices_by_power = sorted(self.__devices, key=lambda x: x.lut.max_power, reverse=True)

        self.__tx_event = asyncio.Event()
        self.__last_tx = time.time()
        self.__last_rx = time.time()

        self.__last_tick = time.time()

        self.__service_task = asyncio.create_task(self.__tick())

    async def switch_inverter(self, on):
        for device in self.__devices:
            device.set_status(on)
            if not device.status_synced:
                device.set_power(0)
        self.__tx_event.set()

    async def is_inverter_on(self):
        on = False
        for device in self.__devices:
            if device.status_synced and device.status:
                return True
            if not device.status_synced:
                on = None
        return on
    
    @property
    def on_inverter_status_change(self):
        return self.__on_status_change

    async def set_inverter_power(self, power):
        reachable_inverters = [x for x in self.__devices_by_power if x.power is not None]
        old_power = sum((x.power if x.power is not None else x.max_power for x in self.__devices), 0)
        new_power = sum((x.max_power for x in self.__devices if x.power is None), 0)
        inverters_to_change = []
        delta = power - old_power
        if delta > 0:
            for inverter in sorted(reachable_inverters, key=lambda x: x.power):
                if delta > 0:
                    inverters_to_change.append(inverter)
                    delta -= inverter.max_power - inverter.power
                else:
                    new_power += inverter.power
        elif delta < 0:
            for inverter in sorted(reachable_inverters, key=lambda x: x.power, reverse=True):
                if delta < 0:
                    inverters_to_change.append(inverter)
                    delta += inverter.power - inverter.min_power
                else:
                    new_power += inverter.power
        else:
            return power, 0
        
        delta = power - old_power
        for inverter in inverters_to_change:
            target_power = inverter.power + delta
            _, actual_power = inverter.set_power(target_power)
            new_power += actual_power
            delta -= actual_power - inverter.power

        self.__tx_event.set()

        # old_power = 0
        # new_power = 0
        # relative_power = power / self.__total_max_power
        # last_inverter = self.__devices_by_power[-1]
        # for device in self.__devices_by_power:
        #     old_power += device.power_absolute
        #     target_power = round(device.lut.max_power * relative_power) if device is not last_inverter else power
        #     if not device.is_on:
        #         target_power = 0
        #     _, actual_power = device.set_power(target_power)
        #     new_power += actual_power
        #     power -= actual_power
        # self.__tx_event.set()

        return new_power, new_power - old_power
        
    async def get_inverter_power(self):
        power = 0
        for device in self.__devices:
            if device.power is None:
                return None
            power += device.power
        return power
        
    def get_inverter_energy(self):
        energy = sum((x.get_energy() for x in self.__devices), 0)
        self.__log.send(f'{energy:.1f} Wh fed since last check.')
        return energy
    
    @property
    def device_types(self):
        return self.__device_types
    
    async def __tick(self):
        while True:
            try:
                now = time.time()
                seconds = now - self.__last_tick
                self.__last_tick = now
                if seconds > 0:
                    for device in self.__devices:
                        device.add_energy(seconds)
                if self.__tx_event.is_set() or now - self.__last_tx > 30:
                    if await self.__sync_to_inverters():
                        self.__tx_event.clear()
                        self.__last_tx = now
                if any((not x.status_synced) or (not x.power_synced) for x in self.__devices) or now - self.__last_rx > 30:
                    self.__last_rx = now
                    await self.__sync_from_inverters()
            except Exception as e:
                log.error(f'Opendtu cycle failed: {e}')
                sys.print_exception(e, log.trace)
            await asyncio.sleep(1.0)
    
    async def __sync_to_inverters(self):
        with self.__create_session() as session:
            switch_requests = (x.get_status_request() for x in self.__devices)
            switch_request_payload = ','.join(x for x in switch_requests if x is not None)
            if len(switch_request_payload) > 0:
                self.__log.send(f'Sending switch request.')
                await self.__post(session, 'power/config', 'data={'+switch_request_payload+'}')
                return True

            power_requests = (x.get_power_request() for x in self.__devices)
            power_request_payload = ','.join(x for x in power_requests if x is not None)
            if len(power_request_payload) > 0:
                self.__log.send(f'Sending power change request.')
                await self.__post(session, 'limit/config', 'data={'+power_request_payload+'}')
                return True
            
            return False

    async def __sync_from_inverters(self):
        with self.__create_session() as session:
            json = await self.__get(session, 'livedata/status')
        try:
            data = {x['serial']: (x['producing'], x['reachable'], x['limit_relative']) for x in json['inverters']}
            for device in self.__devices:
                values = data.get(device.serial, (None, None, None))
                device.update(values[0], values[2])
                if False in (device.status_synced, device.power_synced):
                    self.__tx_event.set()
            new_status = await self.is_inverter_on()
            if new_status != self.__last_status:
                self.__on_status_change.run_all(new_status)
                self.__last_status = new_status
        except Exception as e:
            self.__log.send(f'No status available.')
            for device in self.__devices:
                device.update(None, None)
    
    def __create_session(self):
        return ClientSession(self.__host, self.__port, self.__auth)

    async def __get(self, session, query):
        for i in reversed(range(3)):
           try:
               response = await session.get(f'api/{query}')
               status = response.status
               if status >= 200 and status <= 299:
                   json = await response.json()
                   leds.notify_control()
                   return json
               else:
                   self.__log.send(f'Inverter query {query} failed with code {status}, {i} retries left.')
           except Exception as e:
               self.__log.send(f'Inverter query {query} failed: {str(e)}, {i} retries left.')
           await asyncio.sleep(1)
        return None
    
    async def __post(self, session, query, payload):
        for i in reversed(range(3)):
            try:
                header = {'Content-Type': 'text/plain'}
                response = await session.post(f'api/{query}', headers=header, data=payload)
                status = response.status
                if status >= 200 and status <= 299:
                    json = await response.json()
                    if json["type"] == "success":
                        leds.notify_control()
                        return json
                print(payload)
                print(json)
                self.__log.send(f'Inverter command {query} failed with code {status}.')
            except Exception as e:
                self.__log.send(f'Inverter command {query} failed: {str(e)}, {i} retries left.')
            await asyncio.sleep(1)
        return None
