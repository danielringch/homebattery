from asyncio import sleep
from struct import pack, unpack
from .micromqtt import MicroMqtt
from ssl import CERT_NONE
from .types import BatteryData, CallbackCollection, MODE_PROTECT, STATUS_ON, STATUS_OFF, to_operation_mode

class Mqtt():
    def __init__(self, config: dict):
        config = config["mqtt"]

        self.__ip, self.__port = config['host'].split(':')
        self.__port = int(self.__port)
        ca = config.get('ca', None)
        tls_insecure = config.get('tls_insecure', False)
        user = config.get('user', None)
        password = config.get('password', None)

        self.__live_consumption_topic = config["live_consumption_topic"]
        self.__charger_state_topic = f'{config["root"]}/cha/state'
        self.__charger_energy_topic = f'{config["root"]}/cha/e'
        self.__inverter_state_topic = f'{config["root"]}/inv/state'
        self.__inverter_power_topic = f'{config["root"]}/inv/p'
        self.__inverter_energy_topic = f'{config["root"]}/inv/e'
        self.__solar_state_topic = f'{config["root"]}/sol/state'
        self.__solar_energy_topic = f'{config["root"]}/sol/e'
        self.__battery_device_root = f'{config["root"]}/bat/dev/'
        self.__mode_set_topic = f'{config["root"]}/mode/set'
        self.__mode_actual_topic = f'{config["root"]}/mode/actual'
        self.__locked_topic = f'{config["root"]}/locked'

        self.__mqtt = MicroMqtt(self.__on_mqtt_connect)

        if ca:
            self.__mqtt.tls_set(ca_certs=ca, cert_reqs=CERT_NONE if tls_insecure else None)

        if user or password:
            self.__mqtt.username_pw_set(user, password)

        self.__mqtt.message_callback_add(self.__live_consumption_topic, self.__on_live_consumption)
        self.__mqtt.message_callback_add(self.__mode_set_topic, self.__on_mode)

        self.__subscriptions = [
            (self.__live_consumption_topic, 0),
            (self.__mode_set_topic, 0) #TODO change to 1 or 2
        ]

        self.__connect_callback = CallbackCollection()
        self.__live_consumption_callback = CallbackCollection()
        self.__mode_callback = CallbackCollection()

    async def __on_mqtt_connect(self):
        for subscription in self.__subscriptions:
            await self.__mqtt.subscribe(topic=subscription[0], qos=subscription[1])
        self.__connect_callback.run_all()

    def __del__(self):
        pass

    async def connect(self):
        await self.__mqtt.connect(self.__ip, self.__port, 60)

    async def subscribe(self, topic, qos, callback):
        self.__mqtt.message_callback_add(topic, callback)
        while not self.__mqtt.connected:
            await sleep(1)
        await self.__mqtt.subscribe(topic, qos)

    async def send_mode(self, mode: str):
        await self.__mqtt.publish(self.__mode_actual_topic, mode.encode('utf-8'), qos=1, retain=False)

    async def send_charger_status(self, status: str):
        value = self.status_to_byte(status)
        await self.__mqtt.publish(self.__charger_state_topic, value, qos=1, retain=False)

    async def send_charger_energy(self, energy):
        await self.__mqtt.publish(self.__charger_energy_topic, pack('!H', int(energy)), qos=1, retain=False)

    async def send_inverter_status(self, status: str):
        value = self.status_to_byte(status)
        await self.__mqtt.publish(self.__inverter_state_topic, value, qos=1, retain=False)

    async def send_inverter_power(self, power: int):
        await self.__mqtt.publish(self.__inverter_power_topic, pack('!H', int(power)), qos=1, retain=False)

    async def send_inverter_energy(self, energy: int):
        await self.__mqtt.publish(self.__inverter_energy_topic, pack('!H', int(energy)), qos=1, retain=False)

    async def send_solar_status(self, status: str):
        value = self.status_to_byte(status)
        await self.__mqtt.publish(self.__solar_state_topic, value, qos=1, retain=False)

    async def send_solar_energy(self, energy: int):
        await self.__mqtt.publish(self.__solar_energy_topic, pack('!H', int(energy)), qos=1, retain=False)

    async def send_battery(self, data: BatteryData):
        await self.__mqtt.publish(f'{self.__battery_device_root}{data.name}/v', pack('!H', round(data.v * 100)), qos=1, retain=False)
        await self.__mqtt.publish(f'{self.__battery_device_root}{data.name}/i', pack('!h', round(data.i * 10)), qos=1, retain=False)
        await self.__mqtt.publish(f'{self.__battery_device_root}{data.name}/soc', pack('!B', int(data.soc)), qos=1, retain=False)
        await self.__mqtt.publish(f'{self.__battery_device_root}{data.name}/c', pack('!H', round(data.c * 10)), qos=1, retain=False)
        await self.__mqtt.publish(f'{self.__battery_device_root}{data.name}/n', pack('!H', round(data.n)), qos=1, retain=False)
        i = 0
        for temp in data.temps:
            await self.__mqtt.publish(f'{self.__battery_device_root}{data.name}/temp/{i}', pack('!h', round(temp * 10)), qos=1, retain=False)
            i += 1
        i = 0
        for cell in data.cells:
            await self.__mqtt.publish(f'{self.__battery_device_root}{data.name}/cell/{i}', pack('!H', round(cell * 1000)), qos=1, retain=False)
            i += 1

    async def send_locked(self, reason: str):
        payload = reason.encode('utf-8') if reason is not None else None
        await self.__mqtt.publish(self.__locked_topic, payload, qos=1, retain=False)

    @property
    def connected(self):
        return self.__mqtt.connected
    
    @property
    def on_connect(self):
        return self.__connect_callback

    @property
    def on_live_consumption(self):
        return self.__live_consumption_callback
    
    @property
    def on_mode(self):
        return self.__mode_callback

    def __on_live_consumption(self, topic, payload):
        power = unpack('!H', payload)[0]
        self.__live_consumption_callback.run_all(power)

    def __on_mode(self, topic, payload):
        try:
            mode = to_operation_mode(payload.decode('utf-8'))
        except:
            mode = MODE_PROTECT
        self.__mode_callback.run_all(mode)

    @staticmethod
    def status_to_byte(status):
        if status == STATUS_ON:
            return bytes((0x01,))
        elif status == STATUS_OFF:
            return bytes((0x00,))
        return bytes((0xFF,))
