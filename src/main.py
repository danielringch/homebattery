import asyncio, gc, json, machine
from machine import Pin, WDT

from backend.core.logging import *
from backend.core.display import display


__version__ = "0.1.0"

prefix = '[daytradebatterybackend] {0}'


async def main():
    log.debug(f'DayTradeBattery Backend {__version__}')
    display.print('DayTradeBattery', __version__)

    with open("/config/config.json", "r") as stream:
        config = json.load(stream)

    await asyncio.sleep(1.0)

    from backend.core.network import Network
    log.debug('Connecting to network...')
    display.print('Connecting to', 'network...')
    network = Network(config)
    if not network.connect():
        machine.reset()
    watchdog = WDT(timeout=5000)

    log.debug('Configuring logging...')
    display.print('Configuring', 'logging...')
    log.configure(config)

    from backend.core.backendmqtt import Mqtt
    log.debug('Configuring MQTT...')
    display.print('Configuring', 'MQTT...')
    mqtt = Mqtt(config)

    watchdog.feed()
    gc.collect()

    display.print('Configuring', 'modules...')

    from backend.modules.devices import Devices
    devices = Devices(config)

    gc.collect()

    from backend.modules.battery import Battery
    battery = Battery(config, devices)

    gc.collect()

    from backend.modules.charger import Charger
    charger = Charger(config, devices, mqtt)

    gc.collect()

    from backend.modules.inverter import Inverter
    inverter = Inverter(config, devices, mqtt)

    gc.collect()

    from backend.modules.solar import Solar
    solar = Solar(config, devices)

    from backend.modules.supervisor import Supervisor
    supervisor = Supervisor(config, watchdog, mqtt, inverter, charger, battery)
    watchdog.feed()

    log.debug('Connecting to MQTT broker...')
    display.print('Connecting to', 'MQTT broker...')

    await mqtt.connect()
    watchdog.feed()

    battery_task = asyncio.create_task(battery.run())
    charger_task = asyncio.create_task(charger.run())
    inverter_task = asyncio.create_task(inverter.run())
    solar_task = asyncio.create_task(solar.run())

    supervisor_task = asyncio.create_task(supervisor.run())
    supervisor_ping = False
    def supervisor_callback():
        nonlocal supervisor_ping
        supervisor_ping = True
    supervisor.on_cycle_finished.add(supervisor_callback)

    gc.collect()

    from backend.modules.outputs import Outputs

    outputs = Outputs(mqtt, supervisor, battery, charger, inverter, solar)

    led = Pin("LED", Pin.OUT)
    while True:
        gc.collect()
        if supervisor_ping:
            led.toggle()
            supervisor_ping = False
        await asyncio.sleep(0.1)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()

    try:
        loop.run_until_complete(main())
    finally:
        loop.close()

#exec(open("main.py").read())