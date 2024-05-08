from machine import Pin, I2C
from micropython import const
from .singletons import Singletons
from .ssd1306 import SSD1306
from .types import OperationMode

_DISPLAY_LOG_NAME = const('display')

class Display:
    def __init__(self):
        self.__log = Singletons.log().create_logger(_DISPLAY_LOG_NAME)
        try:

            i2c = I2C(id=0, sda=Pin(0), scl=Pin(1))
            self.__display = SSD1306(128, 64, i2c)

            self.__display.contrast(51)

            self.__display.show()
        except OSError as e:
            self.__log.info('No display detected.')
            self.__display = None

        self.__mode = None
        self.__lock = None
        self.__c_bat = None
        self.__p_sol = None
        self.__p_inv = None
        self.__p_grd = None

    def update_mode(self, mode: OperationMode):
        self.__mode = mode
        self.__refresh()

    def update_lock(self, lock: str):
        self.__lock = lock
        self.__refresh()

    def update_battery_capacity(self, capacity: float):
        self.__c_bat = f'{capacity:.1f}' if capacity is not None else None
        self.__refresh()

    def update_solar_power(self, power: int):
        self.__p_sol = power
        self.__refresh()

    def update_inverter_power(self, power: int):
        self.__p_inv = power
        self.__refresh()

    def update_consumption(self, power: int):
        self.__p_grd = power
        self.__refresh()

    def print(self, *lines: str):
        if self.__display is None:
            return
        self.__display.fill(0) 
        i = 0
        for line in lines:
            self.__display.text(line, 0, i, 1)
            i += 10
        try:
            self.__display.show()
        except OSError as e:
            self.__log.error(f'Update failed: {e}')

    def __refresh(self):
        mode = f'Mode: {self.__mode.name if self.__mode else "unknown"}'
        lock = f'! {self.__lock}' if self.__lock is not None else 'normal operation'
        c_bat = f'C_bat: {self.__c_bat} Ah'
        p_sol = f'P_sol: {self.__p_sol} W'
        p_inv = f'P_inv: {self.__p_inv} W'
        p_grd = f'P_grd: {self.__p_grd} W'
        self.print(mode, lock, c_bat, p_sol, p_inv, p_grd)
