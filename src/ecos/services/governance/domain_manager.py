#!/usr/bin/env python3
"""Domain Manager v2 — L4域生命周期管理 | ecos domain <cmd>"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import yaml

# L0 audit integration
try:
    from l0_audit import get_audit_log, validate_operation  # type: ignore[reportMissingImports]

    L0_AUDIT = True
except ImportError:
    L0_AUDIT = False

    def validate_operation(*a, **kw):
        return {"passed": True, "violations": []}

    def get_audit_log(*a, **kw):
        return []


# Unified audit integration
try:
    from audit_unified import log_event, print_audit_report, query_events  # type: ignore[reportMissingImports]

    HAS_AUDIT_UNIFIED = True
except ImportError:
    HAS_AUDIT_UNIFIED = False

    def query_events(**kw):
        return {
            "events": [],
            "total": 0,
            "sources": {},
            "passed": 0,
            "failed": 0,
            "anomalies": 0,
        }

    def print_audit_report(r):
        print("  ⚠️  unified audit 不可用")

    def log_event(**kw):
        return {
            "id": None,
            "timestamp": __import__("time").time(),
            "passed": True,
            "source": kw.get("source", "fallback"),
        }


# P110-A (ecos domain_manager 拆解, ADR-0108): 2 子模块
# Re-export 保持向后兼容 (ecos CLI / cockpit workflow 等)
# P110-B (TASK-F7114ABA 治本): cmd_bos_validate + lifecycle helpers 拆解
from .domain_manager_bos import (
    cmd_bos_validate,
)
from .domain_manager_cache import (
    _cache_warm,
    _l1_invalidate,
    load_registry,
)
from .domain_manager_domain_cmd import (
    cmd_all_validate,
    cmd_audit,
    cmd_check_refs,
    cmd_create,
    cmd_fix,
    cmd_list,
    cmd_register,  # P110-C (TASK-F7114ABA 治本)
    cmd_relations,
    cmd_stats,
    cmd_status,
    cmd_sync,
    cmd_tree,
    cmd_validate,
)
from .domain_manager_lifecycle import (
    URI_LIFECYCLE_STATES,
    _enrich_with_lifecycle,
    _load_lifecycle,
    _set_uri_state,
    parse_bos_uri,
    resolve_semantic,
)
from .domain_manager_search import cmd_search  # P110-C 治本续: 拆 cmd_search

H = Path.home()
DOCS = H / "Documents"
L0_CONSTRAINTS = Path(__file__).parent.parent / "l0" / "constraints.yaml"  # L0 SSOT
L0_CONSTRAINTS_L4 = (
    DOCS / "@学习进化/_knowledge/10-systems/基建架构/L0-constraints.yaml"
)  # L4缓存
M1_NODES_DIR = DOCS / "@驾驶舱/_meta/nodes"
DOMAIN_INDEX = DOCS / "@驾驶舱/_control/DOMAIN-INDEX.md"

# ── 域类型定义 ──
TYPE_ICONS = {
    "document": "📄",
    "config": "⚙️",
    "engine": "🔧",
    "tool": "🔨",
    "workspace": "📂",
    "storage": "💾",
    "model": "🧠",
    "view": "👁️",
}
KEMS_PLANES = {
    "document": ["_control", "_entities", "_knowledge", "_storage", "_archive"]
}
REQUIRED_TIER1 = [
    "CLAUDE.md",
    "_control/STATE.md",
    "_control/MEMORY.md",
    "_entities/ENTITIES.md",
    "_control/TIMELINE.md",
]
SKIP_AUDIT = {
    "Workspace",
    ".claude",
    "Obsidian",
    "Documents",
    "Desktop",
    "Downloads",
    "Library",
    "Movies",
    "Music",
    "Pictures",
    "Public",
    "Applications",
}

# ── 三层缓存系统 (L1: Memory / L2: JSON / L3: SSOT) ──
# L1: 进程内存 TTL 缓存
_L1_CACHE: dict[str, dict] = {}
L1_TTL = 60  # seconds

# L2: 持久化 JSON 缓存
BOS_CACHE_FILE = H / ".ecos" / "bos" / "cache.json"
L2_TTL = 300  # seconds (5 min)

# L3: SSOT (直接从 YAML/M1 节点读取 — 无缓存)


def find_domain(registry, name):
    for d in registry:
        if (
            d["id"] == name
            or d.get("name") == name
            or d.get("name", "").replace("@", "") == name
        ):
            return d
    return None


def resolve_path(domain):
    """解析域物理路径——处理子域 (parent_path) 和相对路径"""
    # Try explicit storage path
    for key in ["storage", "storage_path"]:
        s = domain.get(key)
        if s:
            p = Path(s)
            if p.exists():
                return p
            p2 = DOCS / s.lstrip("/")
            if p2.exists():
                return p2
            # Return the explicit path even if not found (for diagnostics)
            return p

    # For document domains without storage, construct from @name
    name = domain.get("name", "").replace("@", "")
    parent = domain.get("parent_path", "")
    if parent:
        p = DOCS / parent / name
        if p.exists():
            return p
        return DOCS / f"@{name}"  # fallback
    return DOCS / f"@{name}"


def scan_filesystem():
    """扫描文件系统发现候选域，排除已知非域目录"""
    found = []
    for root in [DOCS, H / "SharedWork", H, Path("/Volumes/SharedDisk")]:
        if not root.exists():
            continue
        try:
            for item in root.iterdir():
                if item.name in SKIP_AUDIT:
                    continue
                if item.is_symlink() or item.is_dir():
                    if item.name.startswith("."):
                        continue
                    if (item / "CLAUDE.md").exists() or any(
                        (item / p).exists() for p in ["_control", "_knowledge"]
                    ):
                        found.append(item)
        except PermissionError:
            continue
    return found


# ── 校验 ──
def _count_files(dir_path: Path, suffix: str = ".md") -> int:
    """Count files recursively in a directory (skip hidden)."""
    if not dir_path.is_dir():
        return 0
    return sum(
        1
        for f in dir_path.rglob(f"*{suffix}")
        if not f.name.startswith(".") and ".git" not in f.parts
    )


def _check_frontmatter(file_path: Path) -> bool:
    """Check if a file has YAML frontmatter."""
    if not file_path.exists():
        return False
    content = file_path.read_text(encoding="utf-8", errors="ignore")
    return content.startswith("---") and "---" in content[3:20]


def validate_domain(path, dtype="document", tier=1):
    results = []
    path = Path(path)

    # CLAUDE.md
    c = path / "CLAUDE.md"
    results.append(("CLAUDE.md", c.exists(), "入口文件" if c.exists() else "缺失"))

    # KEMS planes existence
    for p in KEMS_PLANES.get(dtype, []):
        pp = path / p
        exists = pp.is_dir()
        results.append((f"KEMS/{p}/", exists, "存在" if exists else "缺失"))

    # KEMS content quality (document domains only)
    if dtype == "document":
        for p in KEMS_PLANES.get(dtype, []):
            pp = path / p
            if pp.is_dir():
                md_count = _count_files(pp)
                # Check frontmatter in STATE.md / MEMORY.md / ENTITIES.md
                for key_file in [
                    "STATE.md",
                    "MEMORY.md",
                    "ENTITIES.md",
                    "INDEX.md",
                    "TIMELINE.md",
                ]:
                    kf = pp / key_file
                    if kf.exists():
                        has_fm = _check_frontmatter(kf)
                        if not has_fm:
                            results.append(
                                (f"quality/{p}/{key_file}", False, "缺 frontmatter")
                            )
                results.append(
                    (
                        f"size/{p}/",
                        md_count > 0,
                        f"{md_count} 文件" if md_count else "空",
                    )
                )

    # Tier 1
    if tier == 1:
        for r in REQUIRED_TIER1:
            pp = path / r
            results.append((r, pp.exists(), "存在" if pp.exists() else "缺失"))

    # BOS connectivity (check if domain has BOSRoute M1 node)
    m1_bos = Path(__file__).resolve().parent.parent / "ssot" / "mof" / "m1" / "bosroute"
    if m1_bos.exists():
        has_bos = any(
            f.name.startswith("BOSROUTE-") for f in m1_bos.iterdir() if f.is_file()
        )
        results.append(
            (
                "BOSRoute M1",
                has_bos,
                f"{len(list(m1_bos.glob('*.yaml')))} 路由" if has_bos else "缺失",
            )
        )

    return results


# ── 命令 ──


def cmd_resolve(args):
    """BOS URI → 物理路径解析"""
    if not args:
        print("用法: ecos domain resolve <bos://l4/vault/...>")

        return
    registry = load_registry()
    uri = args[0]
    d, sub = parse_bos_uri(uri, registry)
    if not d:
        print(f"❌ 无法解析: {uri}")
        return

    # Check lifecycle
    result = _enrich_with_lifecycle(uri, {"domain": d, "subpath": sub})
    if result.get("_error"):
        print(f"  {result['_error']}")
        return
    warning = result.get("_warning", "")

    base = resolve_path(d)
    full = base / sub if sub else base
    exists = full.exists()
    print(f"\n  {uri}")
    if warning:
        print(f"  {warning}")
    print(f"  → {full} {'✅' if exists else '❌'}")
    print(
        f"  域: {d.get('name', d['id'])} | 类型: {d.get('domain_type', '?')} | 大小: {full.stat().st_size if exists else 0} bytes"
    )
    print(f"  生命周期: {result['lifecycle']}\n")


# ── BOS URI 约束评估 (X4-C10~C13) ──


def cmd_routes(args):
    """生成 BOS routes.json 缓存"""
    registry = load_registry()
    routes = {}
    for d in registry:
        did = d["id"]
        p = resolve_path(d)
        entry = {
            "path": str(p),
            "type": d.get("domain_type", "document"),
            "layer": d.get("layer", "L4"),
            "exists": p.exists(),
        }
        # Add semantic shortcuts
        if d.get("domain_type", "document") == "document":
            entry["semantic"] = {}
            for shortcut in ["_state", "_memory", "_entities", "_timeline", "_claude"]:
                resolved = resolve_semantic(d, shortcut)
                if resolved:
                    entry["semantic"][shortcut] = resolved
        routes[did] = entry

    # Also add name aliases
    for d in registry:
        name = d.get("name", "").replace("@", "")
        if name and name != d["id"]:
            routes[name] = routes[d["id"]]

    routes_file = Path.home() / ".ecos" / "bos" / "routes.json"
    routes_file.parent.mkdir(parents=True, exist_ok=True)
    with open(routes_file, "w") as f:
        json.dump(routes, f, indent=2, ensure_ascii=False)
    print(f"✅ routes.json ({len(routes)} entries) → {routes_file}\n")


def cmd_read(args):
    """通过BOS URI读取域资源"""
    if not args:
        print("用法: ecos domain read <bos://l4/vault/...>")

        return
    registry = load_registry()
    uri = args[0]
    d, sub = parse_bos_uri(uri, registry)
    if not d:
        print(f"❌ 无法解析: {uri}")
        return

    # Check lifecycle
    result = _enrich_with_lifecycle(uri, {"domain": d, "subpath": sub})
    if result.get("_error"):
        print(f"  {result['_error']}")
        return
    result.get("_warning", "")

    base = resolve_path(d)
    full = base / sub if sub else base
    if not full.exists():
        print(f"❌ 不存在: {full}")
        return
    if full.is_dir():
        items = os.listdir(full)
        print(f"\n  📁 {uri}/ ({len(items)} items)")
        for i in sorted(items)[:20]:
            ip = full / i
            print(f"    {'📁' if ip.is_dir() else '📄'} {i}")
        if len(items) > 20:
            print(f"    ... +{len(items) - 20}")
    else:
        content = full.read_text()
        max_lines = int(args[1]) if len(args) > 1 else 50
        lines = content.split("\n")[:max_lines]
        print(f"\n  📄 {uri} ({len(content)} bytes)\n")
        for line in lines:
            print(f"  {line}")
        if len(content.split("\n")) > max_lines:
            print(f"\n  ... (共{len(content.split('\n'))}行)")
    print()


# ── URI 生命周期 CLI ──


def cmd_lifecycle_set(args):
    """设置 URI 生命周期状态: ecos domain lifecycle-set <bos://uri> <state> [--note ...]"""
    if len(args) < 2:
        print("用法: ecos domain lifecycle-set <bos://uri> <state> [--note ...]")
        print(f"  state: {'|'.join(URI_LIFECYCLE_STATES)}")
        return
    uri = args[0]
    state = args[1]
    note = ""
    for i, a in enumerate(args[2:], 2):
        if a == "--note" and i + 1 < len(args):
            note = args[i + 1]
    if state not in URI_LIFECYCLE_STATES:
        print(f"❌ 无效状态: {state} (允许: {URI_LIFECYCLE_STATES})")
        return
    ok, msg = _set_uri_state(uri, state, note)
    if ok:
        print(f"  ✅ {uri}: {msg}")
    else:
        print(f"  ❌ {msg}")


