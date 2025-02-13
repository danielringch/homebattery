from asyncio import create_task, sleep_ms
from ..interfaces.solarinterface import SolarInterface
from ...core.addonmodbus import AddOnModbus
from ...core.logging import CustomLogger
from ...core.triggers import triggers, TRIGGER_300S
from ...core.types import to_port_id, run_callbacks, STATUS_ON, STATUS_OFF, STATUS_SYNCING, STATUS_FAULT
from ...core.types import MEASUREMENT_STATUS, MEASUREMENT_VOLTAGE, MEASUREMENT_CURRENT, MEASUREMENT_POWER, MEASUREMENT_ENERGY
from ...helpers.streamreader import read_big_uint16
from ...helpers.valueaggregator import ValueAggregator

__current_multipliers_50 = [(1 / 2), 1, (1 / 4), (1 / 6)]
__current_multipliers_100 = [1, 2, (1 / 2), (1 / 3)]
__current_multipliers_200 = [2, 4, 1, (2 / 3)]
__current_multipliers_300 = [3, 6, (3 / 2), 1]

__connection_timeout = 3

class GenericSolar(SolarInterface):
    def __init__(self, name, config):
        from ...core.singletons import Singletons
        from ...core.types import TYPE_SOLAR
        self.__name = name
        self.__device_types = (TYPE_SOLAR,)
        self.__log: CustomLogger = Singletons.log.create_logger(name)
        self.__slave_address = int(config['address'])
        port = config['port']
        port_id = to_port_id(port)
        if Singletons.ports[port_id] is None:
            self.__port = AddOnModbus(port_id, 9600, 8, 0, 1)
            Singletons.ports[port_id] = self.__port
        elif type(Singletons.ports[port_id]) is AddOnModbus:
            self.__port = Singletons.ports[port_id]
            if not self.__port.is_compatible(9600, 8, 0, 1):
                raise Exception('Port ', port, ' has incompatible settings')
        else:
            raise Exception('Port ', port, 'is already in use')

        current_range = int(config['current_range'])
        if current_range == 50:
            self.__multipliers = __current_multipliers_50
        elif current_range == 100:
            self.__multipliers = __current_multipliers_100
        elif current_range == 200:
            self.__multipliers = __current_multipliers_200
        elif current_range == 300:
            self.__multipliers = __current_multipliers_300
        else:
            raise Exception()
        self.__multiplier: float = None
        self.__threshold = config['threshold']

        self.__voltage_avg = ValueAggregator()
        self.__current_avg = ValueAggregator()
        self.__power_avg = ValueAggregator()
        self.__power_under_threshold = ValueAggregator()

        self.__connected = __connection_timeout
        self.__status = STATUS_SYNCING
        self.__power = 0
        self.__voltage = 0.0
        self.__current = 0.0

        self.__energy_delta = 0
        self.__clear_energy = True

        self.__on_data = list()

        self.__worker_task = create_task(self.__worker())
        triggers.add_subscriber(self.__on_trigger)

    @property
    def device_types(self):
        return self.__device_types
    
    @property
    def name(self):
        return self.__name
    
    async def switch_solar(self, on):
        pass

    @property
    def on_solar_data(self):
        return self.__on_data
    
    def get_solar_data(self):
        return {
            MEASUREMENT_STATUS: self.__status,
            MEASUREMENT_VOLTAGE: self.__voltage,
            MEASUREMENT_CURRENT: self.__current,
            MEASUREMENT_POWER: self.__power
        }

    ###############

    async def __worker(self):
        while True:
            await sleep_ms(300)
            try:
                if self.__multiplier is None:
                    await self.__read_current_range()
                    continue

                if self.__clear_energy:
                    await self.__reset_energy()
                    continue

                energy = await self.__read_measurement()
                if energy is not None:
                    self.__energy_delta = energy

            except Exception as e:
                self.__log.error('Cycle failed: ', e)
                self.__log.trace(e)
    
    def __on_trigger(self, trigger_type):
        try:
            voltage = round(self.__voltage_avg.average(clear_afterwards=True), 2)
            current = round(self.__current_avg.average(clear_afterwards=True), 2)
            power = round(self.__power_avg.average(clear_afterwards=True))
            self.__log.info('Voltage=', voltage, 'V Current=', current, 'A Power=', power, 'W')
            if self.__status != STATUS_FAULT:
                self.__set_status(STATUS_ON if power > 0 else STATUS_OFF)
            data = {}
            if trigger_type == TRIGGER_300S:
                data[MEASUREMENT_STATUS] = self.__status
                data[MEASUREMENT_VOLTAGE] = voltage
                data[MEASUREMENT_CURRENT] = current
                data[MEASUREMENT_POWER] = power
                data[MEASUREMENT_ENERGY] = self.__get_energy()
            if voltage != self.__voltage:
                self.__voltage = voltage
                data[MEASUREMENT_VOLTAGE] = voltage
            if current != self.__current:
                self.__current = current
                data[MEASUREMENT_CURRENT] = current
            if power != self.__power:
                self.__power = power
                data[MEASUREMENT_POWER] = power
            if data:
                run_callbacks(self.__on_data, self, data)
        except Exception as e:
            self.__log.error('Trigger cycle failed: ', e)
            self.__log.trace(e)

    def __get_energy(self):
        energy = self.__energy_delta
        self.__energy_delta = 0
        if energy > 0:
            self.__clear_energy = True
        energy_under_threshold = round(self.__power_under_threshold.integral(clear_afterwards=True))
        self.__log.info(energy, ' Wh fed after last check, ', energy_under_threshold, 'Wh under threshold')
        energy = max(0, energy - energy_under_threshold)
        return energy

    def __set_status(self, new_status):
        status_changed = (new_status != self.__status)
        self.__status = new_status
        if status_changed:
            run_callbacks(self.__on_data, self, {MEASUREMENT_STATUS: self.__status})

    def __update_connection_status(self, success: bool):
        if success:
            self.__connected = __connection_timeout
            if self.__status == STATUS_FAULT:
                self.__set_status(STATUS_SYNCING)
            return
        self.__log.error('Failed to read sensor.')
        if self.__connected == 0:
            self.__set_status(STATUS_FAULT)
        if self.__connected > 0:
            self.__connected -= 1

    async def __read_measurement(self):
        rx = await self.__port.read_input(self.__slave_address, 0, 6)
        if (rx is None) or (len(rx) < 12):
            self.__update_connection_status(False)
            return None
        try:
            voltage = read_big_uint16(rx, 0) / 100
            current = read_big_uint16(rx, 2) / 100 * self.__multiplier
            power = (read_big_uint16(rx, 4) + (read_big_uint16(rx, 6) << 16)) * self.__multiplier / 10
            energy = (read_big_uint16(rx, 8) + (read_big_uint16(rx, 10) << 16)) * self.__multiplier
            self.__log.info('Measurement: ', voltage, 'V ', current, 'A ', power, 'W ', energy, 'Wh')
            self.__voltage_avg.add(voltage)
            if power < self.__threshold:
                current = 0.0
                power = 0.0
                self.__power_under_threshold.add(power)
            else:
                self.__power_under_threshold.add(0)
            self.__current_avg.add(current)
            self.__power_avg.add(power)
            self.__update_connection_status(True)
        except:
            self.__update_connection_status(False)
            return None

        return energy

    async def __read_current_range(self):
        self.__log.info('Read current range')
        rx = await self.__port.read_holding(self.__slave_address, 3, 1)
        if (rx is None) or (len(rx) < 2):
            self.__update_connection_status(False)
            self.__log.error('Failed to read current range')
            return
        index = read_big_uint16(rx, 0)
        if index >= len(self.__multipliers):
            self.__update_connection_status(False)
            self.__log.error('Invalid current range')
            return
        self.__multiplier = self.__multipliers[index]
        self.__log.info('multiplier=', self.__multiplier)
        self.__update_connection_status(True)

    async def __reset_energy(self):
        packet = bytearray(2)
        packet[0] = self.__slave_address
        packet[1] = 0x42
        rx = await self.__port.send_custom(packet)
        if (rx is None) or (len(rx) < 4) or (rx[1] != 0x42):
            self.__update_connection_status(False)
            self.__log.error('Failed to reset energy')
            return
        self.__clear_energy = False
        self.__update_connection_status(True)

