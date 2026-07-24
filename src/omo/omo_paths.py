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
PROJECTS_DIR = _MODULE_DIR.parents[2]  # /Users/xiamingxing/Workspace/projects
WORKSPACE_ROOT = _MODULE_DIR.parents[3]  # /Users/xiamingxing/Workspace
HOME_DIR = _MODULE_DIR.parents[4]  # /Users/xiamingxing

# 关键路径
OMO_ROOT = WORKSPACE_ROOT / ".omo"
KAIRON_DIR = PROJECTS_DIR / "kairon"
KAIRON_PACKAGES = KAIRON_DIR / "packages"

# 运行时镜像根 (高 churn 的 self-healing/ingress/evolution 产物写这里, 不入仓)
RUNTIME_OMO_ROOT = WORKSPACE_ROOT / "runtime" / "omo"

# 治理子路径 (稳定 SSOT, 入仓)
TRUTH_DIR = OMO_ROOT / "_truth"
CONTROL_DIR = OMO_ROOT / "_control"
DELIVERY_DIR = OMO_ROOT / "_delivery"
ARCHIVE_DIR = OMO_ROOT / "_archive"
EVIDENCE_DIR = DELIVERY_DIR / "evidence"
EVIDENCE_LEGACY_DIR = DELIVERY_DIR / "evidence-legacy"
EVIDENCE_ALIAS_DIR = OMO_ROOT / "evidence"
KNOWLEDGE_DIR = OMO_ROOT / "_knowledge"
LOG_DIR = OMO_ROOT / "_log"
STANDARDS_DIR = OMO_ROOT / "standards"
CRON_DIR = OMO_ROOT / "cron"
GOALS_DIR = OMO_ROOT / "goals"
PITCHES_DIR = OMO_ROOT / "pitches"
TESTS_DIR = OMO_ROOT / "tests"
CAPABILITIES_DIR = OMO_ROOT / "capabilities"
CHANGE_LOG_DIR = OMO_ROOT / "change-log"
TASKS_DIR = OMO_ROOT / "tasks"
TASKS_PLANNED_DIR = OMO_ROOT / "tasks" / "planned"
TASKS_ACTIVE_DIR = OMO_ROOT / "tasks" / "active"
TASKS_DONE_DIR = OMO_ROOT / "tasks" / "done"
STATE_DIR = OMO_ROOT / "state"
WORKERS_DIR = OMO_ROOT / "workers"
DEBT_DIR = OMO_ROOT / "debt"
DECISIONS_DIR = KNOWLEDGE_DIR / "decisions"
DEBT_ITEMS_DIR = OMO_ROOT / "debt" / "items"
STATE_SYSTEM_YAML = OMO_ROOT / "state" / "system.yaml"
PROJECTS_REGISTRY_YAML = OMO_ROOT / "PROJECTS.yaml"
ROOT_INDEX_MD = OMO_ROOT / "INDEX.md"
OMO_GOVERNANCE_SURFACES_STANDARD = STANDARDS_DIR / "omo-governance-surfaces.md"
OMO_GOVERNANCE_SURFACES_REGISTRY = (
    TRUTH_DIR / "registry" / "omo-governance-surfaces.yaml"
)

# 运行时镜像子路径 (高 churn 产物)
RUNTIME_DELIVERY_DIR = RUNTIME_OMO_ROOT / "_delivery"
RUNTIME_CONTROL_DIR = RUNTIME_OMO_ROOT / "_control"
RUNTIME_CHANGE_LOG_DIR = RUNTIME_OMO_ROOT / "change-log"
RUNTIME_TASKS_DIR = RUNTIME_OMO_ROOT / "tasks"
RUNTIME_TRUTH_DIR = RUNTIME_OMO_ROOT / "_truth"


def runtime_omo_path(relative: str | Path) -> Path:
    """Return a runtime mirror path under RUNTIME_OMO_ROOT.

    Example:
        runtime_omo_path("_delivery/ingress/registry.yaml")
        -> /.../Workspace/runtime/omo/_delivery/ingress/registry.yaml
    """
    return RUNTIME_OMO_ROOT / Path(relative)


def ensure_runtime_omo_dir(relative: str | Path) -> Path:
    """Create the runtime mirror directory if missing and return it."""
    path = RUNTIME_OMO_ROOT / Path(relative)
    path.mkdir(parents=True, exist_ok=True)
    return path


# Runtime projection registry (ADR-0129)
RUNTIME_PROJECTIONS_REGISTRY = TRUTH_DIR / "registry" / "runtime-projections.yaml"


