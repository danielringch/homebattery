from asyncio import create_task, Event
from struct import unpack
from ubinascii import hexlify
from time import time
from .interfaces.batteryinterface import BatteryInterface
from ..core.backendmqtt import Mqtt
from ..core.devicetools import print_battery
from ..core.types import BatteryData, run_callbacks

class MqttBattery(BatteryInterface):
    class Parser():
        def __init__(self, name, root, log, cell_count, temp_count):
            self.__log = log
            self.__root = root
            self.data = BatteryData(name, is_forwarded=True)
            self.data_event = Event()
            self.temps = list(None for _ in range(temp_count))
            self.cells = list(None for _ in range(cell_count))
            self.__clear()

        @property
        def complete(self):
            return self.v is not None\
                    and self.i is not None\
                    and self.soc is not None\
                    and self.c is not None\
                    and self.n is not None\
                    and None not in self.temps\
                    and None not in self.cells

        def parse(self, topic: str, payload: bytes):
            now = time()
            if self.timestamp + 10 < now:
                self.__clear()

            try:
                length = len(topic)
                topic = topic.replace(self.__root, '', 1)
                if length == len(topic): # no match
                    raise Exception

                if topic == '/v':
                    self.v=unpack('!H', payload)[0] / 100
                elif topic == '/i':
                    self.i=unpack('!h', payload)[0] / 10
                elif topic == '/soc':
                    self.soc=unpack('!B', payload)[0]
                elif topic == '/c':
                    self.c=unpack('!H', payload)[0] / 10
                elif topic == '/n':
                    self.n=unpack('!H', payload)[0]
                else:
                    parts = topic.split('/', 2)
                    cat = parts[1]
                    i = int(parts[2])
                    if cat == 'temp':
                        self.temps[i] = unpack('!h', payload)[0] / 10
                    elif cat == 'cell':
                        self.cells[i] = unpack('!H', payload)[0] / 1000
                    else:
                        raise Exception()
            except:
                self.__log.error('Ignoring non matching battery data: topic=', topic, ' payload=', hexlify(payload, " "))
                return
            
            if self.timestamp == 0:
                self.timestamp = now
            if self.complete:
                self.data.update(
                    v=self.v,
                    i=self.i,
                    soc=self.soc,
                    c=self.c,
                    c_full=0,
                    n=self.n,
                    temps=tuple(self.temps),
                    cells=tuple(self.cells)
                )
                self.data.timestamp = self.timestamp # use the timestamp of the oldest received MQTT packet
                self.data_event.set()
                self.__clear()

        def __clear(self):
            self.timestamp = 0
            self.v = None
            self.i = None
            self.soc = None
            self.c = None
            self.n = None
            for i in range(len(self.temps)):
                self.temps[i] = None
            for i in range(len(self.cells)):
                self.cells[i] = None
            

    def __init__(self, name, config, mqtt: Mqtt):
        from ..core.singletons import Singletons
        from ..core.types import TYPE_BATTERY
        self.__name = name
        self.__device_types = (TYPE_BATTERY,)
        self.__log = Singletons.log.create_logger(name)

        self.__topic_root = config['root_topic']
        self.__cell_count = int(config['cell_count'])
        self.__temp_count = int(config['temperature_count'])

        self.__parser = self.Parser(self.__name, self.__topic_root, self.__log, self.__cell_count, self.__temp_count)

        self.__on_data = list()

        self.__receive_task = create_task(self.__receive(mqtt))

    async def read_battery(self):
        pass

    async def __receive(self, mqtt: Mqtt):
        await mqtt.subscribe(self.__topic_root + '/#', 0, self.__parser.parse)

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

    
