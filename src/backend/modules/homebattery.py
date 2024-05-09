from asyncio import create_task, sleep
from gc import collect as gc_collect
from gc import mem_alloc, mem_free
from json import load as load_json
gc_collect()
from ..core.addonport import AddonPort
gc_collect()
from ..core.display import Display
gc_collect()
from ..core.microblecentral import MicroBleCentral
gc_collect()
from ..core.leds import Leds
gc_collect()
from ..core.logging import Logging
gc_collect()
from ..core.watchdog import Watchdog
gc_collect()
from .devices import Devices
gc_collect()
from .battery import Battery
gc_collect()
from .charger import Charger
gc_collect()
from .inverter import Inverter
gc_collect()
from .solar import Solar
gc_collect()
from .modeswitcher import ModeSwitcher
gc_collect()
from .supervisor import Supervisor
gc_collect()
from .outputs import Outputs
gc_collect()

__version__ = "0.1.0"

prefix = '[homebattery] {0}'


async def homebattery():
    gc_collect()

    from ..core.singletons import Singletons
    Singletons.log = Logging()
    Singletons.leds = Leds()
    Singletons.display = Display()
    Singletons.addon_port_1 = AddonPort(1, 0)
    Singletons.addon_port_2 = AddonPort(0, 1)
    Singletons.ble = MicroBleCentral()

    log = Singletons.log
    display = Singletons.display
    log.debug(f'Homebattery {__version__}')
    display.print('Homebattery', __version__)

    gc_collect()
    print_memory(log)

    await sleep(3.0)

    with open("/config.json", "r") as stream:
        config = load_json(stream)

    watchdog = Watchdog()
    
    from ..core.network import Network
    log.debug('Connecting to network...')
    display.print('Connecting to', 'network...')
    network = Network(config)
    network.connect(watchdog)
    network.get_network_time(watchdog)

    log.debug('Configuring logging...')
    display.print('Configuring', 'logging...')
    log.configure(config)

    from ..core.backendmqtt import Mqtt
    log.debug('Configuring MQTT...')
    display.print('Configuring', 'MQTT...')
    mqtt = Mqtt(config)

    watchdog.feed()
    gc_collect()

    display.print('Configuring', 'modules...')
    devices = Devices(config, mqtt)
    gc_collect()
    battery = Battery(config, devices)
    charger = Charger(config, devices, mqtt)
    inverter = Inverter(config, devices, mqtt)
    solar = Solar(config, devices, mqtt)
    modeswitcher = ModeSwitcher(config, mqtt, inverter, charger, solar)
    supervisor = Supervisor(config, watchdog, mqtt, modeswitcher, inverter, charger, battery)
    watchdog.feed()

    gc_collect()

    log.debug('Connecting to MQTT broker...')
    display.print('Connecting to', 'MQTT broker...')
    await mqtt.connect()
    watchdog.feed()

    battery_task = create_task(battery.run())
    charger_task = create_task(charger.run())
    inverter_task = create_task(inverter.run())
    solar_task = create_task(solar.run())
    modeswitcher.run()
    supervisor.run()
    outputs = Outputs(mqtt, supervisor, battery, charger, inverter, solar)

    gc_collect()
    print_memory(log)

    i = 0
    while True:
        gc_collect()
        await sleep(1)
        i += 1
        if i >= 60:
            i = 0
            print_memory(log)

def print_memory(log):
    log.info(f'Used memory: {mem_alloc()} Free memory: {mem_free()}')
