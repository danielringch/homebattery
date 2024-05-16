from asyncio import create_task, Event, sleep
from micropython import const
from socket import getaddrinfo, socket, AF_INET, SOCK_DGRAM
from time import localtime
from uio import IOBase
from .microsocket import BUSY_ERRORS
from .types import SimpleFiFo

_UTF8 = const('utf-8')
_NEWLINE = const('\n')

class Logging:
    def __init__(self):
        self.__blacklist = set()
        self.__task = None
        self.__counter = 0
        self.__buffer = SimpleFiFo()
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
        self.__counter += 1
        if self.__counter > 999:
            self.__counter = 0
        now = localtime()  # Get current time
        formatted_time = '{:02d}:{:02d}:{:02d}'.format(now[3], now[4], now[5])
        self.__buffer.append('%03d ' % self.__counter)
        header = '%s [%s] ' % (formatted_time, channel)
        self.__buffer.append(header)
        print(header, end='')
        for part in msg:
            string = str(part)
            print(string, end='')
            self.__buffer.append(string)
        print('')
        self.__buffer.append(_NEWLINE)

        if self.__task is None:
            while not self.__buffer.empty:
                _ = self.__buffer.popleft()
        else:
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
                    while not self.__buffer.empty:
                        try:
                            socke.sendto(self.__buffer.popleft().encode(_UTF8), address)
                        except OSError as e:
                            if e.args[0] in BUSY_ERRORS:
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
        if blob.endswith(_NEWLINE):
            lines = "".join(self.__buffer)
            for line in lines.split(_NEWLINE)[:-1]:
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
