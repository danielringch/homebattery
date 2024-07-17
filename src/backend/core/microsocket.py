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
        def __init__(self, log, ip, port, cert, cert_req):
            self.__log = log
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
        
        async def receive_into(self, buffer, offset, length):
            async with self.__receive_lock:
                self.__check_socket()

                view = memoryview(buffer)
                bytes_remaining = length
                start = ticks_ms()
                while bytes_remaining > 0 and ticks_diff(ticks_ms(), start) < self.__timeout and self.__connected:
                    try:
                        chunk_size = self.__socket.readinto(view[offset:], bytes_remaining)
                        if chunk_size is not None:
                            bytes_remaining -= chunk_size
                            offset += chunk_size
                    except OSError as e:
                        self.__handle_socket_exception(e, 'receive')
                    await sleep(0.05)

                if bytes_remaining <= 0:
                    return offset
                elif not self.__connected:
                    raise MicroSocketClosedExecption()
                else:
                    raise MicroSocketTimeoutException()
                
        async def receiveline(self):
            async with self.__receive_lock:
                self.__check_socket()

                start = ticks_ms()
                data = None
                while ticks_diff(ticks_ms(), start) < self.__timeout and self.__connected and not data:
                    try:
                        data = self.__socket.readline()
                    except OSError as e:
                        self.__handle_socket_exception(e, 'receive')
                    await sleep(0.05)

                if data:
                    return data
                elif not self.__connected:
                    raise MicroSocketClosedExecption()
                else:
                    raise MicroSocketTimeoutException()
                
        async def receiveone(self):
            async with self.__receive_lock:
                self.__check_socket()

                start = ticks_ms()
                data = None
                while ticks_diff(ticks_ms(), start) < self.__timeout and self.__connected and not data:
                    try:
                        data = self.__socket.read(1)
                    except OSError as e:
                        self.__handle_socket_exception(e, 'receive')
                    await sleep(0.05)

                if data:
                    return data
                elif not self.__connected:
                    raise MicroSocketClosedExecption()
                else:
                    raise MicroSocketTimeoutException()
                
        async def receiveall(self, timeout: int):
            async with self.__receive_lock:
                self.__check_socket()

                self.__socket.settimeout(timeout)

                data = None
                try:
                    data = self.__socket.read()
                except OSError as e:
                    code = e.args[0]
                    if code not in BUSY_ERRORS:
                        self.__connected = False

                self.__socket.setblocking(False)

                return data
            
        def empty_receive_queue(self):
            self.__check_socket()
            _ = self.__socket.read()
            
        async def send(self, data, length=0):
            async with self.__send_lock:
                self.__check_socket()
            
                if length:
                    data = data[:length]
                else:
                    length = len(data)
                while length > 0 and self.__connected:
                    try:
                        chunk_size = self.__socket.write(data)
                        length -= chunk_size
                        if length > 0:
                            data = data[chunk_size:]
                    except OSError as e:
                        self.__handle_socket_exception(e, 'send')
                    await sleep(0.05)

                if length > 0:
                    raise MicroSocketTimeoutException()
                elif not self.__connected:
                    raise MicroSocketClosedExecption()

        def __check_socket(self):
            if not self.__connected:
                raise MicroSocketClosedExecption()
            
        def __handle_socket_exception(self, e, operation):
            code = e.args[0]
            if code in BUSY_ERRORS:
                return
            if code == ECONNRESET:
                self.__log.error('Socket ', operation, ' failed: connection reset.')
                self.__connected = False
            elif code == ECONNABORTED:
                self.__log.error('Socket ', operation, ' failed: connection aborted.')
                self.__connected = False
            else:
                self.__connected = False
                self.__log.error('Socket ', operation, ' failed: ', code)