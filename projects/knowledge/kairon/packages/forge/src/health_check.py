import sys

from forge import health_check as _impl

sys.modules[__name__] = _impl
