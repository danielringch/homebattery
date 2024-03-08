
from collections import deque
from machine import Pin, Timer

class Leds:
    def __init__(self):
        self.__queue = deque((), 10)
        self.__timer = Timer(-1)
        self.__timer.init(mode=Timer.PERIODIC, freq=10, callback=self.__on_timer)

        self.__mqtt_on = False
        self.__control_on = False
        self.__bluetooth_on = False

        self.__mqtt_pin = Pin(4 , Pin.OUT)
        self.__control_pin = Pin(3 , Pin.OUT)
        self.__bluetooth_pin = Pin(2 , Pin.OUT)


    def notify_mqtt(self):
        self.__mqtt_on = True

    def notify_control(self):
        self.__control_on = True

    def notify_bluetooth(self):
        self.__bluetooth_on = True

    def __on_timer(self, t):
        if self.__mqtt_on:
            self.__mqtt_pin.on()
            self.__mqtt_on = False
        else:
            self.__mqtt_pin.off()

        if self.__control_on:
            self.__control_pin.on()
            self.__control_on = False
        else:
            self.__control_pin.off()

        if self.__bluetooth_on:
            self.__bluetooth_pin.on()
            self.__bluetooth_on = False
        else:
            self.__bluetooth_pin.off()

leds = Leds()