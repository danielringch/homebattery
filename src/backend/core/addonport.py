import asyncio
from machine import Pin, UART

from .microdeque import MicroDeque
from .types import CallbackCollection

class AddonPort:
    def __init__(self, uart_id: int, spi_id: int):
        if uart_id == 0:
            self.__uart = UART(0, tx=Pin(12) , rx=Pin(13))
        elif uart_id == 1:
            self.__uart = UART(1, tx=Pin(4) , rx=Pin(5))
        self.__uart = UART(uart_id)
        _ = spi_id

        self.__connected = False
        self.__rx_task = None
        self.__on_rx = CallbackCollection()

    def connect(self, baud, bits, parity, stop):
        self.__uart.init(baudrate=baud, bits=bits, parity=parity, stop=stop)
        self.__connected = True
        self.__rx_task = asyncio.create_task(self.__receive())

    def send(self, buffer):
        print(buffer)
        bytes = self.__uart.write(buffer)
        print(f'{bytes} Bytes sent')

    async def __receive(self):
        while self.__connected:
            while True:
                bytes = self.__uart.any()
                if bytes > 0:
                    data = self.__uart.read(min(64, bytes))
                    self.on_rx.run_all(data)
                else:
                    break
            await asyncio.sleep(0.1)

    @property
    def on_rx(self):
        return self.__on_rx

addon_ports = (AddonPort(1, 0), AddonPort(0, 1))