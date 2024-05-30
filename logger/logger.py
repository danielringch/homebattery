import argparse, logging, socket, sys
from logging.handlers import TimedRotatingFileHandler

def receive_log_messages(host, port):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as socke:
            socke.bind((host, port))
            print(f"[Listening on {host}:{port}]")

            while True:
                try:
                    payload, _ = socke.recvfrom(1024)
                    payload = payload.decode('utf-8', errors="replace")
                    logging.debug(payload)
                except socket.error as e:
                    print(f"[Error: {e}]")

    except Exception as e:
        print(f"[Error: {e}]")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Receive log messages over TCP socket")
    parser.add_argument("--host", type=str, help="Host address")
    parser.add_argument("--port", type=int, help="Port number")
    parser.add_argument("--file", type=str, help="Path to output file.")
    parser.add_argument("--backup", type=int, default=0, help="Limit number of backed up log files.")

    args = parser.parse_args()

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(fmt='%(message)s')

    class ModuleFilter(logging.Filter):
        def filter(self, record):
            return record.name == 'root'

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.terminator = ''
    stdout_handler.setFormatter(formatter)
    stdout_handler.addFilter(ModuleFilter())
    logger.addHandler(stdout_handler)

    file_handler = TimedRotatingFileHandler(args.file, when="midnight", interval=1, backupCount=args.backup)
    file_handler.terminator = ''
    file_handler.setFormatter(formatter)
    file_handler.addFilter(ModuleFilter())
    logger.addHandler(file_handler)

    receive_log_messages(args.host, args.port)