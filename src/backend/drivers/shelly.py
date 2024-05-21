from asyncio import create_task, Event, sleep, TimeoutError, wait_for
from micropython import const
from time import time
from .interfaces.chargerinterface import ChargerInterface
from ..core.microaiohttp import ClientSession
from ..core.types import run_callbacks, STATUS_ON, STATUS_OFF, STATUS_SYNCING, STATUS_FAULT

_REFRESH_INTERVAL = const(120)
_TIMER_INTERVAL = const(300)

class Shelly(ChargerInterface):
    def __init__(self, name, config):
        super(Shelly, self).__init__()
        from ..core.singletons import Singletons
        from ..core.types import TYPE_CHARGER
        self.__name = name
        self.__device_types = (TYPE_CHARGER,)
        self.__log = Singletons.log.create_logger(name)
        self.__host, self.__port = config['host'].split(':')
        self.__port = int(self.__port)
        self.__relay_id = int(config['relay_id'])

        self.__ui = Singletons.ui

        self.__shall_on = False
        self.__last_status = STATUS_SYNCING
        self.__last_on_command = 0
        self.__sync_trigger = Event()
        self.__sync_task = create_task(self.__sync())

        self.__on_status_change = list()

        self.__on_request = f'relay/{self.__relay_id}?turn=on&timer={_TIMER_INTERVAL}'
        self.__off_request = f'relay/{self.__relay_id}?turn=off'
        self.__state_request = f'relay/{self.__relay_id}'
        self.__energy_request = f'rpc/Switch.GetStatus?id={self.__relay_id}'
        self.__energy_reset_request = f'rpc/Switch.ResetCounters?id={self.__relay_id}&type=["aenergy"]'

    async def switch_charger(self, on):
        self.__shall_on = on
        self.__sync_trigger.set()

    def get_charger_status(self):
        return self.__last_status
    
    @property
    def on_charger_status_change(self):
        return self.__on_status_change

    async def get_charger_energy(self):
        json = await self.__get(self.__energy_request)
        energy = float(json['aenergy']['total']) if json is not None else None
        if energy is None:
            return None
        _ = await self.__get(self.__energy_reset_request)
        self.__log.info(f'{energy:.1f}', ' Wh consumed since last check.')
        return energy

    @property
    def name(self):
        return self.__name

    @property
    def device_types(self):
        return self.__device_types
    
    async def __sync(self):
        while True:
            json = await self.__get(self.__state_request)
            on = json['ison'] if json is not None else None
            if on is None:
                status = STATUS_FAULT
            elif on and self.__shall_on:
                status = STATUS_ON
            elif not on and not self.__shall_on:
                status = STATUS_OFF
            else:
                status = STATUS_SYNCING

            self.__log.info('Status: ', status)
            if status != self.__last_status:
                run_callbacks(self.__on_status_change, status)
            self.__last_status = status

            now = time()
            request_necessary = (status == STATUS_SYNCING) or (status == STATUS_FAULT)
            if request_necessary or\
                    (self.__shall_on and (now - self.__last_on_command) >= (_REFRESH_INTERVAL - 5)):
                self.__log.info('Sending switch request, on=', self.__shall_on)
                await self.__get(self.__on_request if self.__shall_on else self.__off_request)
                if self.__shall_on:
                    self.__last_on_command = now
            try:
                timeout = _REFRESH_INTERVAL if not request_necessary else 2
                await wait_for(self.__sync_trigger.wait(), timeout=timeout)
            except TimeoutError:
                pass
            self.__sync_trigger.clear()

    def __create_session(self):
        return ClientSession(self.__log, self.__host, self.__port)
    
    async def __get(self, query):
        for i in reversed(range(3)):
            try:
                with self.__create_session() as session:
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
            await sleep(1)
        return None
        