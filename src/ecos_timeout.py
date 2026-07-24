"""向后兼容 Shim — 导入已迁移至 ecos.common.ecos_timeout。"""

from ecos.common.ecos_timeout import *
from ecos.common.ecos_timeout import TimeoutError, retry, timeout
