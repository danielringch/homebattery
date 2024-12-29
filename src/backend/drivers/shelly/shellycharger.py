from asyncio import create_task, Event, sleep, TimeoutError, wait_for
from micropython import const
from time import time
from ..interfaces.chargerinterface import ChargerInterface
from ...core.logging import CustomLogger
from ...core.triggers import triggers, TRIGGER_300S
from ...core.microaiohttp import ClientSession
from ...core.types import run_callbacks, STATUS_ON, STATUS_OFF, STATUS_SYNCING, STATUS_FAULT, STATUS_OFFLINE
from ...core.types import MEASUREMENT_STATUS, MEASUREMENT_ENERGY, MEASUREMENT_POWER
from ...helpers.valueaggregator import ValueAggregator

_REFRESH_INTERVAL = const(120)
_TIMER_INTERVAL = const(300)

class ShellyCharger(ChargerInterface):
    def __init__(self, name, config):
        super(ShellyCharger, self).__init__()
        from ...core.singletons import Singletons
        from ...core.types import TYPE_CHARGER
        self.__name = name
        self.__device_types = (TYPE_CHARGER,)
        self.__log: CustomLogger = Singletons.log.create_logger(name)
        self.__host, self.__port = config['host'].split(':')
        self.__port = int(self.__port)
        self.__generation = int(config['generation'])
        self.__relay_id = int(config['relay_id'])

        self.__ui = Singletons.ui

        self.__shall_on = False
        self.__last_status = STATUS_SYNCING
        self.__last_on_command = 0
        self.__sync_trigger = Event()
        self.__sync_task = create_task(self.__sync())

        self.__power = 0
        self.__power_integral = ValueAggregator()

        self.__last_reported_power = 0

        self.__on_data = []

        self.__on_request = f'relay/{self.__relay_id}?turn=on&timer={_TIMER_INTERVAL}'
        self.__off_request = f'relay/{self.__relay_id}?turn=off'
        self.__state_request = f'relay/{self.__relay_id}'
        self.__power_request = f'meter/{self.__relay_id}' if (self.__generation == 1) else f'rpc/Switch.GetStatus?id={self.__relay_id}'

        triggers.add_subscriber(self.__on_trigger)

    @property
    def name(self):
        return self.__name

    @property
    def device_types(self):
        return self.__device_types

    async def switch_charger(self, on):
        self.__shall_on = on
        self.__sync_trigger.set()

    @property
    def on_charger_data(self):
        return self.__on_data
    
    def get_charger_data(self):
        return {
            MEASUREMENT_STATUS: self.__last_status,
            MEASUREMENT_POWER: self.__power
        }
    
    async def __sync(self):
        while True:
            try:
                await wait_for(self.__sync_trigger.wait(), timeout=_REFRESH_INTERVAL)
            except TimeoutError:
                pass
            self.__sync_trigger.clear()

            status = await self.__get_status()
            if status in (STATUS_ON, STATUS_OFF):
                await sleep(3)

            if status == STATUS_SYNCING:
                await self.__switch(self.__shall_on)
            else:
                self.__power = await self.__get_power()
                self.__power_integral.add(self.__power)

            if (time() - self.__last_on_command) > _REFRESH_INTERVAL:
                await self.__switch(self.__shall_on)

            if status == STATUS_SYNCING: # prevent reporting status change to SYNCING when relay switches fast
                await sleep(1)
                status = await self.__get_status()

            if status not in (STATUS_ON, STATUS_OFF): # retry setting the switch faster
                self.__sync_trigger.set()

            if status != self.__last_status:
                self.__last_status = status
                self.__log.info('Status=', status)
                run_callbacks(self.__on_data, self, {MEASUREMENT_STATUS: status})

    def __on_trigger(self, trigger_type):
        try:
            data = {}
            if trigger_type == TRIGGER_300S:
                data[MEASUREMENT_STATUS] = self.__last_status
                data[MEASUREMENT_POWER] = self.__power
                energy = round(self.__power_integral.integral() / 3600)
                if energy:
                    self.__power_integral.clear()
                data[MEASUREMENT_ENERGY] = energy
                self.__log.info('Status=', self.__last_status, ' Power=', self.__power, 'W Energy=', energy, 'Wh')
            if self.__power != self.__last_reported_power:
                self.__last_reported_power = self.__power
                data[MEASUREMENT_POWER] = self.__power
                self.__log.info('Power=', self.__power, 'W')
            if data:
                run_callbacks(self.__on_data, self, data)
            if self.__last_status == STATUS_ON:
                self.__sync_trigger.set()
        except Exception as e:
            self.__log.error('Trigger cycle failed: ', e)
            self.__log.trace(e)
    
    async def __switch(self, on: bool):
        self.__log.info('Sending switch request, on=', on)
        if on:
            await self.__get(self.__on_request)
            self.__last_on_command = time()
        else:
            await self.__get(self.__off_request)

    async def __get_status(self):
        json = await self.__get(self.__state_request)
        on = json['ison'] if json is not None else None
        if on is None:
            return STATUS_OFFLINE
        elif on and self.__shall_on:
            return STATUS_ON
        elif not on and not self.__shall_on:
            return STATUS_OFF
        else:
            return STATUS_SYNCING

    async def __get_power(self):
        json = await self.__get(self.__power_request)
        key = 'power' if self.__generation == 1 else 'apower'
        power = float(json[key]) if json is not None else None
        if power is None:
            self.__log.error(f'No power data available.')
            return 0
        return round(power)
    
    async def __get(self, query):
        for i in reversed(range(3)):
            try:
                with ClientSession(self.__log, self.__host, self.__port) as session:
                    response = await session.get(query)
                    status = response.status
                    if (status >= 200 and status <= 299):
                        json = await response.json()
                        self.__ui.notify_control()
                        return json
                    else:
                        self.__log.error('Charger query ', query, ' for ', self.__host, ' failed with code ', status, ', ', i, ' retries left.')
            except Exception as e:
                self.__log.error('Charger query ', query, ' for ', self.__host, ' failed: ', e, ', ', i, ' retries left.')
                self.__log.trace(e)
            await sleep(1)
        return None
        