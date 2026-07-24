"""向后兼容 Shim — 导入已迁移至 ecos.protocol.ssb.ssb_auth。"""

from ecos.protocol.ssb.ssb_auth import *
from ecos.protocol.ssb.ssb_auth import (
    _load_key,
    compute_signature,
    verify,
)