def cmd_lifecycle_list(args):
    """列出所有 URI 生命周期状态"""
    lifecycle = _load_lifecycle()
    uris = lifecycle.get("uris", {})
    if not uris:
        print("\n  📋 暂无 URI 生命周期记录\n")
        return
    # Filter
    state_filter = args[0] if args else None
    print(f"\n  ═══ URI 生命周期 ({len(uris)} 条) ═══\n")
    print(f"  {'状态':<12} {'URI':<50} {'备注'}")
    print(f"  {'─' * 12} {'─' * 50} {'─' * 30}")
    for u, info in sorted(uris.items()):
        s = info.get("state", "?")
        if state_filter and s != state_filter:
            continue
        icons = {"proposed": "🆕", "active": "✅", "deprecated": "⚠️", "removed": "❌"}
        note = info.get("note", "")[:28]
        print(f"  {icons.get(s, '?')} {s:<10} {u:<50} {note}")
    print()


def cmd_lifecycle_status(args):
    """URI 生命周期状态统计"""
    lifecycle = _load_lifecycle()
    uris = lifecycle.get("uris", {})
    if not uris:
        print("\n  📋 暂无 URI 生命周期记录\n")
        return
    counts = {}
    for info in uris.values():
        s = info.get("state", "?")
        counts[s] = counts.get(s, 0) + 1
    print("\n  ═══ URI 生命周期统计 ═══\n")
    for state in URI_LIFECYCLE_STATES:
        c = counts.get(state, 0)
        icons = {"proposed": "🆕", "active": "✅", "deprecated": "⚠️", "removed": "❌"}
        print(f"  {icons.get(state, '?')} {state:<12} {c}")
    print(f"\n  总计: {len(uris)} URI\n")


