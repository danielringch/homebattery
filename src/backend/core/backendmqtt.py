from asyncio import sleep
from struct import pack, unpack
from .micromqtt import MicroMqtt
from ssl import CERT_NONE
from .types import BatteryData, MODE_PROTECT, run_callbacks, STATUS_ON, STATUS_OFF, to_operation_mode

class Mqtt():
    def __init__(self, config: dict):
        config = config["mqtt"]

        self.__ip, self.__port = config['host'].split(':')
        self.__port = int(self.__port)
        ca = config.get('ca', None)
        tls_insecure = config.get('tls_insecure', False)
        user = config.get('user', None)
        password = config.get('password', None)
        self.__mqtt = MicroMqtt(self.__on_mqtt_connect)
        if ca:
            self.__mqtt.tls_set(ca_certs=ca, cert_reqs=CERT_NONE if tls_insecure else None)

        if user or password:
            self.__mqtt.username_pw_set(user, password)

        self.__topic_root = str(config["root"])

        self.__mode_set_topic = f'{self.__topic_root}/mode/set'
        self.__mode_actual_topic = f'{self.__topic_root}/mode/actual'
        self.__locked_topic = f'{self.__topic_root}/locked'
        self.__reset_topic = f'{self.__topic_root}/reset'

        self.__live_consumption_topic = config["live_consumption_topic"]

        self.__cha_state = f'{self.__topic_root}/cha/state'
        self.__cha_energy = f'{self.__topic_root}/cha/e'
        self.__cha_dev_root = '%s/cha/dev/%s/%s'
    
        self.__inv_state = f'{self.__topic_root}/inv/state'
        self.__inv_power = f'{self.__topic_root}/inv/p'
        self.__inv_energy = f'{self.__topic_root}/inv/e'
        self.__inv_dev_root = '%s/inv/dev/%s/%s'

        self.__sol_state = f'{self.__topic_root}/sol/state'
        self.__sol_power = f'{self.__topic_root}/sol/p'
        self.__sol_energy = f'{self.__topic_root}/sol/e'
        self.__sol_dev_root = '%s/sol/dev/%s/%s'

        self.__bat_current = f'{self.__topic_root}/bat/i'
        self.__bat_capacity = f'{self.__topic_root}/bat/c'
        self.__bat_dev_root = '%s/bat/dev/%s/%s'
        self.__bat_dev_temp_root = '%s/bat/dev/%s/temp/%i'
        self.__bat_dev_cell_root = '%s/bat/dev/%s/cell/%i'

        self.__mqtt.message_callback_add(self.__live_consumption_topic, self.__on_live_consumption)
        self.__mqtt.message_callback_add(self.__mode_set_topic, self.__on_mode)
        self.__mqtt.message_callback_add(self.__reset_topic, self.__on_reset)

        self.__subscriptions = [
            (self.__live_consumption_topic, 0),
            (self.__mode_set_topic, 0), #TODO change to 1 or 2
            (self.__reset_topic, 0)
        ]

        self.__connect_callback = list()
        self.__live_consumption_callback = list()
        self.__mode_callback = list()

    async def __on_mqtt_connect(self):
        for subscription in self.__subscriptions:
            await self.__mqtt.subscribe(topic=subscription[0], qos=subscription[1])
        run_callbacks(self.__connect_callback)

    def __del__(self):
        pass

    async def connect(self):
        await self.__mqtt.connect(self.__ip, self.__port, 60)

    async def subscribe(self, topic, qos, callback):
        self.__mqtt.message_callback_add(topic, callback)
        while not self.__mqtt.connected:
            await sleep(1)
        await self.__mqtt.subscribe(topic, qos)

# general

    async def send_mode(self, mode: str):
        await self.__mqtt.publish(self.__mode_actual_topic, mode.encode('utf-8'), qos=1, retain=False)

    async def send_locked(self, reason: str):
        payload = reason.encode('utf-8') if reason is not None else None
        await self.__mqtt.publish(self.__locked_topic, payload, qos=1, retain=False)

