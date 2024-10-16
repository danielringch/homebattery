from time import localtime, time
from .logging import CustomLogger
from .types import STATUS_FAULT, STATUS_OFF, STATUS_ON, STATUS_SYNCING
from ..helpers.batterydata import BatteryData

def get_energy_execution_timestamp():
    now = localtime()
    now_seconds = time()
    minutes = now[4]
    seconds = now[5]
    extra_seconds = (minutes % 15) * 60 + seconds
    seconds_to_add = (15 * 60) - extra_seconds
    return now_seconds + seconds_to_add

def merge_driver_statuses(statuses):
    if len(statuses) == 0:
        return STATUS_OFF
    if STATUS_FAULT in statuses:
        return STATUS_FAULT
    if all(x == STATUS_ON for x in statuses):
        return STATUS_ON
    if all(x == STATUS_OFF for x in statuses):
        return STATUS_OFF
    return STATUS_SYNCING

def print_battery(logger: CustomLogger, battery: BatteryData):
    v = f'{battery.v:.2f} V' if battery.v is not None else 'unknown'
    i = f'{battery.i:.2f} A' if battery.i is not None else 'unknown'
    logger.info('Voltage: ', v, ' | Current: ', i)

    soc = f'{battery.soc:.1f} %' if battery.soc is not None else 'unknown'
    c = f'{battery.c:.1f}' if battery.c is not None else 'unknown'
    c_full = f'{battery.c_full:.1f}' if battery.c_full is not None else 'unknown'
    logger.info('SoC: ', soc, ' | ', c, ' / ', c_full, ' Ah')

    n = f'{battery.n:.0f}' if battery.n is not None else 'unknown'
    temps = ' | '.join(f'{x:.1f}' for x in battery.temps) if battery.temps is not None else 'unknown'
    logger.info('Cycles: ', n, ' | Temperatures [°C]: ', temps)

    cells = ' | '.join(f'{x:.3f}' for x in battery.cells) if battery.cells is not None else 'unknown'
    logger.info('Cells [V]: ', cells)
