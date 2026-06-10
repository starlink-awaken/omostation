"""OMO 路径常量(从 kairon_governance.paths 迁移, 适配 omo 包布局).

路径推导:
  omo/src/omo/omo_paths.py
    parents[0] = omo/src/omo  (module dir)
    parents[1] = omo/src
    parents[2] = omo project (OMO_SRC_PARENT)
    parents[3] = projects
    parents[4] = Workspace   (WORKSPACE_ROOT)
    parents[5] = $HOME
"""
from __future__ import annotations

from pathlib import Path

_MODULE_DIR = Path(__file__).resolve().parent
OMO_SRC_PARENT = _MODULE_DIR.parents[1]  # /Users/xiamingxing/Workspace/projects/omo
PROJECTS_DIR = _MODULE_DIR.parents[2]    # /Users/xiamingxing/Workspace/projects
WORKSPACE_ROOT = _MODULE_DIR.parents[3]  # /Users/xiamingxing/Workspace
HOME_DIR = _MODULE_DIR.parents[4]        # /Users/xiamingxing

# 关键路径
OMO_ROOT = WORKSPACE_ROOT / ".omo"
KAIRON_DIR = PROJECTS_DIR / "kairon"
KAIRON_PACKAGES = KAIRON_DIR / "packages"

# 治理子路径
DELIVERY_DIR = OMO_ROOT / "_delivery"
KNOWLEDGE_DIR = OMO_ROOT / "_knowledge"
TASKS_PLANNED_DIR = OMO_ROOT / "tasks" / "planned"
DECISIONS_DIR = KNOWLEDGE_DIR / "decisions"
DEBT_ITEMS_DIR = OMO_ROOT / "debt" / "items"
STATE_SYSTEM_YAML = OMO_ROOT / "state" / "system.yaml"

# Agora 路由表 (P30 拆分后, agora 已迁出 kairon, 现位于 projects/agora)
# P31-W0-AGORA-ACTUAL-FIX: 修正路径指向
AGORA_ROUTES_PATH = PROJECTS_DIR / "agora" / "src" / "agora-routes.json"

# 治理历史 (kairon-governance 旧 JSONL 路径保持不变, 保证历史连续性)
GOVERNANCE_HISTORY_PATH = KNOWLEDGE_DIR / "governance-history.jsonl"

# Daemon 运行时
DAEMON_PID_FILE = Path("/tmp/omo-governance-daemon.pid")
DAEMON_LOG_FILE = DELIVERY_DIR / "daemon.log"

__all__ = (
    "AGORA_ROUTES_PATH",
    "DAEMON_LOG_FILE",
    "DAEMON_PID_FILE",
    "DEBT_ITEMS_DIR",
    "DECISIONS_DIR",
    "DELIVERY_DIR",
    "GOVERNANCE_HISTORY_PATH",
    "HOME_DIR",
    "KAIRON_DIR",
    "KAIRON_PACKAGES",
    "KNOWLEDGE_DIR",
    "OMO_ROOT",
    "OMO_SRC_PARENT",
    "PROJECTS_DIR",
    "STATE_SYSTEM_YAML",
    "TASKS_PLANNED_DIR",
    "WORKSPACE_ROOT",
)
