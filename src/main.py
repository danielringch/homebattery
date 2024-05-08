import asyncio, gc, json
gc.collect()
from backend.core.watchdog import Watchdog
gc.collect()
from backend.modules.devices import Devices
gc.collect()
from backend.modules.battery import Battery
gc.collect()
from backend.modules.charger import Charger
gc.collect()
from backend.modules.inverter import Inverter
gc.collect()
from backend.modules.solar import Solar
gc.collect()
from backend.modules.modeswitcher import ModeSwitcher
gc.collect()
from backend.modules.supervisor import Supervisor
gc.collect()
from backend.modules.outputs import Outputs
gc.collect()

__version__ = "0.1.0"

prefix = '[homebattery] {0}'


async def main():
    gc.collect()
    from backend.core.logging_singleton import log
    from backend.core.userinterface_singleton import display
    log.debug(f'Homebattery {__version__}')
    display.print('Homebattery', __version__)

    await asyncio.sleep(3.0)

    with open("/config.json", "r") as stream:
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
    devices = Devices(config, mqtt)
    battery = Battery(config, devices)
    charger = Charger(config, devices, mqtt)
    inverter = Inverter(config, devices, mqtt)
    solar = Solar(config, devices, mqtt)
    modeswitcher = ModeSwitcher(config, mqtt, inverter, charger, solar)
    supervisor = Supervisor(config, watchdog, mqtt, modeswitcher, inverter, charger, battery)
    watchdog.feed()

    gc.collect()

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
    outputs = Outputs(mqtt, supervisor, battery, charger, inverter, solar)

    gc.collect()

    i = 0
    while True:
        gc.collect()
        await asyncio.sleep(1)
        i += 1
        if i >= 60:
            i = 0
            log.info(f'Used memory: {gc.mem_alloc()} Free memory: {gc.mem_free()}')


if __name__ == "__main__":
    loop = asyncio.get_event_loop()

    try:
        loop.run_until_complete(main())
    finally:
        loop.close()

#exec(open("main.py").read())