class Singletons:
    _addon_port_1 = None
    _addon_port_2 = None
    _log = None
    _ble = None
    _operationmode = None
    _devicetype = None
    _inverterstatus = None
    _display = None
    _leds = None

    @staticmethod
    def addon_port_1():
        return Singletons._addon_port_1
    
    @staticmethod
    def addon_port_2():
        return Singletons._addon_port_2
    
    @staticmethod
    def ble():
        return Singletons._ble
    
    @staticmethod
    def devicetype():
        return Singletons._devicetype
    
    @staticmethod
    def display():
        return Singletons._display
    
    @staticmethod
    def inverterstatus():
        return Singletons._inverterstatus
    
    @staticmethod
    def leds():
        return Singletons._leds
    
    @staticmethod
    def log():
        return Singletons._log
    
    @staticmethod
    def operationmode():
        return Singletons._operationmode
    
    @staticmethod
    def set_addon_ports(port1, port2):
        Singletons._addon_port_1 = port1
        Singletons._addon_port_2 = port2

    @staticmethod
    def set_ble(ble):
        Singletons._ble = ble

    @staticmethod
    def set_devicetype(type):
        Singletons._devicetype = type

    @staticmethod
    def set_display(display):
        Singletons._display = display

    @staticmethod
    def set_inverterstatus(status):
        Singletons._inverterstatus = status

    @staticmethod
    def set_leds(leds):
        Singletons._leds = leds

    @staticmethod
    def set_log(log):
        Singletons._log = log

    @staticmethod
    def set_operationmode(mode):
        Singletons._operationmode = mode
