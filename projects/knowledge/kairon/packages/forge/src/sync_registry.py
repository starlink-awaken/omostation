import sys

from forge import sync_registry as _impl

sys.modules[__name__] = _impl
