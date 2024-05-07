import asyncio, sys, time
from .interfaces.inverterinterface import InverterInterface
from ..core.microaiohttp import ClientSession
from ..core.logging_singleton import log
from ..core.userinterface_singleton import leds
from ..core.types import CallbackCollection, EnumEntry, InverterStatus, PowerLut
from ..core.types_singletons import bool2string, devicetype, inverterstatus

class AhoyCommand(EnumEntry):
    pass

class AhoyCommandValues:
    def __init__(self):
        self.__dict = {}
        self.turn_on = AhoyCommand('turn_on', self.__dict)
        self.turn_off = AhoyCommand('turn_off', self.__dict)
        self.reset = AhoyCommand('reset', self.__dict)
        self.change_power = AhoyCommand('change_power', self.__dict)

ahoycommand = AhoyCommandValues()

class AhoyDtu(InverterInterface):
    __ahoy_state_to_internal_state = {
        0: inverterstatus.fault,
        1: inverterstatus.off,
        2: inverterstatus.on,
        3: inverterstatus.off,
        4: inverterstatus.fault
    }

    def __init__(self, name, config):
        self.__device_types = (devicetype.inverter,)
        self.__log = log.get_custom_logger(name)
        self.__host, self.__port = config['host'].split(':')
        self.__port = int(self.__port)

        self.__on_status_change = CallbackCollection()
        self.__on_power_change = CallbackCollection()

        self.__tx_event = asyncio.Event()
        self.__last_tx = time.time()
        self.__last_rx = time.time()

        self.__last_tick = time.time()

        self.__service_task = asyncio.create_task(self.__tick())

        self.__name = name
        self.__id = config['id']
        self.__power_lut = PowerLut(config['power_lut'])
        self.__shall_status = inverterstatus.off
        self.__current_status = inverterstatus.syncing
        self.__shall_percent = self.__power_lut.min_percent
        self.__current_percent = None
        self.__current_power = None
        self.__last_command_type = None
        self.__last_status_command_type = None
        self.__energy = 0 # unusual unit: Ws , too keep things integer can only divide once by 3600

###################
# General
###################

    @property
    def name(self):
        return self.__name
    
    @property
    def device_types(self):
        return self.__device_types
    
###################
# Status
###################
    
    async def switch_inverter(self, on: bool):
        old_value = self.__shall_status
        self.__shall_status = inverterstatus.on if on else inverterstatus.off
        if old_value != self.__shall_status:
            self.__shall_percent = self.__power_lut.min_percent
            self.__log.send(f'New target state: {self.__shall_status}')
            self.__tx_event.set()

    def get_inverter_status(self):
        return self.__current_status
    
    @property
    def __is_status_synced(self):
        return self.__shall_status == self.__current_status
    
    @property
    def on_inverter_status_change(self):
        return self.__on_status_change
    
###################
# Power
###################
    
    async def set_inverter_power(self, power):
        old_percent = self.__shall_percent
        self.__shall_percent, shall_power = self.__power_lut.get_percent(power)
        if old_percent != self.__shall_percent:
            self.__log.send(f'New power target: {self.__shall_percent}% / {shall_power}W.')
            self.__tx_event.set()
        return shall_power
        
    def get_inverter_power(self):
        if  self.__current_status != inverterstatus.on:
            return 0
        if not self.__is_power_synced:
            return None
        return self.__current_power
    
    @property
    def min_power(self):
        return self.__power_lut.min_power

    @property
    def max_power(self):
        return self.__power_lut.max_power
    
    @property
    def __is_power_synced(self):
        return self.__shall_percent == self.__current_percent
    
    @property
    def on_inverter_power_change(self):
        return self.__on_power_change
    
###################
# Energy
###################

    def __add_energy(self, seconds):
        if self.__current_status != inverterstatus.on or self.__current_power is None:
            return
        self.__energy += self.__current_power * seconds

    def get_inverter_energy(self):
        energy = self.__energy / 3600
        self.__energy = 0
        self.__log.send(f'{energy:.1f} Wh fed since last check.')
        return energy
        
