from .types import DeviceTypeValues, InverterStatusValues, OperationModeValues

bool2string = {True: 'true', False: 'false', None: 'none'}

bool2on = {True: 'on', False: 'off', None: 'unknown'}

operationmode = OperationModeValues()

devicetype = DeviceTypeValues()

inverterstatus = InverterStatusValues()