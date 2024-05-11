from asyncio import Event, sleep
from bluetooth import BLE
from bluetooth import UUID as BT_UUID
from micropython import const
from ubinascii import hexlify, unhexlify

_IRQ_PERIPHERAL_CONNECT = const(7)
_IRQ_PERIPHERAL_DISCONNECT = const(8)
_IRQ_GATTC_SERVICE_RESULT = const(9)
_IRQ_GATTC_SERVICE_DONE = const(10)
_IRQ_GATTC_CHARACTERISTIC_RESULT = const(11)
_IRQ_GATTC_CHARACTERISTIC_DONE = const(12)
_IRQ_GATTC_DESCRIPTOR_RESULT = const(13)
_IRQ_GATTC_DESCRIPTOR_DONE = const(14)
_IRQ_GATTC_READ_RESULT = const(15)
_IRQ_GATTC_READ_DONE = const(16)
_IRQ_GATTC_WRITE_DONE = const(17)
_IRQ_GATTC_NOTIFY = const(18)
_IRQ_MTU_EXCHANGED = const(21)
_IRQ_CONNECTION_UPDATE = const(27)

_BLUETOOTH_LOG_NAME = const('bluetooth')


class MicroBleAlreadyConnectedError(Exception):
    def __str__(self):
        return 'MicroBleAlreadyConnectedError'
    

class MicroBleNoDescriptorError(Exception):
    def __str__(self):
        return 'MicroBleNoDescriptorError'


class MicroBleTimeoutError(Exception):
    def __init__(self, action):
        super().__init__()
        self.__action = action
    def __str__(self):
        return f'MicroBleTimeoutError during: {self.__action}'


class MicroBleConnectionClosedError(Exception):
    def __str__(self):
        return 'MicroBleNoDescriptorError'

class MicroBleBuffer:
    def __init__(self, size):
        self.buffer = bytearray(size)
        self.length = 0

