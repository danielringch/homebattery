from asyncio import create_task, Event, sleep
from collections import deque
from machine import Pin
from ..interfaces.solarinterface import SolarInterface
from ...core.addonserial import AddOnSerial
from ...core.types import to_port_id, run_callbacks, STATUS_ON, STATUS_OFF, STATUS_SYNCING
from ...helpers.valueaggregator import ValueAggregator

_OFF_STATES = const((3,4,5,7,247))

class VictronMppt(SolarInterface):
    def __init__(self, name, config):
        from ...core.singletons import Singletons
        from ...core.types import TYPE_SOLAR
        self.__name = name
        self.__device_types = (TYPE_SOLAR,)
        self.__log = Singletons.log.create_logger(name)
        port = config['port']
        port_id = to_port_id(port)
        if Singletons.ports[port_id] is not None:
            raise Exception('Port ', port, 'is already in use')
        
        self.__port = AddOnSerial(port_id)
        self.__port.set_mode(line=True)
        self.__port.connect(19200, 0, None, 1)
        self.__port.on_rx.append(self.__on_rx)
        self.__rx_buffer = deque(tuple(), 256)
        self.__rx_trigger = Event()
        self.__rx_task = create_task(self.__receive())

        self.__control_pin = Pin(4, Pin.OUT)
        self.__control_pin.off()

        self.__power_avg = ValueAggregator()
        self.__power = 0
        self.__energy_value = None
        self.__energy_delta = 0
        self.__last_status = STATUS_SYNCING

        self.__on_status_change = list()
        self.__on_power_change = list()

        self.__worker_task = create_task(self.__worker())


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
    def name(self):
        return self.__name

    @property
    def device_types(self):
        return self.__device_types
    
    async def __worker(self):
        cycles_count = 0
        while True:
            try:
                await sleep(6)
                cycles_count += 1
                power = round(self.__power_avg.average(clear_afterwards=True))
                if (power != self.__power) or (cycles_count >= 10):
                    self.__power = power
                    self.__log.info('Power: ', power, ' W')
                    run_callbacks(self.__on_power_change, self, power)
                if cycles_count >= 10:
                    cycles_count = 0
            except Exception as e:
                self.__log.error('Worker cycle failed: ', e)
                self.__log.trace(e)

    
    def __on_rx(self, data):
        self.__rx_buffer.append(data)
        self.__rx_trigger.set()

    async def __receive(self):
        while True:
            while self.__rx_buffer:
                line = self.__rx_buffer.popleft()
                if len(line) > 4: # 1 start 1 tab 1 value 1 newline
                    end = len(line)
                    while line[end - 1] <= 32: # find trailing whitespace characters
                        end -= 1
                    self.__parse(line, end)

            await self.__rx_trigger.wait()
            self.__rx_trigger.clear()

    def __parse(self, line: bytes, end: int):
        try:
            if line[0] == 80 and line[1] == 80 and line[2] == 86 and line[3] == 9: # PPV
                power = int(str(line[4:end], 'utf-8'))
                self.__power_avg.add(power)
            elif line[0] == 67 and line[1] == 83 and line[2]  == 9: # CS
                status = STATUS_ON if int(str(line[3:end], 'utf-8')) in _OFF_STATES else STATUS_OFF
                if status != self.__last_status:
                    self.__last_status = status
                    self.__log.info('Status: ', status)
                    run_callbacks(self.__on_status_change, self, status)
            elif line[0] == 72 and line[1] == 50 and line[2] == 48 and line[3] == 9: # H20
                energy = int(str(line[4:end], 'utf-8')) * 10
                if self.__energy_value is None: # first readout after startup
                    pass
                elif self.__energy_value > energy: # end of the day or begin of a new day
                    self.__energy_delta += energy
                else:
                    self.__energy_delta += energy - self.__energy_value
                self.__energy_value = energy
        except:
            self.__log.error('Invalid packet received: ', line)
