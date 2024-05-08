from asyncio import Lock, sleep
from socket import getaddrinfo, socket
from utime import ticks_ms, ticks_diff
from uerrno import EAGAIN, EINPROGRESS, ETIMEDOUT, ECONNRESET, ECONNABORTED

BUSY_ERRORS = [EAGAIN, EINPROGRESS, ETIMEDOUT, -110]

class MicroSocketException(Exception):
    def __str__(self):
        return 'MicroSocketException'

class MicroSocketTimeoutException(Exception):
    def __str__(self):
        return 'MicroSocketTimeoutException'

class MicroSocketClosedExecption(Exception):
    def __str__(self):
        return 'MicroSocketClosedExecption'

class MicroSocket:
        def __init__(self, ip, port, cert, cert_req):
            address = getaddrinfo(ip, port)[0][-1]
            cert = cert
            cert_req = cert_req

            self.__timeout = 5000

            self.__socket = socket()
            self.__socket.settimeout(1)

            self.__send_lock = Lock()
            self.__receive_lock = Lock()

            self.__connected = True
            try:
                self.__socket.connect(address)          
            except OSError as e:
                self.__handle_socket_exception(e, 'open')

            if self.__connected:
                if cert:
                    import ssl
                    self.__socket = ssl.wrap_socket(self.__socket, cert=cert, cert_reqs=cert_req)

                self.__socket.setblocking(False)
            else:
                raise MicroSocketClosedExecption()

        @property
        def is_connected(self):
            return self.__connected

        def close(self):
            self.__socket.close()
            self.__connected = False
        
        async def receive(self, length):
            async with self.__receive_lock:
                self.__check_socket()

                data = bytearray(length)
                buffer = memoryview(data)
                received_bytes_count = 0
                start = ticks_ms()
                while received_bytes_count < length and ticks_diff(ticks_ms(), start) < self.__timeout and self.__connected:
                    try:
                        chunk_size = self.__socket.readinto(buffer[received_bytes_count:], length - received_bytes_count)
                        if chunk_size is not None:
                            received_bytes_count += chunk_size
                    except OSError as e:
                        self.__handle_socket_exception(e, 'receive')
                    await sleep(0.05)
                end = ticks_ms()

                if received_bytes_count >= length:
                    return data
                elif not self.__connected:
                    raise MicroSocketClosedExecption()
                else:
                    raise MicroSocketTimeoutException()
                
        async def receiveline(self):
            async with self.__receive_lock:
                self.__check_socket()

                start = ticks_ms()
                data = None
                success = False
                while ticks_diff(ticks_ms(), start) < self.__timeout and self.__connected and not data:
                    try:
                        data = self.__socket.readline()
                    except OSError as e:
                        self.__handle_socket_exception(e, 'receive')
                    await sleep(0.05)
                end = ticks_ms()

                if data:
                    return data
                elif not self.__connected:
                    raise MicroSocketClosedExecption()
                else:
                    raise MicroSocketTimeoutException()
            
        def empty_receive_queue(self):
            self.__check_socket()
            _ = self.__socket.read()
            
        async def send(self, data, length=0):
            async with self.__send_lock:
                self.__check_socket()
            
                data = memoryview(data)
                if length:
                    data = data[:length]
                else:
                    length = len(data)
                start = ticks_ms()
                while data and ticks_diff(ticks_ms(), start) < self.__timeout and self.__connected:
                    try:
                        chunk_size = self.__socket.write(data)
                        data = data[chunk_size:]
                    except OSError as e:
                        self.__handle_socket_exception(e, 'send')
                    await sleep(0.05)
                end = ticks_ms()

                if data:
                    raise MicroSocketTimeoutException()
                elif not self.__connected:
                    raise MicroSocketClosedExecption()

        def __check_socket(self):
            if not self.__connected:
                raise MicroSocketClosedExecption()
            
        def __handle_socket_exception(self, e, operation):
            code = e.args[0]
            if code in (ECONNRESET, ECONNABORTED):
                self.__connected = False
            elif code in BUSY_ERRORS:
                pass
            else:
                self.__connected = False
                print(f'Socket {operation} failed: {code}.')