from asyncio import create_task, sleep
from binascii import hexlify‚
from sys import print_exception
from ..interfaces.chargerinterface import ChargerInterface
from ...core.addonmodbus import AddOnModbus
from ...core.types import to_port_id, run_callbacks, STATUS_ON, STATUS_OFF, STATUS_SYNCING, STATUS_FAULT
from ...helpers.streamreader import read_big_uint16

class HeidelbergWallbox(ChargerInterface):
    def __init__(self, name, config):
        from ...core.singletons import Singletons
        from ...core.types import TYPE_CHARGER
        self.__name = name
        self.__device_types = (TYPE_CHARGER,)
        self.__log = Singletons.log.create_logger(name)
        self.__slave_address = config['address']
        port = config['port']
        port_id = to_port_id(port)
        if Singletons.ports[port_id] is None:
            self.__port = AddOnModbus(port_id, 19200, 8, 0, 1)
            Singletons.ports[port_id] = self.__port
        elif type(Singletons.ports[port_id]) is AddOnModbus:
            self.__port = Singletons.ports[port_id]
            if not self.__port.is_compatible(19200, 8, 0, 1):
                raise Exception('Port ', port, ' has incompatible settings')
        else:
            raise Exception('Port ', port, 'is already in use')
        
        self.__payload_to_status = (\
            STATUS_FAULT, # not defined \
            STATUS_FAULT, # not defined \
            STATUS_OFF, # A1, not connected, not allowed \
            STATUS_ON, # A2, not connected, allowed \
            STATUS_OFF, # B1, no request, not allowed \
            STATUS_ON, # B2, no request, allowed \
            STATUS_OFF, # C1, request, not allowed \
            STATUS_ON, # C2, request, allowed \
            STATUS_ON, # Derating \
            STATUS_FAULT, # car error \
            STATUS_OFF, # wallbox locked \
            STATUS_FAULT) # wallbox error

        self.__active_errors = set()
        self.__error_debounced = False

        self.__requested_status = STATUS_OFF
        self.__device_status = STATUS_SYNCING
        self.__shown_status = STATUS_SYNCING

        self.__standby_disabled = False

        self.__register_version = None
        self.__hw_min_current = None
        self.__hw_max_current = None

        self.__requested_current_limit = 16
        self.__actual_current_limit = None

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
    
    async def switch_charger(self, on):
        pass
    
    def get_charger_status(self):
        return self.__shown_status
    
    @property
    def on_charger_status_change(self):
        return self.__on_status_change
    
    async def get_charger_energy(self):
        return 0

    ###############

    async def __worker(self):
        schedule = (self.__read_status, self.__read_current, self.__read_current_limit, self.__read_power)

        while True:
            for request in schedule:
                try:
                    if self.__register_version is None:
                        await self.__read_register_version()
                        await sleep(1)

                    if self.__hw_min_current is None:
                        await self.__read_hardware_minimal_current()
                        await sleep(1)

                    if self.__hw_max_current is None:
                        await self.__read_hardware_maximal_current()
                        await sleep(1)

                    if self.__actual_current_limit != self.__requested_current_limit:
                        await self.__write_current_limit()
                        await sleep(1)
                        await self.__read_current_limit()
                        await sleep(1)

                    await request()
                    await sleep(5) 
                except Exception as e:
                    self.__log.error('Cycle failed: ', e)
                    from ...core.singletons import Singletons
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
            # TODO: reset values that might be reset by wallbox when leaving standby
        else:
            self.__active_errors.add(message)
        return True

    def __handle_status_change(self):
        new_status = self.__device_status
        if self.__error_debounced:
            new_status = STATUS_FAULT
        if new_status != self.__shown_status:
            self.__log.info('Status=', new_status)
            self.__shown_status = new_status
            run_callbacks(self.__on_status_change, new_status)

    async def __read_status(self):
        rx = await self.__port.read_input(self.__slave_address, 5, 1)
        if self.__handle_communication_error((rx is None) or (len(rx) < 2), 'Can not read device status: communication error'):
            return
        try:
            raw_status = read_big_uint16(rx, 0)
            status = self.__payload_to_status[raw_status] # type: ignore
        except:
            status = STATUS_FAULT
        self.__log.info('Status=', status, ' (', raw_status, ')')
        if status != self.__device_status:
            self.__device_status = status
            self.__handle_status_change()

    async def __read_register_version(self):
        rx = await self.__port.read_input(self.__slave_address, 4, 1)
        if self.__handle_communication_error((rx is None) or (len(rx) < 2), 'Can not read register version: communication error'):
            return
        value = read_big_uint16(rx, 0)
        self.__log.info('Register version=', hexlify(rx))
        self.__register_version = value

    async def __read_hardware_minimal_current(self):
        rx = await self.__port.read_input(self.__slave_address, 101, 1)
        if self.__handle_communication_error((rx is None) or (len(rx) < 2), 'Can not read hardware minimal current: communication error'):
            return
        amperes = read_big_uint16(rx, 0)
        self.__log.info('Hardware minimal current=', amperes, ' A')
        self.__hw_min_current = amperes

    async def __read_hardware_maximal_current(self):
        rx = await self.__port.read_input(self.__slave_address, 100, 1)
        if self.__handle_communication_error((rx is None) or (len(rx) < 2), 'Can not read hardware maximal current: communication error'):
            return
        amperes = read_big_uint16(rx, 0)
        self.__log.info('Hardware maximal current=', amperes, ' A')
        self.__hw_max_current = amperes

    async def __read_current(self):
        rx = await self.__port.read_input(self.__slave_address, 6, 3)
        if self.__handle_communication_error((rx is None) or (len(rx) < 6), 'Can not read current: communication error'):
            return
        amperes = tuple(read_big_uint16(rx, 2 * i) / 10 for i in range(3))
        self.__log.info('Currents=', amperes[0], ' A | ', amperes[1], ' A | ', amperes[2], ' A')

    async def __read_power(self):
        rx = await self.__port.read_input(self.__slave_address, 14, 1)
        if self.__handle_communication_error((rx is None) or (len(rx) < 2), 'Can not read power: communication error'):
            return
        power = read_big_uint16(rx, 0) / 1000
        self.__log.info('Power=', power, ' W')

    async def __read_current_limit(self):
        rx = await self.__port.read_holding(self.__slave_address, 261, 1)
        if self.__handle_communication_error((rx is None) or (len(rx) < 2), 'Can not read current limit: communication error'):
            return
        amperes = read_big_uint16(rx, 0) / 10
        self.__log.info('Current limit=', amperes, ' A')
        self.__actual_current_limit = amperes

    async def __write_current_limit(self):
        self.__log.info('Set current limit to ', self.__requested_current_limit, ' A')
        value = min(60, max(160, round(self.__requested_current_limit * 10)))
        rx = await self.__port.write_single(self.__slave_address, 261, value)
        if self.__handle_communication_error((rx is None) or (len(rx) < 2), 'Can not write current limit: communication error'):
            return
        rx_current = read_big_uint16(rx, 0) # type: ignore
        self.__handle_communication_error(rx_current != value, 'Can not write current limit: different value received')

