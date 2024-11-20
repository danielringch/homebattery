from asyncio import create_task, sleep
from ..interfaces.consumptioninterface import ConsumptionInterface
from ...core.logging import CustomLogger
from ...core.microaiohttp import ClientSession
from ...core.microsocket import MicroSocketClosedExecption, MicroSocketTimeoutException
from ...core.types import run_callbacks

class HttpConsumption(ConsumptionInterface):
    def __init__(self, name, config):
        from ...core.singletons import Singletons
        from ...core.types import TYPE_CONSUMPTION
        self.__name = name
        self.__device_types = (TYPE_CONSUMPTION,)
        self.__log: CustomLogger = Singletons.log.create_logger(name)

        self.__callbacks = list()

        self.__host, self.__port = config['host'].split(':')
        self.__port = int(self.__port)
        self.__query = config['query']
        self.__path = config['path']
        self.__interval = int(config['interval'])
        self.__factor = float(config['factor'])

        self.__last_value = None

        self.__task = create_task(self.__run())

    @property
    def name(self):
        return self.__name

    @property
    def device_types(self):
        return self.__device_types
    
    @property
    def on_power(self):
        return self.__callbacks
    
    async def __run(self):
        while True:
            try:
                with ClientSession(self.__log, self.__host, self.__port) as session:
                    response = await session.get(self.__query)
                    status = response.status
                    if (status >= 200 and status <= 299):
                        json = await response.json()
                        for step in self.__path:
                            json = json[step]
                        power = round(float(json) * self.__factor)
                        if power != self.__last_value:
                            self.__last_value = power
                            run_callbacks(self.__callbacks, self, power)
                    else:
                        self.__log.error('Query failed with code ', status)
            except (MicroSocketClosedExecption, MicroSocketTimeoutException):
                self.__log.error('Server did not respond.')
            except Exception as e:
                self.__log.error('Cycle failed: ', e)
                self.__log.trace(e)
            await sleep(self.__interval)

