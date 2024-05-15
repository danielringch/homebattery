from asyncio import create_task, Event, sleep
from micropython import const
from socket import getaddrinfo, socket, AF_INET, SOCK_DGRAM
from collections import namedtuple
from time import localtime
from uio import IOBase
from .byteringbuffer import ByteRingBuffer
from .microsocket import BUSY_ERRORS

_SEP1 = const(' [')
_SEP2 = const('] ')
_UTF8 = const('UTF-8')

class Logging:
    MessageBlob = namedtuple("MessageBlob", "channel message")

    def __init__(self):
        self.__blacklist = set()
        self.__task = None
        self.__counter = 0
        self.__buffer = ByteRingBuffer(2048, ignore_overflow=True)
        self.trace = TraceLogger(self, 'trace')

    def configure(self, config):
        config = config['logging']
        for sender in config['ignore']:
            self.__blacklist.add(sender)
        if 'host' in config:
            host, port = config['host'].split(':')
            self.__event = Event()
            self.__task = create_task(self.__run(host, port))
            self.__event.set()
        else:
            self.info('Logging via UDP disabled.')

    def create_logger(self, sender: str):
        return CustomLogger(self, sender)

    def get_custom_logger(self, prefix):
        return Customlogging(self, prefix)

    def debug(self, *msg):
        self.__send('debug', *msg)

    def error(self, *msg):
        self.__send('error', *msg)

    def info(self, *msg):
        self.__send('info', *msg)      

    def send(self, sender, *msg):
        self.__send(sender, *msg)

    def __send(self, channel, *msg):
        if channel in self.__blacklist:
            return
        now = localtime()  # Get current time
        formatted_time = "{:02d}:{:02d}:{:02d}".format(now[3], now[4], now[5])
        print(formatted_time, end='')
        print(_SEP1, end='')
        print(channel, end='')
        print(_SEP2, end='')
        for part in msg:
            print(str(part), end='')
        print('')

        if self.__task is not None:
            self.__buffer.extend(f'{self.__counter:03d} '.encode(_UTF8), 999)
            self.__counter += 1
            if self.__counter > 999:
                self.__counter = 0
            self.__buffer.extend(formatted_time.encode(_UTF8), 999)
            self.__buffer.extend(_SEP1.encode(_UTF8), 999)
            self.__buffer.extend(channel.encode(_UTF8), 999)
            self.__buffer.extend(_SEP2.encode(_UTF8), 999)
            for part in msg:
                self.__buffer.extend(str(part).encode(_UTF8), 999)
            self.__buffer.append(0xA) # newline
            self.__event.set()
    
    async def __run(self, host, port):
        address = getaddrinfo(host, int(port))[0][-1]
        socke = None

        while True:
            try:
                socke = socket(AF_INET, SOCK_DGRAM)
                while True:
                    await self.__event.wait()
                    self.__event.clear()
                    while not self.__buffer.empty():
                        blob = self.__buffer.popuntil(128)
                        if len(blob) > 0:
                            try:
                                socke.sendto(blob, address)
                            except OSError as e:
                                if e.args[0] in BUSY_ERRORS:
                                    pass
                        await sleep(0.05)                    
            except Exception as e:
                print(f'External logging failed: {e}')
            finally:
                if socke is not None:
                    socke.close()
                    socke = None

class Customlogging:
    def __init__(self, logger: Logging, prefix: str):
        self.__logger = logger
        self.__prefix = prefix

    def send(self, *msg):
        self.__logger.__send(self.__prefix, *msg)

class CustomLogger:
    def __init__(self, logger: Logging, sender: str):
        self.__logger = logger
        self.__sender = sender

    def info(self, *msg):
        self.__logger.__send(self.__sender, *msg)

    def error(self, *msg):
        self.__logger.__send('error@%s' % self.__sender, *msg)

class TraceLogger(IOBase):
    def __init__(self, logger: Logging, prefix: str):
        self.__logger = logger
        self.__prefix = prefix
        self.__buffer = list()

    def write(self, bytes):
        blob = bytes.decode('utf-8')
        self.__buffer.append(blob)
        if blob.endswith('\n'):
            lines = "".join(self.__buffer)
            for line in lines.split('\n')[:-1]:
                self.__logger.__send(self.__prefix, line)
            self.__buffer.clear()

    def writelines(self, lines):
        pass

    def read(self):
        raise ValueError()

    def encoding(self):
        return 'utf-8'

    def readable(self) -> bool:
        return False

    def writable(self) -> bool:
        return True
    
    def seekable(self) -> bool:
        return False
    
    def flush(self) -> None:
        self.__logger.__send(self.__prefix, "".join(self.__buffer))

    def close(self) -> None:
        pass

    def closed(self) -> bool:
        return False
    
    def fileno(self) -> int:
        raise OSError()
    
    def isatty(self) -> bool:
        return False
    
    def readline(self, _):
        raise ValueError
    
    def readlines(self, _):
        raise ValueError
    
    def seek(self, *_):
        raise OSError
    
    def tell(self, *_):
        raise OSError
    
    def truncate(self, *_):
        pass
