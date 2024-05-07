
import asyncio, socket, time
from collections import namedtuple
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
        self.__event = asyncio.Event()
        self.__task = asyncio.create_task(self.__run(config))
        self.__event.set()

    def get_custom_logger(self, prefix):
        return Customlogging(self, prefix)

    def alert(self, message):
        self.__send('alert', message)

    def debug(self, message):
        self.__send('debug', message)

    def display(self, message):
        self.__send('display', message)

    def error(self, message):
        self.__send('error', message)

    def info(self, message):
        self.__send('info', message)

    def inverter(self, message):
        self.__send('inverter', message)      

    def accounting(self, message):
        self.__send('accounting', message)

    def verbose(self, message):
        self.__send('verbose', message)

    def battery(self, message):
        self.__send('battery', message)

    def bluetooth(self, message):
        self.__send('bluetooth', message)

    def modeswitch(self, message):
        self.__send('modeswitch', message)

    def mqtt(self, message):
        self.__send('mqtt', message)

    def netzero(self, message):
        self.__send('netzero', message)

    def supervisor(self, message):
        self.__send('supervisor', message)

    def __send(self, channel, message):
        if channel in self.__blacklist:
            return
        now = time.localtime()  # Get current time
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
        address = socket.getaddrinfo(host, int(port))[0][-1]
        socke = None

        while True:
            try:
                socke = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
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
                        await asyncio.sleep(0.05)                    
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
