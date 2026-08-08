"""ecos.services.governance.domain_manager_lifecycle — lifecycle helpers 拆分 (P110).

P110 关联: TASK-F7114ABA (omo lint god-module 800L 硬规则).
domain_manager.py 1406L 拆分: lifecycle helpers (~160L) 独立到本模块.

8 个 helper 函数 (内部状态管理 + URI 解析):
- _load_lifecycle / _save_lifecycle / _transition_valid
- _get_uri_state / _set_uri_state / _enrich_with_lifecycle
- resolve_semantic / parse_bos_uri

模式: 业务函数 import 在顶层 (无循环: lifecycle 不依赖 domain_manager
的 cmd_* 函数, 只用 resolve_path). 单一真源仍是 domain_manager.
原模块通过顶层 re-export 保持调用方不变.
"""

# 依赖: SEMANTIC_MAP, resolve_path (lazy import in parse_bos_uri 避免循环)
# (NOTE: 当前 cmd_bos_validate 路径不在此模块, 但 parse_bos_uri 用)

import json
from datetime import datetime

# URI 生命周期状态枚举 + 合法转换映射 (供 cmd_lifecycle_* 使用, 跨模块共享)
URI_LIFECYCLE_STATES = ["proposed", "active", "deprecated", "removed"]
URI_LIFECYCLE_TRANSITIONS = {
    "proposed": {"active", "deprecated"},
    "active": {"deprecated", "removed"},
    "deprecated": {"removed", "active"},
    "removed": set(),
}
SEMANTIC_MAP = {
    "_state": ["_control/STATE.md", "STATE.md"],
    "_memory": ["_control/MEMORY.md", "MEMORY.md"],
    "_entities": ["_knowledge/ENTITIES.md"],
    "_timeline": ["_control/TIMELINE.md"],
    "_claude": ["CLAUDE.md"],
}

# 注: URI_LIFECYCLE_FILE 改为惰性 import in _load_lifecycle / _save_lifecycle
# (避免 lifecycle 模块 import 时触发 domain_manager 顶层 URI_LIFECYCLE_FILE
#  与 lifecycle 的循环)


