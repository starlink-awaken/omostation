import sys

from forge import build_graph as _impl

sys.modules[__name__] = _impl
