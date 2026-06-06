import sys

from ecos.core import ssb_auth as _impl

sys.modules[__name__] = _impl
