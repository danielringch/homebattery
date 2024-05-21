from asyncio import create_task, Event, Lock, sleep, wait_for, TimeoutError
from gc import collect as gc_collect
from ubinascii import hexlify
from machine import unique_id
from micropython import const

from .microsocket import MicroSocket, MicroSocketTimeoutException, MicroSocketClosedExecption
from .mqtttools import connect_to_bytes, publish_to_bytes, puback_to_bytes, subscribe_to_bytes, pingreq_to_bytes, disconnect_to_bytes
from .mqtttools import mark_as_duplicate
from .mqtttools import read_packet, bytes_to_pingresp, bytes_to_suback, bytes_to_puback, bytes_to_publish, bytes_to_connack
from .mqtttools import PACKET_TYPE_CONNACK, PACKET_TYPE_PUBLISH, PACKET_TYPE_PUBACK, PACKET_TYPE_SUBACK, PACKET_TYPE_PINGRESP

from utime import time
from uerrno import EINPROGRESS, ETIMEDOUT, ECONNRESET

class MQTTError(Exception):
    pass


BUSY_ERRORS = [EINPROGRESS, ETIMEDOUT, -110]

_KEEPALIVE = const(60)
_PING_INTERVAL = const(30)
_MAX_PACKET_SIZE = const(256)
_OVERDUE_TIMEOUT = const(10)
_OUTPUT_BUFFER_SIZE = const(10)

