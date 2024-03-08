import asyncio, struct, time

from ..core.microaiohttp import ClientSession, BasicAuth
from ..core.logging import *
from ..core.leds import leds
from ..core import devicetype

class OpenDtu:
    class PowerLut:
        def __init__(self, path):
            self.__lut = None
            self.__lut_length = 0
            self.__min_power = 65535
            self.__max_power = 0
            with open(path, 'r') as file:
                for line in file:
                    line = line.strip().strip('{},')
                    if not line:
                        continue
                    self.__lut_length += 1
                file.seek(0)

                self.__lut = bytearray(3 * self.__lut_length)
                lut_index = 0

                for line in file:
                    line = line.strip().strip('{},')
                    if not line:
                        continue

                    key, value = line.split(':')
                    percent = int(key.strip(' "'))
                    power = int(value.strip())
                    self.__min_power = min(self.__min_power, power)
                    self.__max_power = max(self.__max_power, power)
                    struct.pack_into('@HB', self.__lut, lut_index, power, percent)
                    lut_index += 3

        def get_power(self, percent):
            for i in range(self.__lut_length):
                power_entry, percent_entry = struct.unpack_from('@HB', self.__lut, 3 * i)
                # if percent is smaller than supported, this returns the smallest power possible
                if percent <= percent_entry:
                    return power_entry
            else:
                # if percent is higher than supported, this returns the biggest power possible
                return power_entry
                
        def get_percent(self, power):
            previous_percent = None
            power = max(self.__min_power, min(self.__max_power, power))
            for i in range(self.__lut_length):
                power_entry, percent_entry = struct.unpack_from('@HB', self.__lut, 3 * i)
                if power_entry > power:
                    return previous_percent
                previous_percent = percent_entry
            else:
                return previous_percent
                
        @property
        def min_power(self):
            return self.__min_power

        @property
        def max_power(self):
            return self.__max_power


    def __init__(self, name, config):
        self.__device_types = (devicetype.inverter,)
        self.__log = log.get_custom_logger(name)
        self.__host, self.__port = config['host'].split(':')
        self.__port = int(self.__port)
        self.__serial = config['serial']
        self.__auth = BasicAuth("admin", config['password'])

        self.__power_lut = self.PowerLut(config['power_lut'])
        self.__current_on = False
        self.__current_power = 0
        self.__energy = 0 # unusual unit: Ws , too keep things integer can only divide once by 3600
        self.__last_tick = time.time()

    async def tick(self):
        now = time.time()
        seconds = now - self.__last_tick
        self.__last_tick = now
        if seconds > 0:
            self.__add_energy(seconds)

    async def switch_inverter(self, on):
        with self.__create_session() as session:
            payload = f'"serial":"{self.__serial}","power":{"true" if on else "false"}' 
            payload = 'data={'+payload+'}'
            await self.__post(session, 'power/config', payload)

    async def is_inverter_on(self):
        with self.__create_session() as session:
            json = await self.__get(session, 'livedata/status')
        if json is None:
            self.__current_on = False
            return None
        try:
            ons = {x['serial']: x['producing'] for x in json['inverters']}
            self.__current_on = ons[self.__serial]
            return self.__current_on
        except:
            self.__log.send(f'No status available.')
        self.__current_on = False
        return None

    async def set_inverter_power(self, power):
        with self.__create_session() as session:
            old_percent = await self.__get_current_relative_power(session)
            if old_percent is None:
                self.__current_power = 0
                return self.__current_power, 0

            percent = self.__power_lut.get_percent(max(self.__power_lut.min_power, min(self.__power_lut.max_power, power)))
            try:
                old_power = self.__power_lut.get_power(old_percent)
                if percent == old_percent:
                    self.__current_power = old_power
                    return self.__current_power, 0
            except KeyError:
                old_power = 0
            self.__current_power = self.__power_lut.get_power(percent)
            delta = self.__current_power - old_power
            
            self.__log.send(f'Power change: {delta} W, total: {self.__current_power} W.')

            payload = f'"serial":"{self.__serial}","limit_type":1, "limit_value":{percent}' 
            payload = 'data={'+payload+'}'
            response = await self.__post(session, 'limit/config', payload)
            if response is None:
                return 0, 0
            return self.__current_power, delta
        
    async def get_inverter_power(self):
        with self.__create_session() as session:
            percent = await self.__get_current_relative_power(session)
            if percent is None:
                self.__current_power = 0
            else:
                self.__current_power = self.__power_lut.get_power(percent)
            return self.__current_power
        
    async def get_inverter_energy(self):
        energy = self.__energy / 3600.0
        self.__energy = 0
        self.__log.send(f'{energy:.1f} Wh fed since last check.')
        return energy
    
    @property
    def device_types(self):
        return self.__device_types
        
    async def __get_current_relative_power(self, session):
        json = await self.__get(session, 'limit/status')
        if json is None:
           return None
        
        try:
           powers = {x: y['limit_relative'] for x, y in json.items()}
           return int(powers[self.__serial])
        except:
           self.__log.send(f'No relative power available for inverter {self.__serial}.')
        return None
    
    def __add_energy(self, seconds):
        if not self.__current_on:
            return
        self.__energy += self.__current_power * seconds
    
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
                self.__log.send(f'Inverter command {query} failed with code {status}.')
            except Exception as e:
                self.__log.send(f'Inverter command {query} failed: {str(e)}, {i} retries left.')
            await asyncio.sleep(1)
        return None
