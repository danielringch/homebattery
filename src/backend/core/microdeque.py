
class MicroDequeOverflowError(Exception):
    pass

class MicroDeque:
    def __init__(self, size):
        self.__buffer = list()
        for _ in range(size + 1):
            self.__buffer.append(None)
        self.__start = 0
        self.__end = 0
        self.__max = size

    def __bool__(self):
        return not self.empty()
    
    def __len__(self):
        if self.__start < self.__end:
            return self.__end - self.__start
        else:
            return (self.__max + 1) - (self.__start - self.__end)
        
    def __getitem__(self, index):
        #TODO bounday checks
        if index >= 0:
            tmp_index = self.__start + index
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
        return self.__start == self.__end

    def clear(self):
        i = self.__start
        while i != self.__end:
            self.__buffer[i] = None
            i = self.__increment(i)
        self.__start = self.__end

    def append(self, element):
        self.__buffer[self.__end] = element
        self.__end = self.__increment(self.__end)
        if self.__end == self.__start: #overflow
            self.__start = self.__increment(self.__start)
            raise MicroDequeOverflowError('Deque overflow.')

    def peekleft(self):
        if self.empty():
            raise IndexError('Peek from empty deque.')
        return self.__buffer[self.__start]
    
    def popleft(self):
        if self.empty():
            raise IndexError('Pop from empty deque.')
        value = self.__buffer[self.__start]
        self.__buffer[self.__start] = None
        self.__start = self.__increment(self.__start)
        return value

    def __increment(self, value):
        if value >= self.__max:
            return 0
        else:
            return value + 1
        
    class Iter:
        def __init__(self, instance):
            self.__deque = instance
            self.__index = self.__deque.__start

        def __iter__(self):
            return self
        
        def __next__(self):
            if self.__index == self.__deque.__end:
                raise StopIteration
            item = self.__deque.__buffer[self.__index]
            self.__index = self.__deque.__increment(self.__index)
            return item
        