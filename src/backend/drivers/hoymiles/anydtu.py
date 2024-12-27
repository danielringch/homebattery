from asyncio import Event, create_task, sleep, Lock
from micropython import const
from time import time
from ..interfaces.inverterinterface import InverterInterface
from ...core.logging import CustomLogger
from ...core.triggers import triggers, TRIGGER_300S
from ...core.types import PowerLut, run_callbacks, STATUS_FAULT, STATUS_OFF, STATUS_ON, STATUS_SYNCING
from ...helpers.valueaggregator import ValueAggregator
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

        self.__power_lut = PowerLut(config['power_lut'])

        self.__name = name
        self.__public_status = STATUS_SYNCING
        self.__public_power = 0
        self.__target_power = 0

        self.__device_power = None

        self.__last_command_type = None
        self.__last_status_command_type = None
        self.__energy = ValueAggregator() # unusual unit: Ws , too keep things integer can only divide once by 3600

        self.__lock = Lock()
        self.__rx_task = create_task(self.__do_rx())
        self.__tx_task = create_task(self.__do_tx())
        triggers.add_subscriber(self.__on_trigger)

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
        if (self.__target_power > 0) == on:
            return
        self.__target_power = self.__power_lut.min_power if on else 0
        self.__log.info('New target state: ', 'on' if on else 'off')
        self.__tx_event.set()

    def get_inverter_status(self):
        return self.__public_status
    
    @property
    def __is_status_synced(self):
        if self.__target_power == 0:
            return self.__public_status == STATUS_OFF
        else:
            return self.__public_status == STATUS_ON
    
    @property
    def on_inverter_status_change(self):
        return self.__on_status_change
    
###################
# Power
###################
    
    async def set_inverter_power(self, power):
        if self.__target_power == 0: # inverter is not switched on:
            return 0
        target_percent, target_power = self.__power_lut.get_percent(power)
        if target_power != self.__target_power:
            self.__target_power = target_power
            self.__log.info('New power target: ', target_percent, ' % / ', self.__target_power, ' W')
            self.__tx_event.set()
        return target_power
        
    def get_inverter_power(self):
        return self.__public_power
    
    @property
    def min_power(self):
        return self.__power_lut.min_power

    @property
    def max_power(self):
        return self.__power_lut.max_power
    
    @property
    def __is_power_synced(self):
        if self.__target_power == 0:
            return self.__device_power == self.__power_lut.min_power
        else:
            return self.__device_power == self.__target_power
    
    @property
    def on_inverter_power_change(self):
        return self.__on_power_change
    
###################
# Energy
###################

    def get_inverter_energy(self):
        energy = round(self.__energy.integral() / 3600, 1)
        if energy > 0: # if the integral is too small yet, do not clear to not loose data
            self.__energy.clear()
        self.__log.info(f'{energy:.1f}', ' Wh fed since last check.')
        return energy
        
###################
# Internal
###################

    def __on_trigger(self, trigger_type):
        try:
            if trigger_type != TRIGGER_300S:
                return
            run_callbacks(self.__on_status_change, self, self.__public_status)
            run_callbacks(self.__on_power_change, self, self.__public_power)
        except Exception as e:
            self.__log.error('Trigger cycle failed: ', e)
            self.__log.trace(e)

    def __set_public_status(self, new_status):
        if new_status == self.__public_status:
            return
        self.__public_status = new_status
        run_callbacks(self.__on_status_change, self, new_status)
        self.__log.info('State=', new_status)
        if new_status != STATUS_ON:
            self.__set_public_power(0)
        
    def __set_public_power(self, new_power):
        if new_power == self.__public_power:
            return
        self.__public_power = new_power
        run_callbacks(self.__on_power_change, self, new_power)
        self.__log.info('Power=', new_power, 'W')

    async def __do_rx(self):
        while True:
            try:
                await sleep(2)
                async with self.__lock:
                    await self.__sync_from_inverters()
                self.__energy.add(self.__public_power)
            except Exception as e:
                self.__log.error('RX cycle failed: ', e)
                self.__log.trace(e)


    async def __do_tx(self):
        while True:
            try:
                await sleep(1)
                async with self.__lock:
                    await self.__sync_to_inverters()
            except Exception as e:
                self.__log.error('TX cycle failed: ', e)
                self.__log.trace(e)

    async def __sync_to_inverters(self):
        if not self.__tx_event.is_set():
            return
        
        if self.__is_status_synced and self.__is_power_synced:
            return

        now = time()
        delta = now - self.__last_tx
        wait_time = self.__get_wait_time()
        if delta < wait_time:
            return

        #prio 1: switch off
        if not self.__is_status_synced and self.__target_power == 0:
            self.__last_command_type = _CMD_TURN_OFF
            self.__last_status_command_type = _CMD_TURN_OFF
            self.__log.info('Sending switch off command.')
            await self.__adapter.switch_off()
            self.__last_tx = time()
            self.__tx_event.clear()
            return True
        
        #prio 2: reset (a power change will not survive reset, so reset first)
        if not self.__is_status_synced and self.__target_power > 0 and self.__last_status_command_type == _CMD_TURN_ON:
            self.__last_command_type = _CMD_RESET
            self.__last_status_command_type = _CMD_RESET
            self.__log.info('Sending reset command.')
            await self.__adapter.reset()
            self.__last_tx = time()
            self.__tx_event.clear()
            return True
        
        #prio 3: change power
        if not self.__is_power_synced:
            self.__last_command_type = _CMD_CHANGE_POWER
            self.__log.info('Sending power change request.')
            percent, _ = self.__power_lut.get_percent(self.__target_power)
            await self.__adapter.change_power(percent)
            self.__last_tx = time()
            self.__tx_event.clear()
            return True
        
        #prio 4: switch on
        if not self.__is_status_synced and self.__target_power > 0:
            self.__last_command_type = _CMD_TURN_ON
            self.__last_status_command_type = _CMD_TURN_ON
            self.__log.info('Sending switch on command.')
            await self.__adapter.switch_on()
            self.__last_tx = time()
            self.__tx_event.clear()
            return True
        
        return False

    async def __sync_from_inverters(self):
        try:
            status, limit = await self.__adapter.read()
            self.__update(status, limit)
            if False in (self.__is_status_synced, self.__is_power_synced):
                self.__tx_event.set()
        except Exception as e:
            self.__log.error('No status available.')
            self.__update(None, None)

    def __update(self, status, power_percent):
        if status != STATUS_ON \
                and self.__target_power > 0 \
                and self.__public_status == STATUS_ON:
            # inverter deactivated itself
            self.__set_public_status(STATUS_FAULT)
        elif status == None:
            # currently no communication with ahoydtu
            self.__set_public_status(STATUS_SYNCING)
        else:
            self.__set_public_status(status)

        # power percent was observed to have garbage valued from time to time when syncing, just ignore them
        if power_percent is not None and power_percent <= 100:
            self.__device_power, _ = self.__power_lut.get_power(power_percent)
            if self.__public_status == STATUS_ON:
                self.__set_public_power(self.__device_power)

        if not self.__is_status_synced or not self.__is_power_synced:
            self.__log.info('target_power=', self.__target_power, ' device_status=', self.__public_status, ' device_power=', self.__device_power)

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
