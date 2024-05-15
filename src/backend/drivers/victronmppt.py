from asyncio import create_task, Event
from machine import Pin
from .interfaces.solarinterface import SolarInterface
from ..core.byteringbuffer import ByteRingBuffer
from ..core.types import run_callbacks, STATUS_ON, STATUS_OFF, STATUS_SYNCING

class VictronMppt(SolarInterface):
    def __init__(self, name, config):
        from ..core.singletons import Singletons
        from ..core.types import TYPE_SOLAR
        self.__device_types = (TYPE_SOLAR,)
        self.__log = Singletons.log.create_logger(name)
        port = config['port']
        if port == "ext1":
            self.__port = Singletons.addon_port_1
        elif port == "ext2":
            self.__port = Singletons.addon_port_2
        else:
           raise Exception('Unknown port: ', port)
        self.__port.connect(19200, 0, None, 1)
        self.__port.on_rx.append(self.__on_rx)
        self.__rx_buffer = ByteRingBuffer(1024)
        self.__rx_task = create_task(self.__receive())
        self.__rx_trigger = Event()

        self.__control_pin = Pin(4, Pin.OUT)
        self.__control_pin.off()

        self.__power_hysteresis = max(int(config['power_hysteresis']), 1)
        self.__power = self.__power_hysteresis * -1 # make sure hysteresis is reached in the first run
        self.__energy_value = None
        self.__energy_delta = 0
        self.__last_status = STATUS_SYNCING

        self.__on_status_change = list()
        self.__on_power_change = list()


    async def switch_solar(self, on):
        self.__control_pin.value(on)
    
    def get_solar_status(self):
        return self.__last_status
    
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
        self.__log.info(energy, ' Wh fed after last check')
        return energy
    
    @property
    def device_types(self):
        return self.__device_types
    
    def __on_rx(self, data, length):
        if not self.__rx_buffer.full():
            self.__rx_buffer.extend(data, length)
            self.__rx_trigger.set()
        else:
            self.__log.error('Input buffer overflow.')

    async def __receive(self):
        buffer = bytearray(42)
        view = memoryview(buffer)
        pointer = 0
        split = 0
        
        while True:
            while not self.__rx_buffer.empty():
                byte = self.__rx_buffer.popleft()
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
                value_changed = abs(power - self.__power) >= self.__power_hysteresis
                if value_changed:
                    self.__log.info('Power: ', power, ' W')
                    run_callbacks(self.__on_power_change, power)
                    self.__power = power
            elif header_str == 'CS':
                status = STATUS_ON if int(str(payload, 'utf-8')) in (3,4,5,7,247) else STATUS_OFF
                if status != self.__last_status:
                    self.__log.info('Status: ', status)
                    run_callbacks(self.__on_status_change, status)
                self.__last_status = status
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
            self.__log.error('Invalid packet received: ', bytes(header) , bytes(payload) if payload is not None else None)
