"""向后兼容 Shim — 导入已迁移至 ecos.common.ecos_timeout。"""

from ecos.common.ecos_timeout import *  # noqa: F403
from ecos.common.ecos_timeout import timeout, TimeoutError, retry  # noqa: F401
