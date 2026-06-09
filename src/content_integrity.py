"""向后兼容 Shim — 导入已迁移至 ecos.common.content_integrity。"""

from ecos.common.content_integrity import *  # noqa: F403
from ecos.common.content_integrity import check_integrity  # noqa: F401
