from asyncio import sleep
from ...core.microaiohttp import ClientSession
from ...core.types import STATUS_FAULT, STATUS_OFF, STATUS_ON, STATUS_SYNCING
from .dtuadapter import DtuAdapter
from .anydtu import AnyDtu

class AhoyDtu(AnyDtu):
    def __init__(self, name, config):
        adapter = AhoyDtuAdapter(config)
        super().__init__(name, config, adapter)

class AhoyDtuAdapter(DtuAdapter):
    def __init__(self, config):
        from ...core.singletons import Singletons
        self.__log = None
        self.__host, self.__port = config['host'].split(':')
        self.__port = int(self.__port)
        self.__id = config['id']
        self.__ui = Singletons.ui

        self.__ahoy_state_to_internal_state = {
            0: STATUS_FAULT,
            1: STATUS_OFF,
            2: STATUS_ON,
            3: STATUS_OFF,
            4: STATUS_FAULT
        }

    def configure(self, log):
        self.__log = log

    async def switch_on(self):
        command = '{"id":%d,"cmd":"power","val":1}' % self.__id
        await self.__send_command(command)

    async def switch_off(self):
        command = '{"id":%d,"cmd":"power","val":0}' % self.__id
        await self.__send_command(command)

    async def reset(self):
        command = '{"id":%d,"cmd":"restart"}' % self.__id
        await self.__send_command(command)

    async def change_power(self, percent: int):
        command = '{"id":%d,"cmd":"limit_nonpersistent_relative","val":%d}' % (self.__id, percent)
        await self.__send_command(command)

    async def read(self):
        with self.__create_session() as session:
            json = await self.__get(session, f'api/inverter/id/{self.__id}')
        try:
            status = self.__ahoy_state_to_internal_state.get(int(json['status']), STATUS_FAULT)
            limit = int(json['power_limit_read'])
            return status, limit
        except Exception as e:
            self.__log.error('No status available.')
            return None, None

    async def __send_command(self, command):
        with self.__create_session() as session:
            await self.__post(session, 'api/ctrl', command)

    def __create_session(self):
        return ClientSession(self.__log, self.__host, self.__port)
    
    async def __get(self, session, query):
        for i in reversed(range(3)):
           try:
               response = await session.get(query)
               status = response.status
               if status >= 200 and status <= 299:
                   json = await response.json()
                   self.__ui.notify_control()
                   return json
               else:
                   self.__log.error('Inverter query ', query, ' failed with code ', status, ', ', i, ' retries left.')
           except Exception as e:
                self.__log.error('Inverter query ', query, ' failed: ', e, ', ', i, ' retries left.')
           await sleep(1)
        return None

    async def __post(self, session, query, payload):
        for i in reversed(range(3)):
            try:
                header = {'Content-Type': 'text/plain'}
                response = await session.post(query, headers=header, data=payload)
                status = response.status
                if status >= 200 and status <= 299:
                    json = await response.json()
                    if json["success"] in (True, "true"):
                        self.__ui.notify_control()
                        return json
                self.__log.error('Inverter command ', query, ' failed with code ', status)
            except Exception as e:
                self.__log.error('Inverter command ', query, ' failed: ', str(e), ', ', i, ' retries left.')
            await sleep(1)
        return None