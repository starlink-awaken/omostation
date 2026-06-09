"""向后兼容 Shim — 导入已迁移至 ecos.protocol.ssb.ssb_auth。"""

from ecos.protocol.ssb.ssb_auth import *  # noqa: F403
from ecos.protocol.ssb.ssb_auth import compute_signature, _load_key, verify  # noqa: F401
