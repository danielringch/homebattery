import asyncio, gc, json

from backend.core.logging import *
from backend.core.display import display
from backend.core.watchdog import Watchdog


__version__ = "0.1.0"

prefix = '[homebattery] {0}'


async def main():
    log.debug(f'Homebattery {__version__}')
    display.print('Homebattery', __version__)

    await asyncio.sleep(3.0)

    with open("/config/config.json", "r") as stream:
        config = json.load(stream)

    watchdog = Watchdog()
    
    from backend.core.network import Network
    log.debug('Connecting to network...')
    display.print('Connecting to', 'network...')
    network = Network(config)
    network.connect(watchdog)
    network.get_network_time(watchdog)

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

    from backend.modules.modeswitcher import ModeSwitcher
    from backend.modules.supervisor import Supervisor
    modeswitcher = ModeSwitcher(config, mqtt, inverter, charger)
    supervisor = Supervisor(config, watchdog, mqtt, modeswitcher, inverter, charger, battery)
    watchdog.feed()

    log.debug('Connecting to MQTT broker...')
    display.print('Connecting to', 'MQTT broker...')

    await mqtt.connect()
    watchdog.feed()

    battery_task = asyncio.create_task(battery.run())
    charger_task = asyncio.create_task(charger.run())
    inverter_task = asyncio.create_task(inverter.run())
    solar_task = asyncio.create_task(solar.run())
    modeswitcher.run()
    supervisor.run()

    gc.collect()

    from backend.modules.outputs import Outputs
    outputs = Outputs(mqtt, supervisor, battery, charger, inverter, solar)

    while True:
        gc.collect()
        await asyncio.sleep(0.5)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()

    try:
        loop.run_until_complete(main())
    finally:
        loop.close()

#exec(open("main.py").read())