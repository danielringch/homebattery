from asyncio import sleep_ms, Lock
from machine import UART
from rp2 import StateMachine
from struct import pack, pack_into
from ubinascii import hexlify

from .rs485tools import init_rs485

class AddOnRs485:
    def __init__(self, port_id: int, baud, bits, parity, stop):
        from .singletons import Singletons
        self.__log = Singletons.log.create_logger(f'rs485_{port_id}')

        self.__external_lock = Lock()
        self.__internal_lock = Lock()

        assert bits == 8
        parity_bytes = 1 if parity is not None else 0
        self.__byte_time_us = (1 + bits + stop + parity_bytes) * 1000 * 1000 / baud
        timeout_ms = round(self.__byte_time_us * 256 * 2.6 / 1000) # max mtu is 256, 2.6 is byte + 1.5 char gap + 0.1 safety
        timeout_char_ms = round(self.__byte_time_us * 1.6 / 1000)

        self.__port_id = port_id
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

    async def send(self, data):
        async with self.__internal_lock:
            try:
                # TX
                self.__log.info(f'TX {hexlify(data)}')

                self.__sm.active(1)
                self.__sm.restart()
                self.__sm.put(data)

                # RX
                await sleep_ms(round(self.__byte_time_us * len(data) / 1000 + 1)) # wait roughly the send time to get an more exact RX timeout
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
            finally:
                await sleep_ms(500)
