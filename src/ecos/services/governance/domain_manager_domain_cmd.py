"""P110-A: ecos domain_manager_domain_cmd 子模块 (从 domain_manager.py 提取).

ADR-0108 P110-A 拆解: 9 个 CLI 域命令 (~365L) 拆出.

业务 (9 functions, 全是 CLI cmd_* 薄包装):
  - 域列表: cmd_list, cmd_tree
  - 域状态: cmd_status, cmd_stats
  - 域审计: cmd_audit, cmd_relations
  - 域校验: cmd_validate, cmd_all_validate
  - 域写操作: cmd_create

模块依赖: (同 domain_manager.py)
  - sys, os, json, yaml (stdlib)
  - pathlib (Path), datetime, collections (defaultdict)
  - l0_audit (optional, try/except)
  - audit_unified (optional, try/except)

向后兼容 (P88-P108 模式):
  domain_manager.py 通过 `from .domain_manager_domain_cmd import (...)` re-export,
  保持 `from ecos.services.governance.domain_manager import cmd_list` 等不破.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# L0 SSOT 约束 (供 cmd_register / cmd_capabilities 等用, P110-C 跨模块共享)
import yaml

# 惰性 import (避免 domain_manager 顶层 re-export 时的循环)
# L0_CONSTRAINTS / DOMAIN_INDEX 在 cmd_register / cmd_capabilities 内部用

# L0 audit integration
try:
    from l0_audit import get_audit_log, validate_operation

    L0_AUDIT = True
except ImportError:
    L0_AUDIT = False

    def validate_operation(*a, **kw):
        return {"passed": True, "violations": []}

    def get_audit_log(*a, **kw):
        return []


# Unified audit integration
try:
    from audit_unified import log_event, print_audit_report, query_events

    HAS_AUDIT_UNIFIED = True
except ImportError:
    HAS_AUDIT_UNIFIED = False

    def query_events(**kw):
        return {"events": [], "total": 0}

    def print_audit_report(*a, **kw):
        return ""

    def log_event(*a, **kw):
        return None


# ── 模块级常量（从 domain_manager.py 拆出，ADR-0108 P110-A）──
DOCS = Path.home() / "Documents"
TYPE_ICONS = {
    "document": "\U0001f4c4",
    "config": "\u2699\ufe0f",
    "engine": "\U0001f527",
    "tool": "\U0001f528",
    "workspace": "\U0001f4c2",
    "storage": "\U0001f4be",
    "model": "\U0001f9e0",
    "view": "\U0001f441\ufe0f",
}
KEMS_PLANES = {
    "document": ["_control", "_entities", "_knowledge", "_storage", "_archive"]
}


# ── 懒加载函数（避免循环 import：domain_manager.py 在 import 本模块时尚未完全执行）──
def _get_dm():
    from ecos.services.governance import domain_manager

    return domain_manager


def find_domain(registry, name):
    return _get_dm().find_domain(registry, name)


def resolve_path(domain):
    return _get_dm().resolve_path(domain)


def validate_domain(path, dtype, tier):
    return _get_dm().validate_domain(path, dtype, tier)


def scan_filesystem():
    return _get_dm().scan_filesystem()


def _get_cache():
    from ecos.services.governance import domain_manager_cache

    return domain_manager_cache


def load_registry(force_reload: bool = False):
    return _get_cache().load_registry(force_reload)


def invalidate_registry_cache():
    return _get_cache().invalidate_registry_cache()


def cmd_list(args):
    registry = load_registry()
    by_type = defaultdict(list)
    for d in registry:
        by_type[d.get("domain_type", "document")].append(d)

    if "--json" in args:
        print(
            json.dumps(
                [
                    {
                        k: d.get(k)
                        for k in ["id", "name", "domain_type", "layer", "status"]
                    }
                    for d in registry
                ],
                indent=2,
                ensure_ascii=False,
            )
        )
        return

    print(f"\n{'ID':<20} {'类型':<12} {'名称':<18} {'状态':<8} {'路径'}")
    print("-" * 80)
    for dtype in [
        "document",
        "config",
        "engine",
        "tool",
        "workspace",
        "storage",
        "model",
        "view",
    ]:
        for d in by_type.get(dtype, []):
            icon = TYPE_ICONS.get(dtype, "")
            p = resolve_path(d)
            path_ok = "✅" if (p and p.exists()) else "❌"
            print(
                f"{icon} {d['id']:<17} {dtype:<12} {d.get('name', '?'):<18} {d.get('status', 'active'):<8} {path_ok} {p}"
            )
    print(f"\n  {len(registry)} 域 · {len(by_type)} 类型\n")


def cmd_status(args):
    registry = load_registry()
    if not args:
        print("用法: ecos domain status <域>")

        return
    d = find_domain(registry, args[0])
    if not d:
        print(f"❌ '{args[0]}' 未注册")
        return

    p = resolve_path(d)
    print(
        f"\n  {TYPE_ICONS.get(d.get('domain_type', ''), '')} {d.get('name', d['id'])}"
    )
    print(
        f"  ID: {d['id']}  |  类型: {d.get('domain_type', '?')}  |  层: {d.get('layer', '?')}  |  Tier: {d.get('governance_tier', '-')}"
    )
    print(f"  路径: {p} {'✅' if p.exists() else '❌'}")
    if d.get("description"):
        print(f"  说明: {d['description'][:100]}")
    print()


def cmd_validate(args):
    registry = load_registry()
    if not args:
        print("用法: ecos domain validate <域>")

        return
    d = find_domain(registry, args[0])
    if not d:
        print(f"❌ '{args[0]}' 未注册")
        return

    p = resolve_path(d)
    if not p.exists():
        print(f"❌ 路径不存在: {p}")
        return

    dtype = d.get("domain_type", "document")
    tier = d.get("governance_tier", 1)
    print(f"\n  校验: {d.get('name', d['id'])} ({dtype}, Tier {tier})  →  {p}")
    print("  " + "-" * 55)

    results = validate_domain(p, dtype, tier)
    passed = sum(1 for _, ok, _ in results if ok)
    failed = len(results) - passed
    for name, ok, detail in results:
        print(f"  {'✅' if ok else '❌'} {name:<25} {detail}")
    print(f"\n  {passed}✅  {failed}❌\n")


def cmd_tree(args):
    """目录树——标注KEMS面"""
    registry = load_registry()
    if not args:
        print("用法: ecos domain tree <域>")

        return
    d = find_domain(registry, args[0])
    if not d:
        print(f"❌ '{args[0]}' 未注册")
        return

    p = resolve_path(d)
    if not p.exists():
        print(f"❌ {p}")
        return

    planes = {pl for pl in KEMS_PLANES.get(d.get("domain_type", ""), [])}
    print(f"\n  {d.get('name', d['id'])}/")

    def tree(dir_path, prefix="", depth=0):
        if depth > 3:
            return
        items = sorted(
            [
                i
                for i in dir_path.iterdir()
                if not i.name.startswith(".") and not i.name.startswith("__")
            ],
            key=lambda x: (not x.is_dir(), x.name),
        )
        for i, item in enumerate(items):
            is_last = i == len(items) - 1
            branch = "└── " if is_last else "├── "
            marker = ""
            if item.is_dir():
                if item.name in planes:
                    marker = " ← KEMS"
                elif item.name.startswith("_"):
                    marker = " ← sys"
                branch += f"📁 {item.name}{marker}"
            else:
                branch += f"📄 {item.name}"
            print(f"  {prefix}{branch}")
            if item.is_dir() and depth < 2:
                tree(item, prefix + ("    " if is_last else "│   "), depth + 1)

    tree(p)
    print()


def cmd_audit(args):
    registry = load_registry()
    reg_paths = set()
    for d in registry:
        p = resolve_path(d)
        if p:
            reg_paths.add(str(p.resolve()))

    # Phase 1: registered check
    print("\n  === 已注册域 ===\n")
    ok = 0
    miss = 0
    for d in registry:
        p = resolve_path(d)
        exists = p.exists() if p else False
        print(f"  {'✅' if exists else '❌'} {d.get('name', d['id']):<20} {p}")
        if exists:
            ok += 1
        else:
            miss += 1
    print(f"\n  存在:{ok}  缺失:{miss}")

    # Phase 2: unregistered scan
    print("\n  === 未注册候选 ===\n")
    found = scan_filesystem()
    unreg = [d for d in found if str(d.resolve()) not in reg_paths]
    if unreg:
        for d in unreg:
            has_claude = (d / "CLAUDE.md").exists()
            print(f"  📁 {d} {'(有CLAUDE.md)' if has_claude else '(有KEMS面)'}")
        print(f"\n  候选: {len(unreg)}")
    else:
        print("  ✅ 无未注册候选")
    print()


def cmd_relations(args):
    """域间关系图"""
    load_registry()
    print("\n  域间关系:")
    relations = {
        "governs": ("@驾驶舱", "所有Document域"),
        "provides_to": ("@公共", "@学习进化 @个人 @家庭生活 @工作文档"),
        "consumes": ("@学习进化", "minerva knowledge"),
        "configures": (".ai .agents", "L3入口·Agent运行时"),
        "executes_on": ("bin ToolBox", "L1运行时·launchd"),
        "archives_for": ("SharedDisk", "@家庭生活 @个人 @学习进化"),
        "complements": ("@个人", "@家庭生活 (我 vs 我们)"),
        "syncs_via": ("@家庭生活", "SharedConf → iCloud"),
    }
    for rel, (src, dst) in relations.items():
        print(f"  {src:<20} ──{rel}──→  {dst}")
    print()


def cmd_stats(args):
    """全域统计"""
    registry = load_registry()
    by_type = defaultdict(list)
    by_layer = defaultdict(list)
    for d in registry:
        by_type[d.get("domain_type", "document")].append(d)
        by_layer[d.get("layer", "L4")].append(d)

    print("\n  ═══ 全域统计 ═══\n")
    print(f"  总域数:   {len(registry)}")
    print(f"  类型数:   {len(by_type)}")
    print("\n  按类型:")
    for t in [
        "document",
        "config",
        "engine",
        "tool",
        "workspace",
        "storage",
        "model",
        "view",
    ]:
        if t in by_type:
            print(f"    {TYPE_ICONS.get(t, '')} {t:<12} {len(by_type[t])}")
    print("\n  按层:")
    for layer in sorted(by_layer.keys()):
        print(f"    {layer:<12} {len(by_layer[layer])}")

    # Path health
    ok = sum(1 for d in registry if resolve_path(d).exists())
    print(f"\n  路径健康: {ok}/{len(registry)} ({100 * ok // len(registry)}%)")

    # KEMS health — check document domains
    docs = [d for d in registry if d.get("domain_type", "document") == "document"]
    kems_ok = sum(
        1
        for d in docs
        if resolve_path(d).exists()
        and all((resolve_path(d) / p).is_dir() for p in KEMS_PLANES.get("document", []))
    )
    print(f"  KEMS完整:  {kems_ok}/{len(docs)} (document域)")
    if docs and kems_ok < len(docs):
        for d in docs:
            p = resolve_path(d)
            if p.exists():
                missing = [
                    pl
                    for pl in KEMS_PLANES.get("document", [])
                    if not (p / pl).is_dir()
                ]
                if missing:
                    print(f"    ⚠️  {d.get('name', '?')}: 缺 {' '.join(missing)}")
    print()


def cmd_create(args):
    """交互式创建新域"""
    print("\n  ═══ 创建新域 ═══\n")

    # 1. Name
    name = input("  域名称 (如: @我的域): ").strip()
    if not name:
        print("❌ 取消")
        return
    if not name.startswith("@"):
        name = "@" + name

    # 2. Type
    print("\n  域类型:")
    for i, t in enumerate(["document", "config", "engine", "tool", "workspace"], 1):
        print(f"    {i}. {TYPE_ICONS.get(t, '')} {t}")
    ti = input("  选择 [1]: ").strip() or "1"
    dtype = (
        ["document", "config", "engine", "tool", "workspace"][int(ti) - 1]
        if ti.isdigit() and 1 <= int(ti) <= 5
        else "document"
    )

    # 3. Path
    default_path = DOCS / name
    path_str = input(f"  路径 [{default_path}]: ").strip()
    path = Path(path_str) if path_str else default_path

    # 4. ID
    domain_id = input(
        f"  ID [{name.replace('@', '').replace(' ', '-').lower()}]: "
    ).strip()
    if not domain_id:
        domain_id = name.replace("@", "").replace(" ", "-").lower()

    # 5. Tier
    tier_str = input("  Tier [1-完整/3-最小] [1]: ").strip() or "1"

    # L0 audit: pre-check
    audit = validate_operation(domain_id, "domain_create")
    if not audit["passed"]:
        print(f"  ⚠️  L0审计: {len(audit['violations'])}项违规")
        for v in audit["violations"]:
            print(f"     - {v['constraint']}: {v.get('note', '')}")
        if input("  继续? [y/N]: ").strip().lower() != "y":
            print("❌ 取消")
            return
    tier = int(tier_str) if tier_str in ("1", "3") else 1

    print("\n  确认创建:")
    print(f"    名称: {name}  |  ID: {domain_id}  |  类型: {dtype}  |  Tier: {tier}")
    print(f"    路径: {path}")
    ok = input("\n  创建? [Y/n]: ").strip().lower()
    if ok and ok != "y":
        print("❌ 取消")
        return

    # Create
    path.mkdir(parents=True, exist_ok=True)

    if dtype == "document":
        # Create KEMS structure
        for plane in KEMS_PLANES.get("document", []):
            (path / plane).mkdir(exist_ok=True)
        (path / "_archive").mkdir(exist_ok=True)

        # Create CLAUDE.md
        claude_content = f"""# {name} — 域入口

