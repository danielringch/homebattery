from asyncio import create_task, sleep
from struct import unpack
from sys import print_exception
from .interfaces.inverterinterface import InverterInterface
from ..core.addonmodbus import AddOnModbus
from ..core.types import to_port_id, run_callbacks, STATUS_ON, STATUS_OFF, STATUS_SYNCING, STATUS_FAULT

class RegistersXX00S:
    def __init__(self):
        self.switch = 0
        self.switch_flags = 0x0100
        self.status = 0
        self.max_power = 6
        self.temporary = 2
        self.power_limit = 3
        self.power = 11
        self.energy = 28

class RegistersTLX:
    def __init__(self):
        self.switch = 0
        self.switch_flags = 0x0000
        self.status = 0
        self.max_power = 6
        self.temporary = 2
        self.power_limit = 3
        self.power = 35
        self.energy = 55

class GrowattInverterModbus(InverterInterface):
    def __init__(self, name, config):
        from ..core.singletons import Singletons
        from ..core.types import TYPE_INVERTER
        self.__name = name
        self.__device_types = (TYPE_INVERTER,)
        self.__log = Singletons.log.create_logger(name)
        self.__slave_address = config['address']
        family = config['family']
        if family == 'xx00-S':
            self.__registers = RegistersXX00S()
        elif family == 'TL-X':
            self.__registers = RegistersTLX()
        else:
            raise Exception('Unknown device family: ', family)
        port = config['port']
        port_id = to_port_id(port)
        if Singletons.ports[port_id] is None:
            self.__port = AddOnModbus(port_id, 9600, 8, None, 1)
            Singletons.ports[port_id] = self.__port
        elif type(Singletons.ports[port_id]) is AddOnModbus:
            self.__port = Singletons.ports[port_id]
            if not self.__port.is_compatible(9600, 8, None, 1):
                raise Exception('Port ', port, ' has incompatible settings')
        else:
            raise Exception('Port ', port, 'is already in use')
        
        self.__payload_to_status = (STATUS_OFF, STATUS_ON)

        self.__active_errors = set()
        self.__error_debounced = False
        
        self.__max_power = None
        self.__power_hysteresis = max(int(config['power_hysteresis']), 1)

        self.__requested_status = STATUS_OFF
        self.__device_status = STATUS_SYNCING
        self.__shown_status = STATUS_SYNCING
        self.__requested_limit = 0
        self.__device_limit = None

        self.__power = 0
        self.__energy = 0
        self.__last_energy = None

        self.__worker_task = create_task(self.__worker())

        self.__on_status_change = list()
        self.__on_power_change = list()

    @property
    def device_types(self):
        return self.__device_types
    
    @property
    def name(self):
        return self.__name
    
    async def switch_inverter(self, on):
        self.__requested_status = STATUS_ON if on else STATUS_OFF
        if self.__device_status != self.__requested_status:
            self.__requested_limit = 1
            self.__log.info('New target state: ', self.__requested_status)
    
    def get_inverter_status(self):
        return self.__shown_status
    
    @property
    def on_inverter_status_change(self):
        return self.__on_status_change
    
    async def set_inverter_power(self, power):
        if self.__max_power is None:
            return 0
        limit = round(power * 100 / self.__max_power)
        limit = max(1, min(100, limit)) # not all models support 0%, so minimum is 1%
        power = limit * self.__max_power // 100
        if limit != self.__requested_limit:
            self.__log.info('New power target: ', limit, ' % / ', power, ' W')
            self.__requested_limit = limit
        return power
    
    def get_inverter_power(self):
        return self.__power
    
    @property
    def min_power(self):
        return 0

    @property
    def max_power(self):
        return self.__max_power if self.__max_power is not None else 0
    
    @property
    def on_inverter_power_change(self):
        return self.__on_power_change
    
    def get_inverter_energy(self):
        energy = self.__energy
        self.__energy = 0
        self.__log.info(energy, ' Wh fed since last check.')
        return energy

    async def __worker(self):
        schedule = (self.__read_power, self.__read_power, self.__read_power, self.__read_power, self.__read_status,\
            self.__read_power, self.__read_power, self.__read_power, self.__read_power, self.__read_power_limit,\
            self.__read_power, self.__read_power, self.__read_power, self.__read_power, self.__read_energy)

        while True:
            for request in schedule:
                try:
                    if self.__max_power is None:
                        await self.__read_max_power()
                        await sleep(1)
                        
                    if self.__device_status != self.__requested_status:
                        await self.__write_state()
                        await sleep(1)
                        await self.__read_status()
                        await sleep(1)

                    if self.__device_limit != self.__requested_limit:
                        await self.__write_limit()
                        await sleep(1)
                        await self.__read_power_limit()
                        await sleep(1)

                    await request()
                    await sleep(1)   
                except Exception as e:
                    self.__log.error('Cycle failed: ', e)
                    from ..core.singletons import Singletons
                    print_exception(e, Singletons.log.trace)

    def __handle_communication_error(self, present, message):
        if not present:
            self.__active_errors.discard(message)
            if self.__error_debounced and len(self.__active_errors) == 0:
                self.__error_debounced = False
                self.__handle_status_change()
            return False
        self.__log.error(message)
        if message in self.__active_errors:
            self.__error_debounced = True
            self.__handle_status_change()
        else:
            self.__active_errors.add(message)
        return True

    def __handle_status_change(self):
        new_status = self.__device_status
        if self.__max_power is None:
            new_status = STATUS_SYNCING
        if self.__error_debounced:
            new_status = STATUS_FAULT
        if new_status != self.__shown_status:
            self.__log.info('Status=', new_status)
            self.__shown_status = new_status
            run_callbacks(self.__on_status_change, self, new_status)

    async def __write_state(self):
        self.__log.info('Set state to ', self.__requested_status)
        value = (1 if self.__requested_status == STATUS_ON else 0) | self.__registers.switch_flags
        rx = await self.__port.write_single(self.__slave_address, self.__registers.switch, value)
        if self.__handle_communication_error((rx is None) or (len(rx) < 2), 'Can not write device state: communication error'):
            return
        received_state = unpack('!H', rx)[0] # type: ignore
        self.__handle_communication_error(received_state != value, 'Can not write device state: different value received')

    async def __write_limit(self):
        self.__log.info('Set limit to ', self.__requested_limit, ' %')
        # enable temporary mode
        rx = await self.__port.write_single(self.__slave_address, self.__registers.temporary, 1)
        if self.__handle_communication_error(rx is None, 'Can not enable temporary mode: communication error'):
            return
        temporary_mode = unpack('!H', rx)[0] # type: ignore
        if self.__handle_communication_error(temporary_mode != 1, 'Can not enable temporary mode: different value received'):
            return
        # write limit
        rx = await self.__port.write_single(self.__slave_address, self.__registers.power_limit, self.__requested_limit)
        if self.__handle_communication_error(rx is None, 'Can not write power limit: communication error'):
            return
        limit = unpack('!H', rx)[0] # type: ignore
        if self.__handle_communication_error(limit != self.__requested_limit, 'Can not write power limit: different value received'):
            return

    async def __read_status(self):
        rx = await self.__port.read_input(self.__slave_address, self.__registers.status, 1)
        if self.__handle_communication_error((rx is None) or (len(rx) < 2), 'Can not read device status: communication error'):
            return
        try:
            status = self.__payload_to_status[unpack('!H', rx)[0]] # type: ignore
        except:
            status = STATUS_FAULT
        if status != self.__device_status:
            self.__device_status = status
            self.__handle_status_change()

    async def __read_power(self):
        rx = await self.__port.read_input(self.__slave_address, self.__registers.power, 2)
        if self.__handle_communication_error((rx is None) or (len(rx) < 2), 'Can not read power: communication error'):
            return
        power = round(unpack('!I', rx)[0] / 10) # type: ignore
        if abs(power - self.__power) >= self.__power_hysteresis: # value changed
            self.__log.info('Power=', power, ' W')
            self.__power = power
            run_callbacks(self.__on_power_change, self, power)

    async def __read_energy(self):
        rx = await self.__port.read_input(self.__slave_address, self.__registers.energy, 2)
        if self.__handle_communication_error((rx is None) or (len(rx) < 4), 'Can not read energy: communication error'):
            return
        energy = round(unpack('!I', rx)[0] * 100) # type: ignore
        self.__log.info('Total energy=', energy, ' Wh')
        if self.__last_energy is None:
            self.__last_energy = energy
        elif energy > self.__last_energy:
            delta = energy - self.__last_energy
            self.__energy += delta
            self.__last_energy = energy

    async def __read_power_limit(self):
        rx = await self.__port.read_holding(self.__slave_address, self.__registers.power_limit, 1)
        if self.__handle_communication_error((rx is None) or (len(rx) < 2), 'Can not read power limit: communication error'):
            return
        self.__device_limit = unpack('!H', rx)[0] # type: ignore
        self.__log.info('Limit=', self.__device_limit, ' %')

    async def __read_max_power(self):
        rx = await self.__port.read_holding(self.__slave_address, self.__registers.max_power, 2)
        if self.__handle_communication_error((rx is None) or (len(rx) < 4), 'Can not read maximum power: communication error'):
            return
        self.__max_power = round(unpack('!I', rx)[0] / 10)
        self.__log.info('Maximum power=', self.__max_power, ' W')
        self.__handle_status_change()
