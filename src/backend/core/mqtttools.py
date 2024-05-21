from micropython import const
from struct import pack_into, unpack
from .microsocket import MicroSocket, MicroSocketTimeoutException

PACKET_TYPE_CONNECT = const(0x10)
PACKET_TYPE_CONNACK = const(0x20)
PACKET_TYPE_PUBLISH = const(0x30)
PACKET_TYPE_PUBACK = const(0x40)
PACKET_TYPE_SUBACK = const(0x90)
PACKET_TYPE_PINGRESP = const(0xD0)


def connect_to_bytes(id: bytes, keep_alive: int, user: str, password: str, buffer: bytearray):
    start = len(buffer)
    # password
    if password is not None:
        start = pack_string_into(buffer, start, password) 
    # user
    if user is not None:
        start = pack_string_into(buffer, start, user)
    # id
    id_length = len(id)
    buffer[start - id_length: start] = id
    start -= id_length + 2
    pack_into('!H', buffer, start, id_length)
    # properties
    start -= 1
    buffer[start] = 0x00
    # keep alive
    start -= 2 
    pack_into('!H', buffer, start, keep_alive)
    # connect flags
    start -= 1
    buffer[start] = 0x02 + ((1 << 7) if user is not None else 0) + ((1 << 6) if password is not None else 0)
    # version
    start -= 1
    buffer[start] = 0x05
    # protocol
    start = pack_string_into(buffer, start, 'MQTT')
    # fixed header
    return add_fixed_header(buffer, start, PACKET_TYPE_CONNECT)

def subscribe_to_bytes(pid: int, topic: str, qos: int, buffer: bytearray):
    start = len(buffer)
    # options
    start -= 1
    pack_into('!B', buffer, start, 1 << 5 | qos) # options
    # topic
    start = pack_string_into(buffer, start, topic)
    # properties
    start -= 1
    buffer[start] = 0
    # pid
    start -= 2
    pack_into('!H', buffer, start, pid)
    # fixed header
    return add_fixed_header(buffer, start, 0x82)

def publish_to_bytes(pid: int, topic: str, payload: bytes, qos: int, retain: bool, buffer: bytearray):
    start = len(buffer)
    # data
    if payload is not None and len(payload) > 0:
        start = pack_before(buffer, start, payload)
    # properties
    start -= 1
    buffer[start] = 0
    # pid
    if qos > 0:
        start -= 2
        pack_into('!H', buffer, start, pid)
    # topic
    start = pack_string_into(buffer, start, topic)
    # fixed header
    type = PACKET_TYPE_PUBLISH | qos << 1 | retain # duplicate flag is not set here
    return add_fixed_header(buffer, start, type)

def mark_as_duplicate(buffer: bytearray, index: int, is_duplicate: bool):
    if is_duplicate and (buffer[index] & 0xF0 == PACKET_TYPE_PUBLISH):
        buffer[index] |= 1 << 3

def puback_to_bytes(pid: int):
    buffer = bytearray(4)
    buffer[0] = PACKET_TYPE_PUBACK
    buffer[1] = 0x02
    pack_into('!H', buffer, 2, pid)
    return buffer

def pingreq_to_bytes():
    return b"\xc0\0"

def disconnect_to_bytes():
    return b"\xe0\0"

async def read_packet(sock: MicroSocket, buffer: bytearray):
    type = None
    while type is None or len(type) < 1:
        try:
            type = await sock.receiveone()
        except MicroSocketTimeoutException:
            pass
    
    type = type[0]

    offset = 0
    buffer[offset] = type
    offset += 1
    length, offset = await receive_variable_integer(sock, buffer, offset)
    if length > 0:
        offset = await sock.receive_into(buffer, offset, length)

    return type & 0xF0

def bytes_to_connack(buffer: bytes):
    payload_length, offset = from_variable_interger(buffer, 1)

    if payload_length < 4: # 1 byte flags, 1 byte reason
        return 'too short'

    flags = buffer[offset]
    offset += 1
    if flags != 0:
        return 'no clean session'
    
    reason = buffer[offset]
    if reason != 0:
        return f'reason: {reason}'
    
    return None

def bytes_to_pingresp(buffer: bytes):
    payload_length, _ = from_variable_interger(buffer, 1)
    return payload_length == 0

def bytes_to_suback(buffer: bytes):
    payload_length, offset = from_variable_interger(buffer, 1)

    if payload_length < 4: # 2 bytes PID, 1 byte properties, 1 byte payload
        return 'too short', None, None
    
    pid = unpack('!H', buffer[offset:offset + 2])[0]
    offset += 2

    property_length = buffer[offset]
    offset += 1

    if property_length != 0:
        return 'properties have content', pid, None
    
    reason = buffer[offset]
    if reason > 2:
        return f'error reason {reason}', pid, None
    
    return None, pid, None

def bytes_to_puback(buffer: bytes):
    payload_length, offset = from_variable_interger(buffer, 1)

    if payload_length < 2:
        return 'too short', None
    
    pid = unpack('!H', buffer[offset:offset + 2])[0]
    offset += 2

    reason = buffer[offset] if payload_length > 2 else 0

    if reason != 0 and reason != 0x10:
        return f'error reason {reason}', pid
    
    return None, pid

def bytes_to_publish(buffer: bytes):
    packet_length, offset = from_variable_interger(buffer, 1)
    packet_length += offset # type and packet length are excluded from packet length
    qos = (buffer[0] & 6) >> 1

    topic_length = unpack('!H', buffer[offset:offset + 2])[0]
    offset += 2
    topic = buffer[offset:offset + topic_length].decode('utf-8')
    offset += topic_length

    if qos > 0:
        pid = unpack('!H', buffer[offset:offset + 2])[0]
        offset += 2
    else:
        pid = 0

    property_length, offset = from_variable_interger(buffer, offset)

    offset += property_length # ignore properties for now

    payload = buffer[offset: packet_length]

    return pid, qos, topic, payload

def to_variable_integer(value):
    buffer = bytearray(b'/0/0/0/0')
    last_used_byte = 0
    while value > 0x7F:
        buffer[last_used_byte] = (value & 0x7F) | 0x80
        value >>= 7
        last_used_byte += 1
    buffer[last_used_byte] = value  
    return buffer[:last_used_byte + 1]

def from_variable_interger(buffer, offset):
    n = 0
    sh = 0
    while 1:
        b = buffer[offset]
        n |= (b & 0x7F) << sh
        if not b & 0x80:
            return n, offset + 1
        sh += 7
        offset += 1
    return 0, offset

async def receive_variable_integer(sock: MicroSocket, buffer: bytearray, offset: int):
    n = 0
    sh = 0
    while 1:
        res = await sock.receiveone()
        b = res[0]
        buffer[offset] = b
        offset += 1
        n |= (b & 0x7F) << sh
        if not b & 0x80:
            return n, offset
        sh += 7
    return 0, offset

def add_fixed_header(buffer: bytearray, end: int, type: int):
    packet_length = len(buffer) - end
    start = -1 + pack_before(buffer, end, to_variable_integer(packet_length))
    buffer[start] = type
    return start

def pack_string_into(buffer, end: int, string: str):
    if string is None or len(string) == 0:
        start = end - 2
        pack_into('!H', buffer, start, 0)
        return start
    encoded = string.encode('utf-8')
    start = -2 + pack_before(buffer, end, encoded)
    pack_into('!H', buffer, start, len(encoded))
    return start

def pack_before(buffer: bytearray, end, payload: bytes):
    start = end - len(payload)
    buffer[start:end] = payload
    return start