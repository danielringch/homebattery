from asyncio import create_task, Lock, sleep, wait_for, TimeoutError
from gc import collect as gc_collect
from re import match
from ubinascii import hexlify
from machine import unique_id
from micropython import const

from .logging import CustomLogger
from .microsocket import MicroSocket, MicroSocketTimeoutException, MicroSocketClosedExecption
from .mqtttools import connect_to_bytes, bytes_to_connack, disconnect_to_bytes
from .mqtttools import publish_to_bytes, bytes_to_publish
from .mqtttools import pubx_to_bytes, bytes_to_pubx
from .mqtttools import subscribe_to_bytes, bytes_to_suback
from .mqtttools import pingreq_to_bytes, bytes_to_pingresp
from .mqtttools import mark_as_duplicate, read_packet, filter_to_regex
from .mqtttools import PACKET_TYPE_CONNACK, PACKET_TYPE_PUBLISH, PACKET_TYPE_PUBACK, PACKET_TYPE_SUBACK, PACKET_TYPE_PINGRESP
from .mqtttools import PACKET_TYPE_PUBREC, PACKET_TYPE_PUBREL, PACKET_TYPE_PUBCOMP

from utime import time
from uerrno import EINPROGRESS, ETIMEDOUT, ECONNRESET

class MQTTError(Exception):
    pass

BUSY_ERRORS = [EINPROGRESS, ETIMEDOUT, -110]

_KEEPALIVE = const(60)
_PING_INTERVAL = const(30)
_SEND_LOOP_INTERVAL = const(4)
_MAX_PACKET_SIZE = const(512)
_OVERDUE_TIMEOUT = const(10)
_OUTPUT_BUFFER_SIZE = const(10)

