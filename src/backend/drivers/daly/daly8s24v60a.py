from asyncio import sleep
from bluetooth import UUID as BT_UUID
from ubinascii import unhexlify
from ..interfaces.batteryinterface import BatteryInterface
from ...core.logging import CustomLogger
from ...core.devicetools import print_battery
from ...core.microblecentral import MicroBleCentral, MicroBleDevice, MicroBleTimeoutError
from ...core.types import run_callbacks
from ...helpers.batterydata import BatteryData
from ...helpers.streamreader import BigEndianSteamReader

class Daly8S24V60A(BatteryInterface):
    def __init__(self, name, config):
        from ...core.singletons import Singletons
        from ...core.types import TYPE_BATTERY
        self.__name = name
        self.__device_types = (TYPE_BATTERY,)
        self.__mac = config['mac']

        self.__ble = Singletons.ble
        self.__log: CustomLogger = Singletons.log.create_logger(name)

        self.__on_data = list()

        self.__device = None
        self.__receive_task = None
        self.__receiving = False
        self.__data = BatteryData(name)

    async def read_battery(self):
        rx_characteristic = None
        try:
            self.__ble.activate()
            self.__data.reset()

            if self.__device is None:
                self.__device = MicroBleDevice(self.__ble)
                await self.__device.connect(self.__mac, 1, timeout=10000)
            else:
                await self.__device.reconnect(timeout=10000)
            
            service = await self.__device.service(BT_UUID(0xfff0))
            tx_characteristic = await service.characteristic(BT_UUID(0xfff2))
            rx_characteristic = await service.characteristic(BT_UUID(0xfff1))
            rx_descriptor = await rx_characteristic.descriptor()

            rx_characteristic.enable_rx(self.__handle_blob)

            await tx_characteristic.write(b'')
            await rx_descriptor.write(unhexlify('01'), is_request=True)

            self.__receiving = True
            await tx_characteristic.write(unhexlify('d2030000003ed7b9'))

            for _ in range(50):
                await sleep(0.1)
                if self.__data.valid:
                    break
            else:
                self.__log.error('Failed to receive battery data.')
                return
            
            print_battery(self.__log, self.__data)
            run_callbacks(self.__on_data, self.__data)

        except MicroBleTimeoutError as e:
            self.__log.error(str(e))
        except Exception as e:
            self.__log.error('BLE error: ', e)
            self.__log.trace(e)
        finally:
            if self.__receive_task is not None:
                self.__receive_task.cancel()
            if rx_characteristic is not None:
                rx_characteristic.disable_rx()
            if self.__device is not None:
                await self.__device.disconnect()
            self.__ble.deactivate()

    @property
    def on_battery_data(self):
        return self.__on_data

    @property
    def name(self):
        return self.__name

    @property
    def device_types(self):
        return self.__device_types

    def __handle_blob(self, data):
        if not self.__receiving:
            return
        if len(data) < 128:
            self.__log.error('Dropping too short bluetooth packet, mac=', self.__mac, ' len=', len(data))
            return
        if data[0] != 0xd2 or data[1] != 0x03 or data[2] != 0x7c:
            self.__log.error('Dropping unknown bluetooth packet, mac=', self.__mac, ' data=', data)
            return
        
        if not self.__parse(data):
            self.__log.error('Dropping inplausible bluetooth packet, mac=', self.__mac, ' data=', data)
            return
        
        self.__receiving = False

    def __parse(self, data):
        reader = BigEndianSteamReader(data, 0)
        temp_1 = reader.uint8_at(94) - 40
        temp_2 = reader.uint8_at(96) - 40
        self.__data.temps = (temp_1, temp_2)
        self.__data.cells = tuple(x / 1000 for x in (reader.uint16_at(i) for i in range(3, 35, 2)) if x > 0)

        self.__data.v=reader.uint16_at(83) / 10
        self.__data.i=(reader.uint16_at(85) - 30000) / 10
        self.__data.soc=reader.uint16_at(87) / 10
        self.__data.c=reader.uint16_at(99) / 10
        self.__data.n=reader.uint16_at(105)

        data_plausible = True
        data_plausible &= self.__check_range(self.__data.v / len(self.__data.cells), 0.5, 5)
        data_plausible &= self.__check_range(self.__data.i, -300, 300)
        data_plausible &= self.__check_range(self.__data.soc, 0, 100)
        data_plausible &= self.__check_range(self.__data.c, 0, 750)
        data_plausible &= self.__check_range(self.__data.n, 0, 30000)
        for temp in self.__data.temps:
            data_plausible &= self.__check_range(temp, -40, 80)
        for cell in self.__data.cells:
            data_plausible &= self.__check_range(cell, 0.5, 5)

        if not data_plausible:
            self.__data.reset()
            return False

        self.__data.validate()
        return True

    @staticmethod
    def __check_range(value, min, max):
        return value >= min and value <= max