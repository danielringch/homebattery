from asyncio import create_task, Event
from machine import Pin, I2C, Timer
from .ssd1306 import SSD1306

class UserInterface:
    def __init__(self):
        from .singletons import Singletons
        self.__log = Singletons.log.create_logger('ui')
        self.__update_event = Event()

        self.__sw1 = Pin(9, Pin.IN)
        self.__sw2 = Pin(8, Pin.IN)

        try:

            i2c = I2C(id=0, sda=Pin(0), scl=Pin(1))
            self.__display = SSD1306(128, 64, i2c)

            self.__display.contrast(51)

            self.__display.show()

            self.__display_task = create_task(self.__run())
        except OSError as e:
            self.__log.info('No display detected.')
            self.__display = None
            # no display means no baseboard, so there are no external pull up resistors
            self.__sw1.init(pull=Pin.PULL_UP)
            self.__sw2.init(pull=Pin.PULL_UP)

        self.__mode = None
        self.__lock = None
        self.__c_bat = None
        self.__p_sol = None
        self.__p_inv = None
        self.__p_grd = None

        self.__mqtt = SingleLed(18)
        self.__control = SingleLed(19)
        self.__bluetooth = SingleLed(20)
        self.__inverter = SingleLed(22)
        self.__charger = SingleLed(26)
        self.__solar = SingleLed(27)
        self.__watchdog = SingleLed("LED")

        self.__index = 0
        self.__timer = Timer(-1)
        self.__timer.init(mode=Timer.PERIODIC, freq=10, callback=self.__on_timer)

# jumpers

    @property
    def sw1(self):
        return not bool(self.__sw1.value())
    
    @property
    def sw2(self):
        return not bool(self.__sw2.value())

# display

    def update_mode(self, mode: str):
        self.__mode = mode
        self.__update_event.set()

    def update_lock(self, lock: str):
        self.__lock = lock
        self.__update_event.set()

    def update_battery_capacity(self, capacity: float):
        self.__c_bat = f'{capacity:.1f}' if capacity is not None else None
        self.__update_event.set()

    def update_solar_power(self, power: int):
        self.__p_sol = power
        self.__update_event.set()

    def update_inverter_power(self, power: int):
        self.__p_inv = power
        self.__update_event.set()

    def update_consumption(self, power: int):
        self.__p_grd = power
        self.__update_event.set()

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

# LEDs

    def notify_mqtt(self):
        self.__mqtt.flash()

    def notify_control(self):
        self.__control.flash()

    def notify_bluetooth(self):
        self.__bluetooth.flash()

    def notify_watchdog(self):
        self.__watchdog.flash()

    def switch_inverter_locked(self, on):
        self.__inverter.switch(on)

    def switch_charger_locked(self, on):
        self.__charger.switch(on)

    def switch_solar_locked(self, on):
        self.__solar.switch(on)

    def switch_inverter_on(self, on):
        self.__inverter.blink(on)

    def switch_charger_on(self, on):
        self.__charger.blink(on)

    def switch_solar_on(self, on):
        self.__solar.blink(on)

# internal

    async def __run(self):
        while True:
            await self.__update_event.wait()
            self.__update_event.clear()

            self.__refresh_display()

    def __refresh_display(self):
        mode = f'Mode: {self.__mode if self.__mode else "unknown"}'
        lock = f'! {self.__lock}' if self.__lock is not None else 'normal operation'
        c_bat = f'C_bat: {self.__c_bat} Ah'
        p_sol = f'P_sol: {self.__p_sol} W'
        p_inv = f'P_inv: {self.__p_inv} W'
        p_grd = f'P_grd: {self.__p_grd} W'
        self.print(mode, lock, c_bat, p_sol, p_inv, p_grd)

    def __on_timer(self, t):
        self.__mqtt.update(self.__index)
        self.__control.update(self.__index)
        self.__bluetooth.update(self.__index)
        self.__inverter.update(self.__index)
        self.__charger.update(self.__index)
        self.__solar.update(self.__index)
        self.__watchdog.update(self.__index)
        self.__index += 1
        if self.__index >= 20:
            self.__index = 0

class SingleLed:
    def __init__(self, pin):
        self.__steady = False
        self.__flash = False
        self.__blink = False
        self.__pin = Pin(pin, Pin.OUT)
        self.__pin.off()

    def switch(self, on):
        self.__steady = on

    def flash(self):
        self.__flash = True

    def blink(self, on):
        self.__blink = on

    def update(self, index):
        blink_on = self.__blink and index >= 10
        self.__pin.value(self.__steady or blink_on or self.__flash)
        self.__flash = False