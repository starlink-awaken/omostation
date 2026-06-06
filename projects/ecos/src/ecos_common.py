"""向后兼容 Shim — 导入已迁移至 ecos.common.common。"""
from ecos.common.common import *  # noqa: F403
from ecos.common.common import ECOS_HOME, TZ, get_conn, now_iso, SSB_DB_PATH, INTEGRATE_AUTO_SCORE, INTEGRATE_CANDIDATE_SCORE  # noqa: F401