class MicroMqtt():
    class InputMessage:
        def __init__(self):
            self.pid = None
            self.topic = None
            self.payload = None

        def fill(self, pid: int, topic: str, payload: str):
            self.pid = pid
            self.topic = topic
            self.payload = payload

        def clear(self):
            self.pid = None
            self.topic = None
            self.payload = None

        @property
        def empty(self):
            return self.pid == None

    class OutputMessage:
        def __init__(self):
            self.clear()

        def fill(self, builder: bytearray, start: int):
            self.payload = builder[start:]

        def clear(self):
            self.payload = None
            self.timestamp = 0

        @property
        def empty(self):
            return self.payload == None
            
        def is_overdue(self, now):
            return self.timestamp + _OVERDUE_TIMEOUT < now
        
    class Subscription:
        def __init__(self, topic: str, qos: int, callback):
            self.topic = topic
            self.qos = qos
            self.regex = filter_to_regex(topic)
            self.callback = callback

    def __init__(self, topic_root: str, connect_callback):
        from .singletons import Singletons
        self.__log: CustomLogger = Singletons.log.create_logger('mqtt')
        self.__ui = Singletons.ui

        self.__ip = None
        self.__port = None
        self.__cert = None
        self.__cert_req = None
        self.__user = None
        self.__password = None

        self.__topic_root = topic_root.encode('utf-8')

        self.__socket = None

        self.__id = hexlify(unique_id())

        self.__connected = False
        self.__on_connect = connect_callback

        self.__subscriptions = list()

        self.__tx_builder = bytearray(_MAX_PACKET_SIZE)
        self.__tx_builder_lock = Lock()
        self.__tx_buffer = tuple(self.OutputMessage() for _ in range(_OUTPUT_BUFFER_SIZE))
        self.__rx_buffer = bytearray(_MAX_PACKET_SIZE)
        self.__rx_pids = set()

        self.__send_task = None
        self.__receive_task = None
        self.__supervisor_task = None

        self.__lock = Lock()
        self.__receive_lock = Lock()

    def tls_set(self, ca_certs, cert_reqs):
        self.__cert = ca_certs
        self.__cert_req = cert_reqs

    def username_pw_set(self, user, password):
        self.__user = user
        self.__password = password

    async def connect(self, ip, port, timeout):
        self.__ip = ip
        self.__port = port
        await self.__connect()

    @property
    def connected(self):
        return self.__connected and self.__socket and self.__socket.is_connected

    async def subscribe(self, topic, qos, callback):
        subscription = self.Subscription(topic, qos, callback)
        self.__subscriptions.append(subscription)

        if not self.__connected: # subscriptions will be done later automatically when connecting
            return
        
        await self.__subscribe(subscription)

    async def publish(self, topic, payload, qos, retain):
        async with self.__tx_builder_lock:
            pid, packet = await self.__get_free_buffer()

            start = publish_to_bytes(pid, self.__topic_root, topic, payload, qos, retain, self.__tx_builder)
            packet.fill(self.__tx_builder, start)

        self.__log.info('TX PUBLISH, pid=', pid, ' qos=', qos, ' topic=~/', topic)
        await self.__send_packet(packet)
        if qos == 0:
            packet.clear()

    async def __connect(self):
        self.__log.info("Connecting to broker.")
        self.__socket = MicroSocket(self.__log, self.__ip, self.__port, self.__cert, self.__cert_req)
        if not self.__socket.is_connected:
            return

        while True:
            try:
                await self.__send_connect_message()
                try:
                    success = await wait_for(self.__receive_connack(), 5)
                except TimeoutError:
                    continue

                if not success:
                    raise MQTTError()

                self.__log.info('Connected to broker.')
                self.__connected = True

                self.__send_task = create_task(self.__send_loop())
                self.__receive_task = create_task(self.__receive_loop())
                if not self.__supervisor_task:
                    self.__supervisor_task = create_task(self.__supervisor_loop())

                for subscription in self.__subscriptions:
                    await self.__subscribe(subscription)

                await self.__on_connect()
                break
            except MicroSocketTimeoutException:
                pass
            except MicroSocketClosedExecption:
                await self.__disconnect()
                self.__socket = MicroSocket(self.__log, self.__ip, self.__port, self.__cert, self.__cert_req)
            except MQTTError:
                self.__log.info('Connection to broker failed.')

    async def __disconnect(self):
        self.__connected = False
        if not self.__socket:
            return
        if self.__socket.is_connected:
            try:
                await self.__socket.send(disconnect_to_bytes())
            except OSError:
                pass
        self.__socket.close()
        self.__socket = None
        gc_collect()

    async def __send_connect_message(self):
        assert self.__socket is not None

        async with self.__tx_builder_lock:
            _, packet = await self.__get_free_buffer()

            start = connect_to_bytes(self.__id, _KEEPALIVE, self.__user, self.__password, self.__tx_builder)
            packet.fill(self.__tx_builder, start)

        await self.__send_packet(packet)
        packet.clear()

    async def __ping(self):
        if not self.connected:
            return
        await self.__socket.send(pingreq_to_bytes())

    async def __subscribe(self, subscription):
        async with self.__tx_builder_lock:
            pid, packet = await self.__get_free_buffer()

            start = subscribe_to_bytes(pid, subscription.topic, subscription.qos, self.__tx_builder)
            packet.fill(self.__tx_builder, start)
            
        self.__log.info('TX SUBSCRIBE, pid=', pid, ' qos=', subscription.qos, ': ', subscription.topic)
        await self.__send_packet(packet)

    async def __receive_data(self):
        if self.__socket is None:
            return
        async with self.__receive_lock:
            type = await read_packet(self.__socket, self.__rx_buffer)

            self.__ui.notify_mqtt()

            if type & 0xF0 == PACKET_TYPE_PUBLISH:
                await self.__receive_publish(self.__rx_buffer)
            elif type == PACKET_TYPE_PUBACK:
                self.__receive_puback(self.__rx_buffer)
            elif type == PACKET_TYPE_PUBREC:
                await self.__receive_pubrec(self.__rx_buffer)
            elif type == PACKET_TYPE_PUBREL:
                await self.__receive_pubrel(self.__rx_buffer)
            elif type == PACKET_TYPE_PUBCOMP:
                self.__receive_pubcomp(self.__rx_buffer)
            elif type == PACKET_TYPE_SUBACK:
                self.__receive_suback(self.__rx_buffer)
            elif type == PACKET_TYPE_PINGRESP:
                self.__receive_pingresp(self.__rx_buffer)
            else:
                self.__log.error('Unkown MQTT code: ', type)

    async def __receive_connack(self):
        assert self.__socket is not None

        async with self.__receive_lock:
            type = await read_packet(self.__socket, self.__rx_buffer)
            if type != PACKET_TYPE_CONNACK:
                self.__log.error('Bad CONACK: wrong header: ', type)

            error = bytes_to_connack(self.__rx_buffer)

            if error is not None:
                self.__log.error('Bad CONACK: ', error)
                return False
            
            return True
        
    async def __receive_publish(self, buffer: bytes):
        pid, qos, topic, payload = bytes_to_publish(buffer)

        if qos == 1:
            self.__log.info('TX PUBACK, pid=', pid)  
            await self.__send_buffer(pubx_to_bytes(PACKET_TYPE_PUBACK, pid))
        elif qos == 2:
            self.__log.info('TX PUBREC, pid=', pid)
            await self.__send_buffer(pubx_to_bytes(PACKET_TYPE_PUBREC, pid))

        if qos == 2 and pid in self.__rx_pids:
            self.__log.info('RX PUBLISH duplicate, pid=', pid, ' qos=', qos, ' topic=', topic)
            return

        self.__log.info('RX PUBLISH, pid=', pid, ' qos=', qos, ' topic=', topic)
        try:
            callback = self.__get_message_callback(topic)
            if callback is not None:
                callback(topic, payload)
            else:
                self.__log.error('No callback for topic ', topic)
        except KeyError:
            pass
        except Exception as e:
            self.__log.error('Callback failed: ', e)
            self.__log.trace(e)

    def __receive_puback(self, buffer: bytes):
        error, pid = bytes_to_pubx(buffer)

        if error is not None:
            self.__log.error('Bad PUBACK: ', error, ', pid=', pid)
        else:
            self.__log.info('RX PUBACK, pid=', pid)

        if pid is not None and pid > 0:
            self.__tx_buffer[pid - 1].clear()

    async def __receive_pubrec(self, buffer: bytes):
        error, pid = bytes_to_pubx(buffer)

        if error is not None:
            self.__log.error('Bad PUBREC: ', error, ', pid=', pid)
        else:
            self.__log.info('RX PUBREC, pid=', pid)

        if pid is not None and pid > 0:
            packet = self.__tx_buffer[pid - 1]
            packet.clear()
            packet.fill(pubx_to_bytes(PACKET_TYPE_PUBREL, pid), 0)
            self.__log.info('TX PUBREL, pid=', pid)  
            await self.__send_packet(packet)

    async def __receive_pubrel(self, buffer: bytes):
        error, pid = bytes_to_pubx(buffer)

        if error is not None:
            self.__log.error('Bad PUBREL: ', error, ', pid=', pid)
        else:
            self.__log.info('RX PUBREL, pid=', pid)

        if pid is not None and pid > 0:
            self.__rx_pids.discard(pid)
            self.__log.info('TX PUBCOMP, pid=', pid)  
            await self.__send_buffer(pubx_to_bytes(PACKET_TYPE_PUBCOMP, pid))

    def __receive_pubcomp(self, buffer: bytes):
        error, pid = bytes_to_pubx(buffer)

        if error is not None:
            self.__log.error('Bad PUBCOMP: ', error, ', pid=', pid)
        else:
            self.__log.info('RX PUBCOMP, pid=', pid)

        if pid is not None and pid > 0:
            self.__tx_buffer[pid - 1].clear()

    def __receive_suback(self, buffer: bytes):
        error, pid, qos = bytes_to_suback(buffer)

        if error is not None:
            self.__log.error('Bad SUBACK: ', error, ', pid=', pid, ' qos=', qos)
        else:
            self.__log.info('RX SUBACK, pid=', pid, ' qos=', qos)

        if pid is not None and pid > 0:
            self.__tx_buffer[pid - 1].clear()

    def __receive_pingresp(self, buffer: bytes):
        valid = bytes_to_pingresp(buffer)
        if not valid:
            self.__log.error('Bad PINGRESP.')
            return
        self.__log.info('RX PINGRESP.')

    async def __send_packet(self, packet: OutputMessage):
        assert self.__socket

        mark_as_duplicate(packet.payload, packet.timestamp > 0) # publish message has been sent before

        await self.__send_buffer(packet.payload)
        packet.timestamp = time()

    async def __send_buffer(self, buffer: bytes):
        assert self.__socket
        await self.__socket.send(buffer)
        self.__ui.notify_mqtt()

    async def __get_free_buffer(self):
        while True:
            for i in range(_OUTPUT_BUFFER_SIZE):
                buffer = self.__tx_buffer[i]
                if buffer.empty:
                    return i + 1, buffer
            await sleep(0.1)

    def __get_message_callback(self, topic):
        for subscription in self.__subscriptions:
            if match(subscription.regex, topic) is not None:
                return subscription.callback
        return None

    async def __send_loop(self):
        last_ping = 0
        while True:
            await sleep(_SEND_LOOP_INTERVAL)
            try:
                now = time()

                for packet in self.__tx_buffer:
                    if packet.empty or not packet.is_overdue(now):
                        continue
                    await self.__send_packet(packet)

                if last_ping + _PING_INTERVAL < now:
                    await self.__ping()
                    last_ping = now

            except Exception as e:
                self.__log.error('Send loop error: ', e)
                self.__log.error('Send loop crashed, disconnecting...')
                await self.__disconnect()
                return

    async def __receive_loop(self):
        while True:
            try:
                await wait_for(self.__receive_data(), _KEEPALIVE)
            except TimeoutError:
                self.__log.error('Server is no longer responding, disconnecting...')
                await self.__disconnect()
                return
            except Exception as e:
                self.__log.error('Receive loop error: ', e)
                self.__log.error('Receive loop crashed, disconnecting...')
                await self.__disconnect()
                return

    async def __supervisor_loop(self):
        while True:
            while True:
                if not self.connected:
                    self.__log.error('Disconnect detected: socket is closed.')
                    break
                await sleep(3)
            self.__send_task.cancel()
            self.__receive_task.cancel()
            async with self.__lock:
                await self.__disconnect()
                self.__log.info('Disconnected by supervisor.')
            await self.__connect()
            self.__log.info('Connected by supervisor.')
            await sleep(20)  
