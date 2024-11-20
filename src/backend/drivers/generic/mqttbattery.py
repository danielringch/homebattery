from asyncio import create_task, Event
from sys import print_exception
from time import time
from ..interfaces.batteryinterface import BatteryInterface
from ...core.backendmqtt import Mqtt
from ...core.devicetools import print_battery
from ...core.types import run_callbacks
from ...helpers.batterydata import BatteryData

class MqttBattery(BatteryInterface):
    class Parser():
        def __init__(self, name, log):
            self.__log = log
            self.data = BatteryData(name, is_forwarded=True)
            self.data_event = Event()

        def parse(self, topic: str, payload: bytes):
            now = time()
            if not payload:
                return
            try:
                self.data.from_json(payload.decode('utf-8'))
            except Exception as e:
                self.__log.error('Failed to read battery data: ', e)
                from ...core.singletons import Singletons
                print_exception(e, Singletons.log.trace)
                self.data.reset()
                return
            
            if self.data.valid:
                self.data_event.set()

    def __init__(self, name, config, mqtt: Mqtt):
        from ...core.singletons import Singletons
        from ...core.types import TYPE_BATTERY
        self.__name = name
        self.__device_types = (TYPE_BATTERY,)
        self.__log = Singletons.log.create_logger(name)

        self.__topic_root = config['root_topic']

        self.__parser = self.Parser(self.__name, self.__log)

        self.__on_data = list()

        self.__receive_task = create_task(self.__receive(mqtt))

    async def read_battery(self):
        pass

    async def __receive(self, mqtt: Mqtt):
        await mqtt.subscribe(self.__topic_root, 0, self.__parser.parse)

        while True:
            await self.__parser.data_event.wait()
            self.__parser.data_event.clear()

            print_battery(self.__log, self.__parser.data)
            run_callbacks(self.__on_data, self.__parser.data)

    @property
    def on_battery_data(self):
        return self.__on_data

    @property
    def name(self):
        return self.__name

    @property
    def device_types(self):
        return self.__device_types
