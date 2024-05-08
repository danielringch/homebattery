from asyncio import create_task, get_event_loop, sleep
from gc import collect as gc_collect
from gc import mem_alloc, mem_free
from json import load as load_json
gc_collect()
from backend.core.addonport import AddonPort
gc_collect()
from backend.core.display import Display
gc_collect()
from backend.core.microblecentral import MicroBleCentral
gc_collect()
from backend.core.leds import Leds
gc_collect()
from backend.core.logging import Logging
gc_collect()
from backend.core.singletons import Singletons
gc_collect()
from backend.core.types import OperationModeValues, DeviceTypeValues, InverterStatusValues
gc_collect()
from backend.core.watchdog import Watchdog
gc_collect()
from backend.modules.devices import Devices
gc_collect()
from backend.modules.battery import Battery
gc_collect()
from backend.modules.charger import Charger
gc_collect()
from backend.modules.inverter import Inverter
gc_collect()
from backend.modules.solar import Solar
gc_collect()
from backend.modules.modeswitcher import ModeSwitcher
gc_collect()
from backend.modules.supervisor import Supervisor
gc_collect()
from backend.modules.outputs import Outputs
gc_collect()

from micropython import mem_info

__version__ = "0.1.0"

prefix = '[homebattery] {0}'


async def main():
    gc_collect()
    mem_info(1)

    Singletons.set_operationmode(OperationModeValues())
    Singletons.set_devicetype(DeviceTypeValues())
    Singletons.set_inverterstatus(InverterStatusValues())
    Singletons.set_log(Logging())
    Singletons.set_leds(Leds())
    Singletons.set_display(Display())
    Singletons.set_addon_ports(AddonPort(1, 0), AddonPort(0, 1))
    Singletons.set_ble(MicroBleCentral())

    log = Singletons.log()
    display = Singletons.display()
    log.debug(f'Homebattery {__version__}')
    display.print('Homebattery', __version__)

    await sleep(3.0)

    with open("/config.json", "r") as stream:
        config = load_json(stream)

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
    mem_info(1)

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
    mem_info(1)

    i = 0
    while True:
        gc_collect()
        await sleep(1)
        i += 1
        if i >= 60:
            i = 0
            log.info(f'Used memory: {mem_alloc()} Free memory: {mem_free()}')


if __name__ == "__main__":
    loop = get_event_loop()

    try:
        loop.run_until_complete(main())
    finally:
        loop.close()

#exec(open("main.py").read())