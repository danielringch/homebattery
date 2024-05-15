from asyncio import create_task, sleep
from machine import Pin, UART

from .types import run_callbacks

class AddonPort:
    def __init__(self, uart_id: int, spi_id: int):
        if uart_id == 0:
            self.__uart = UART(0, tx=Pin(12) , rx=Pin(13))
        elif uart_id == 1:
            self.__uart = UART(1, tx=Pin(4) , rx=Pin(5))
        self.__uart = UART(uart_id)
        _ = spi_id

        self.__rx_buffer = bytearray(64)
        self.__connected = False
        self.__rx_task = None
        self.__on_rx = list()

    def connect(self, baud, bits, parity, stop):
        self.__uart.init(baudrate=baud, bits=bits, parity=parity, stop=stop)
        self.__connected = True
        self.__rx_task = create_task(self.__receive())

    def send(self, buffer):
        print(buffer)
        bytes = self.__uart.write(buffer)
        print(bytes, ' Bytes sent')

    async def __receive(self):
        while self.__connected:
            while True:
                if self.__uart.any() > 0:
                    length = self.__uart.readinto(self.__rx_buffer)
                    run_callbacks(self.on_rx, self.__rx_buffer, length)
                else:
                    break
            await sleep(0.1)

    @property
    def on_rx(self):
        return self.__on_rx