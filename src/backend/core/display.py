from machine import Pin, I2C
from ..drivers.ssd1306 import SSD1306_I2C
from .types import operationmode, OperationMode

class Display:
    def __init__(self):
        try:
            i2c = I2C(id=0, sda=Pin(12), scl=Pin(13))
            self.__display = SSD1306_I2C(128, 64, i2c)

            self.__display.contrast(51)

            self.__display.show()
        except OSError as e:
            self.__display = None

        self.__mode = None
        self.__lock = None
        self.__p_rem = None
        self.__p_inv = None
        self.__c_bat = None

    def update_mode(self, mode: OperationMode):
        self.__mode = mode
        self.__refresh()

    def update_lock(self, lock: str):
        self.__lock = lock
        self.__refresh()

    def update_consumption(self, power: int):
        self.__p_rem = power
        self.__refresh()

    def update_inverter_power(self, power: int):
        self.__p_inv = power
        self.__refresh()

    def update_battery_capacity(self, capacity: float):
        self.__c_bat = f'{capacity:.1f}' if capacity is not None else None
        self.__refresh()

    def print(self, *lines: str):
        if self.__display is None:
            return
        self.__display.fill(0) 
        i = 0
        for line in lines:
            self.__display.text(line, 0, i, 1)
            i += 10
        self.__display.show()

    def __refresh(self):
        header = 'DayTradeBattery'
        mode = f'Mode: {self.__mode.name if self.__mode else "unknown"}'
        lock = f'! {self.__lock}' if self.__lock is not None else 'normal operation'
        p_rem = f'P_rem: {self.__p_rem} W'
        p_inv = f'P_inv: {self.__p_inv} W'
        c_bat  = f'C_bat: {self.__c_bat} Ah'
        self.print(header, mode, lock, p_rem, p_inv, c_bat)

display = Display()