###################
# Internal
###################
    
    async def __tick(self):
        while True:
            try:
                now = time.time()
                seconds = now - self.__last_tick
                self.__last_tick = now
                if seconds > 0:
                    self.__add_energy(seconds)
                await self.__sync_to_inverters()
                if not self.__is_status_synced or not self.__is_power_synced or now - self.__last_rx > 30:
                    await self.__sync_from_inverters()
            except Exception as e:
                log.error(f'Ahoydtu cycle failed: {e}')
                sys.print_exception(e, log.trace)
            await asyncio.sleep(1.0)

    def __update(self, status, power_percent):
        last_status = self.__current_status
        if status != inverterstatus.on \
            and self.__shall_status == inverterstatus.on \
            and self.__current_status == inverterstatus.on:
            # inverter deactivated itself
            self.__current_status = inverterstatus.fault
        else:
            self.__current_status = status

        last_percent = self.__current_percent
        if power_percent is None or power_percent > 100:
            self.__current_power = None
            self.__current_percent = None
        else:
            self.__current_power, self.__current_percent = self.__power_lut.get_power(power_percent)
        status_str = self.__current_status if self.__is_status_synced else f'{self.__current_status}->{self.__shall_status}'
        power_str = self.__current_percent if self.__is_power_synced else f'{self.__current_percent}->{self.__shall_percent}'
        self.__log.send(f'State={status_str} Power={power_str} %')

        if last_status != self.__current_status:
            self.__on_status_change.run_all(self.__current_status)
        if last_percent != self.__current_percent:
            self.__on_power_change.run_all(self.__current_power)

    def __get_next_request(self):
        if self.__is_status_synced and self.__is_power_synced:
            return None

        now = time.time()
        delta = now - self.__last_tx
        wait_time = self.__get_wait_time()
        if delta < wait_time:
            return None

        #prio 1: switch off
        if not self.__is_status_synced and self.__shall_status != inverterstatus.on:
            self.__last_command_type = ahoycommand.turn_off
            self.__last_status_command_type = ahoycommand.turn_off
            self.__log.send('Sending switch off command.')
            return f'"id":{self.__id},"cmd":"power","val":0'
        
        #prio 2: reset (a power change will not survive reset, so reset first)
        if not self.__is_status_synced and self.__shall_status == inverterstatus.on and self.__last_status_command_type  == ahoycommand.turn_on:
            self.__last_command_type = ahoycommand.reset
            self.__last_status_command_type = ahoycommand.reset
            self.__log.send('Sending reset command.')
            return f'"id":{self.__id},"cmd":"restart"'
        
        #prio 3: change power
        if not self.__is_power_synced:
            self.__last_command_type = ahoycommand.change_power
            self.__log.send('Sending power change request.')
            return f'"id":{self.__id},"cmd":"limit_nonpersistent_relative","val":{self.__shall_percent}'
        
        #prio 4: switch on
        if not self.__is_status_synced and self.__shall_status == inverterstatus.on:
            self.__last_command_type = ahoycommand.turn_on
            self.__last_status_command_type = ahoycommand.turn_on
            self.__log.send('Sending switch on command.')
            return f'"id":{self.__id},"cmd":"power","val":1'
        
        return None

    def __get_wait_time(self):
        if self.__last_command_type in (ahoycommand.turn_on, ahoycommand.turn_off):
            if self.__is_status_synced:
                return 0
            else:
                return 30
        elif self.__last_command_type == ahoycommand.reset:
            if self.__is_status_synced:
                return 0
            else:
                return 60
        elif self.__last_command_type == ahoycommand.change_power:
            if self.__is_power_synced:
                return 0
            else:
                return 30
        return 0

    async def __sync_to_inverters(self):
        if not self.__tx_event.is_set():
            return
        request = self.__get_next_request()
        if request is None:
            return
        with self.__create_session() as session:
            await self.__post(session, 'ctrl', '{'+request+'}')
            self.__last_tx = time.time()
            self.__tx_event.clear()
            return True

    async def __sync_from_inverters(self):
        with self.__create_session() as session:
            json = await self.__get(session, f'inverter/id/{self.__id}')
        try:
            status = self.__ahoy_state_to_internal_state.get(int(json['status']), inverterstatus.fault)
            limit = int(json['power_limit_read'])
            self.__update(status, limit)
            if False in (self.__is_status_synced, self.__is_power_synced):
                self.__tx_event.set()
            self.__last_rx = time.time()
        except Exception as e:
            self.__log.send(f'No status available.')
            self.__update(None, None)
    
    def __create_session(self):
        return ClientSession(self.__host, self.__port)

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
                    if json["success"] in (True, "true"):
                        leds.notify_control()
                        return json
                self.__log.send(f'Inverter command {query} failed with code {status}.')
            except Exception as e:
                self.__log.send(f'Inverter command {query} failed: {str(e)}, {i} retries left.')
            await asyncio.sleep(1)
        return None
