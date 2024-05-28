from asyncio import create_task, sleep
from machine import Pin, UART

from .types import run_callbacks

class AddonPort:
    def __init__(self, uart_id: int, spi_id: int):
        if uart_id == 0:
            self.__uart = UART(0, tx=Pin(12) , rx=Pin(13), timeout=100)
        elif uart_id == 1:
            self.__uart = UART(1, tx=Pin(4) , rx=Pin(5), timeout=100)
        self.__uart = UART(uart_id)
        _ = spi_id

        self.__line_mode = False
        self.__connected = False
        self.__rx_task = None
        self.__on_rx = list()

    def set_mode(self, line: bool):
        self.__line_mode = line

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
                    if self.__line_mode:
                        bytes = self.__uart.readline()
                    else:
                        bytes = self.__uart.read(64)
                    if bytes is not None and len(bytes) > 0:
                        run_callbacks(self.on_rx, bytes)
                else:
                    break
            await sleep(0.1)

    @property
    def on_rx(self):
        return self.__on_rx