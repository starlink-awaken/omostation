"""向后兼容 Shim — 导入已迁移至 ecos.protocol.ssb.ssb_client。"""

from ecos.protocol.ssb.ssb_client import *  # noqa: F403
from ecos.protocol.ssb.ssb_client import SSBClient, SSB_DB_PATH, _now  # noqa: F401
