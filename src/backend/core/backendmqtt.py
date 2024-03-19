import struct
from .micromqtt import MicroMqtt
from ssl import CERT_NONE
from .types import *


class Mqtt():
    def __init__(self, config: dict):
        config = config["mqtt"]

        self.__ip, self.__port = config['host'].split(':')
        self.__port = int(self.__port)
        ca = config.get('ca', None)
        tls_insecure = config.get('tls_insecure', False)
        user = config.get('user', None)
        password = config.get('password', None)

        self.__live_consumption_topic = config["live_power_topic"]
        self.__charger_state_topic = f'{config["root"]}/charger/state'
        self.__charger_energy_topic = f'{config["root"]}/charger/energy'
        self.__inverter_state_topic = f'{config["root"]}/inverter/state'
        self.__inverter_power_topic = f'{config["root"]}/inverter/power'
        self.__solar_state_topic = f'{config["root"]}/solar/state'
        self.__solar_energy_topic = f'{config["root"]}/solar/energy'
        self.__inverter_energy_topic = f'{config["root"]}/inverter/energy'
        self.__battery_capacity_topic = f'{config["root"]}/battery/capacity'
        self.__mode_topic = f'{config["root"]}/mode'
        self.__locked_topic = f'{config["root"]}/locked'

        self.__mqtt = MicroMqtt(self.__on_mqtt_connect)

        if ca:
            self.__mqtt.tls_set(ca_certs=ca, cert_reqs=CERT_NONE if tls_insecure else None)

        if user or password:
            self.__mqtt.username_pw_set(user, password)

        self.__mqtt.message_callback_add(self.__live_consumption_topic, self.__on_live_consumption)
        self.__mqtt.message_callback_add(self.__mode_topic, self.__on_mode)

        self.__live_consumption_callback = CallbackCollection()
        self.__mode_callback = CallbackCollection()

    def __on_mqtt_connect(self):
        self.__mqtt.subscribe(self.__live_consumption_topic, qos=0)
        self.__mqtt.subscribe(self.__mode_topic, qos=0) #TODO change to 1 or 2

    def __del__(self):
        pass

    async def connect(self):
        await self.__mqtt.connect(self.__ip, self.__port, 60)

    def send_charger_state(self, on):
        payload = struct.pack('!B', on) if on is not None else None
        self.__mqtt.publish(self.__charger_state_topic, payload, qos=1, retain=False)

    def send_charger_energy(self, energy):
        self.__mqtt.publish(self.__charger_energy_topic, struct.pack('!H', int(energy)), qos=1, retain=False)

    def send_inverter_state(self, on: bool):
        payload = struct.pack('!B', on) if on is not None else None
        self.__mqtt.publish(self.__inverter_state_topic, payload, qos=1, retain=False)

    def send_inverter_power(self, power: int):
        self.__mqtt.publish(self.__inverter_power_topic, struct.pack('!H', int(power)), qos=1, retain=False)

    def send_inverter_energy(self, energy: int):
        self.__mqtt.publish(self.__inverter_energy_topic, struct.pack('!H', int(energy)), qos=1, retain=False)

    def send_solar_state(self, on: bool):
        payload = struct.pack('!B', on) if on is not None else None
        self.__mqtt.publish(self.__solar_state_topic, payload, qos=1, retain=False)

    def send_solar_energy(self, energy: int):
        self.__mqtt.publish(self.__solar_energy_topic, struct.pack('!H', int(energy)), qos=1, retain=False)

    def send_battery_state(self, data: BatterySummary):
        if data.capacity_remaining is not None:
            payload = struct.pack('!h', round(data.capacity_remaining * 10))
            self.__mqtt.publish(self.__battery_capacity_topic, payload, qos=1, retain=False)

    def send_locked(self, reason: str):
        payload = reason.encode('utf-8') if reason is not None else None
        self.__mqtt.publish(self.__locked_topic, payload, qos=1, retain=False)

    @property
    def connected(self):
        return self.__mqtt.connected

    @property
    def on_live_consumption(self):
        return self.__live_consumption_callback
    
    @property
    def on_mode(self):
        return self.__mode_callback

    def __on_live_consumption(self, payload):
        power = struct.unpack('!H', payload)[0]
        self.__live_consumption_callback.run_all(power)

    def __on_mode(self, payload):
        try:
            mode = operationmode.from_string(payload.decode('utf-8'))
        except:
            mode = operationmode.idle
        self.__mode_callback.run_all(mode)

