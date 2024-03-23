
import asyncio, socket, struct, time
from collections import namedtuple, deque
from uio import IOBase
from .microsocket import BUSY_ERRORS

class Logging:
    MessageBlob = namedtuple("MessageBlob", "channel message")

    def __init__(self):
        self.__task = None
        self.__queue = deque((), 50)
        self.trace = TraceLogger(self, 'trace')

    def configure(self, config):
        self.__event = asyncio.Event()
        self.__task = asyncio.create_task(self.__run(config, self.__queue))
        self.__event.set()

    def get_custom_logger(self, prefix):
        return Customlogging(self, prefix)

    def alert(self, message):
        self.__send('alert', message)

    def debug(self, message):
        self.__send('debug', message)

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

    def mqtt(self, message):
        self.__send('mqtt', message)

    def netzero(self, message):
        self.__send('netzero', message)

    def supervisor(self, message):
        self.__send('supervisor', message)

    def __send(self, channel, message):
        now = time.localtime()  # Get current time
        formatted_time = "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}".format(
            now[0], now[1], now[2],
            now[3], now[4], now[5]
        )
        message = f'[{formatted_time}] [{channel}] {message}'
        print(message)
        self.__queue.append(message)
        if self.__task is None:
            return
        try:
            self.__event.set()
        except AttributeError:
            pass
    
    async def __run(self, config, queue):
        config = config['logging']
        host, port = config['host'].split(':')
        address = socket.getaddrinfo(host, int(port))[0][-1]
        socke = None

        while True:
            try:
                counter = 0
                socke = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                while True:
                    await self.__event.wait()
                    self.__event.clear()
                    while len(queue) > 0:
                        message = (f'{counter:03d} ' + queue.popleft() + '\n').encode('utf-8')
                        try:
                            socke.sendto(message, address)
                        except OSError as e:
                            if e.args[0] in BUSY_ERRORS:
                                pass
                        counter += 1
                        if counter > 999:
                            counter = 0
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

log = Logging()
