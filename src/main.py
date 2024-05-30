from asyncio import get_event_loop
from backend.modules.homebattery import homebattery

if __name__ == "__main__":
    loop = get_event_loop()

    try:
        loop.run_until_complete(homebattery())
    finally:
        loop.close()

#exec(open("main.py").read())