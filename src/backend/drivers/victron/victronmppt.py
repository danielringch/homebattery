from asyncio import create_task, Event
from collections import deque
from machine import Pin
from ..interfaces.solarinterface import SolarInterface
from ...core.addonserial import AddOnSerial
from ...core.triggers import TRIGGER_300S, triggers
from ...core.types import to_port_id, run_callbacks, STATUS_ON, STATUS_OFF, STATUS_SYNCING
from ...core.types import MEASUREMENT_STATUS, MEASUREMENT_POWER, MEASUREMENT_ENERGY
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

        self.__on_data = []

        triggers.add_subscriber(self.__on_trigger)


    async def switch_solar(self, on):
        self.__control_pin.value(on)

    @property
    def on_solar_data(self):
        return self.__on_data
    
    def get_solar_data(self):
        return {
            MEASUREMENT_STATUS: self.__last_status,
            MEASUREMENT_POWER: self.__power
        }
    
    @property
    def name(self):
        return self.__name

    @property
    def device_types(self):
        return self.__device_types
    
    def __on_trigger(self, trigger_type):
        try:
            power = round(self.__power_avg.average(clear_afterwards=True))
            data = {}
            if trigger_type == TRIGGER_300S:
                data[MEASUREMENT_STATUS] = self.__last_status
                data[MEASUREMENT_POWER] = power
                data[MEASUREMENT_ENERGY] = self.__get_energy()
            if power != self.__power:
                self.__power = power
                self.__log.info('Power: ', power, ' W')
                data[MEASUREMENT_POWER] = power
            if data:
                run_callbacks(self.__on_data, self, data)
        except Exception as e:
            self.__log.error('Trigger cycle failed: ', e)
            self.__log.trace(e)
    
    def __on_rx(self, data):
        self.__rx_buffer.append(data)
        self.__rx_trigger.set()

    def __get_energy(self):
        energy = self.__energy_delta
        self.__energy_delta = 0
        self.__log.info(energy, ' Wh fed after last check')
        return energy

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
                    run_callbacks(self.__on_data, self, {MEASUREMENT_STATUS: status})
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
