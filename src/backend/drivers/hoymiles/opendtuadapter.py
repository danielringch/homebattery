from asyncio import sleep
from ...core.microaiohttp import ClientSession, BasicAuth
from ...core.types import STATUS_FAULT, STATUS_OFF, STATUS_ON, STATUS_SYNCING
from .dtuadapter import DtuAdapter
from .anydtu import AnyDtu

class OpenDtu(AnyDtu):
    def __init__(self, name, config):
        adapter = OpenDtuAdapter(config)
        super().__init__(name, config, adapter)

class OpenDtuAdapter(DtuAdapter):
    def __init__(self, config):
        from ...core.singletons import Singletons
        self.__log = None
        self.__host, self.__port = config['host'].split(':')
        self.__port = int(self.__port)
        self.__auth = BasicAuth("admin", config['password'])
        self.__serial = config['serial']
        self.__ui = Singletons.ui


    def configure(self, log):
        self.__log = log

    async def switch_on(self):
        command = f'"serial":"{self.__serial}","power":true'
        await self.__send_command('power', command)

    async def switch_off(self):
        command = f'"serial":"{self.__serial}","power":false'
        await self.__send_command('power', command)

    async def reset(self):
        command = f'"serial":"{self.__serial}","restart":true'
        await self.__send_command('power', command)

    async def change_power(self, percent: int):
        command = f'"serial":"{self.__serial}","limit_type":1, "limit_value":{percent}'
        await self.__send_command('limit', command)

    async def read(self):
        with self.__create_session() as session:
            json = await self.__get(session, 'livedata/status')
        try:
            data = {x['serial']: (x['producing'], x['reachable'], x['limit_relative']) for x in json['inverters']}
            producing, reachable, limit = data[self.__serial]
            if reachable:
                status = STATUS_ON if producing else STATUS_OFF
                limit = int(limit)
            else:
                status = STATUS_FAULT
                limit = None
            return status, limit
        except Exception as e:
            self.__log.error(f'No status available.')
            return None, None

    async def __send_command(self, domain, command):
        with self.__create_session() as session:
            await self.__post(session, f'{domain}/config', 'data={'+command+'}')

    def __create_session(self):
        return ClientSession(self.__log, self.__host, self.__port, self.__auth)

    async def __get(self, session, query):
        for i in reversed(range(3)):
           try:
               response = await session.get(f'api/{query}')
               status = response.status
               if status >= 200 and status <= 299:
                   json = await response.json()
                   self.__ui.notify_control()
                   return json
               else:
                   self.__log.error(f'Inverter query {query} failed with code {status}, {i} retries left.')
           except Exception as e:
               self.__log.error(f'Inverter query {query} failed: {str(e)}, {i} retries left.')
           await sleep(1)
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
                        self.__ui.notify_control()
                        return json
                self.__log.error(f'Inverter command {query} failed with code {status}.')
            except Exception as e:
                self.__log.error(f'Inverter command {query} failed: {str(e)}, {i} retries left.')
            await sleep(1)
        return None
    