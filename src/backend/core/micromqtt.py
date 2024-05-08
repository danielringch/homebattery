import asyncio, gc, ubinascii
from collections import deque, OrderedDict
from ubinascii import hexlify
from machine import unique_id
import ustruct as struct

from .microsocket import MicroSocket, MicroSocketTimeoutException, MicroSocketClosedExecption

from utime import time
from uerrno import EINPROGRESS, ETIMEDOUT, ECONNRESET

class MQTTException(Exception):
    pass

BUSY_ERRORS = [EINPROGRESS, ETIMEDOUT, -110]

class MicroMqtt():
    def __init__(self, connect_callback):
        from .logging_singleton import log
        self.__log = log

        self.__connect_callback = connect_callback

        self.__frontend = self.Frontend(self.__on_connect)

        self.__send_task = None
        self.__receive_task = None
        self.__packet_task = None
        self.__supervisor_task = None

        self.__callbacks = {}

        self.__lock = asyncio.Lock()

    def tls_set(self, ca_certs, cert_reqs):
        self.__frontend.tls_set(ca_certs, cert_reqs)

    def username_pw_set(self, user, password):
        self.__frontend.username_pw_set(user, password)

    async def connect(self, ip, port, timeout):
        self.__frontend.address_set(ip, port)
        await self.__frontend.connect()

    def subscribe(self, topic, qos):
        self.__frontend.subscribe(topic, qos)

    def publish(self, topic, payload, qos, retain):
        self.__frontend.publish(topic, payload, qos, retain)

    def message_callback_add(self, topic, callback):
        self.__callbacks[topic] = callback

    @property
    def connected(self):
        return (self.__frontend.last_rx + 60) > time()

    def __on_connect(self):
        self.__send_task = asyncio.create_task(self.__send_loop())
        self.__receive_task = asyncio.create_task(self.__receive_loop())
        self.__packet_task = asyncio.create_task(self.__packet_loop())
        if not self.__supervisor_task:
            self.__supervisor_task = asyncio.create_task(self.__supervisor_loop())

        self.__connect_callback()

    async def __send_loop(self):
        while True:
            async with self.__lock:
                try:
                    await self.__frontend.flush_output_buffer()
                except Exception as e:
                    self.__log.mqtt(f'Send loop error: {e}')
                    self.__log.mqtt(f'Send loop crashed, disconnecting...')
                    await self.__frontend.disconnect()
                    return
            await asyncio.sleep(0.1)

    async def __receive_loop(self):
        while True:
            try:
                await self.__frontend.receive_data()
            except Exception as e:
                self.__log.mqtt(f'Receive loop error: {e}')
                self.__log.mqtt(f'Receive loop crashed, disconnecting...')
                await self.__frontend.disconnect()
                return
            await asyncio.sleep(0.1)

    async def __packet_loop(self):
        while True:
            await self.__frontend.data_available_event.wait()
            self.__frontend.data_available_event.clear()
            while len(self.__frontend.input_buffer) > 0:
                packet = self.__frontend.input_buffer.popleft()
                try:
                    self.__callbacks[packet.topic](packet.topic, packet.data)
                except KeyError:
                    pass
                except Exception as e:
                    self.__log.mqtt(f'Callback failed: {e}')

    async def __supervisor_loop(self):
        while True:
            while True:
                if not self.__frontend.is_connected:
                    self.__log.mqtt(f'Disconnect detected: socket is closed.')
                    break
                if (self.__frontend.last_rx + 60) < time():
                    self.__self.__log.mqtt(f'Disconnect detected: connection lost.')
                    break
                if (min(self.__frontend.last_rx, self.__frontend.last_tx) + 30) < time():
                    try:
                        await self.__frontend.ping()
                    except Exception as e:
                        self.__log.mqtt(f'Disconnect detected: ping failed: {e}.')
                        break
                await asyncio.sleep(3)
            self.__send_task.cancel()
            self.__receive_task.cancel()
            self.__packet_task.cancel()
            async with self.__lock:
                await self.__frontend.disconnect()
                self.__log.mqtt('Disconnected by supervisor.')
            await self.__frontend.connect()
            self.__log.mqtt('Connected by supervisor.')
            await asyncio.sleep(20)

    class Frontend:
        class SubscribeMessage():
            def __init__(self, pid, topic, qos):
                self.pid = pid
                self.topic = topic
                self.qos = qos
                self.sent_at = None

            def mark_sent(self):
                self.sent_at = time()

        class PublishMessage:
            def __init__(self, pid, topic, data, qos, retain):
                self.pid = pid
                self.topic = topic
                self.data = data
                self.qos = qos
                self.retain = retain
                self.sent_at = None

            def mark_sent(self):
                self.sent_at = time()

        class InputMessage:
            def __init__(self, topic, data, retained):
                self.topic = topic
                self.data = data
                self.retained = retained

        def __init__(self, connect_callback):
            from .logging_singleton import log
            self.__log = log

            from .userinterface_singleton import leds
            self.__leds = leds

            self.data_available_event = asyncio.Event()

            self.__ip = None
            self.__port = None
            self.__cert = None
            self.__cert_req = None
            self.__user = None
            self.__password = None

            self.__on_connect = connect_callback

            self.__id = hexlify(unique_id())
            self.__keepalive = 60
            self.__send_timeout = 5

            self.__lock = asyncio.Lock()
            self.__send_lock = asyncio.Lock()
            self.__receive_lock = asyncio.Lock()

            self.__backend = None
            self.last_rx = time()
            self.last_tx = time()

            self.__pid_generator = self.__get_pid()

            self.__subscribe_buffer = OrderedDict()
            self.__publish_buffer = OrderedDict()
            self.input_buffer = deque((), 10)

        def address_set(self, ip, port):
            self.__ip = ip
            self.__port = port

        def tls_set(self, ca_certs, cert_reqs):
            self.__cert = ca_certs
            self.__cert_req = cert_reqs

        def username_pw_set(self, user, password):
            self.__user = user
            self.__password = password

        async def connect(self):
            self.__log.mqtt("Connecting to broker.")
            self.__backend = MicroMqtt.Backend(self.__ip, self.__port, self.__cert, self.__cert_req)
            if not self.__backend.is_connected:
                return

            while True:
                try:
                    await self.__send_connect_message(self.__keepalive, self.__user, self.__password)
                    success = await self.__receive_connect_ack()
                    if not success:
                        await asyncio.sleep(1)
                        continue

                    self.__log.mqtt('Connected to broker.')

                    self.__on_connect()
                    break
                except MicroSocketTimeoutException:
                    pass
                except MicroSocketClosedExecption:
                    await self.disconnect()
                    self.__backend = MicroMqtt.Backend(self.__ip, self.__port, self.__cert, self.__cert_req)
                except MQTTException:
                    self.__log.mqtt('Connection to broker failed.')

        async def disconnect(self):
            if not self.__backend:
                return
            if self.__backend.is_connected:
                try:
                    await self.__backend.send(b"\xe0\0")
                except OSError:
                    pass
            self.__backend.close()
            self.__backend = None
            gc.collect()

        @property
        def is_connected(self):
            return self.__backend and self.__backend.is_connected

        async def ping(self):
            if not self.__backend or not self.__backend.is_connected:
                return
            await self.__backend.send(b"\xc0\0")
            self.last_tx = time()

        def subscribe(self, topic, qos):
            self.__check_qos(qos)
            pid = next(self.__pid_generator)
            self.__subscribe_buffer[pid] = self.SubscribeMessage(pid, topic, qos)


        def publish(self, topic, data, qos, retain):
            self.__check_qos(qos)
            pid = next(self.__pid_generator)
            self.__publish_buffer[pid] = self.PublishMessage(pid, topic, data, qos, retain)

        async def flush_output_buffer(self):
            if self.__backend is None:
                return
            now = time()

            for packet in self.__subscribe_buffer.values():
                if packet.sent_at is not None and now < packet.sent_at + self.__send_timeout:
                    break

                await self.__send_subscribe_message(packet)
                self.__leds.notify_mqtt()

            publish_pids = list(self.__publish_buffer.keys())
            for pid in publish_pids:
                packet = self.__publish_buffer[pid]
                if packet.sent_at is not None and now < packet.sent_at + self.__send_timeout:
                    break

                await self.__send_publish_message(packet)
                self.__leds.notify_mqtt()

                if packet.qos == 0:
                    self.__publish_buffer.pop(pid, None)
                else:
                    break

        async def receive_data(self):
            if self.__backend is None:
                return
            async with self.__receive_lock:
                try:
                    raw_data = await self.__backend.receive(1)
                except:
                    return
                if raw_data is None or len(raw_data) != 1:
                    return
            
                code = raw_data[0]

                if code == 0xd0:
                    await self.__receive_ping()
                    self.__leds.notify_mqtt()
                elif code == 0x90:
                    await self.__receive_subscribe_ack()
                    self.__leds.notify_mqtt()
                elif code == 0x40:
                    await self.__receive_publish_ack()
                    self.__leds.notify_mqtt()
                elif code & 0xF0 == 0x30:
                    await self.__receive_packet(code)
                    self.__leds.notify_mqtt()
                else:
                    self.__log.mqtt(f'Unkown MQTT code: {code}.')

        async def __send_connect_message(self, keep_alive, user, password):
            assert self.__backend is not None

            paket_type = bytearray(b'\x10')
            protocol = self.__string_to_bytes('MQTT')
            version = bytearray(b'\x05')
            connect_flags = bytearray(b'\x02' if not self.__user else b'\xC2')
            keep_alive = struct.pack('!H', keep_alive)
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
                await self.__backend.send(
                    paket_type + size + protocol + version + connect_flags + keep_alive + properties + id + user + password)
                self.last_tx = time()
            
        async def __send_subscribe_message(self, packet):
            assert self.__backend is not None

            paket_type = bytearray(b'\x82')
            pid = struct.pack('!H', packet.pid)
            properties = bytearray(b'\x00')
            topic = self.__string_to_bytes(packet.topic)
            options = struct.pack('!B', 1 << 5 | packet.qos)

            size = self.__to_variable_integer(len(pid) + len(properties) + len(topic) + len(options))

            async with self.__send_lock:
                await self.__backend.send(paket_type + size + pid + properties + topic + options)
                packet.mark_sent()
                self.__log.mqtt(f'Outgoing subscription, pid={packet.pid}, qos={packet.qos}: {packet.topic}')
                self.last_tx = time()

        async def __send_publish_message(self, packet):
            assert self.__backend is not None

            is_duplicate = packet.sent_at is not None
            
            paket_type = bytearray(b"\x30")
            paket_type[0] |= packet.qos << 1 | packet.retain | is_duplicate << 3

            topic = self.__string_to_bytes(packet.topic)
            pid = struct.pack('!H', packet.pid) if packet.qos > 0 else bytearray()
            properties = bytearray(b'\x00')
            data = packet.data if packet.data else bytes()

            size = self.__to_variable_integer(len(topic) + len(pid) + len(properties) + len(data))

            async with self.__send_lock:
                await self.__backend.send(paket_type + size + topic + pid + properties + data)
                packet.mark_sent()
                self.__log.mqtt(f'Outgoing message, pid={packet.pid}, qos={packet.qos}, topic={packet.topic}: {self.bytes_to_hex(data)}')
                self.last_tx = time()

        async def __receive_connect_ack(self):
            assert self.__backend is not None

            async with self.__receive_lock:
                code, remaining_length = await self.__backend.receive(2)
                if code != 0x20:
                    self.__backend.empty_receive_queue()
                    self.__log.mqtt(f'Bad CONACK packet: wrong header: {code}.')
                    return False
            
                response = await self.__backend.receive(remaining_length)
            
            if response[0] != 0:
                self.__log.mqtt('Bad CONACK packet: no clean session.')
                return False
            
            if response[1] != 0:
                self.__log.mqtt(f'Connection failed with code {response[3]}')
                return False

            self.last_rx = time()
            return True

        async def __receive_ping(self):
            assert self.__backend is not None

            length = await self.__backend.receive_variable_integer()
            if length != 0:
                self.__log.mqtt(f'Bad PINGRESP packet: unexpected length: {length}.')
                return
            self.__log.mqtt('Incoming PINGRESP.')
            self.last_rx = time()

        async def __receive_subscribe_ack(self):
            assert self.__backend is not None

            length = await self.__backend.receive_variable_integer()
            response = await self.__backend.receive(length)

            if len(response) < 4:
                self.__log.mqtt(f'Bad SUBACK packet: too short.')
                return

            pid = struct.unpack('!H', response[:2])[0]
            if response[2] != 0:
                self.__log.mqtt(f'Bad SUBACK packet: unexpected variable header length: {response[2]}.')
                return
            reason = response[3]
            if reason > 2:
                self.__log.mqtt(f'SUBACK failed with code {reason}')
                return
            
            self.__log.mqtt(f'Incoming SUBACK, pid={pid}, qos=unkown.')
            async with self.__lock:
                self.__subscribe_buffer.pop(pid, None)
            self.last_rx = time()
            

        async def __receive_publish_ack(self):
            assert self.__backend is not None

            length = await self.__backend.receive_variable_integer()
            response = await self.__backend.receive(length)
            if len(response) < 2:
                self.__log.mqtt(f'Bad PUBACK packet: too short, length={length}, packet={response}')
                return
            pid = response[0] << 8 | response[1]
            reason = response[2] if len(response) > 2 else b'\x00'

            async with self.__lock:
                self.__publish_buffer.pop(pid, None)

            if reason != b'\x00' and reason != b'\x10':
                self.__log.mqtt(f'Incoming PUBACK failed, pid={pid}, reason={reason}.')
            else:
                self.__log.mqtt(f'Incoming PUBACK, pid={pid}.')            
            self.last_rx = time()

        async def __receive_packet(self, code):
            assert self.__backend is not None

            qos = code & 6 >> 1

            length = await self.__backend.receive_variable_integer()
            response = await self.__backend.receive(length)

            offset = 2
            topic_length = struct.unpack('!H', response[:offset])[0]
            topic = response[offset:offset+topic_length].decode('utf-8')
            offset += topic_length


            try:
                self.__check_qos(qos)
            except:
                self.__log.mqtt(f'Invalid qos at topic {topic}, code {code}.')
                raise
            if qos > 0:
                pid = struct.unpack('!H', response[offset:offset+2])[0]
                offset += 2
            else:
                pid = 0

            property_length, byte_offset = self.__from_variable_integer(memoryview(response)[offset:])
            offset += property_length + byte_offset

            payload = response[offset:]

            if qos > 0:
                pkt = bytearray(b"\x40\x02\0\0")  # Send PUBACK
                struct.pack_into("!H", pkt, 2, pid)
                async with self.__send_lock:
                    await self.__backend.send(pkt)
                    self.last_tx = time()

            self.input_buffer.append(self.InputMessage(topic, payload, False))
            self.__log.mqtt(f'Incoming message pid={pid}, qos={qos}, topic={topic}: {self.bytes_to_hex(payload)}')
            self.last_rx = time()
            self.data_available_event.set()

        def __to_variable_integer(self, value):
            buffer = bytearray(b'/0/0/0/0')
            last_used_byte = 0
            while value > 0x7F:
                buffer[last_used_byte] = (value & 0x7F) | 0x80
                value >>= 7
                last_used_byte += 1
            buffer[last_used_byte] = value  
            return buffer[:last_used_byte + 1]
        
        def __from_variable_integer(self, buffer):
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
            if len(bytes) == 0:
                return ''
            return ubinascii.hexlify(bytes, ' ').decode('utf-8')
            
        @staticmethod
        def __string_to_bytes(string):
            return struct.pack("!H", len(string)) + bytearray(string, 'utf-8')

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

    class Backend:
        def __init__(self, ip, port, cert, cert_req):
            self.__socket = MicroSocket(ip, port, cert, cert_req)

        @property
        def is_connected(self):
            return self.__socket.is_connected
        
        def close(self):
            self.__socket.close()
        
        async def receive(self, length):
            return await self.__socket.receive(length)
            
        def empty_receive_queue(self):
            self.__socket.empty_receive_queue()
            
        async def receive_variable_integer(self):
            n = 0
            sh = 0
            while 1:
                res = await self.__socket.receive(1)
                b = res[0]
                n |= (b & 0x7F) << sh
                if not b & 0x80:
                    return n
                sh += 7
            
        async def send(self, data, length=0):
            await self.__socket.send(data, length)

        async def send_string(self, data):
            await self.__socket.send(struct.pack("!H", len(data)))
            await self.__socket.send(data)
        


            