> L4 | KEMS 六面 | v1.0 | {datetime.now().strftime("%Y-%m-%d")}

## 控制面
- STATE: `_control/STATE.md`
- MEMORY: `_control/MEMORY.md`

## 知识面
- `_knowledge/` — 编号分类

## 维护
创建: {datetime.now().strftime("%Y-%m-%d")}
"""
        (path / "CLAUDE.md").write_text(claude_content)

        if tier == 1:
            (path / "_control" / "STATE.md").write_text(
                f"# STATE — {name}\n\n> 创建: {datetime.now().strftime('%Y-%m-%d')}\n\n## 当前阶段\n\n初始化\n"
            )
            (path / "_control" / "MEMORY.md").write_text(
                f"# MEMORY — {name}\n\n> 创建: {datetime.now().strftime('%Y-%m-%d')}\n"
            )
            (path / "_entities").mkdir(exist_ok=True)
            (path / "_entities" / "ENTITIES.md").write_text(
                f"# ENTITIES — {name}\n\n> 创建: {datetime.now().strftime('%Y-%m-%d')}\n"
            )
            (path / "_control" / "TIMELINE.md").write_text(
                f"# TIMELINE — {name}\n\n> 创建: {datetime.now().strftime('%Y-%m-%d')}\n"
            )

    print(f"\n  ✅ 域已创建: {path}")
    print(f"  下一步: ecos domain register {domain_id}  # 注册到L0\n")


def cmd_all_validate(args):
    """校验所有document域"""
    registry = load_registry()
    docs = [d for d in registry if d.get("domain_type", "document") == "document"]
    print(f"\n  校验 {len(docs)} 个 document 域:\n")

    total_pass = 0
    total_fail = 0
    for d in docs:
        p = resolve_path(d)
        if not p.exists():
            print(f"  ❌ {d.get('name', d['id']):<16} 路径不存在")
            total_fail += 1
            continue
        results = validate_domain(p, "document", d.get("governance_tier", 1))
        passed = sum(1 for _, ok, _ in results if ok)
        failed = len(results) - passed
        total_pass += passed
        total_fail += failed
        icon = "✅" if failed == 0 else "⚠️"
        print(
            f"  {icon} {d.get('name', d['id']):<16} {passed}/{len(results)} passed"
            + (
                f"  (缺: {', '.join(n for n, ok, _ in results if not ok)[:50]})"
                if failed
                else ""
            )
        )

    print(f"\n  {total_pass}✅  {total_fail}❌\n")


# P110-C: cmd_register 拆解 (77L, 治本 domain_manager 治本)
def cmd_register(args):
    """注册新域到L0"""
    if len(args) < 1:
        print(
            "用法: ecos domain register <路径> [--type document] [--name 名称] [--id domain-id]"
        )
        return

    path = Path(args[0])
    if not path.exists():
        print(f"❌ 路径不存在: {path}")
        return

    # Parse flags
    dtype = "document"
    name = path.name
    domain_id = name.replace("@", "").replace(" ", "-").lower()
    for i, a in enumerate(args[1:], 1):
        if a == "--type" and i + 1 < len(args):
            dtype = args[i + 1]
        if a == "--name" and i + 1 < len(args):
            name = args[i + 1]
        if a == "--id" and i + 1 < len(args):
            domain_id = args[i + 1]

    # Tier auto-detect
    tier = 1 if (path / "_control" / "STATE.md").exists() else 3

    # 惰性 import (避免 domain_manager_domain_cmd 顶层 import 的循环)
    from .domain_manager import L0_CONSTRAINTS

    # Read existing registry as YAML
    try:
        with open(L0_CONSTRAINTS) as f:
            data = yaml.safe_load(f) or {}
    except Exception as e:  # defensive fallback
        print(f"❌ 无法读取 L0-constraints.yaml: {e}")
        return

    registry = data.get("domain_registry", [])
    if registry is None:
        registry = []

    # Check for duplicate by ID or path
    existing_ids = {d.get("id") for d in registry if isinstance(d, dict)}
    existing_paths = {d.get("storage") for d in registry if isinstance(d, dict)}
    if domain_id in existing_ids:
        print(f"⚠️  ID '{domain_id}' 已存在")
        return
    if str(path) in existing_paths:
        print(f"⚠️  路径 '{path}' 已注册")
        return

    # Build entry as dict (safe YAML serialization — no f-string injection risk)
    new_entry = {
        "id": domain_id,
        "name": name,
        "layer": "L4",
        "governance_tier": tier,
        "domain_type": dtype,
        "claude_md": str(path / "CLAUDE.md") if (path / "CLAUDE.md").exists() else None,
        "state_md": str(path / "_control" / "STATE.md")
        if (path / "_control" / "STATE.md").exists()
        else None,
        "status": "active",
        "storage": str(path),
        "description": f"注册于 {datetime.now().strftime('%Y-%m-%d')}",
    }
    registry.append(new_entry)
    data["domain_registry"] = registry

    # Write back via yaml.dump (auto-escapes special chars, replaces old string concatenation)
    from .domain_manager import L0_CONSTRAINTS

    with open(L0_CONSTRAINTS, "w") as f:
        yaml.dump(
            data, f, default_flow_style=False, allow_unicode=True, sort_keys=False
        )
    print(f"✅ 已注册: {name} ({domain_id}) → L0-constraints.yaml\n")
    print("   ℹ️  注意: yaml.dump 会重排文件格式（注释丢失）。用 git diff 确认变更。\n")


# P110-C: cmd_search + cmd_fix 拆解 (141L)
def cmd_sync(args):
    registry = load_registry()
    by_type = defaultdict(list)
    for d in registry:
        by_type[d.get("domain_type", "document")].append(d)

    lines = [
        "# DOMAIN-INDEX — 全域注册表\n",
        f"> @驾驶舱/_control/ | auto-generated {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n",
        f"## {len(registry)} 域 · {len(by_type)} 类型\n\n",
    ]
    for dtype in [
        "document",
        "config",
        "engine",
        "tool",
        "workspace",
        "storage",
        "model",
        "view",
    ]:
        items = by_type.get(dtype, [])
        if not items:
            continue
        lines.append(f"### {TYPE_ICONS.get(dtype, '')} {dtype} ({len(items)})\n\n")
        lines.append("| ID | 名称 | 层 | Tier | 路径 |\n|---|---|---|---|---|\n")
        for d in items:
            p = resolve_path(d)
            lines.append(
                f"| {d['id']} | {d.get('name', '-')} | {d.get('layer', '-')} | {d.get('governance_tier', '-')} | {p} |\n"
            )
        lines.append("\n")

    lines.append(f"---\n*auto: {datetime.now().isoformat()}*\n")
    from .domain_manager import DOMAIN_INDEX

    with open(DOMAIN_INDEX, "w") as f:
        f.writelines(lines)
    print(f"✅ DOMAIN-INDEX.md ({len(registry)}域)\n")


# ── BOS URI 支持 ──

# 语义化快捷方式 → 物理路径映射
SEMANTIC_MAP = {
    "_state": ["_control/STATE.md", "DASHBOARD.md", "CLAUDE.md"],
    "_memory": ["_control/MEMORY.md", "MEMORY.md"],
    "_entities": ["_entities/ENTITIES.md", "_control/ENTITIES.md", "ENTITIES.md"],
    "_timeline": ["_control/TIMELINE.md", "TIMELINE.md"],
    "_claude": ["CLAUDE.md"],
    "_health": None,  # 特殊处理: 运行 validate
    "_tree": None,  # 特殊处理: 目录树
}

# ── URI 生命周期管理 ──
# 状态机: proposed → active → deprecated → removed
URI_LIFECYCLE_TRANSITIONS = {
    "proposed": ["active", "deprecated", "removed"],
    "active": ["deprecated", "removed"],
    "deprecated": ["removed"],
    "removed": [],
}
H = Path.home()
URI_LIFECYCLE_FILE = H / ".ecos" / "bos" / "lifecycle.json"


def cmd_check_refs(args):
    """检查域间路径引用是否可解析"""
    registry = load_registry()
    print("\n  ═══ 域间引用检查 ═══\n")

    broken = 0
    for d in registry:
        claude = resolve_path(d) / "CLAUDE.md" if resolve_path(d).exists() else None
        if not claude or not claude.exists():
            continue

        content = claude.read_text()
        # Find potential path references (words containing /)
        import re

        refs = re.findall(r"`([^`]+/[^`]+)`", content)
        refs += re.findall(r"\]\(([^)]+)\)", content)

        for ref in refs:
            # Try resolving relative to domain path
            full = resolve_path(d) / ref
            if full.exists():
                continue
            # Try relative to DOCS
            full2 = DOCS / ref
            if full2.exists():
                continue
            # Only report if it looks like a domain path
            if any(
                p in ref
                for p in [
                    "@",
                    "驾驶舱",
                    "学习进化",
                    "个人",
                    "公共",
                    "工作文档",
                    "家庭生活",
                    "_control",
                    "_knowledge",
                ]
            ):
                broken += 1
                print(f"  ❌ {d.get('name', d['id'])}: `{ref[:60]}` → 不可解析")

    if broken == 0:
        print("  ✅ 所有引用可解析")
    else:
        print(f"\n  {broken} 个断链引用")
    print()


# P110-C: cmd_fix 拆解 (67L)
def cmd_fix(args):
    """自动修复常见问题"""
    if not args:
        print("用法: ecos domain fix <域> [--dry-run]")

        return
    registry = load_registry()
    d = find_domain(registry, args[0])
    if not d:
        print(f"❌ '{args[0]}' 未注册")
        return

    p = resolve_path(d)
    if not p.exists():
        print(f"❌ {p}")
        return

    dry = "--dry-run" in args
    dtype = d.get("domain_type", "document")
    tier = d.get("governance_tier", 1)
    results = validate_domain(p, dtype, tier)
    fixes = 0

    print(f"\n  🔧 修复: {d.get('name', d['id'])} {'(dry-run)' if dry else ''}\n")

    for name, ok, detail in results:
        if ok:
            continue

        if name == "KEMS/_archive/":
            if not dry:
                (p / "_archive").mkdir(exist_ok=True)
            print("  ✅ 创建 _archive/")
            fixes += 1

        elif name == "_control/TIMELINE.md" and tier == 1:
            if not dry:
                (p / "_control" / "TIMELINE.md").write_text(
                    f"# TIMELINE — {d.get('name', d['id'])}\n\n> 创建: {datetime.now().strftime('%Y-%m-%d')}\n\n| 日期 | 事件 |\n|------|------|\n"
                )
            print("  ✅ 创建 _control/TIMELINE.md 模板")
            fixes += 1

        elif name == "_entities/ENTITIES.md" and tier == 1:
            (p / "_entities").mkdir(exist_ok=True)
            if not dry:
                (p / "_entities" / "ENTITIES.md").write_text(
                    f"# ENTITIES — {d.get('name', d['id'])}\n\n> 创建: {datetime.now().strftime('%Y-%m-%d')}\n"
                )
            print("  ✅ 创建 _entities/ENTITIES.md 模板")
            fixes += 1

        elif "KEMS/" in name:
            plane = name.replace("KEMS/", "").replace("/", "")
            if not dry:
                (p / plane).mkdir(exist_ok=True)
            print(f"  ✅ 创建 {plane}/")
            fixes += 1

    if fixes == 0:
        print("  ✅ 无需修复")
    elif not dry:
        print(f"\n  ✅ {fixes} 项已修复 · ecos domain validate 重新校验")
    else:
        print(f"\n  📋 {fixes} 项待修复 · 去掉 --dry-run 执行")
