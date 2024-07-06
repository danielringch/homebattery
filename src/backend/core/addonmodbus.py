from asyncio import sleep, Lock
from machine import Pin, UART
from struct import pack, pack_into
from time import sleep as sleep_blocking
from ubinascii import hexlify

class AddOnModbus:
    def __init__(self, port_id: int, baud, bits, parity, stop):
        from .singletons import Singletons
        self.__log = Singletons.log.create_logger(f'modbus{port_id}')
        self.__ui = Singletons.ui
        self.__external_lock = Lock()
        self.__internal_lock = Lock()

        parity_bytes = 1 if parity is not None else 0
        self.__byte_time = (1 + bits + stop + parity_bytes) / baud
        timeout = round(self.__byte_time * 1000 * 256 * 2.6) # max mtu is 256, 2.6 is byte + 1.5 char gap + 0.1 safety
        timeout_char = round(self.__byte_time * 1000 * 1.6)

        if port_id == 0:
            self.__uart = UART(1, tx=Pin(4) , rx=Pin(5), timeout=timeout, timeout_char=timeout_char)
            self.__rx_enable = Pin(6, Pin.OUT)
            self.__tx_enable = Pin(7, Pin.OUT)
        elif port_id == 1:
            self.__uart = UART(0, tx=Pin(12) , rx=Pin(13), timeout=timeout, timeout_char=timeout_char)
            self.__rx_enable = Pin(14, Pin.OUT)
            self.__tx_enable = Pin(15, Pin.OUT)
        else:
            raise Exception('Unknow port id: ', port_id)
        
        self.__settings = (baud, bits, parity, stop)
        self.__uart.init(baudrate=baud, bits=bits, parity=parity, stop=stop)

        self.__set_direction(False)

    @property
    def lock(self):
        return self.__external_lock

    def is_compatible(self, baud, bits, parity, stop):
        settings = (baud, bits, parity, stop)
        return settings == self.__settings
    
    async def read_holding(self, address, register, count):
        async with self.__internal_lock:
            tx = bytearray(8)
            pack_into('!BBHH', tx, 0, address, 3, register, count)
            rx = await self.__query(tx)
            if rx is None or not self.__check_input_packet(7, rx):
                return None
            return rx[3:-2]
    
    async def read_input(self, address, register, count):
        async with self.__internal_lock:
            tx = bytearray(8)
            pack_into('!BBHH', tx, 0, address, 4, register, count)
            rx = await self.__query(tx)
            if rx is None or not self.__check_input_packet(7, rx):
                return None
            return rx[3:-2]
    
    async def write_single(self, address, register, data):
        async with self.__internal_lock:
            self.__ui.notify_control()
            tx = bytearray(8)
            pack_into('!BBHH', tx, 0, address, 6, register, data)
            rx = await self.__query(tx)
            if rx is None or not self.__check_input_packet(8, rx):
                return None
            return rx[4:-2]
        
    async def write_multi(self, address, register, data):
        async with self.__internal_lock:
            self.__ui.notify_control()
            payload_length = 2 * len(data)
            tx = bytearray(9 + payload_length)
            pack_into('!BBHHB', tx, 0, address, 0x10, register, len(data), payload_length)
            index = 7
            for word in data:
                pack_into('!H', tx, index, word)
                index += 2
            rx = await self.__query(tx)
            if rx is None or not self.__check_input_packet(8, rx):
                return None
            return bytearray()

    async def __query(self, packet):
        # TX
        self.__set_direction(True)
        packet[-2:] = self.__get_crc(packet, len(packet) - 2)
        self.__log.info(f'TX {hexlify(packet)}')
        bytes = self.__uart.write(packet)
        self.__uart.flush()
        # no async here, sleep time must not be longer to avoid send collision on the line
        sleep_blocking(self.__byte_time + 0.001) # flush() returns when last byte is still being sent

        # RX
        self.__set_direction(False)
        for _ in range(10):
            await sleep(0.1)
            if self.__uart.any():
                break
        bytes = self.__uart.read(256)
        await sleep(self.__byte_time * 3.5) # minimum frame gap from modbus RTU spec
        if bytes is None:
            self.__log.error('No answer received')
            return None
        self.__log.info(f'RX {hexlify(bytes)}')
        return bytes

    def __get_crc(self, bytes, length):
        crc = 0xFFFF
        for i in range(length):
            crc = self.__add_byte_to_crc(crc, bytes[i])
        return pack('<H', crc)
    
    def __check_input_packet(self, min_length, buffer):
        if len(buffer) < min_length:
            self.__log.error('Invalid packet ', hexlify(buffer), ': too short')
            return False
        expected_crc = self.__get_crc(buffer, len(buffer) - 2)
        received_crc = buffer[-2:]
        if received_crc != expected_crc:
            self.__log.error('Invalid packet: wrong CRC; expected=', hexlify(expected_crc), ' received=', hexlify(received_crc))
            return False
        return True

    @micropython.viper
    def __add_byte_to_crc(self, crc: int, byte: int) -> int:
        crc ^= byte
        for i in range(8):
            if crc & 1:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
        return crc
    
    def __set_direction(self, send: bool):
        if send is None:
            self.__rx_enable.value(True)
            self.__tx_enable.value(False)
        elif send == True:
            self.__rx_enable.value(True)
            self.__tx_enable.value(True)
        else:
            self.__tx_enable.value(False)
            self.__rx_enable.value(False)
        sleep_blocking(0.001)
