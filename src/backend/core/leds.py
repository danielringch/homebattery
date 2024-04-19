
from machine import Pin, Timer

class Leds:
    class SingleLed:
        def __init__(self, pin):
            self.__on = False
            self.__pin = Pin(pin, Pin.OUT)
            self.__pin.off()

        def switch(self, on):
            self.__on = on
            self.__pin.value(self.__on)

        def notify(self):
            self.__on = True

        def flash(self):
            self.__pin.value(self.__on)
            self.__on = False

    def __init__(self):
        self.__mqtt = self.SingleLed(18)
        self.__control = self.SingleLed(19)
        self.__bluetooth = self.SingleLed(20)
        self.__inverter = self.SingleLed(22)
        self.__charger = self.SingleLed(26)
        self.__solar = self.SingleLed(27)
        self.__watchdog = self.SingleLed("LED")

        self.__timer = Timer(-1)
        self.__timer.init(mode=Timer.PERIODIC, freq=10, callback=self.__on_timer)

    def notify_mqtt(self):
        self.__mqtt.notify()

    def notify_control(self):
        self.__control.notify()

    def notify_bluetooth(self):
        self.__bluetooth.notify()

    def notify_watchdog(self):
        self.__watchdog.notify()

    def switch_inverter_locked(self, on):
        self.__inverter.switch(on)

    def switch_charger_locked(self, on):
        self.__charger.switch(on)

    def switch_solar_locked(self, on):
        self.__solar.switch(on)

    def __on_timer(self, t):
        self.__mqtt.flash()
        self.__control.flash()
        self.__bluetooth.flash()
        self.__watchdog.flash()

leds = Leds()