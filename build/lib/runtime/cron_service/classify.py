"""脚本—项目分类规则 SSOT（单一权威分类器）

所有需要判断脚本归属的地方（SSOT 迁移、桥接同步、审计）都从这里读取。
新增项目只需要在这里加前缀规则，其他脚本自动跟进。
"""

from pathlib import Path

# ── 脚本→项目映射 ────────────────────────────────────────────
# 规则：脚本名以任意前缀开头 → 归入对应项目
SCRIPT_PREFIX_MAP = {
    "SharedBrain": [
        "agora-watchdog",
        "auto_pull",
        "bootstrap",
        "bos_",
        "bottleneck",
        "collect_",
        "collective_",
        "common_paths",
        "compression_stats",
        "db_consolidate",
        "detect_api",
        "distributed_consensus",
        "docker_smoke",
        "evolution_engine",
        "execute_evolved",
        "generate_",
        "hot_reload_",
        "inject_",
        "metacognition",
        "merge_",
        "migrate_",
        "model_router",
        "planner_state",
        "port-watch",
        "portctl",
        "register-",
        "registry",
        "robustness_regression",
        "run_",
        "self_",
        "setup-auth",
        "simulate_",
        "strategic_awareness",
        "tailscale",
        "test_",
        "test-r3",
        "token_compressor",
        "trend_analyzer",
        "trigger_",
        "update_",
        "verify_",
        "bwg-watchdog",
        "autonomous_planner",
        "validate-",
    ],
    "eCOS": [
        "ecos-",
        "wf-",
        "daily-summary",
        "daily-todo",
        "insight-report",
        "sediment-",
        "pipeline-research",
        "design-pipeline",
    ],
    "wksp": [
        "workspace-",
        "wksp-",
        "freshness-",
        "health-monitor",
        "product-health",
        "auto-archive",
        "dual-baseline",
        "agora-register-workspace",
        "arcnode-",
        "freshness_check",
    ],
    "Forge": [
        "asset-watch",
        "bootstrap-cowork",
        "build-graph",
        "check-updates",
        "classify",
        "ci-architecture",
        "discover-",
        "entropy-",
        "health-check",
        "kos-probe",
        "query-graph",
        "recommend",
        "rss-",
        "run-pipeline",
        "sniff-",
        "sync-",
        "upgrade-",
        "verify-",
    ],
    "agora": ["agora-watchdog", "agora-register"],
    "cron-service": ["cron-service-", "hermes-"],
    "agent-runtime": [
        "agent_autonomy",
        "run-agent-task",
        "codexbar-quota",
        "cost_digest",
        "research_reader",
        "ops_tts",
    ],
    "iris": ["iris-"],
    "kos": ["kos-probe", "wps_note", "wpsnote"],
    "gateway": [],
    "gbrain-repo": [],
    "gstack": [],
    "kronos": ["kronos"],
}

# ── 排除（不需要桥接的） ──────────────────────────────────────

EXCLUDE_FILES = {
    "INDEX.md",
    "SECRETS_INVENTORY.md",
    ".freshness_tracker.json",
    ".x2_daemon_state.json",
}

EXCLUDE_EXTENSIONS = {
    ".bak",
    ".legacy",
    ".ts",
    ".js",
    ".json",
    ".md",
    ".txt",
    ".rst",
    ".cfg",
    ".ini",
    ".toml",
    ".yaml",
    ".yml",
}

EXCLUDE_PREFIXES = {"test_", "test-", ".", "_"}


# ── 分类函数 ──────────────────────────────────────────────────


def classify(name: str) -> str | None:
    """根据文件名判断归属项目，None 表示无匹配"""
    for project, prefixes in SCRIPT_PREFIX_MAP.items():
        for prefix in prefixes:
            if name.startswith(prefix):
                return project
    return None


def should_bridge(name: str) -> bool:
    """检查是否应该桥接到 Hermes"""
    if name in EXCLUDE_FILES:
        return False
    if Path(name).suffix.lower() in EXCLUDE_EXTENSIONS:
        return False
    for p in EXCLUDE_PREFIXES:
        if name.startswith(p) and name != p:
            return False
    return bool(classify(name))


def classify_tasks(tasks: list[str]) -> list[str]:
    """Return classified project names for task/script names, dropping misses."""
    return [project for item in tasks if (project := classify(item))]


def sort_by_priority(tasks: list[str]) -> list[str]:
    """Stable priority helper for compatibility tests."""
    return list(tasks)