# ── 缓存管理 CLI ──


def cmd_cache_status(args):
    """三层缓存状态"""
    l1_size = len(_L1_CACHE)
    l2_size = 0
    l2_age = 0
    try:
        if BOS_CACHE_FILE.exists():
            data = json.loads(BOS_CACHE_FILE.read_text())
            l2_size = len([k for k in data if not k.startswith("_")])
            updated = data.get("_updated", "")
            if updated:
                l2_age = int(
                    (datetime.now() - datetime.fromisoformat(updated)).total_seconds()
                )
    except Exception:  # defensive fallback
        pass

    mtime = 0
    for p in [L0_CONSTRAINTS, L0_CONSTRAINTS_L4]:
        try:
            m = p.stat().st_mtime if p.exists() else 0
            if m > mtime:
                mtime = m
        except Exception:  # defensive fallback
            pass
    ssot_age = int(__import__("time").time() - mtime) if mtime else 0

    print("\n  ═══ 三层缓存状态 ═══\n")
    print(f"  L1 (内存):  {l1_size} 条目  TTL={L1_TTL}s")
    print(f"  L2 (JSON):  {l2_size} 条目  TTL={L2_TTL}s  年龄={l2_age}s")
    print(f"  L3 (SSOT):  L0-constraints.yaml  年龄={ssot_age}s")
    print(f"  缓存文件:   {BOS_CACHE_FILE}")

    # Key detail
    if l1_size > 0:
        print("\n  L1 键列表:")
        for k in sorted(_L1_CACHE.keys()):
            print(f"    • {k}")

    # Warm options
    print("\n  操作:")
    print("    ecos domain cache-warm   预热 L1 从 L2")
    print("    ecos domain cache-clear  清空所有缓存\n")


