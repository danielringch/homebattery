

class BigEndianSteamReader:
    def __init__(self, data: bytes, offset: int):
        self.__data = data
        self.__index = offset

    def uint8(self):
        value = self.__data[self.__index]
        self.__index += 1
        return value

    def uint8_at(self, index: int):
        return self.__data[index]
    
    def uint16(self):
        value = (self.__data[self.__index] << 8) + self.__data[self.__index + 1]
        self.__index += 2
        return value
    
    def uint16_at(self, index: int):
        return (self.__data[index] << 8) + self.__data[index + 1]
    
def read_big_uint8(data: bytes, index: int):
    return data[index]

def read_big_uint16(data: bytes, index: int):
    return (data[index] << 8) + data[index + 1]

def read_big_int16(data: bytes, index: int):
    value = (data[index] << 8) + data[index + 1]
    if value > 0x7FFF:
        value -= 0xFFFF
    return value

def read_big_uint32(data: bytes, index: int):
    return (data[index] << 24) + (data[index + 1] << 16) + (data[index + 2] << 8) + data[index + 3]

def read_big_int32(data: bytes, index: int):
    value = (data[index] << 24) + (data[index + 1] << 16) + (data[index + 2] << 8) + data[index + 3]
    if value > 0x7FFFFFFF:
        value -= 0xFFFFFFFF
    return value

def read_little_uint8(data: bytes, index: int):
    return data[index]

def read_little_uint16(data: bytes, index: int):
    return data[index] + (data[index + 1] << 8)

def read_little_int16(data: bytes, index: int):
    value = data[index] + (data[index + 1] << 8)
    if value > 0x7FFF:
        value -= 0xFFFF
    return value

def read_little_uint32(data: bytes, index: int):
    return data[index] + (data[index + 1] << 8) + (data[index + 2] << 16) + (data[index + 3] << 24)

def read_little_int32(data: bytes, index: int):
    value = data[index] + (data[index + 1] << 8) + (data[index + 2] << 16) + (data[index + 3] << 24)
    if value > 0x7FFFFFFF:
        value -= 0xFFFFFFFF
    return value

class AsciiHexStreamReader:
    def __init__(self, data: bytes, offset: int):
        self.__data = data
        self.__index = offset

    def read_uint8(self):
        new_index = self.__index + 2
        value = int(self.__data[self.__index:new_index].decode('utf-8'), 16)
        self.__index = new_index
        return value
    
    def read_uint16(self):
        new_index = self.__index + 4
        value = int(self.__data[self.__index:new_index].decode('utf-8'), 16)
        self.__index = new_index
        return value
    
    def read_int16(self):
        new_index = self.__index + 4
        value = int(self.__data[self.__index:new_index].decode('utf-8'), 16)
        self.__index = new_index
        if value > 0x7FFF:
            value -= 0xFFFF
        return value
    
    def read_uint24(self):
        new_index = self.__index + 6
        value = int(self.__data[self.__index:new_index].decode('utf-8'), 16)
        self.__index = new_index
        return value