def projection_path(name: str, *, prefer_canonical: bool = True) -> Path:
    """Resolve the path of a registered runtime projection.

    Consumers should use this instead of hard-coding paths like
    `.omo/state/health.yaml` or `BRIEF.md`.

    By default returns the canonical path if it exists, otherwise falls back
    to the legacy path. During ADR-0129 migration this lets readers find
    projections regardless of which phase the workspace is in.
    """
    import yaml

    canonical: Path | None = None
    legacy: Path | None = None
    if RUNTIME_PROJECTIONS_REGISTRY.is_file():
        data = (
            yaml.safe_load(RUNTIME_PROJECTIONS_REGISTRY.read_text(encoding="utf-8"))
            or {}
        )
        entry = (data.get("projections") or {}).get(name)
        if entry:
            canonical = WORKSPACE_ROOT / entry["canonical"]
            legacy = WORKSPACE_ROOT / entry["legacy"]

    # Fallbacks keep existing tests and consumers working if registry is missing
    # or the entry has not been added yet.
    if name == "health":
        canonical = canonical or STATE_DIR / "runtime" / "health.yaml"
        legacy = legacy or STATE_DIR / "health.yaml"
    elif name == "system_health":
        canonical = canonical or STATE_DIR / "runtime" / "system_health.yaml"
        legacy = legacy or STATE_DIR / "system_health.yaml"
    elif name == "governance_data":
        canonical = canonical or STATE_DIR / "runtime" / "governance-data.json"
        legacy = legacy or CONTROL_DIR / "governance-data.json"
    elif name == "brief":
        canonical = canonical or STATE_DIR / "runtime" / "brief.md"
        legacy = legacy or WORKSPACE_ROOT / "BRIEF.md"
    else:
        raise KeyError(f"Unknown runtime projection: {name}")

    if prefer_canonical:
        if canonical.exists():
            return canonical
        if legacy.exists():
            return legacy
        return canonical  # return canonical for writers even if missing
    return legacy if legacy.exists() else canonical


# Agora 路由表 (P30 拆分后, agora 已迁出 kairon, 现位于 projects/agora)
# P31-W0-AGORA-ACTUAL-FIX: 修正路径指向
AGORA_ROUTES_PATH = PROJECTS_DIR / "agora" / "src" / "agora-routes.json"

# 治理历史 (kairon-governance 旧 JSONL 路径保持不变, 保证历史连续性)
GOVERNANCE_HISTORY_PATH = KNOWLEDGE_DIR / "governance-history.jsonl"

# Daemon 运行时
DAEMON_PID_FILE = Path("/tmp/omo-governance-daemon.pid")
DAEMON_LOG_FILE = DELIVERY_DIR / "daemon.log"


def find_omo_dir(start: Path | None = None) -> Path:
    """Resolve the authoritative workspace .omo directory.

    Runtime commands should prefer the workspace root declared by this package,
    instead of accidentally binding to legacy shadow `.omo` directories inside
    subrepositories such as `projects/omo/.omo`.
    """
    if OMO_ROOT.is_dir():
        return OMO_ROOT
    current = (start or Path.cwd()).resolve()
    while current != current.parent:
        candidate = current / ".omo"
        if candidate.is_dir():
            return candidate
        current = current.parent
    return (start or Path.cwd()) / ".omo"


__all__ = (
    "AGORA_ROUTES_PATH",
    "ARCHIVE_DIR",
    "CAPABILITIES_DIR",
    "CHANGE_LOG_DIR",
    "CONTROL_DIR",
    "CRON_DIR",
    "DAEMON_LOG_FILE",
    "DAEMON_PID_FILE",
    "DEBT_DIR",
    "DEBT_ITEMS_DIR",
    "DECISIONS_DIR",
    "DELIVERY_DIR",
    "EVIDENCE_ALIAS_DIR",
    "EVIDENCE_DIR",
    "EVIDENCE_LEGACY_DIR",
    "GOALS_DIR",
    "GOVERNANCE_HISTORY_PATH",
    "HOME_DIR",
    "KAIRON_DIR",
    "KAIRON_PACKAGES",
    "KNOWLEDGE_DIR",
    "LOG_DIR",
    "OMO_GOVERNANCE_SURFACES_REGISTRY",
    "OMO_GOVERNANCE_SURFACES_STANDARD",
    "OMO_ROOT",
    "OMO_SRC_PARENT",
    "PITCHES_DIR",
    "PROJECTS_DIR",
    "PROJECTS_REGISTRY_YAML",
    "ROOT_INDEX_MD",
    "RUNTIME_CHANGE_LOG_DIR",
    "RUNTIME_CONTROL_DIR",
    "RUNTIME_DELIVERY_DIR",
    "RUNTIME_OMO_ROOT",
    "RUNTIME_TASKS_DIR",
    "RUNTIME_TRUTH_DIR",
    "STANDARDS_DIR",
    "STATE_DIR",
    "STATE_SYSTEM_YAML",
    "TASKS_DIR",
    "TASKS_PLANNED_DIR",
    "TESTS_DIR",
    "TRUTH_DIR",
    "WORKERS_DIR",
    "WORKSPACE_ROOT",
    "ensure_runtime_omo_dir",
    "find_omo_dir",
    "runtime_omo_path",
)
