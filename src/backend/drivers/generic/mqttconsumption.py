from asyncio import create_task
from ubinascii import hexlify
from ..interfaces.consumptioninterface import ConsumptionInterface
from ...core.backendmqtt import Mqtt
from ...core.types import run_callbacks
from ...helpers.streamreader import read_big_int16, read_big_int32

class MqttConsumption(ConsumptionInterface):
    def __init__(self, name, config, mqtt: Mqtt):
        from ...core.singletons import Singletons
        from ...core.types import TYPE_CONSUMPTION
        self.__name = name
        self.__device_types = (TYPE_CONSUMPTION,)
        self.__log = Singletons.log.create_logger(name)

        self.__callbacks = list()

        self.__subscribe_task = create_task(mqtt.subscribe(config['topic'], 0, self.__on_power))

    @property
    def name(self):
        return self.__name

    @property
    def device_types(self):
        return self.__device_types
    
    @property
    def on_power(self):
        return self.__callbacks

    def __on_power(self, topic, payload):
        if len(payload) == 2:
            reader = read_big_int16
        elif len(payload) == 4:
            reader = read_big_int32
        else:
            self.__log.error('Unknown payload: ', hexlify(payload, ' '))
            return
        
        run_callbacks(self.__callbacks, self, reader(payload, 0))

