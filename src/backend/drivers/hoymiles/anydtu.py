from asyncio import Event, create_task, sleep
from micropython import const
from time import time
from ..interfaces.inverterinterface import InverterInterface
from ...core.logging import CustomLogger
from ...core.types import PowerLut, run_callbacks, STATUS_FAULT, STATUS_OFF, STATUS_ON, STATUS_SYNCING
from .dtuadapter import DtuAdapter

_CMD_TURN_ON = const('turn_on')
_CMD_TURN_OFF = const('turn_off')
_CMD_RESET = const('reset')
_CMD_CHANGE_POWER = const('change_power')

class AnyDtu(InverterInterface):
    def __init__(self, name, config, adapter: DtuAdapter):
        from ...core.singletons import Singletons
        from ...core.types import TYPE_INVERTER

        self.__device_types = (TYPE_INVERTER,)
        self.__log: CustomLogger = Singletons.log.create_logger(name)

        self.__adapter = adapter
        self.__adapter.configure(self.__log)

        self.__on_status_change = list()
        self.__on_power_change = list()

        self.__tx_event = Event()
        self.__last_tx = time()
        self.__last_rx = time()

        self.__last_tick = time()

        self.__service_task = create_task(self.__tick())

        self.__name = name
        self.__power_lut = PowerLut(config['power_lut'])
        self.__shall_status = STATUS_OFF
        self.__current_status = STATUS_SYNCING
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
        self.__shall_status = STATUS_ON if on else STATUS_OFF
        if old_value != self.__shall_status:
            self.__shall_percent = self.__power_lut.min_percent
            self.__log.info('New target state: ', self.__shall_status)
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
            self.__log.info('New power target: ', self.__shall_percent, ' % / ', shall_power, ' W')
            self.__tx_event.set()
        return shall_power
        
    def get_inverter_power(self):
        if  self.__current_status != STATUS_ON:
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
        if self.__current_status != STATUS_ON or self.__current_power is None:
            return
        self.__energy += self.__current_power * seconds

    def get_inverter_energy(self):
        energy = self.__energy / 3600
        self.__energy = 0
        self.__log.info(f'{energy:.1f}', ' Wh fed since last check.')
        return energy
        
###################
# Internal
###################
    
    async def __tick(self):
        while True:
            try:
                now = time()
                seconds = now - self.__last_tick
                self.__last_tick = now
                if seconds > 0:
                    self.__add_energy(seconds)
                await self.__sync_to_inverters()
                if not self.__is_status_synced or not self.__is_power_synced or now - self.__last_rx > 30:
                    await self.__sync_from_inverters()
            except Exception as e:
                self.__log.error('Cycle failed: ', e)
                self.__log.trace(e)
            await sleep(1.0)

    def __update(self, status, power_percent):
        last_status = self.__current_status
        if status != STATUS_ON \
                and self.__shall_status == STATUS_ON \
                and self.__current_status == STATUS_ON:
            # inverter deactivated itself
            self.__current_status = STATUS_FAULT
        elif status == None:
            # currently no communication with ahoydtu
            self.__current_status = STATUS_SYNCING
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
        self.__log.info('State=', status_str, ' Power=', power_str, ' %')

        if last_status != self.__current_status:
            run_callbacks(self.__on_status_change, self, self.__current_status)
        if (last_percent != self.__current_percent) and self.__current_power is not None:
            run_callbacks(self.__on_power_change, self, self.__current_power)

    async def __run_next_request(self):
        if self.__is_status_synced and self.__is_power_synced:
            return False

        now = time()
        delta = now - self.__last_tx
        wait_time = self.__get_wait_time()
        if delta < wait_time:
            return False

        #prio 1: switch off
        if not self.__is_status_synced and self.__shall_status != STATUS_ON:
            self.__last_command_type = _CMD_TURN_OFF
            self.__last_status_command_type = _CMD_TURN_OFF
            self.__log.info('Sending switch off command.')
            await self.__adapter.switch_off()
            return True
        
        #prio 2: reset (a power change will not survive reset, so reset first)
        if not self.__is_status_synced and self.__shall_status == STATUS_ON and self.__last_status_command_type == _CMD_TURN_ON:
            self.__last_command_type = _CMD_RESET
            self.__last_status_command_type = _CMD_RESET
            self.__log.info('Sending reset command.')
            await self.__adapter.reset()
            return True
        
        #prio 3: change power
        if not self.__is_power_synced:
            self.__last_command_type = _CMD_CHANGE_POWER
            self.__log.info('Sending power change request.')
            await self.__adapter.change_power(self.__shall_percent)
            return True
        
        #prio 4: switch on
        if not self.__is_status_synced and self.__shall_status == STATUS_ON:
            self.__last_command_type = _CMD_TURN_ON
            self.__last_status_command_type = _CMD_TURN_ON
            self.__log.info('Sending switch on command.')
            await self.__adapter.switch_on()
            return True
        
        return False

    def __get_wait_time(self):
        if self.__last_command_type == _CMD_TURN_ON \
                or self.__last_command_type == _CMD_TURN_OFF:
            if self.__is_status_synced:
                return 0
            else:
                return 30
        elif self.__last_command_type == _CMD_RESET:
            if self.__is_status_synced:
                return 0
            else:
                return 60
        elif self.__last_command_type == _CMD_CHANGE_POWER:
            if self.__is_power_synced:
                return 0
            else:
                return 30
        return 0

    async def __sync_to_inverters(self):
        if not self.__tx_event.is_set():
            return
        
        if await self.__run_next_request():
            self.__last_tx = time()
            self.__tx_event.clear()

    async def __sync_from_inverters(self):
        try:
            status, limit = await self.__adapter.read()
            self.__update(status, limit)
            if False in (self.__is_status_synced, self.__is_power_synced):
                self.__tx_event.set()
            self.__last_rx = time()
        except Exception as e:
            self.__log.error('No status available.')
            self.__update(None, None)