# charger

    async def send_charger_status(self, status: str):
        value = self.status_to_byte(status)
        await self.__mqtt.publish(self.__cha_state, value, qos=1, retain=False)

    async def send_charger_energy(self, energy: int):
        await self.__mqtt.publish(self.__cha_energy, pack('!H', int(energy)), qos=1, retain=False)

    async def send_charger_device_energy(self, name: str, energy: int):
        await self.__mqtt.publish(self.__cha_dev_root % (self.__topic_root, name, 'e'), pack('!H', int(energy)), qos=1, retain=False)

# inverter

    async def send_inverter_status(self, status: str):
        value = self.status_to_byte(status)
        await self.__mqtt.publish(self.__inv_state, value, qos=1, retain=False)

    async def send_inverter_power(self, power: int):
        await self.__mqtt.publish(self.__inv_power, pack('!H', int(power)), qos=1, retain=False)

    async def send_inverter_device_power(self, name: str, power: int):
        await self.__mqtt.publish(self.__inv_dev_root % (self.__topic_root, name, 'p'), pack('!H', int(power)), qos=1, retain=False)

    async def send_inverter_energy(self, energy: int):
        await self.__mqtt.publish(self.__inv_energy, pack('!H', int(energy)), qos=1, retain=False)

    async def send_inverter_device_energy(self, name: str, energy: int):
        await self.__mqtt.publish(self.__inv_dev_root % (self.__topic_root, name, 'e'), pack('!H', int(energy)), qos=1, retain=False)

# solar

    async def send_solar_status(self, status: str):
        value = self.status_to_byte(status)
        await self.__mqtt.publish(self.__sol_state, value, qos=1, retain=False)

    async def send_solar_power(self, power: int):
        await self.__mqtt.publish(self.__sol_power, pack('!H', int(power)), qos=1, retain=False)

    async def send_solar_device_power(self, name: str, power: int):
        await self.__mqtt.publish(self.__sol_dev_root % (self.__topic_root, name, 'p'), pack('!H', int(power)), qos=1, retain=False)

    async def send_solar_energy(self, energy: int):
        await self.__mqtt.publish(self.__sol_energy, pack('!H', int(energy)), qos=1, retain=False)

    async def send_solar_device_energy(self, name: str, energy: int):
        await self.__mqtt.publish(self.__sol_dev_root % (self.__topic_root, name, 'e'), pack('!H', int(energy)), qos=1, retain=False)

# battery

    async def send_battery_current(self, current: int):
        await self.__mqtt.publish(self.__bat_current, pack('!h', round(current * 10)), qos=1, retain=False)

    async def send_battery_capacity(self, capacity: int):
        await self.__mqtt.publish(self.__bat_capacity, pack('!H', round(capacity * 10)), qos=1, retain=False)

    async def send_battery_device(self, data: BatteryData):
        name = data.name
        await self.__mqtt.publish(self.__bat_dev_root % (self.__topic_root, name, 'v'), pack('!H', round(data.v * 100)), qos=1, retain=False)
        await self.__mqtt.publish(self.__bat_dev_root % (self.__topic_root, name, 'i'), pack('!h', round(data.i * 10)), qos=1, retain=False)
        await self.__mqtt.publish(self.__bat_dev_root % (self.__topic_root, name, 'soc'), pack('!B', int(data.soc)), qos=1, retain=False)
        await self.__mqtt.publish(self.__bat_dev_root % (self.__topic_root, name, 'c'), pack('!H', round(data.c * 10)), qos=1, retain=False)
        await self.__mqtt.publish(self.__bat_dev_root % (self.__topic_root, name, 'n'), pack('!H', round(data.n)), qos=1, retain=False)
        i = 0
        for temp in data.temps:
            await self.__mqtt.publish(self.__bat_dev_temp_root % (self.__topic_root, name, i), pack('!h', round(temp * 10)), qos=1, retain=False)
            i += 1
        i = 0
        for cell in data.cells:
            await self.__mqtt.publish(self.__bat_dev_cell_root % (self.__topic_root, name, i), pack('!H', round(cell * 1000)), qos=1, retain=False)
            i += 1



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
        run_callbacks(self.__live_consumption_callback, power)

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
