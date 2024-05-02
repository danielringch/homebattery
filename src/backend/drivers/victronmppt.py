import asyncio, time
from machine import Pin

from .interfaces.solarinterface import SolarInterface
from ..core.addonport import addon_ports
from ..core.logging import log
from ..core.microdeque import MicroDeque
from ..core.types import bool2on, CallbackCollection, devicetype

class VictronMppt(SolarInterface):
    def __init__(self, name, config):
        self.__device_types = (devicetype.solar,)
        self.__log = log.get_custom_logger(name)
        port = config['port']
        if port == "ext1":
            self.__port = addon_ports[0]
        elif port == "ext2":
            self.__port = addon_ports[1]
        else:
           raise Exception(f'Unknown port: {port}')
        self.__port.connect(19200, 0, None, 1)
        self.__port.on_rx.add(self.__on_rx)
        self.__rx_packets = MicroDeque(32)
        self.__rx_task = asyncio.create_task(self.__receive())
        self.__rx_trigger = asyncio.Event()


        self.__control_pin = Pin(4, Pin.OUT)
        self.__control_pin.off()

        self.__power = None
        self.__energy_value = None
        self.__energy_delta = 0
        self.__shall_on = False
        self.__is_on = None

        self.__on_status_change = CallbackCollection()
        self.__on_power_change = CallbackCollection()


    async def switch_solar(self, on):
        self.__shall_on = on
        self.__control_pin.value(on)
    
    async def get_solar_status(self):
        return self.__is_on
    
    def get_solar_power(self):
        return self.__power
    
    @property
    def on_solar_status_change(self):
        return self.__on_status_change
    
    @property
    def on_solar_power_change(self):
        return self.__on_power_change
    
    async def get_solar_energy(self):
        energy = self.__energy_delta
        self.__energy_delta = 0
        self.__log.send(f'{energy} Wh fed after last check')
        return energy
    
    @property
    def device_types(self):
        return self.__device_types
    
    def __on_rx(self, data):
        if not self.__rx_packets.full():
            self.__rx_packets.append(data)
            self.__rx_trigger.set()
        else:
            self.__log.send('Input buffer overflow.')

    async def __receive(self):
        buffer = bytearray(42)
        view = memoryview(buffer)
        pointer = 0
        split = 0
        
        while True:
            while not self.__rx_packets.empty():
                blob = self.__rx_packets.popleft()
                for byte in blob:
                    if byte == 13:
                        # ignore \r
                        pass
                    elif byte == 10:
                        if pointer > 0:
                            header = view[:split]
                            payload = view[split:pointer] if pointer > split else None
                            self.__parse(header, payload)
                            pointer = 0
                            split = 0
                    elif byte == 9:
                        split = pointer
                    else:
                        buffer[pointer] = byte
                        pointer += 1
                        pointer = min(pointer, len(buffer) - 1)

            await self.__rx_trigger.wait()
            self.__rx_trigger.clear()

    def __parse(self, header, payload):
        try:
            header_str = str(header, 'utf-8')
            if header_str == 'PPV':
                power = int(str(payload, 'utf-8'))
                value_changed = power != self.__power
                self.__power = power
                if value_changed:
                    self.__log.send(f'Power: {power} W')
                    self.__on_power_change.run_all(power)
            elif header_str == 'CS':
                is_on = int(str(payload, 'utf-8')) in (3,4,5,7,247)
                value_changed = is_on != self.__is_on
                self.__is_on = is_on
                if value_changed:
                    self.__log.send(f'Status: {bool2on[is_on]}')
                    self.__on_status_change.run_all(is_on)
            elif header_str == 'H20':
                energy = int(str(payload, 'utf-8')) * 10
                if self.__energy_value is None: # first readout after startup
                    pass
                elif self.__energy_value > energy: # end of the day or begin of a new day
                    self.__energy_delta += energy
                else:
                    self.__energy_delta += energy - self.__energy_value
                self.__energy_value = energy
        except:
            self.__log.send(f'Invalid packet received: {bytes(header)} {bytes(payload) if payload is not None else None}')