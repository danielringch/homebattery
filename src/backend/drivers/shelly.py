import asyncio, time
from .interfaces.chargerinterface import ChargerInterface
from ..core.microaiohttp import ClientSession
from ..core.leds import leds
from ..core.logging import log
from ..core.types import devicetype

class Shelly(ChargerInterface):
    __refresh_interval = 120

    def __init__(self, name, config):
        super(Shelly, self).__init__()
        self.__device_types = (devicetype.charger,)
        self.__log = log.get_custom_logger(name)
        self.__host, self.__port = config['host'].split(':')
        self.__port = int(self.__port)
        self.__relay_id = int(config['relay_id'])

        self.__shall_on = False
        self.__is_on = None
        self.__last_on_command = 0
        self.__sync_trigger = asyncio.Event()
        self.__sync_task = asyncio.create_task(self.__sync())

        self.__on_request = f'relay/{self.__relay_id}?turn=on&timer=300'
        self.__off_request = f'relay/{self.__relay_id}?turn=off'
        self.__state_request = f'relay/{self.__relay_id}'
        self.__energy_request = f'rpc/Switch.GetStatus?id={self.__relay_id}'
        self.__energy_reset_request = f'rpc/Switch.ResetCounters?id={self.__relay_id}&type=["aenergy"]'

    async def switch_charger(self, on):
        self.__shall_on = on
        self.__sync_trigger.set()

    async def is_charger_on(self):
        self.__is_on = None
        self.__sync_trigger.set()
        for _ in range(10):
            await asyncio.sleep(0.5)
            if self.__is_on is not None:
                return self.__is_on
        else:
            return None

    async def get_charger_energy(self):
        with self.__create_session() as session:
            json = await self.__get(session, self.__energy_request)
            energy = float(json['aenergy']['total']) if json is not None else None
            if energy is None:
                return None
            _ = await self.__get(session, self.__energy_reset_request)
            self.__log.send(f'{energy:.1f} Wh consumed since last check.')
            return energy

    @property
    def device_types(self):
        return self.__device_types
    
    async def __sync(self):
        while True:
            is_synced = False
            with self.__create_session() as session:
                json = await self.__get(session, self.__state_request)
                self.__is_on = json['ison'] if json is not None else None
                is_synced = self.__is_on == self.__shall_on
                self.__log.send(f'State: on={self.__is_on}, synced={is_synced}')
                now = time.time()
                if not is_synced or\
                        (self.__shall_on and (now - self.__last_on_command) >= (self.__refresh_interval - 5)):
                    self.__log.send(f'Sending switch request, on={self.__shall_on}')
                    await self.__get(session, self.__on_request if self.__shall_on else self.__off_request)
                    if self.__shall_on:
                        self.__last_on_command = now
            try:
                timeout = self.__refresh_interval if is_synced else 2
                await asyncio.wait_for(self.__sync_trigger.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                pass
            self.__sync_trigger.clear()

    def __create_session(self):
        return ClientSession(self.__host, self.__port)
    
    async def __get(self, session, query):
        for i in reversed(range(3)):
            try:
                response = await session.get(query)
                status = response.status
                if (status >= 200 and status <= 299):
                    json = await response.json()
                    leds.notify_control()
                    return json
                else:
                    self.__log.send(f'Charger query {query} for {self.__host} failed with code {status}, {i} retries left.')
                #    except aiohttp.ContentTypeError as e:
                #        # other content type usually means request is not supported, so no retry
                #        log.error(f'Charger query {query} for {self.__host} failed: {str(e)}')
                #        return None
            except Exception as e:
                self.__log.send(f'Charger query {query} for {self.__host} failed: {str(e)}, {i} retries left.')
            await asyncio.sleep(1)
        return None
        