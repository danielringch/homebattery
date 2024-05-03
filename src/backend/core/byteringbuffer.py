
class ByteRingBufferOverflowError(Exception):
    pass

class ByteRingBuffer:
    def __init__(self, size):
        self.__max = size + 1
        self.__buffer = bytearray(self.__max)
        self.__view = memoryview(self.__buffer)
        self.__begin = 0
        self.__end = 0

    def __bool__(self):
        return not self.empty()
    
    def __len__(self):
        if self.__begin < self.__end:
            return self.__end - self.__begin
        else:
            return (self.__max) - (self.__begin - self.__end)
        
    def __getitem__(self, index):
        #TODO bounday checks
        if index >= 0:
            tmp_index = self.__begin + index
            if tmp_index >= self.__max:
                tmp_index -= self.__max
        else:
            tmp_index = self.__end + index
            if tmp_index < 0:
                tmp_index += self.__max
        return self.__buffer[tmp_index]
    
    def __iter__(self):
        return self.Iter(self)

    def empty(self):
        return self.__begin == self.__end
    
    def full(self):
        return self.__increment(self.__end) == self.__begin

    def clear(self):
        self.__begin = self.__end

    def append(self, byte, ignore_overflow=False):
        self.__buffer[self.__end] = byte
        self.__end = self.__increment(self.__end)
        if self.__end == self.__begin: #overflow
            self.__begin = self.__increment(self.__begin)
            if not ignore_overflow:
                raise ByteRingBufferOverflowError('Deque overflow.')
        
    def extend(self, bytes, length, ignore_overflow=False):
        effective_length = min(len(bytes), length)
        for i in range(effective_length):
            self.append(bytes[i], ignore_overflow)

    def peekleft(self):
        if self.empty():
            raise IndexError('Peek from empty deque.')
        return self.__buffer[self.__begin]
    
    def popleft(self):
        if self.empty():
            raise IndexError('Pop from empty deque.')
        value = self.__buffer[self.__begin]
        self.__begin = self.__increment(self.__begin)
        return value
    
    def popuntil(self, length):
        length = min(length, self.__len__())
        if self.__begin + length >= self.__max:
            result = self.__view[self.__begin:]
            self.__begin = 0
        else:
            begin = self.__begin
            self.__begin = self.__increment(self.__begin, length)
            result = self.__view[begin:self.__begin]
        return result

    def __increment(self, value, step=1):
        value += step
        if value >= self.__max:
            return value - self.__max
        else:
            return value

    class Iter:
        def __init__(self, instance):
            self.__buffer = instance
            self.__index = self.__buffer.__begin

        def __iter__(self):
            return self
        
        def __next__(self):
            if self.__index == self.__buffer.__end:
                raise StopIteration
            item = self.__buffer.__buffer[self.__index]
            self.__index = self.__buffer.__increment(self.__index)
            return item