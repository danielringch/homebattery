from asyncio import create_task, Event
from struct import unpack
from ubinascii import hexlify
from time import time
from .interfaces.batteryinterface import BatteryInterface
from ..core.backendmqtt import Mqtt
from ..core.devicetools import print_battery
from ..core.types import BatteryData, CallbackCollection

class MqttBattery(BatteryInterface):
    class Parser():
        def __init__(self, name, log, cell_count, temp_count):
            self.__log = log
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

        def parse(self, topic, payload):
            now = time()
            if self.timestamp + 10 < now:
                self.__clear()

            try:
                parts = topic.split('/')
                topic = parts[-1]
                if topic == 'v':
                    self.v=unpack('!H', payload)[0] / 100
                elif topic == 'i':
                    self.i=unpack('!h', payload)[0] / 10
                elif topic == 'soc':
                    self.soc=unpack('!B', payload)[0]
                elif topic == 'c':
                    self.c=unpack('!H', payload)[0] / 10
                elif topic == 'n':
                    self.n=unpack('!H', payload)[0]
                else:
                    topic = parts[-2]
                    i = int(parts[-1])
                    if topic == 'temp':
                        self.temps[i] = unpack('!h', payload)[0] / 10
                    elif topic == 'cell':
                        self.cells[i] = unpack('!H', payload)[0] / 1000
                    else:
                        raise Exception()
            except:
                self.__log.error('Invalid battery data: topic=', topic, ' payload=', hexlify(payload, " "))
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

        self.__root = config['root_topic']
        self.__cell_count = int(config['cell_count'])
        self.__temp_count = int(config['temperature_count'])

        self.__parser = self.Parser(self.__name, self.__log, self.__cell_count, self.__temp_count)

        self.__on_data = CallbackCollection()

        self.__receive_task = create_task(self.__receive(mqtt))

    async def read_battery(self):
        pass

    async def __receive(self, mqtt: Mqtt):
        await mqtt.subscribe(f'{self.__root}/v', 0, self.__parser.parse)
        await mqtt.subscribe(f'{self.__root}/i', 0, self.__parser.parse)
        await mqtt.subscribe(f'{self.__root}/soc', 0, self.__parser.parse)
        await mqtt.subscribe(f'{self.__root}/c', 0, self.__parser.parse)
        await mqtt.subscribe(f'{self.__root}/n', 0, self.__parser.parse)
        for i in range(self.__temp_count):
            await mqtt.subscribe(f'{self.__root}/temp/{i}', 0, self.__parser.parse)
        for i in range(self.__cell_count):
            await mqtt.subscribe(f'{self.__root}/cell/{i}', 0, self.__parser.parse)

        while True:
            await self.__parser.data_event.wait()
            self.__parser.data_event.clear()

            print_battery(self.__log, self.__parser.data)
            self.__on_data.run_all(self.__parser.data)

    @property
    def on_battery_data(self):
        return self.__on_data

    @property
    def name(self):
        return self.__name

    @property
    def device_types(self):
        return self.__device_types

    
