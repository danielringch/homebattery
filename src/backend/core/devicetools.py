from time import localtime, time
from .logging import CustomLogger
from .types import BatteryData, STATUS_FAULT, STATUS_OFF, STATUS_ON, STATUS_SYNCING

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
    temperatues_str = ' ; '.join(f'{x:.1f}' for x in battery.temps)
    cells_str = ' | '.join(f'{x:.3f}' for x in battery.cells)
    logger.info('Voltage: ', battery.v, ' V | Current: ', battery.i, ' A')
    logger.info('SoC: ', battery.soc, ' % | ', battery.c, ' / ', battery.c_full, ' Ah')
    logger.info('Cycles: ', battery.n, ' | Temperatures [°C]: ', temperatues_str)
    logger.info('Cells [V]: ', cells_str)
