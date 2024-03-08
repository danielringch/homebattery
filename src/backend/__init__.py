import sys
micropython = sys.implementation.name == 'micropython'

if micropython:
    from .core import *
else:
    from .core import *
    from .drivers import *
    from .modules import *
