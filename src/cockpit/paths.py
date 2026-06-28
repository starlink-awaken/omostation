"""cockpit.paths — 共享路径常量 (SSOT, 治本循环依赖).

F7114ABA 拆分治本: DB_PATH 等路径定义在此, storage.py (Protocol) +
storage_sqlite.py (实现) 共享, 避免 DB_PATH 两处定义 (拆分遗漏致 SSOT 违反).

循环依赖破除: paths 不 import storage*, storage/storage_sqlite 单向 from .paths.
"""

from pathlib import Path

# cockpit 研究 SQLite DB (研究结果/用户状态/系统历史)
DB_PATH = Path.home() / ".workspace" / "data.db"
