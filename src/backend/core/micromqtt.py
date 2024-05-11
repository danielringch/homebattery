from asyncio import create_task, Event, Lock, sleep
from gc import collect as gc_collect
from ubinascii import hexlify
from machine import unique_id
from micropython import const
from struct import pack, unpack, pack_into

from .microsocket import MicroSocket, MicroSocketTimeoutException, MicroSocketClosedExecption

from utime import time
from uerrno import EINPROGRESS, ETIMEDOUT, ECONNRESET

class MQTTException(Exception):
    pass

_MQTT_LOG_NAME = const('mqtt')

BUSY_ERRORS = [EINPROGRESS, ETIMEDOUT, -110]

_MAX_TX_PACKET_SIZE = const(256)
_OVERDUE_TIMEOUT = const(10)
_OUTPUT_BUFFER_SIZE = const(10)

class MicroMqtt():
    class OutputMessage:
        def __init__(self):
            self.payload = bytearray(_MAX_TX_PACKET_SIZE)
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
        self.__log = Singletons.log.create_logger(_MQTT_LOG_NAME)
        self.__leds = Singletons.leds

        self.__ip = None
        self.__port = None
        self.__cert = None
        self.__cert_req = None
        self.__user = None
        self.__password = None

        self.__socket = None
        self.__last_rx = time()
        self.__last_tx = time()

        self.__id = hexlify(unique_id())
        self.__keepalive = 60

        self.__on_connect = connect_callback
        self.__message_callbacks = {}

        self.__pid_generator = self.__get_pid()

        self.__output_buffer = tuple(self.OutputMessage() for _ in range(_OUTPUT_BUFFER_SIZE))

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
        return self.__socket and self.__socket.is_connected

    async def subscribe(self, topic, qos):
        self.__check_qos(qos)
        pid = next(self.__pid_generator)

        packet = await self.__get_free_buffer()
        buffer = packet.payload

        packet_length = 2 + 1 + (2 + len(topic)) + 1 # pid + properties + topic + options
        if packet_length > _MAX_TX_PACKET_SIZE:
            raise OverflowError(f'Subscribe packet is too big for internal buffer: {packet_length} bytes requested, {_MAX_TX_PACKET_SIZE} available.')

        # packet type
        buffer[0] = 0x82
        offset = 1
        # size
        length_buffer = self.__to_variable_integer(packet_length)
        buffer[offset: offset + len(length_buffer)] = length_buffer
        offset += len(length_buffer)
        # pid
        pack_into('!H', buffer, offset, pid)
        offset += 2
        # properties
        buffer[offset] = 0
        offset += 1
        # topic
        offset += self.__pack_string_into(buffer, offset, topic)
        # options
        pack_into('!B', buffer, offset, 1 << 5 | qos) # options
        offset += 1

        packet.pid = pid
        packet.length = offset
            
        self.__log.info(f'Outgoing subscription, pid={pid}, qos={qos}: {topic}')
        await self.__send_buffer(packet)

    async def publish(self, topic, payload, qos, retain):
        self.__check_qos(qos)
        pid = next(self.__pid_generator)

        packet = await self.__get_free_buffer()
        buffer = packet.payload

        payload_length = len(payload) if payload is not None else 0

        packet_length = (2 + len(topic)) + (2 if qos > 0 else 0) + 1 + payload_length # topic + pid + properties + data
        if packet_length > _MAX_TX_PACKET_SIZE:
            raise OverflowError(f'Packet is too big for internal buffer: {packet_length} bytes requested, {_MAX_TX_PACKET_SIZE} available.')

        # packet type
        buffer[0] = 0x30 | qos << 1 | retain # retain flag is set in __send_buffer()
        offset = 1
        # size
        length_buffer = self.__to_variable_integer(packet_length)
        buffer[offset: offset + len(length_buffer)] = length_buffer
        offset += len(length_buffer)
        # topic
        offset += self.__pack_string_into(buffer, offset, topic)
        # pid
        if qos > 0:
            pack_into('!H', buffer, offset, pid)
            offset += 2
        # properties
        buffer[offset] = 0
        offset += 1
        # data
        if payload_length > 0:
            buffer[offset:offset + payload_length] = payload
        offset += payload_length

        packet.pid = pid
        packet.length = offset

        self.__log.info(f'Outgoing message, pid={pid}, qos={qos}, topic={topic}: {self.bytes_to_hex(payload)}')
        await self.__send_buffer(packet)
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
                await self.__send_connect_message(self.__keepalive, self.__user, self.__password)
                success = await self.__receive_connect_ack()
                if not success:
                    await sleep(1)
                    continue

                self.__log.info('Connected to broker.')

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
            except MQTTException:
                self.__log.info('Connection to broker failed.')

    async def __disconnect(self):
        if not self.__socket:
            return
        if self.__socket.is_connected:
            try:
                await self.__socket.send(b"\xe0\0")
            except OSError:
                pass
        self.__socket.close()
        self.__socket = None
        gc_collect()

    async def __ping(self):
        if not self.connected:
            return
        await self.__socket.send(b"\xc0\0")
        self.__last_tx = time()

    async def __receive_data(self):
        if self.__socket is None:
            return
        async with self.__receive_lock:
            try:
                raw_data = await self.__socket.receive(1)
            except:
                return
            if raw_data is None or len(raw_data) != 1:
                return
            
            self.__leds.notify_mqtt()
            
            code = raw_data[0]

            if code == 0xd0:
                await self.__receive_ping()
            elif code == 0x90:
                await self.__receive_subscribe_ack()
            elif code == 0x40:
                await self.__receive_publish_ack()
            elif code & 0xF0 == 0x30:
                await self.__receive_packet(code)
            else:
                self.__log.error(f'Unkown MQTT code: {code}.')

    async def __send_connect_message(self, keep_alive, user, password):
        assert self.__socket is not None

        paket_type = bytearray(b'\x10')
        protocol = self.__string_to_bytes('MQTT')
        version = bytearray(b'\x05')
        connect_flags = bytearray(b'\x02' if not self.__user else b'\xC2')
        keep_alive = pack('!H', keep_alive)
        properties = bytearray(b'\x00')
        id = self.__string_to_bytes(self.__id)
        if user and password:
            user = self.__string_to_bytes(user)
            password = self.__string_to_bytes(password)
        else:
            user = bytearray()
            password = bytearray()

        size = self.__to_variable_integer(
            len(protocol) + 
            len(version) + 
            len(connect_flags) + 
            len(keep_alive) + 
            len(properties) + 
            len(id) +
            len(user) + 
            len(password))
            
        async with self.__send_lock:
            await self.__socket.send(
                paket_type + size + protocol + version + connect_flags + keep_alive + properties + id + user + password)
            self.__last_tx = time()

    async def __receive_connect_ack(self):
        assert self.__socket is not None

        async with self.__receive_lock:
            code, remaining_length = await self.__socket.receive(2)
            if code != 0x20:
                self.__socket.empty_receive_queue()
                self.__log.error(f'Bad CONACK packet: wrong header: {code}.')
                return False
            
            response = await self.__socket.receive(remaining_length)
            
        if response[0] != 0:
            self.__log.error('Bad CONACK packet: no clean session.')
            return False
            
        if response[1] != 0:
            self.__log.error(f'Connection failed with code {response[3]}')
            return False

        self.__last_rx = time()
        return True
    
    async def __receive_ping(self):
        length = await self.__receive_variable_integer()
        if length != 0:
            self.__log.error(f'Bad PINGRESP packet: unexpected length: {length}.')
            return
        self.__log.info('Incoming PINGRESP.')
        self.__last_rx = time()

    async def __receive_subscribe_ack(self):
        assert self.__socket is not None

        length = await self.__receive_variable_integer()
        response = await self.__socket.receive(length)

        if len(response) < 4:
            self.__log.error(f'Bad SUBACK packet: too short.')
            return

        pid = unpack('!H', response[:2])[0]
        if response[2] != 0:
            self.__log.error(f'Bad SUBACK packet: unexpected variable header length: {response[2]}.')
            return
        reason = response[3]
        if reason > 2:
            self.__log.error(f'SUBACK failed with code {reason}')
            return
            
        for packet in self.__output_buffer:
            if not packet.empty and packet.pid == pid:
                packet.clear()
            
        self.__log.info(f'Incoming SUBACK, pid={pid}, qos=unkown.')
        self.__last_rx = time()

    async def __receive_publish_ack(self):
        assert self.__socket is not None

        length = await self.__receive_variable_integer()
        response = await self.__socket.receive(length)
        if len(response) < 2:
            self.__log.error(f'Bad PUBACK packet: too short, length={length}, packet={response}')
            return
        pid = unpack('!H', response[:2])[0]
        reason = response[2] if len(response) > 2 else b'\x00'

        for packet in self.__output_buffer:
            if not packet.empty and packet.pid == pid:
                packet.clear()

        if reason != b'\x00' and reason != b'\x10':
            self.__log.error(f'Incoming PUBACK failed, pid={pid}, reason={reason}.')
        else:
            self.__log.info(f'Incoming PUBACK, pid={pid}.')            
        self.__last_rx = time()

    async def __receive_packet(self, code):
        assert self.__socket is not None

        qos = code & 6 >> 1

        length = await self.__receive_variable_integer()
        response = await self.__socket.receive(length)

        offset = 2
        topic_length = unpack('!H', response[:offset])[0]
        topic = response[offset:offset+topic_length].decode('utf-8')
        offset += topic_length

        try:
            self.__check_qos(qos)
        except:
            self.__log.error(f'Invalid qos at topic {topic}, code {code}.')
            raise
        if qos > 0:
            pid = unpack('!H', response[offset:offset+2])[0]
            offset += 2
        else:
            pid = 0

        property_length, byte_offset = self.__from_variable_integer(memoryview(response)[offset:])
        offset += property_length + byte_offset

        payload = response[offset:]

        if qos > 0:
            pkt = bytearray(b"\x40\x02\0\0")  # Send PUBACK
            pack_into("!H", pkt, 2, pid)
            async with self.__send_lock:
                await self.__socket.send(pkt)
                self.__last_tx = time()

        self.__log.info(f'Incoming message pid={pid}, qos={qos}, topic={topic}: {self.bytes_to_hex(payload)}')
        self.__last_rx = time()
        try:
            self.__message_callbacks[topic](topic, payload)
        except KeyError:
            pass
        except Exception as e:
            self.__log.error(f'Callback failed: {e}')

    async def __send_buffer(self, packet: OutputMessage):
        assert self.__socket

        if packet.payload[0] == 0x30 and packet.timestamp > 0: # publish message has been sent before
            packet.payload[0] |= 1 << 3

        async with self.__send_lock:
            await self.__socket.send(packet.payload, packet.length)
        now = time()
        packet.timestamp = now
        self.__leds.notify_mqtt()
        self.__last_tx = now

    async def __get_free_buffer(self):
        while True:
            for buffer in self.__output_buffer:
                if buffer.empty:
                    return buffer
            await sleep(0.1)

    async def __receive_variable_integer(self):
        assert self.__socket is not None
        n = 0
        sh = 0
        while 1:
            res = await self.__socket.receive(1)
            b = res[0]
            n |= (b & 0x7F) << sh
            if not b & 0x80:
                return n
            sh += 7

    async def __send_loop(self):
        while True:
            async with self.__lock:
                try:
                    if self.__socket is None:
                        return
                    now = time()

                    for packet in self.__output_buffer:
                        if packet.empty or not packet.is_overdue(now):
                            continue
                        await self.__send_buffer(packet)
                except Exception as e:
                    self.__log.error(f'Send loop error: {e}')
                    self.__log.error(f'Send loop crashed, disconnecting...')
                    await self.__disconnect()
                    return
            await sleep(1)

    async def __receive_loop(self):
        while True:
            try:
                await self.__receive_data()
            except Exception as e:
                self.__log.error(f'Receive loop error: {e}')
                self.__log.error(f'Receive loop crashed, disconnecting...')
                await self.__disconnect()
                return
            #await sleep(0.1)

    async def __supervisor_loop(self):
        while True:
            while True:
                if not self.connected:
                    self.__log.error(f'Disconnect detected: socket is closed.')
                    break
                if (self.__last_rx + 60) < time():
                    self.__log.error(f'Disconnect detected: connection lost.')
                    break
                if (min(self.__last_rx, self.__last_tx) + 30) < time():
                    try:
                        await self.__ping()
                    except Exception as e:
                        self.__log.error(f'Disconnect detected: ping failed: {e}.')
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

    @staticmethod
    def __to_variable_integer(value):
        buffer = bytearray(b'/0/0/0/0')
        last_used_byte = 0
        while value > 0x7F:
            buffer[last_used_byte] = (value & 0x7F) | 0x80
            value >>= 7
            last_used_byte += 1
        buffer[last_used_byte] = value  
        return buffer[:last_used_byte + 1]
        
    @staticmethod
    def __from_variable_integer(buffer):
        i = 0
        n = 0
        sh = 0
        while 1:
            b = buffer[i]
            n |= (b & 0x7F) << sh
            if not b & 0x80:
                return n, i + 1
            sh += 7
            i += 1

    @staticmethod
    def bytes_to_hex(bytes):
        if bytes is None or len(bytes) == 0:
            return ''
        return hexlify(bytes, ' ').decode('utf-8')
            
    @staticmethod
    def __string_to_bytes(string):
        return pack("!H", len(string)) + bytearray(string, 'utf-8')
        
    @staticmethod
    def __pack_string_into(buffer, offset: int, string: str):
        length = len(string)
        pack_into('!H', buffer, offset, length)
        buffer[offset + 2: offset + 2 + length] = string.encode('utf-8')
        return length + 2

    @staticmethod
    def __get_pid():
        pid = 0
        while True:
            pid = pid + 1 if pid < 65535 else 1
            yield pid

    @staticmethod
    def __check_qos(value):
        if not (value == 0 or value == 1):
            raise ValueError(f"Unsupported qos value: {value}.")
