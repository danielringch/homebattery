class CommandBundle:
    def __init__(self, callback, parameters):
        self.__callback = callback
        self.__parameters = parameters

    async def run(self):
        await self.__callback(*self.__parameters)