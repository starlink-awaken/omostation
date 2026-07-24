import importlib
import sys

_mod = importlib.import_module("ecos.l0.emergence")
sys.modules[__name__] = _mod
