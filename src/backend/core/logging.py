from asyncio import create_task, Event, sleep
from socket import getaddrinfo, socket, AF_INET, SOCK_DGRAM
from collections import namedtuple
from time import localtime
from uio import IOBase
from .byteringbuffer import ByteRingBuffer
from .microsocket import BUSY_ERRORS

class Logging:
    MessageBlob = namedtuple("MessageBlob", "channel message")

    def __init__(self):
        self.__blacklist = set()
        self.__task = None
        self.__counter = 0
        self.__buffer = ByteRingBuffer(2048)
        self.trace = TraceLogger(self, 'trace')

    def configure(self, config):
        config = config['logging']
        for sender in config['ignore']:
            self.__blacklist.add(sender)
        self.__event = Event()
        self.__task = create_task(self.__run(config))
        self.__event.set()

    def create_logger(self, sender: str):
        return CustomLogger(self, sender)

    def get_custom_logger(self, prefix):
        return Customlogging(self, prefix)

    def debug(self, message):
        self.__send('debug', message)

    def error(self, message):
        self.__send('error', message)

    def info(self, message):
        self.__send('info', message)      

    def send(self, sender, message):
        self.__send(sender, message)

    def __send(self, channel, message):
        if channel in self.__blacklist:
            return
        now = localtime()  # Get current time
        formatted_time = "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}".format(
            now[0], now[1], now[2],
            now[3], now[4], now[5]
        )
        message = f'[{formatted_time}] [{channel}] {message}'
        print(message)

        self.__buffer.extend(f'{self.__counter:03d} '.encode('utf-8'), 3, ignore_overflow=True)
        self.__counter += 1
        if self.__counter > 999:
            self.__counter = 0
        self.__buffer.extend(message.encode('utf-8'), 999, ignore_overflow=True)
        self.__buffer.append(0xA, ignore_overflow=True) # newline
        if self.__task is None:
            return
        try:
            self.__event.set()
        except AttributeError:
            pass
    
    async def __run(self, config):
        host, port = config['host'].split(':')
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

    def send(self, message):
        self.__logger.__send(self.__prefix, message)

class CustomLogger:
    def __init__(self, logger: Logging, sender: str):
        self.__logger = logger
        self.__sender = sender

    def info(self, message):
        self.__logger.__send(self.__sender, message)

    def error(self, message):
        self.__logger.__send(f'error] [{self.__sender}', message)

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