def cmd_cache_warm(args):
    """预热 L1 缓存从 L2"""
    stats = _cache_warm()
    print(
        f"  ✅ 预热完成: L2={stats['l2_items']} → 预热={stats['warmed']} | L1: {stats['l1_before']}→{stats['l1_after']}"
    )


def cmd_cache_clear(args):
    """清空所有缓存层"""
    _l1_invalidate()
    try:
        if BOS_CACHE_FILE.exists():
            BOS_CACHE_FILE.unlink()
    except Exception:  # defensive fallback
        pass
    print("  ✅ 所有缓存已清空 (L1 + L2)")


# ── 统一审计查询 CLI ──


def cmd_audit_unified(args):
    """统一审计查询: ecos domain audit-unified [--hours 24] [--source all] [--domain <域>] [--event-type <类型>]"""
    hours = 24
    source = "all"
    domain = None
    event_type = None

    for i, a in enumerate(args):
        if a == "--hours" and i + 1 < len(args):
            hours = int(args[i + 1])
        elif a == "--source" and i + 1 < len(args):
            source = args[i + 1]
        elif a == "--domain" and i + 1 < len(args):
            domain = args[i + 1]
        elif a == "--event-type" and i + 1 < len(args):
            event_type = args[i + 1]
        elif a == "--help" or a == "-h":
            print(cmd_audit_unified.__doc__)
            print("  --hours <N>     时间窗口 (小时, 默认24)")
            print("  --source <s>    来源: all|l0|bos|ssb|daemon|healer|unified")
            print("  --domain <d>    域过滤")
            print("  --event-type <t> 事件类型过滤")
            return

    if not HAS_AUDIT_UNIFIED:
        print("\n  ⚠️  audit_unified 模块不可用\n")
        return

    result = query_events(
        hours=hours, source=source, domain=domain, event_type=event_type
    )
    print_audit_report(result)


