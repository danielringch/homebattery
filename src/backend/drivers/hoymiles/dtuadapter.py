

class DtuAdapter:
    def configure(self, log):
        pass

    async def switch_on(self):
        raise NotImplementedError()

    async def switch_off(self):
        raise NotImplementedError()

    async def reset(self):
        raise NotImplementedError()

    async def change_power(self, percent: int):
        raise NotImplementedError()

    async def read(self):
        raise NotImplementedError()