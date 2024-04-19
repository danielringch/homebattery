
from machine import Pin, Timer

class Leds:
    class SingleLed:
        def __init__(self, pin):
            self.__on = False
            self.__pin = Pin(pin, Pin.OUT)

        def notify(self):
            self.__on = True

        def switch(self):
            if self.__on:
                self.__pin.on()
                self.__on = False
            else:
                self.__pin.off()

    def __init__(self):
        self.__mqtt = self.SingleLed(18)
        self.__control = self.SingleLed(19)
        self.__bluetooth = self.SingleLed(20)
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

    def __on_timer(self, t):
        self.__mqtt.switch()
        self.__control.switch()
        self.__bluetooth.switch()
        self.__watchdog.switch()

leds = Leds()