from struct import pack
from .micromqtt import MicroMqtt
from tls import CERT_NONE
from .types import MODE_PROTECT, run_callbacks, STATUS_ON, STATUS_OFF, to_operation_mode
from ..helpers.batterydata import BatteryData

class Mqtt():
    def __init__(self, config: dict):
        config = config["mqtt"]

        self.__topic_root = str(config["root"]) + "/"

        self.__ip, self.__port = config['host'].split(':')
        self.__port = int(self.__port)
        ca = config.get('ca', None)
        tls_insecure = config.get('tls_insecure', False)
        user = config.get('user', None)
        password = config.get('password', None)
        self.__mqtt = MicroMqtt(self.__topic_root, self.__on_mqtt_connect)
        if ca:
            self.__mqtt.tls_set(ca_certs=ca, cert_reqs=CERT_NONE if tls_insecure else None)

        if user or password:
            self.__mqtt.username_pw_set(user, password)


        self.__mode_set_topic = f'{self.__topic_root}mode/set'
        self.__mode_actual_topic = 'mode/actual'
        self.__locked_topic = 'locked'
        self.__reset_topic = f'{self.__topic_root}reset'

        self.__cha_state = 'cha/state'
        self.__cha_energy = 'cha/e'
        self.__cha_dev_root = 'cha/dev/%s/%s'
    
        self.__inv_state = 'inv/state'
        self.__inv_power = 'inv/p'
        self.__inv_energy = 'inv/e'
        self.__inv_dev_root = 'inv/dev/%s/%s'

        self.__sol_state = 'sol/state'
        self.__sol_power = 'sol/p'
        self.__sol_energy = 'sol/e'
        self.__sol_dev_root = 'sol/dev/%s/%s'

        self.__bat_current = 'bat/i'
        self.__bat_capacity = 'bat/c'
        self.__bat_dev_root = 'bat/dev/%s'

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

    async def send_locked(self, reason: str):
        payload = reason.encode('utf-8') if reason is not None else None
        await self.__mqtt.publish(self.__locked_topic, payload, qos=2, retain=False)

# charger

    async def send_charger_status(self, status: str):
        value = self.status_to_byte(status)
        await self.__mqtt.publish(self.__cha_state, value, qos=1, retain=False)

    async def send_charger_energy(self, energy: int):
        await self.__mqtt.publish(self.__cha_energy, pack('!H', int(energy)), qos=2, retain=False)

    async def send_charger_device_energy(self, name: str, energy: int):
        await self.__mqtt.publish(self.__cha_dev_root % (name, 'e'), pack('!H', int(energy)), qos=2, retain=False)

# inverter

    async def send_inverter_status(self, status: str):
        value = self.status_to_byte(status)
        await self.__mqtt.publish(self.__inv_state, value, qos=1, retain=False)

    async def send_inverter_power(self, power: int):
        await self.__mqtt.publish(self.__inv_power, pack('!H', int(power)), qos=0, retain=False)

    async def send_inverter_device_power(self, name: str, power: int):
        await self.__mqtt.publish(self.__inv_dev_root % (name, 'p'), pack('!H', int(power)), qos=0, retain=False)

    async def send_inverter_energy(self, energy: int):
        await self.__mqtt.publish(self.__inv_energy, pack('!H', int(energy)), qos=2, retain=False)

    async def send_inverter_device_energy(self, name: str, energy: int):
        await self.__mqtt.publish(self.__inv_dev_root % (name, 'e'), pack('!H', int(energy)), qos=2, retain=False)

# solar

    async def send_solar_status(self, status: str):
        value = self.status_to_byte(status)
        await self.__mqtt.publish(self.__sol_state, value, qos=1, retain=False)

    async def send_solar_power(self, power: int):
        await self.__mqtt.publish(self.__sol_power, pack('!H', int(power)), qos=0, retain=False)

    async def send_solar_device_power(self, name: str, power: int):
        await self.__mqtt.publish(self.__sol_dev_root % (name, 'p'), pack('!H', int(power)), qos=0, retain=False)

    async def send_solar_energy(self, energy: int):
        await self.__mqtt.publish(self.__sol_energy, pack('!H', int(energy)), qos=2, retain=False)

    async def send_solar_device_energy(self, name: str, energy: int):
        await self.__mqtt.publish(self.__sol_dev_root % (name, 'e'), pack('!H', int(energy)), qos=2, retain=False)

# battery

    async def send_battery_current(self, current: int):
        await self.__mqtt.publish(self.__bat_current, pack('!h', round(current * 10)), qos=0, retain=False)

    async def send_battery_capacity(self, capacity: int):
        await self.__mqtt.publish(self.__bat_capacity, pack('!H', round(capacity * 10)), qos=0, retain=False)

    async def send_battery_device(self, data: BatteryData):
        await self.__mqtt.publish(self.__bat_dev_root % data.name, data.to_json().encode('utf-8'), qos=0, retain=False)

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

    @staticmethod
    def status_to_byte(status):
        if status == STATUS_ON:
            return bytes((0x01,))
        elif status == STATUS_OFF:
            return bytes((0x00,))
        return bytes((0xFF,))
