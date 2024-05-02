
class ByteRingBufferOverflowError(Exception):
    pass

class ByteRingBuffer:
    def __init__(self, size):
        self.__buffer = bytearray(size + 1)
        self.__begin = 0
        self.__end = 0
        self.__max = size

    def __bool__(self):
        return not self.empty()
    
    def __len__(self):
        if self.__begin < self.__end:
            return self.__end - self.__begin
        else:
            return (self.__max + 1) - (self.__begin - self.__end)
        
    def __getitem__(self, index):
        #TODO bounday checks
        if index >= 0:
            tmp_index = self.__begin + index
            if tmp_index > self.__max:
                tmp_index -= self.__max + 1
        else:
            tmp_index = self.__end + index
            if tmp_index < 0:
                tmp_index += self.__max + 1
        return self.__buffer[tmp_index]
    
    def __iter__(self):
        return self.Iter(self)

    def empty(self):
        return self.__begin == self.__end
    
    def full(self):
        return self.__increment(self.__end) == self.__begin

    def clear(self):
        self.__begin = self.__end

    def append(self, byte):
        self.__buffer[self.__end] = byte
        self.__end = self.__increment(self.__end)
        if self.__end == self.__begin: #overflow
            self.__begin = self.__increment(self.__begin)
            raise ByteRingBufferOverflowError('Deque overflow.')
        
    def extend(self, bytes, length):
        effective_length = min(len(bytes), length)
        for i in range(effective_length):
            self.append(bytes[i])

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

    def __increment(self, value):
        if value >= self.__max:
            return 0
        else:
            return value + 1

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