class MicroMqtt():
    class OutputMessage:
        def __init__(self):
            self.payload = bytearray(_MAX_PACKET_SIZE)
            self.clear()

        def clear(self):
            self.length = 0
            self.pid = 0
            self.timestamp = 0

        @property
        def empty(self):
            return self.length == 0
            
        def is_overdue(self, now):
            return self.timestamp + _OVERDUE_TIMEOUT < now

    def __init__(self, connect_callback):
        from .singletons import Singletons
        self.__log = Singletons.log.create_logger('mqtt')
        self.__ui = Singletons.ui

        self.__ip = None
        self.__port = None
        self.__cert = None
        self.__cert_req = None
        self.__user = None
        self.__password = None

        self.__socket = None

        self.__tx_event = Event()

        self.__id = hexlify(unique_id())

        self.__connected = False
        self.__on_connect = connect_callback
        self.__message_callbacks = {}

        self.__current_pid = 0

        self.__tx_buffer = tuple(self.OutputMessage() for _ in range(_OUTPUT_BUFFER_SIZE))
        self.__rx_buffer = bytearray(_MAX_PACKET_SIZE)

        self.__send_task = None
        self.__receive_task = None
        self.__supervisor_task = None


        self.__lock = Lock()
        self.__send_lock = Lock()
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

    async def subscribe(self, topic, qos):
        self.__check_qos(qos)
        pid = self.__get_next_pid()

        packet = await self.__get_free_buffer()
        buffer = packet.payload

        packet.length = subscribe_to_bytes(pid, topic, qos, buffer)
        packet.pid = pid
            
        self.__log.info('TX SUBSCRIBE, pid=', pid, ' qos=', qos, ': ', topic)
        await self.__send_packet(packet)

    async def publish(self, topic, payload, qos, retain):
        self.__check_qos(qos)
        pid = self.__get_next_pid()

        packet = await self.__get_free_buffer()
        buffer = packet.payload

        packet.length = publish_to_bytes(pid, topic, payload, qos, retain, buffer)
        packet.pid = pid

        self.__log.info('TX PUBLISH, pid=', pid, ' qos=', qos, ' topic=', topic)
        await self.__send_packet(packet)
        if qos == 0:
            packet.clear()

    def message_callback_add(self, topic, callback):
        self.__message_callbacks[topic] = callback

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

        packet = await self.__get_free_buffer()
        buffer = packet.payload

        packet.length = connect_to_bytes(self.__id, _KEEPALIVE, self.__user, self.__password, buffer)
        packet.pid = 0 # not used
        await self.__send_packet(packet)
        packet.clear()

    async def __ping(self):
        if not self.connected:
            return
        await self.__socket.send(pingreq_to_bytes())

    async def __receive_data(self):
        if self.__socket is None:
            return
        async with self.__receive_lock:
            type = await read_packet(self.__socket, self.__rx_buffer)

            self.__ui.notify_mqtt()

            if type == PACKET_TYPE_PINGRESP:
                self.__receive_pingresp(self.__rx_buffer)
            elif type == PACKET_TYPE_SUBACK:
                self.__receive_suback(self.__rx_buffer)
            elif type == PACKET_TYPE_PUBACK:
                self.__receive_puback(self.__rx_buffer)
            elif type == PACKET_TYPE_PUBLISH:
                await self.__receive_publish(self.__rx_buffer)
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
    
    def __receive_pingresp(self, buffer: bytes):
        valid = bytes_to_pingresp(buffer)
        if not valid:
            self.__log.error('Bad PINGRESP.')
            return
        self.__log.info('RX PINGRESP.')

    def __receive_suback(self, buffer: bytes):
        error, pid, qos = bytes_to_suback(buffer)

        if pid is not None:
            for packet in self.__tx_buffer:
                if not packet.empty and packet.pid == pid:
                    packet.clear()

        if error is not None:
            self.__log.error('Bad SUBACK: ', error, ', pid=', pid, ' qos=', qos)
        else:
            self.__log.info('RX SUBACK, pid=', pid, ' qos=', qos)        

    def __receive_puback(self, buffer: bytes):
        error, pid = bytes_to_puback(buffer)

        if pid is not None:
            for packet in self.__tx_buffer:
                if not packet.empty and packet.pid == pid:
                    packet.clear()

        if error is not None:
            self.__log.error('Bad PUBACK: ', error, ', pid=', pid)
        else:
            self.__log.info('RX PUBACK, pid=', pid)  

    async def __receive_publish(self, buffer: bytes):
        pid, qos, topic, payload = bytes_to_publish(buffer)

        try:
            self.__check_qos(qos)
        except:
            self.__log.error('Invalid qos at topic ', topic, ', qos=', qos)
            raise

        if qos > 0:
            buffer = puback_to_bytes(pid)
            self.__log.info('TX PUBACK, pid=', pid)  
            await self.__send_buffer(buffer, len(buffer))

        self.__log.info('RX PUBLISH, pid=', pid, ' qos=', qos, ' topic=', topic)
        try:
            self.__message_callbacks[topic](topic, payload)
        except KeyError:
            pass
        except Exception as e:
            self.__log.error('Callback failed: ', e)
            from sys import print_exception
            from ..core.singletons import Singletons
            print_exception(e, Singletons.log.trace)

    async def __send_packet(self, packet: OutputMessage):
        assert self.__socket

        mark_as_duplicate(packet.payload, packet.timestamp > 0) # publish message has been sent before

        await self.__send_buffer(packet.payload, packet.length)
        packet.timestamp = time()

    async def __send_buffer(self, buffer: bytes, length: int):
        assert self.__socket

        async with self.__send_lock:
            if length > 64:
                await self.__socket.send(memoryview(buffer), length)
            else:
                await self.__socket.send(buffer, length)
        self.__ui.notify_mqtt()

    async def __get_free_buffer(self):
        while True:
            for buffer in self.__tx_buffer:
                if buffer.empty:
                    return buffer
            await sleep(0.1)

    async def __send_loop(self):
        while True:
            try:
                await wait_for(self.__tx_event.wait(), _PING_INTERVAL)
                self.__tx_event.clear()
            except TimeoutError:
                pass

            try:
                now = time()
                packet_sent = False

                for packet in self.__tx_buffer:
                    if packet.empty or not packet.is_overdue(now):
                        continue
                    await self.__send_packet(packet)
                    packet_sent = True

                if not packet_sent:
                    await self.__ping()

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

    def __get_next_pid(self):
        self.__current_pid = self.__current_pid + 1 if self.__current_pid < 65536 else 1
        return self.__current_pid    

    @staticmethod
    def __check_qos(value):
        if not (value == 0 or value == 1):
            raise ValueError(f"Unsupported qos value: {value}.")
