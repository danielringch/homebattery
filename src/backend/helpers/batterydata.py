from time import time
from json import dumps, loads

class BatteryData:
    def __init__(self, name, is_forwarded=False):
        self.name = name
        self.is_forwarded = is_forwarded
        self.reset()

    def reset(self):
        self.v = None
        self.i = None
        self.soc = None
        self.c = None
        self.c_full = None
        self.n = None
        self.temps = None
        self.cells = None
        self.timestamp = 0

    def to_json(self):
        if not self.valid:
            raise ValueError()
        json = {}
        self.__pack(json, 'v', self.v)
        self.__pack(json, 'i', self.i)
        self.__pack(json, 'soc', self.soc)
        self.__pack(json, 'c', self.c)
        self.__pack(json, 'c_full', self.c_full)
        self.__pack(json, 'n', self.n)
        self.__pack(json, 'temps', self.temps)
        self.__pack(json, 'cells', self.cells)
        return dumps(json)
    
    def from_json(self, json: str):
        try:
            json_dict = loads(json)
        except:
            self.reset()
            raise
        self.v = self.__unpack(json_dict, 'v', float)
        self.i = self.__unpack(json_dict, 'i', float)
        self.soc = self.__unpack(json_dict, 'soc', float)
        self.c = self.__unpack(json_dict, 'c', float)
        self.c_full = self.__unpack(json_dict, 'c_full', float)
        self.n = self.__unpack(json_dict, 'n', round)
        self.temps = self.__unpack(json_dict, 'temps', tuple)
        self.cells = self.__unpack(json_dict, 'cells', tuple)

        if self.cells: # values for cell voltages are the absolute minimum data we need to work
            self.validate()
        else:
            self.reset()

    def validate(self):
        self.timestamp = time()

    def invalidate(self):
        self.timestamp = 0

    @property
    def valid(self):
        return self.timestamp > 0
    
    def __pack(self, dict, key, value):
        if value is not None:
            dict[key] = value

    def __unpack(self, dict, key, type):
        raw = dict.get(key, None)
        return None if raw is None else type(raw)