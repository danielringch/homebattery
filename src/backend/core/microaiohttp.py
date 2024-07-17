from json import loads
from ubinascii import b2a_base64

from .microsocket import MicroSocket, MicroSocketClosedExecption, MicroSocketException, MicroSocketTimeoutException

class HttpResponse:
    def __init__(self, sock, status, headers):
        self.__socket = sock
        self.__status = status
        self.__headers = headers
        self.encoding = 'utf-8'

    async def read(self):
        try:
            length = self.__headers.get('Content-Length', None)
            if length is None:
                buffer = await self.__socket.receiveall(0.5)
            else:
                buffer = bytearray(length)
                length = await self.__socket.receive_into(buffer, 0, length)
                
        except:
            raise
        return buffer

    async def json(self):
        data = await self.read()
        return loads(data)
    
    async def text(self):
        data = await self.read()
        return str(data, self.encoding)
    
    @property
    def status(self):
        return self.__status
    
class BasicAuth:
    def __init__(self, user, password):
        credentials = b2a_base64(f'{user}:{password}'.encode('ascii'), newline=False).decode('ascii')
        self.__header = b'Authorization: Basic %s\r\n' % credentials

    @property
    def header(self):
        return self.__header

class ClientSession:
    def __init__(self, log, host, port, auth=None):
        self.__log = log
        self.__host = host
        self.__port = port
        self.__auth = auth
        self.__socket = MicroSocket(self.__log, self.__host, self.__port, None, None)

    def __try_close_socket(self):
        if self.__socket.is_connected:
            self.__socket.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.__try_close_socket()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.__try_close_socket()

    async def request(self, method, path, data=None, headers={}):
        try:
            return await self._request(method, path, data, headers)
        except MicroSocketClosedExecption:
            pass
        except:
            self.__try_close_socket()
            raise
        self.__socket = MicroSocket(self.__log, self.__host, self.__port, None, None)
        return await self._request(method, path, data, headers)
        

    async def get(self, url, data=None, headers={}):
        return await self.request('GET', url, data, headers)

    async def post(self, url, data=None, headers={}):
        return await self.request('POST', url, data, headers)
    
    async def _request(self, method, path, data, headers):
        response_headers = {}

        await self.__socket.send(b'%s /%s HTTP/1.1\r\n' % (method, path))
        if not "Host" in headers:
            await self.__socket.send(b"Host: %s\r\n" % self.__host)
        if self.__auth:
            await self.__socket.send(self.__auth.header)
        for k in headers.items():
            await self.__socket.send(b'%s: %s\r\n' % k)

        if data:
            payload = data.encode('iso-8859-1')
            await self.__socket.send(b"Content-Length: %d\r\n" % len(payload))
        else:
            payload = None
                
        await self.__socket.send(b"\r\n")
        if payload:
            await self.__socket.send(payload)

        l = await self.__socket.receiveline()
        l = l.split(None, 2)
        if len(l) < 2:
            # Invalid response
            raise ValueError("HTTP error: BadStatusLine:\n%s" % l)
        status = int(l[1])
        while True:
            l = await self.__socket.receiveline()
            if not l or l == b"\r\n":
                break

            l = str(l, "utf-8")
            k, v = l.split(":", 1)
            response_headers[k] = v.strip()

        response = HttpResponse(self.__socket, status, response_headers)
        return response
