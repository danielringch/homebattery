from asyncio import create_task, sleep
from gc import collect as gc_collect
from gc import mem_alloc, mem_free
from json import load as load_json
from micropython import const
gc_collect()
from ..core.addonport import AddonPort
gc_collect()
from ..core.microblecentral import MicroBleCentral
gc_collect()
from ..core.logging import Logging
gc_collect()
from ..core.userinterface import UserInterface
gc_collect()
from ..core.watchdog import Watchdog
gc_collect()
from .devices import Devices
gc_collect()
from .consumption import Consumption
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

_VERSION = const('1.0.0')

prefix = '[homebattery] {0}'


async def homebattery():
    gc_collect()

    from ..core.singletons import Singletons
    Singletons.log = Logging()
    Singletons.ui = UserInterface()
    Singletons.addon_port_1 = AddonPort(1, 0)
    Singletons.addon_port_2 = AddonPort(0, 1)

    log = Singletons.log
    ui = Singletons.ui
    log.debug('Homebattery ', _VERSION)
    ui.print('Homebattery', _VERSION)

    gc_collect()
    print_memory(log)

    await sleep(3.0)

    if ui.sw1:
        from ..core.network import Network, AP_SSID, AP_PASSWORD
        from ..core.webserver import Webserver
        log.debug('Entering configuration mode.')

        ip = Network({'network':None}).create_hotspot()
        ui.print('Connect to SSID:', AP_SSID, 'Password:', AP_PASSWORD, 'Open:', ip)
        Webserver().run()

    try:
        with open("/config.json", "r") as stream:
            config = load_json(stream)
    except:
        log.error('Invalid configuration.')
        ui.print('Invalid', 'configuration.')
        while True:
            await sleep(1)

    log.debug('Configuring logging...')
    ui.print('Configuring', 'logging...')
    log.configure(config)

    Singletons.ble = MicroBleCentral()
    watchdog = Watchdog()
    
    from ..core.network import Network
    log.debug('Connecting to network...')
    ui.print('Connecting to', 'network...')
    network = Network(config)
    network.connect(watchdog)
    network.get_network_time(watchdog)

    from ..core.backendmqtt import Mqtt
    log.debug('Configuring MQTT...')
    ui.print('Configuring', 'MQTT...')
    mqtt = Mqtt(config)

    watchdog.feed()
    gc_collect()

    ui.print('Configuring', 'modules...')
    devices = Devices(config, mqtt)
    gc_collect()
    consumption = Consumption(devices)
    battery = Battery(config, devices)
    charger = Charger(config, devices)
    inverter = Inverter(config, devices, consumption)
    solar = Solar(config, devices)
    modeswitcher = ModeSwitcher(config, mqtt, inverter, charger, solar)
    supervisor = Supervisor(config, watchdog, mqtt, modeswitcher, consumption, battery)
    outputs = Outputs(mqtt, supervisor, consumption, battery, charger, inverter, solar)
    watchdog.feed()

    gc_collect()

    log.debug('Connecting to MQTT broker...')
    ui.print('Connecting to', 'MQTT broker...')
    await mqtt.connect()
    watchdog.feed()

    battery_task = create_task(battery.run())
    charger_task = create_task(charger.run())
    inverter_task = create_task(inverter.run())
    solar_task = create_task(solar.run())
    modeswitcher.run()
    supervisor.run()
    

    gc_collect()
    print_memory(log)

    i = 0
    while True:
        await sleep(1)
        gc_collect()
        i += 1
        if i >= 60:
            i = 0
            print_memory(log)

def print_memory(log):
    log.info('Memory: ', mem_alloc(), ' used, free: ', mem_free())
