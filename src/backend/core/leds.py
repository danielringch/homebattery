
from machine import Pin, Timer

class Leds:
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

    def __init__(self):
        self.__mqtt = self.SingleLed(18)
        self.__control = self.SingleLed(19)
        self.__bluetooth = self.SingleLed(20)
        self.__inverter = self.SingleLed(22)
        self.__charger = self.SingleLed(26)
        self.__solar = self.SingleLed(27)
        self.__watchdog = self.SingleLed("LED")

        self.__index = 0
        self.__timer = Timer(-1)
        self.__timer.init(mode=Timer.PERIODIC, freq=10, callback=self.__on_timer)

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
