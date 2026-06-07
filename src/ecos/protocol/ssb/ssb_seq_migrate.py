import sys
import importlib
_mod = importlib.import_module("ecos.l0.ssb." + __name__.rsplit(".", 1)[-1])
sys.modules[__name__] = _mod