def cmd_info(args):
    """域综合报告 (status+validate+tree)"""
    if not args:
        print("用法: ecos domain info <域>")

        return
    cmd_status(args)
    cmd_validate(args)
    cmd_tree(args)


def cmd_workflow(args):
    """BOS工作流编排执行"""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from workflow import execute_workflow, list_workflows  # type: ignore[reportMissingImports]

    if not args or args[0] == "list":
        wfs = list_workflows()
        if wfs:
            print("\n  可用工作流:\n")
            for w in wfs:
                wf = __import__("workflow", fromlist=["load_workflow"]).load_workflow(w)
                if wf:
                    print(f"  📋 {w:<25} {wf.get('description', '')}")
        else:
            print("\n  📋 无可用工作流\n")
        return

    name = args[0]
    dry = "--dry-run" in args
    result = execute_workflow(name, dry_run=dry)
    if "error" in result:
        print(f"  ❌ {result['error']}\n")


def cmd_audit_log(args):
    """查询L0审计日志"""
    domain = args[0] if args else None
    entries = get_audit_log(domain=domain, limit=50)

    if not entries:
        print("\n  📋 暂无审计记录\n")
        return

    print(f"\n  ═══ L0审计日志 ({len(entries)}条) ═══\n")
    for e in entries[-20:]:  # last 20
        icon = "✅" if e["passed"] else "❌"
        print(
            f"  {icon} {e['timestamp'][:19]} | {e['operation']:<20} | {e.get('domain', '?'):<15} | {e.get('uri', '')}"
        )
    print()


def cmd_capabilities(args):
    """查询域提供的能力清单"""

    M1_DOMAIN = (
        Path(__file__).resolve().parent.parent / "ssot" / "mof" / "m1" / "domain"
    )
    if not M1_DOMAIN.exists():
        print("⚠️  M1 Domain 节点目录不存在")
        return
    if args:
        target = args[0]
        targets = (
            [target]
            if not target.startswith("bos://")
            else [target.replace("bos://", "").split("/")[0]]
        )
    else:
        targets = None

    found = 0
    for f in sorted(M1_DOMAIN.glob("*.yaml")):
        with open(f) as fh:
            node = yaml.safe_load(fh)
        if not node:
            continue
        props = node.get("properties", {})
        did = node.get("id", "").replace("DOMAIN-", "")
        if targets and did not in targets:
            continue
        found += 1
        caps = props.get("capabilities", [])
        entry = props.get("entry_points", {})
        bos = props.get("bos_uri_pattern", "?")
        dtype = props.get("domain_type", "?")
        print(f"\n  {did}")
        print(f"    类型: {dtype}  BOS: {bos}")
        if caps:
            print("    能力:")
            for c in caps:
                print(f"      - {c}")
        if entry:
            print("    入口:")
            for k, v in entry.items():
                print(f"      {k}: {v}")
    if not found:
        print(f"❌ 未找到域: {args[0] if args else 'any'}")


# ── 主入口 ──
def main():
    cmds = {
        "list": cmd_list,
        "status": cmd_status,
        "validate": cmd_validate,
        "validate-all": cmd_all_validate,
        "tree": cmd_tree,
        "audit": cmd_audit,
        "relations": cmd_relations,
        "sync": cmd_sync,
        "stats": cmd_stats,
        "create": cmd_create,
        "register": cmd_register,
        "fix": cmd_fix,
        "info": cmd_info,
        "check-refs": cmd_check_refs,
        "resolve": cmd_resolve,
        "read": cmd_read,
        "bos-validate": cmd_bos_validate,
        "routes": cmd_routes,
        "search": cmd_search,
        "audit-log": cmd_audit_log,
        "workflow": cmd_workflow,
        "capabilities": cmd_capabilities,
        "lifecycle-set": cmd_lifecycle_set,
        "lifecycle-list": cmd_lifecycle_list,
        "lifecycle-status": cmd_lifecycle_status,
        "cache-status": cmd_cache_status,
        "cache-warm": cmd_cache_warm,
        "cache-clear": cmd_cache_clear,
        "audit-unified": cmd_audit_unified,
    }
    if len(sys.argv) < 2:
        print("\necos domain <cmd> [args]\n")
        for c, f in cmds.items():
            print(f"  {c:<12} {f.__doc__ or ''}")
        print()
        return
    cmd = sys.argv[1]
    args = sys.argv[2:]
    if cmd in cmds:
        cmds[cmd](args)
    else:
        print(f"❌ {cmd}\n可用: {' '.join(cmds)}")


if __name__ == "__main__":
    main()
