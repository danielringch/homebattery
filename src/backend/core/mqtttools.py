from micropython import const
from struct import pack_into, unpack
from .microsocket import MicroSocket, MicroSocketTimeoutException

_CONNECT_FIXED_LENGTH = const(6 + 1 + 1 + 2 + 1 + 2) # protocol + version + connect flags + keep alive + properties + id length
_SUBSCRIBE_FIXED_LENGTH = const(2 + 1 + 2 + 1) # pid + properties + topic length + options
_PUBLISH_FIXED_LENGTH = const(2 + 1) # topic length + properties

PACKET_TYPE_CONNACK = const(0x20)
PACKET_TYPE_PUBLISH = const(0x30)
PACKET_TYPE_PUBACK = const(0x40)
PACKET_TYPE_SUBACK = const(0x90)
PACKET_TYPE_PINGRESP = const(0xD0)

def connect_to_bytes(id: bytes, keep_alive: int, user: str, password: str, buffer: bytearray):
    packet_length = _CONNECT_FIXED_LENGTH + \
            len(id) + ((2 + len(user)) if user is not None else 0) + ((2 + len(password)) if password is not None else 0)
    # packet type
    buffer[0] = 0x10
    offset = 1
    # size
    length_buffer = to_variable_integer(packet_length)
    buffer[offset: offset + len(length_buffer)] = length_buffer
    offset += len(length_buffer)
    if offset + packet_length > len(buffer):
        raise OverflowError(f'CONNECT too big for internal buffer: {offset + packet_length} / {len(buffer)} bytes.')
    # protocol
    offset += pack_string_into(buffer, offset, 'MQTT')
    # version
    buffer[offset] = 0x05
    offset += 1
    # connect flags
    buffer[offset] = 0x02 + ((1 << 7) if user is not None else 0) + ((1 << 6) if password is not None else 0)
    offset += 1
    # keep alive
    pack_into('!H', buffer, offset, keep_alive)
    offset += 2   
    # properties
    buffer[offset] = 0x00
    offset += 1     
    # id
    id_length = len(id)
    pack_into('!H', buffer, offset, id_length)
    offset += 2
    buffer[offset: offset + id_length] = id
    offset += id_length
    # user
    if user is not None:
        offset += pack_string_into(buffer, offset, user)
    # password
    if password is not None:
        offset += pack_string_into(buffer, offset, password) 
    return offset       

def subscribe_to_bytes(pid: int, topic: str, qos: int, buffer: bytearray):
    packet_length = _SUBSCRIBE_FIXED_LENGTH + len(topic)
    # packet type
    buffer[0] = 0x82
    offset = 1
    # size
    length_buffer = to_variable_integer(packet_length)
    buffer[offset: offset + len(length_buffer)] = length_buffer
    offset += len(length_buffer)
    if offset + packet_length > len(buffer):
        raise OverflowError(f'SUBSCRIBE too big for internal buffer: {offset + packet_length} / {len(buffer)} bytes.')
    # pid
    pack_into('!H', buffer, offset, pid)
    offset += 2
    # properties
    buffer[offset] = 0
    offset += 1
    # topic
    offset += pack_string_into(buffer, offset, topic)
    # options
    pack_into('!B', buffer, offset, 1 << 5 | qos) # options
    offset += 1
    return offset

def publish_to_bytes(pid: int, topic: str, payload: bytes, qos: int, retain: bool, buffer: bytearray):
    payload_length = len(payload) if payload is not None else 0
    packet_length = _PUBLISH_FIXED_LENGTH + len(topic) + (2 if qos > 0 else 0) + payload_length
    # packet type
    buffer[0] = 0x30 | qos << 1 | retain # duplicate flag is not set here
    offset = 1
    # size
    length_buffer = to_variable_integer(packet_length)
    buffer[offset: offset + len(length_buffer)] = length_buffer
    offset += len(length_buffer)
    if offset + packet_length > len(buffer):
        raise OverflowError(f'PUBLISH too big for internal buffer: {offset + packet_length} / {len(buffer)} bytes.')
    # topic
    offset += pack_string_into(buffer, offset, topic)
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
    return offset

def mark_as_duplicate(buffer: bytearray, is_duplicate: bool):
    if is_duplicate and (buffer[0] & 0x30 == 0x30):
        buffer[0] |= 1 << 3

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

def pack_string_into(buffer, offset: int, string: str):
    length = len(string)
    pack_into('!H', buffer, offset, length)
    buffer[offset + 2: offset + 2 + length] = string.encode('utf-8')
    return length + 2