def _load_lifecycle() -> dict:
    """读取 URI 生命周期文件"""
    # 惰性 import (避免 lifecycle 模块顶层 import 触发循环)
    from .domain_manager import URI_LIFECYCLE_FILE  # type: ignore[reportAttributeAccessIssue]

    try:
        if URI_LIFECYCLE_FILE.exists():
            return json.loads(URI_LIFECYCLE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        pass
    return {"uris": {}, "_created": datetime.now().isoformat()}


def _save_lifecycle(data: dict) -> None:
    """写入 URI 生命周期文件"""
    from .domain_manager import URI_LIFECYCLE_FILE  # type: ignore[reportAttributeAccessIssue]

    URI_LIFECYCLE_FILE.parent.mkdir(parents=True, exist_ok=True)
    data["_updated"] = datetime.now().isoformat()
    URI_LIFECYCLE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def _transition_valid(from_state: str, to_state: str) -> bool:
    """检查状态转换是否合法"""
    allowed = URI_LIFECYCLE_TRANSITIONS.get(from_state, [])
    return to_state in allowed


def _get_uri_state(uri: str, lifecycle: dict = None) -> dict | None:  # type: ignore[reportArgumentType]
    """查询 URI 生命周期状态"""
    if lifecycle is None:
        lifecycle = _load_lifecycle()
    return lifecycle.get("uris", {}).get(uri)


def _set_uri_state(uri: str, state: str, note: str = "") -> tuple[bool, str]:
    """设置 URI 生命周期状态"""
    lifecycle = _load_lifecycle()
    uris = lifecycle.setdefault("uris", {})

    current = uris.get(uri, {})
    old_state = current.get("state", "proposed")

    # First registration: proposed is always valid
    if not current:
        pass
    elif not _transition_valid(old_state, state):
        return (
            False,
            f"非法转换: {old_state} → {state} (允许: {URI_LIFECYCLE_TRANSITIONS.get(old_state, [])})",
        )

    now = datetime.now().isoformat()
    uris[uri] = {
        "uri": uri,
        "state": state,
        "old_state": old_state if current else None,
        "created_at": current.get("created_at", now) if current else now,
        "updated_at": now,
        "note": note or current.get("note", ""),
        "transitions": current.get("transitions", [])
        + [{"from": old_state if current else None, "to": state, "at": now}],
    }
    _save_lifecycle(lifecycle)
    return True, f"{old_state or '—'} → {state}"


def _enrich_with_lifecycle(uri: str, result: dict) -> dict:
    """给解析结果附加生命周期信息"""
    lc = _get_uri_state(uri)
    if lc:
        result["lifecycle"] = lc["state"]
        result["lifecycle_note"] = lc.get("note", "")
        if lc["state"] == "deprecated":
            result["_warning"] = f"⚠️ 此 URI 已标记为 deprecate: {lc.get('note', '')}"
        elif lc["state"] == "removed":
            result["_error"] = f"❌ 此 URI 已移除 (410): {lc.get('note', '')}"
    else:
        result["lifecycle"] = "active"  # default
    return result


def resolve_semantic(domain: dict, shortcut: str) -> str:
    """将 _state/_memory 等语义快捷方式解析为实际文件路径"""
    # 惰性 import (避免 lifecycle 模块 import 时触发循环)
    from .domain_manager import resolve_path

    if shortcut not in SEMANTIC_MAP:
        return None  # type: ignore[reportReturnType]
    candidates = SEMANTIC_MAP[shortcut]
    if candidates is None:
        return shortcut  # 特殊处理
    base = resolve_path(domain)
    for c in candidates:
        full = base / c
        if full.exists():
            return c
    return candidates[0]  # fallback


def parse_bos_uri(uri: str, registry: list):
    """bos://{domain}[/{path}] → (domain, subpath)  v2格式"""
    # 惰性 import (避免 domain_manager 顶层 re-export 时的循环)
    from .domain_manager import SEMANTIC_MAP, resolve_path  # type: ignore[reportAttributeAccessIssue]

    if not uri.startswith("bos://"):
        return None, None

    # Strip prefix
    rest = uri.replace("bos://", "")

    # Handle v1 format (bos://l4/vault/...) → strip layer prefix
    parts = rest.split("/", 2)
    if parts[0] in ("l4", "l3", "l2", "l1", "l0", "storage", "model"):
        # v1 format: skip layer
        domain_id = parts[1] if len(parts) > 1 else ""
        subpath = parts[2] if len(parts) > 2 else ""
    else:
        # v2 format: bos://vault/_control/...
        domain_id = parts[0]
        subpath = "/".join(parts[1:]) if len(parts) > 1 else ""

    # Unified domain lookup helper
    def match_domain(d, q):
        if d["id"] == q:
            return True
        name = d.get("name", "").replace("@", "")
        if name == q or name.replace(" ", "") == q:
            return True
        if name.startswith(q):
            return True
        if q in d["id"]:
            return True
        return False

    # Handle semantic shortcuts (_state, _memory, etc.)
    if subpath and subpath.split("/")[0] in SEMANTIC_MAP:
        shortcut = subpath.split("/")[0]
        for d in registry:
            if match_domain(d, domain_id):
                resolved = resolve_semantic(d, shortcut)
                if resolved:
                    remainder = "/".join(subpath.split("/")[1:])
                    subpath = f"{resolved}/{remainder}" if remainder else resolved
                    return d, subpath
                return d, subpath

    # Strip .md extension for lookup flexibility
    if subpath.endswith(".md"):
        subpath[:-3]
    else:
        pass

    # Find domain (unified lookup)
    for d in registry:
        if match_domain(d, domain_id):
            # Try exact subpath first
            p = resolve_path(d)
            if not subpath:
                return d, ""
            full = p / subpath
            if full.exists():
                return d, subpath
            full2 = p / (subpath + ".md")
            if full2.exists():
                return d, subpath + ".md"
            return d, subpath

    return None, None
