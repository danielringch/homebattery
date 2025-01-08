from json import dumps
from .micromqtt import MicroMqtt
from tls import CERT_NONE, CERT_REQUIRED
from .types import MODE_PROTECT, run_callbacks, to_operation_mode
from ..helpers.batterydata import BatteryData

class Mqtt():
    def __init__(self, config: dict):
        config = config["mqtt"]

        self.__topic_root = str(config["root"]) + "/"

        self.__ip, self.__port = config['host'].split(':')
        self.__port = int(self.__port)
        user = config.get('user', None)
        password = config.get('password', None)
        self.__mqtt = MicroMqtt(self.__topic_root, self.__on_mqtt_connect)
        tls = config.get('tls', None)
        if tls is not None:
            ca = tls.get('ca', None)
            insecure = tls.get('insecure', False)
            self.__mqtt.tls_set(ca_certs=ca, cert_reqs=CERT_NONE if insecure else CERT_REQUIRED)

        if user or password:
            self.__mqtt.username_pw_set(user, password)


        self.__mode_set_topic = f'{self.__topic_root}mode/set'
        self.__mode_actual_topic = 'mode/actual'
        self.__locked_topic = 'locked'
        self.__reset_topic = f'{self.__topic_root}reset'

        self.__cha = 'cha/sum'
        self.__cha_dev = 'cha/dev/%s'

        self.__hea = 'hea/sum'
        self.__hea_dev = 'hea/dev/%s'
    
        self.__inv = 'inv/sum'
        self.__inv_dev = 'inv/dev/%s'

        self.__sol = 'sol/sum'
        self.__sol_dev = 'sol/dev/%s'

        self.__bat = 'bat/sum'
        self.__bat_dev = 'bat/dev/%s'

        self.__sen_dev = 'sen/dev/%s'

        self.__connect_callback = list()
        self.__mode_callback = list()

    async def __on_mqtt_connect(self):
        run_callbacks(self.__connect_callback)

    def __del__(self):
        pass

    async def connect(self):
        await self.__mqtt.subscribe(self.__mode_set_topic, 2, self.__on_mode)
        await self.__mqtt.subscribe(self.__reset_topic, 1, self.__on_reset)
        await self.__mqtt.connect(self.__ip, self.__port, 60)

    async def subscribe(self, topic, qos, callback):
        await self.__mqtt.subscribe(topic, qos, callback)

# general

    async def send_mode(self, mode: str):
        await self.__mqtt.publish(self.__mode_actual_topic, mode.encode('utf-8'), qos=2, retain=False)

    async def send_locked(self, labels):
        await self.__mqtt.publish(self.__locked_topic, dumps(labels).encode('utf-8'), qos=2, retain=False)

# charger

    async def send_charger_summary(self, data: dict):
        payload = dumps(data).encode('utf-8')
        await self.__mqtt.publish(self.__cha, payload, qos=2, retain=False)

    async def send_charger_device(self, name: str, data: dict):
        payload = dumps(data).encode('utf-8')
        await self.__mqtt.publish(self.__cha_dev % name, payload, qos=2, retain=False)

# heater

    async def send_heater_summary(self, data: dict):
        payload = dumps(data).encode('utf-8')
        await self.__mqtt.publish(self.__hea, payload, qos=2, retain=False)

    async def send_heater_device(self, name: str, data: dict):
        payload = dumps(data).encode('utf-8')
        await self.__mqtt.publish(self.__hea_dev % name, payload, qos=2, retain=False)

# inverter

    async def send_inverter_summary(self, data: dict):
        payload = dumps(data).encode('utf-8')
        await self.__mqtt.publish(self.__inv, payload, qos=2, retain=False)

    async def send_inverter_device(self, name: str, data: dict):
        payload = dumps(data).encode('utf-8')
        await self.__mqtt.publish(self.__inv_dev % name, payload, qos=2, retain=False)

# solar

    async def send_solar_summary(self, data: dict):
        payload = dumps(data).encode('utf-8')
        await self.__mqtt.publish(self.__sol, payload, qos=2, retain=False)

    async def send_solar_device(self, name: str, data: dict):
        payload = dumps(data).encode('utf-8')
        await self.__mqtt.publish(self.__sol_dev % name, payload, qos=2, retain=False)

# battery

    async def send_battery_summary(self, data: dict):
        payload = dumps(data).encode('utf-8')
        await self.__mqtt.publish(self.__bat, payload, qos=2, retain=False)

    async def send_battery_device(self, data: BatteryData):
        await self.__mqtt.publish(self.__bat_dev % data.name, data.to_json().encode('utf-8'), qos=0, retain=False)

# sensor

    async def send_sensor_device(self, name: str, data: dict):
        payload = dumps(data).encode('utf-8')
        await self.__mqtt.publish(self.__sen_dev % name, payload, qos=2, retain=False)

# other

    @property
    def connected(self):
        return self.__mqtt.connected
    
    @property
    def on_connect(self):
        return self.__connect_callback
    
    @property
    def on_mode(self):
        return self.__mode_callback

    def __on_mode(self, topic, payload):
        try:
            mode = to_operation_mode(payload.decode('utf-8'))
        except:
            mode = MODE_PROTECT
        run_callbacks(self.__mode_callback, mode)

    def __on_reset(self, topic, payload):
        try:
            if payload.decode('utf-8') == 'reset':
                from machine import reset
                reset()
        except:
            pass
