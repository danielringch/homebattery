import asyncio, time
from ..drivers.shelly import *
from ..core.types import OperationMode, operationmode, ChargeMode, chargemode, CallbackCollection, devicetype
from ..core.logging import *
from ..core.backendmqtt import Mqtt
from .devices import Devices

operation_mode_to_charge_mode = {
    operationmode.idle: chargemode.off,
    operationmode.discharge: chargemode.off,
    operationmode.charge: chargemode.charge
}

class Charger:
    def __init__(self, config: dict, devices: Devices, mqtt: Mqtt):
        self.__lock = asyncio.Lock()
        self.__mqtt = mqtt

        self.__charge_mode = None

        self.__on_energy = CallbackCollection()

        self.__chargers = []
        for device in devices.devices:
            if devicetype.charger not in device.device_types:
                continue
            self.__chargers.append(device)

        self.__set_next_energy_execution()

    async def run(self):
        while True:
            try:
                now = time.time()
                async with self.__lock:
                    for charger in self.__chargers:
                        await charger.tick()
                    if now >= self.__next_energy_execution:
                        await self.__get_energy()
                        self.__set_next_energy_execution()
            except Exception as e:
                log.error(f'Charger cycle failed: {e}')
            await asyncio.sleep(0.1)

    async def is_on(self):
        async with self.__lock:
            actual_mode = await self.__get_charge_mode()
            if actual_mode == self.__charge_mode:
                return actual_mode != chargemode.off
            return None

    async def set_mode(self, mode: OperationMode):
        async with self.__lock:
            self.__charge_mode = operation_mode_to_charge_mode[mode]
            for charger in self.__chargers:
                await charger.switch_charger(self.__charge_mode == chargemode.charge)

            state_confirmed, state = await self.__confirm_on(self.__charge_mode)
            if not state_confirmed:
                log.alert(f'Not all chargers are confirmed in mode {self.__charge_mode.name}.')
                state = None
            on = None if state is None else state != chargemode.off
            self.__mqtt.send_charger_state(on)
            return on

    @property
    def on_energy(self):
        return self.__on_energy

    async def __confirm_on(self, mode: ChargeMode, retries: int =15):
        for _ in range(retries):
            actual_mode = await self.__get_charge_mode()
            if mode == actual_mode:
                return True, actual_mode
            await asyncio.sleep(2.0)
        else:
            return False, actual_mode

    async def __get_charge_mode(self):
        if len(self.__chargers) == 0:
            return False
        mode = None
        for charger in self.__chargers:
            on = await charger.is_charger_on()
            if on is None:
                return None
            if mode is None:
                mode = on
            elif on != mode:
                return None
        return chargemode.charge if on else chargemode.off

    async def __get_energy(self):
        energy = 0.0
        for charger in self.__chargers:
            charger_energy = await charger.get_charger_energy()
            if charger_energy is not None:
                energy += charger_energy
        self.__on_energy.run_all(round(energy))

    def __set_next_energy_execution(self):
        now = time.localtime()
        now_seconds = time.time()
        minutes = now[4]
        seconds = now[5]
        extra_seconds = (minutes % 15) * 60 + seconds
        seconds_to_add = (15 * 60) - extra_seconds
        self.__next_energy_execution = now_seconds + seconds_to_add