class MicroBleDevice:
    def __init__(self, central: MicroBleCentral):
        from .singletons import Singletons
        self.__log = Singletons.log.create_logger(_BLUETOOTH_LOG_NAME)
        self.__leds = Singletons.leds

        self.__central = central
        self.__ble = central.__ble
        self.__mtu = None
        self.__address = None
        self.__address_type = None
        self.__handle = None

        self.__services = []

        self.__service_event = Event()
        self.__characteristics_event = Event()
        self.__descriptors_event = Event()
        self.__read_event = Event()
        self.__write_event = Event()

    async def connect(self, mac, address_type, timeout = 5000):
        self.__printable_address = mac
        self.__address = unhexlify(mac.replace(':', ''))
        self.__address_type = address_type

        await self.reconnect(timeout)

    async def reconnect(self, timeout = 5000):
        if self.__central.__current_device is not None:
            raise MicroBleAlreadyConnectedError()

        try:
            self.__handle = None
            self.__mtu = None
            self.__central.__current_device = self
            self.__log.info(f'Connecting to {self.__printable_address}.')
            self.__ble.gap_connect(self.__address_type, self.__address)
            self.__leds.notify_bluetooth()
            for _ in range (timeout // 100):
                if self.__handle is not None:
                    break
                await sleep(0.1)
            else:
                self.__ble.gap_connect(None)
                raise MicroBleTimeoutError('connect')

            self.__ble.gattc_exchange_mtu(self.__handle)
            self.__leds.notify_bluetooth()
            for _ in range (timeout // 100):
                if self.__mtu is not None:
                    break
                await sleep(0.1)
            else:
                raise MicroBleTimeoutError('mtu exchange')
        except AttributeError:
            if self.__central.__current_device is None:
                raise MicroBleConnectionClosedError()
            else:
                raise
        finally:
            if self.__handle is None:
                self.__central.__current_device = None

    async def disconnect(self, timeout = 5000):
        try:
            if self.__handle is None:
                return
            self.__ble.gap_disconnect(self.__handle)
            self.__leds.notify_bluetooth()
            for _ in range (timeout // 100):
                if self.__central.__current_device is None and self.__handle is None:
                    return
                await sleep(0.1)
        finally:
            # Even if device did not respond, there is nothing we can do, so mark as disconnected
            self.__log.info(f'Disconnected from {self.__printable_address}.')
            self.__central.__current_device = None
            self.__handle = None


    async def service(self, uuid, timeout = 5000):
        result = self.__get_service_by_uuid(uuid)
        if result is not None:
            return result
        self.__service_event.clear()
        self.__ble.gattc_discover_services(self.__handle, uuid)
        for _ in range (timeout // 100):
            await sleep(0.1)
            if self.__service_event.is_set():
                result = self.__get_service_by_uuid(uuid)
                if result is not None:
                    return result
        raise MicroBleTimeoutError('service read')


    def __get_service_by_uuid(self, uuid):
        for service in self.__services:
            if service.uuid == uuid:
                return service
        return None


    def __get_service_by_handle(self, handle):
        for service in self.__services:
            if service.start_handle <= handle and service.end_handle >= handle:
                return service
        return None


    def __get_characteristic_by_handle(self, handle):
        service = self.__get_service_by_handle(handle)
        if service is None:
            return
        for characteristic in service.__characteristics:
            if characteristic.value_handle <= handle and characteristic.end_handle >= handle:
                return characteristic
        return None


    async def __write(self, target_handle, data, is_request, timeout):
        self.__write_event.clear()
        self.__leds.notify_bluetooth()
        self.__ble.gattc_write(self.__handle, target_handle, data, 1 if is_request else 0)
        if not is_request:
            return
        for _ in range (timeout // 100):
            await sleep(0.1)
            if self.__write_event.is_set():
                break
        else:
            raise MicroBleTimeoutError('data write')
        return


    async def __read(self, target_handle, timeout):
        self.__read_event.clear()
        self.__leds.notify_bluetooth()
        self.__ble.gattc_read(self.__handle, target_handle)
        for _ in range (timeout // 100):
            await sleep(0.1)
            if self.__read_event.is_set():
                break
        else:
            raise MicroBleTimeoutError('data read')
        return


class MicroBleService:
    def __init__(self, device, uuid, start_handle, end_handle):
        self.__device = device
        self.uuid = uuid
        self.start_handle = start_handle
        self.end_handle = end_handle

        self.__characteristics = []


    async def characteristic(self, uuid, timeout = 5000):
        result = self.__get_characteristic_by_uuid(uuid)
        if result is not None:
            return result
        self.__device.__characteristics_event.clear()
        self.__device.__ble.gattc_discover_characteristics(self.__device.__handle, self.start_handle, self.end_handle, uuid)
        for _ in range (timeout // 100):
            await sleep(0.1)
            if self.__device.__characteristics_event.is_set():
                result = self.__get_characteristic_by_uuid(uuid)
                if result is not None:
                    return result
        raise MicroBleTimeoutError('characteristic read')


    def __get_characteristic_by_uuid(self, uuid):
        for characteristic in self.__characteristics:
            if characteristic.uuid == uuid:
                return characteristic
        return None


class MicroBleCharacteristic:
    def __init__(self, device: MicroBleDevice, uuid, value_handle, end_handle):
        self.__device = device
        self.uuid = uuid
        self.value_handle = value_handle
        self.end_handle = end_handle

        self.__descriptor = None

        self.__rx_handler = None


    async def write(self, data, is_request=False, timeout = 5000):
        await self.__device.__write(self.value_handle, data, is_request, timeout)


    async def read(self, timeout = 5000):
        await self.__device.__read(self.value_handle, timeout)


    def enable_rx(self, handler):
        self.__rx_handler = handler

    def disable_rx(self):
        self.__rx_handler = None

    async def descriptor(self, timeout = 5000):
        if self.__descriptor is not None:
            return self.__descriptor
        if self.value_handle == self.end_handle:
            raise MicroBleNoDescriptorError()
        self.__device.__descriptors_event.clear()
        self.__device.__ble.gattc_discover_descriptors(self.__device.__handle, self.value_handle, self.end_handle)
        for _ in range (timeout // 100):
            await sleep(0.1)
            if self.__device.__descriptors_event.is_set():
                if self.__descriptor is not None:
                    return self.__descriptor
        raise MicroBleTimeoutError('descriptor read')

    def __enqueue(self, data):
        if self.__rx_handler is not None:
            self.__rx_handler(data)

class MicroBleDescriptor:
    def __init__(self, device, handle):
        self.__device = device
        self.handle = handle

    async def write(self, data, is_request=False, timeout = 5000):
        await self.__device.__write(self.handle, data, is_request, timeout)

    async def read(self, timeout = 5000):
        await self.__device.__read(self.handle, timeout)
    

class MicroBleCentral:
    def __init__(self):
        from .singletons import Singletons
        self.__log = Singletons.log.create_logger(_BLUETOOTH_LOG_NAME)
        self.__leds = Singletons.leds

        self.__ble = BLE()
        self.__buffer = MicroBleBuffer(512)
        self.__current_device = None
    
    def activate(self):
        self.__ble.active(True)
        self.__ble.config(mtu=512)
        self.__ble.irq(self.__on_irq)

    def deactivate(self):
        self.__ble.active(False)
            
    def __on_irq(self, event, data):
        self.__leds.notify_bluetooth()
        try:
            if event == _IRQ_PERIPHERAL_CONNECT:
                conn_handle, addr_type, addr = data
                printable_address = hexlify(addr, ':').decode('utf-8')
                self.__log.info(f'Connect event, handle={conn_handle}, type={addr_type}, addr={printable_address} .')
                if self.__current_device is None or \
                        addr_type != self.__current_device.__address_type or \
                        addr != self.__current_device.__address:
                    self.__log.info(f'No matching device for event.')
                    self.__ble.gap_disconnect(conn_handle)
                    return
                self.__current_device.__handle = conn_handle
            elif event == _IRQ_PERIPHERAL_DISCONNECT:
                conn_handle, _, _ = data
                self.__log.info(f'Disconnect event, handle={conn_handle} .')
                if not self.__check_connection_handle(conn_handle):
                    return
                self.__current_device.__handle = None
                self.__current_device = None
            elif event == _IRQ_MTU_EXCHANGED:
                conn_handle, mtu = data
                self.__log.info(f'Mtu exchanged event, handle={conn_handle}, mtu={mtu} .')
                if not self.__check_connection_handle(conn_handle):
                    return
                self.__current_device.__mtu = mtu
            elif event == _IRQ_GATTC_SERVICE_RESULT:
                conn_handle, start_handle, end_handle, uuid = data
                self.__log.info(f'Service event, connection={conn_handle}, start={start_handle}, end={end_handle}, uuid={uuid} .')
                if not self.__check_connection_handle(conn_handle):
                    return
                uuid = BT_UUID(uuid) # uuid is only passed as memoryview
                self.__current_device.__services.append(MicroBleService(self.__current_device, uuid, start_handle, end_handle))
            elif event == _IRQ_GATTC_SERVICE_DONE:
                self.__log.info('Service done event.')
                if self.__current_device is None:
                    return
                self.__current_device.__service_event.set()
            elif event == _IRQ_GATTC_CHARACTERISTIC_RESULT:
                conn_handle, end_handle, value_handle, properties, uuid = data
                self.__log.info(f'Characteristic event, connection={conn_handle}, end={end_handle}, value={value_handle}, uuid={uuid} .')
                if not self.__check_connection_handle(conn_handle):
                    return
                uuid = BT_UUID(uuid) # uuid is only passed as memoryview
                service = self.__current_device.__get_service_by_handle(value_handle)
                if service is None:
                    return
                service.__characteristics.append(MicroBleCharacteristic(self.__current_device, uuid, value_handle, end_handle))
            elif event == _IRQ_GATTC_CHARACTERISTIC_DONE:
                self.__log.info('Characteristic done event.')
                if self.__current_device is None:
                    return
                self.__current_device.__characteristics_event.set()
            elif event == _IRQ_GATTC_DESCRIPTOR_RESULT:
                conn_handle, dsc_handle, uuid = data
                self.__log.info(f'Descriptor event, connection={conn_handle}, value={dsc_handle}, uuid={uuid} .')
                if not self.__check_connection_handle(conn_handle) or uuid != BT_UUID(0x2902):
                    return
                characteristic = self.__current_device.__get_characteristic_by_handle(dsc_handle)
                if characteristic is None:
                    return
                characteristic.__descriptor = MicroBleDescriptor(self.__current_device, dsc_handle)
            elif event == _IRQ_GATTC_DESCRIPTOR_DONE:
                conn_handle, status = data
                self.__log.info('Descriptor done event, connection={conn_handle}, status={status}.')
                if not self.__check_connection_handle(conn_handle):
                    return
                self.__current_device.__descriptors_event.set()
            elif event == _IRQ_GATTC_READ_RESULT:
                conn_handle, value_handle, char_data = data
                self.__log.info(f'Read result event, connection={conn_handle}, characteristic={value_handle}, len={len(char_data)}')
                if not self.__check_connection_handle(conn_handle):
                    return
                characteristic = self.__current_device.__get_characteristic_by_handle(value_handle)
                if characteristic is None:
                    return
                characteristic.__enqueue(bytes(char_data))
            elif event == _IRQ_GATTC_READ_DONE:
                conn_handle, value_handle, status = data
                self.__log.info(f'Read done event, connection={conn_handle}, characteristic={value_handle}, status={status}')
                if not self.__check_connection_handle(conn_handle):
                    return
                self.__current_device.__read_event.set()
            elif event == _IRQ_GATTC_WRITE_DONE:
                conn_handle, value_handle, status = data
                self.__log.info(f'Write done event, connection={conn_handle}, characteristic={value_handle}, status={status}')
                if not self.__check_connection_handle(conn_handle):
                    return
                self.__current_device.__write_event.set()
            elif event == _IRQ_GATTC_NOTIFY:
                conn_handle, value_handle, notify_data = data
                self.__log.info(f'Notify event, connection={conn_handle}, characteristic={value_handle}, len={len(notify_data)}')
                if not self.__check_connection_handle(conn_handle):
                    return
                characteristic = self.__current_device.__get_characteristic_by_handle(value_handle)
                if characteristic is None:
                    return
                characteristic.__enqueue(bytes(notify_data))
            elif event == _IRQ_CONNECTION_UPDATE:
                # The remote device has updated connection parameters.
                conn_handle, conn_interval, conn_latency, supervision_timeout, status = data
                self.__log.info(f'Connection update event, connection={conn_handle}, interval={conn_interval}, latency={conn_latency}, supervision_timeout={supervision_timeout}, status={status}')
            else:
                self.__log.error(f'Unknown event: {event}.')
        except Exception as e:
            self.__log.error(f'Error in IRQ callback: {e}')


    def __check_connection_handle(self, handle):
        if self.__current_device is None or handle != self.__current_device.__handle:
            self.__log.error(f'No matching device for event.')
            return False
        return True
