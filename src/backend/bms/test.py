import asyncio
import subprocess
import logging
from bleak import BleakClient, BleakScanner

async def main():
    print(f'Hi!')

    devices = await BleakScanner.discover()
    for d in devices:
        print(d)
        print(d.)

    #client = BleakClient('A4:C1:37:50:4A:97')
    #await client.connect()
    #print('connected')
    #asyncio.wait(3)
    #await client.disconnect()
    #print('disconnected')


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(main())
    finally:
        loop.close()