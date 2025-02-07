from asyncio import sleep_ms, Lock
from machine import UART
from rp2 import StateMachine
from struct import pack, pack_into
from ubinascii import hexlify

from .rs485tools import init_rs485

class AddOnModbus:
    def __init__(self, port_id: int, baud, bits, parity, stop):
        from .singletons import Singletons
        self.__log = Singletons.log.create_logger(f'modbus{port_id}')
        self.__ui = Singletons.ui
        self.__external_lock = Lock()
        self.__internal_lock = Lock()

        assert bits == 8
        parity_bytes = 1 if parity is not None else 0
        self.__byte_time_us = (1 + bits + stop + parity_bytes) * 1000 * 1000 / baud
        timeout_ms = round(self.__byte_time_us * 256 * 2.6 / 1000) # max mtu is 256, 2.6 is byte + 1.5 char gap + 0.1 safety
        timeout_char_ms = round(self.__byte_time_us * 1.6 / 1000)

        self.__uart: UART = None # type: ignore
        self.__sm: StateMachine = None # type: ignore
        self.__uart, self.__sm = init_rs485(port_id, baud, bits, parity, stop, timeout_ms, timeout_char_ms)

        self.__settings = (baud, bits, parity, stop)

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
        
    async def send_custom(self, packet):
        async with self.__internal_lock:
            self.__ui.notify_control()
            tx = packet + bytearray(2)
            rx = await self.__query(tx)
            if rx is None or not self.__check_input_packet(4, rx):
                return None
            return rx

    async def __query(self, packet):
        # TX
        packet[-2:] = self.__get_crc(packet, len(packet) - 2)
        self.__log.info(f'TX {hexlify(packet)}')

        self.__sm.active(1)
        self.__sm.restart()
        self.__sm.put(packet)

        # RX
        await sleep_ms(round(self.__byte_time_us * len(packet) / 1000 + 1)) # wait roughly the send time to get an more exact RX timeout
        for _ in range(11):
            await sleep_ms(100)
            if self.__uart.any():
                break
        self.__sm.active(0)
        bytes = self.__uart.read(256)
        await sleep_ms(round(self.__byte_time_us * 3.5 / 1000)) # minimum frame gap from modbus RTU spec
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
