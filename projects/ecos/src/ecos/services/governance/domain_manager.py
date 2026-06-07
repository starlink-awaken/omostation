#!/usr/bin/env python3
"""Domain Manager v2 — L4域生命周期管理 | ecos domain <cmd>"""
import sys, os, json, yaml
from pathlib import Path
from datetime import datetime

# L0 audit integration
try:
    from l0_audit import validate_operation, get_audit_log
    L0_AUDIT = True
except ImportError:
    L0_AUDIT = False
    def validate_operation(*a,**kw): return {"passed":True,"violations":[]}
    def get_audit_log(*a,**kw): return []
from collections import defaultdict

H = Path.home()
DOCS = H / "Documents"
L0_CONSTRAINTS = Path(__file__).parent.parent / "l0" / "constraints.yaml"  # L0 SSOT
L0_CONSTRAINTS_L4 = DOCS / "@学习进化/_knowledge/10-systems/基建架构/L0-constraints.yaml"  # L4缓存
M1_NODES_DIR = DOCS / "@驾驶舱/_meta/nodes"
DOMAIN_INDEX = DOCS / "@驾驶舱/_control/DOMAIN-INDEX.md"

# ── 域类型定义 ──
TYPE_ICONS = {"document":"📄","config":"⚙️","engine":"🔧","tool":"🔨","workspace":"📂","storage":"💾","model":"🧠","view":"👁️"}
KEMS_PLANES = {"document":["_control","_entities","_knowledge","_storage","_archive"]}
REQUIRED_TIER1 = ["CLAUDE.md","_control/STATE.md","_control/MEMORY.md","_entities/ENTITIES.md","_control/TIMELINE.md"]
SKIP_AUDIT = {"Workspace",".claude","Obsidian","Documents","Desktop","Downloads","Library","Movies","Music","Pictures","Public","Applications"}

# ── 数据加载 (带 TTL 缓存) ──
_registry_cache = {"data": None, "ts": 0.0, "path": None}
REGISTRY_CACHE_TTL = 60  # seconds

def load_registry(force_reload: bool = False):
    """Load domain registry with TTL cache.
    
    Args:
        force_reload: If True, bypass cache and reload from disk.
    """
    global _registry_cache
    now = __import__("time").time()
    
    p = L0_CONSTRAINTS if L0_CONSTRAINTS.exists() else L0_CONSTRAINTS_L4
    if not p.exists(): return []
    
    path_str = str(p.resolve())
    if (not force_reload 
        and _registry_cache["data"] is not None 
        and (now - _registry_cache["ts"]) < REGISTRY_CACHE_TTL
        and _registry_cache["path"] == path_str):
        return _registry_cache["data"]
    
    with open(p) as f:
        data = yaml.safe_load(f).get("domain_registry", [])
    
    _registry_cache = {"data": data, "ts": now, "path": path_str}
    return data

def invalidate_registry_cache():
    """Force next load_registry() to reload from disk."""
    global _registry_cache
    _registry_cache["data"] = None

def find_domain(registry, name):
    for d in registry:
        if d["id"]==name or d.get("name")==name or d.get("name","").replace("@","")==name:
            return d
    return None

def resolve_path(domain):
    """解析域物理路径——处理子域 (parent_path) 和相对路径"""
    # Try explicit storage path
    for key in ["storage","storage_path"]:
        s = domain.get(key)
        if s:
            p = Path(s)
            if p.exists(): return p
            p2 = DOCS / s.lstrip("/")
            if p2.exists(): return p2
            # Return the explicit path even if not found (for diagnostics)
            return p
    
    # For document domains without storage, construct from @name
    name = domain.get("name","").replace("@","")
    parent = domain.get("parent_path","")
    if parent:
        p = DOCS / parent / name
        if p.exists(): return p
        return DOCS / f"@{name}"  # fallback
    return DOCS / f"@{name}"

def scan_filesystem():
    """扫描文件系统发现候选域，排除已知非域目录"""
    found = []
    for root in [DOCS, H/"SharedWork", H, Path("/Volumes/SharedDisk")]:
        if not root.exists(): continue
        try:
            for item in root.iterdir():
                if item.name in SKIP_AUDIT: continue
                if item.is_symlink() or item.is_dir():
                    if item.name.startswith("."): continue
                    if (item/"CLAUDE.md").exists() or any((item/p).exists() for p in ["_control","_knowledge"]):
                        found.append(item)
        except PermissionError: continue
    return found

# ── 校验 ──
def _count_files(dir_path: Path, suffix: str = ".md") -> int:
    """Count files recursively in a directory (skip hidden)."""
    if not dir_path.is_dir(): return 0
    return sum(1 for f in dir_path.rglob(f"*{suffix}") if not f.name.startswith(".") and ".git" not in f.parts)

def _check_frontmatter(file_path: Path) -> bool:
    """Check if a file has YAML frontmatter."""
    if not file_path.exists(): return False
    content = file_path.read_text(encoding="utf-8", errors="ignore")
    return content.startswith("---") and "---" in content[3:20]

def validate_domain(path, dtype="document", tier=1):
    results = []
    path = Path(path)
    
    # CLAUDE.md
    c = path/"CLAUDE.md"
    results.append(("CLAUDE.md", c.exists(), "入口文件" if c.exists() else "缺失"))
    
    # KEMS planes existence
    for p in KEMS_PLANES.get(dtype,[]):
        pp = path/p
        exists = pp.is_dir()
        results.append((f"KEMS/{p}/", exists, "存在" if exists else "缺失"))
    
    # KEMS content quality (document domains only)
    if dtype == "document":
        for p in KEMS_PLANES.get(dtype,[]):
            pp = path/p
            if pp.is_dir():
                md_count = _count_files(pp)
                # Check frontmatter in STATE.md / MEMORY.md / ENTITIES.md
                for key_file in ["STATE.md", "MEMORY.md", "ENTITIES.md", "INDEX.md", "TIMELINE.md"]:
                    kf = pp / key_file
                    if kf.exists():
                        has_fm = _check_frontmatter(kf)
                        if not has_fm:
                            results.append((f"quality/{p}/{key_file}", False, "缺 frontmatter"))
                results.append((f"size/{p}/", md_count > 0, f"{md_count} 文件" if md_count else "空"))
    
    # Tier 1
    if tier==1:
        for r in REQUIRED_TIER1:
            pp = path/r
            results.append((r, pp.exists(), "存在" if pp.exists() else "缺失"))
    
    # BOS connectivity (check if domain has BOSRoute M1 node)
    m1_bos = Path(__file__).resolve().parent.parent / "ssot" / "mof" / "m1" / "bosroute"
    if m1_bos.exists():
        has_bos = any(f.name.startswith("BOSROUTE-") for f in m1_bos.iterdir() if f.is_file())
        results.append(("BOSRoute M1", has_bos, f"{len(list(m1_bos.glob('*.yaml')))} 路由" if has_bos else "缺失"))

    return results

# ── 命令 ──

def cmd_list(args):
    registry = load_registry()
    by_type = defaultdict(list)
    for d in registry: by_type[d.get("domain_type","document")].append(d)
    
    if "--json" in args:
        print(json.dumps([{k:d.get(k) for k in ["id","name","domain_type","layer","status"]} for d in registry], indent=2, ensure_ascii=False))
        return
    
    print(f"\n{'ID':<20} {'类型':<12} {'名称':<18} {'状态':<8} {'路径'}")
    print("-"*80)
    for dtype in ["document","config","engine","tool","workspace","storage","model","view"]:
        for d in by_type.get(dtype,[]):
            icon = TYPE_ICONS.get(dtype,"")
            p = resolve_path(d)
            path_ok = "✅" if (p and p.exists()) else "❌"
            print(f"{icon} {d['id']:<17} {dtype:<12} {d.get('name','?'):<18} {d.get('status','active'):<8} {path_ok} {p}")
    print(f"\n  {len(registry)} 域 · {len(by_type)} 类型\n")

def cmd_status(args):
    registry = load_registry()
    if not args: print("用法: ecos domain status <域>"); return
    d = find_domain(registry, args[0])
    if not d: print(f"❌ '{args[0]}' 未注册"); return
    
    p = resolve_path(d)
    print(f"\n  {TYPE_ICONS.get(d.get('domain_type',''),'')} {d.get('name',d['id'])}")
    print(f"  ID: {d['id']}  |  类型: {d.get('domain_type','?')}  |  层: {d.get('layer','?')}  |  Tier: {d.get('governance_tier','-')}")
    print(f"  路径: {p} {'✅' if p.exists() else '❌'}")
    if d.get("description"): print(f"  说明: {d['description'][:100]}")
    print()

def cmd_validate(args):
    registry = load_registry()
    if not args: print("用法: ecos domain validate <域>"); return
    d = find_domain(registry, args[0])
    if not d: print(f"❌ '{args[0]}' 未注册"); return
    
    p = resolve_path(d)
    if not p.exists(): print(f"❌ 路径不存在: {p}"); return
    
    dtype = d.get("domain_type","document")
    tier = d.get("governance_tier",1)
    print(f"\n  校验: {d.get('name',d['id'])} ({dtype}, Tier {tier})  →  {p}")
    print("  "+"-"*55)
    
    results = validate_domain(p, dtype, tier)
    passed = sum(1 for _,ok,_ in results if ok)
    failed = len(results)-passed
    for name,ok,detail in results:
        print(f"  {'✅' if ok else '❌'} {name:<25} {detail}")
    print(f"\n  {passed}✅  {failed}❌\n")

def cmd_tree(args):
    """目录树——标注KEMS面"""
    registry = load_registry()
    if not args: print("用法: ecos domain tree <域>"); return
    d = find_domain(registry, args[0])
    if not d: print(f"❌ '{args[0]}' 未注册"); return
    
    p = resolve_path(d)
    if not p.exists(): print(f"❌ {p}"); return
    
    planes = {pl for pl in KEMS_PLANES.get(d.get("domain_type",""),[])}
    print(f"\n  {d.get('name',d['id'])}/")
    
    def tree(dir_path, prefix="", depth=0):
        if depth>3: return
        items = sorted([i for i in dir_path.iterdir() if not i.name.startswith(".") and not i.name.startswith("__")],
                      key=lambda x: (not x.is_dir(), x.name))
        for i,item in enumerate(items):
            is_last = (i==len(items)-1)
            branch = "└── " if is_last else "├── "
            marker = ""
            if item.is_dir():
                if item.name in planes: marker = " ← KEMS"
                elif item.name.startswith("_"): marker = " ← sys"
                branch += f"📁 {item.name}{marker}"
            else:
                branch += f"📄 {item.name}"
            print(f"  {prefix}{branch}")
            if item.is_dir() and depth<2:
                tree(item, prefix+("    " if is_last else "│   "), depth+1)
    
    tree(p)
    print()

def cmd_audit(args):
    registry = load_registry()
    reg_paths = set()
    for d in registry:
        p = resolve_path(d)
        if p: reg_paths.add(str(p.resolve()))
    
    # Phase 1: registered check
    print("\n  === 已注册域 ===\n")
    ok=0;miss=0
    for d in registry:
        p = resolve_path(d)
        exists = p.exists() if p else False
        print(f"  {'✅' if exists else '❌'} {d.get('name',d['id']):<20} {p}")
        if exists: ok+=1
        else: miss+=1
    print(f"\n  存在:{ok}  缺失:{miss}")
    
    # Phase 2: unregistered scan
    print("\n  === 未注册候选 ===\n")
    found = scan_filesystem()
    unreg = [d for d in found if str(d.resolve()) not in reg_paths]
    if unreg:
        for d in unreg:
            has_claude = (d/"CLAUDE.md").exists()
            print(f"  📁 {d} {'(有CLAUDE.md)' if has_claude else '(有KEMS面)'}")
        print(f"\n  候选: {len(unreg)}")
    else:
        print("  ✅ 无未注册候选")
    print()

def cmd_relations(args):
    """域间关系图"""
    registry = load_registry()
    print("\n  域间关系:")
    relations = {
        "governs":       ("@驾驶舱", "所有Document域"),
        "provides_to":   ("@公共",    "@学习进化 @个人 @家庭生活 @工作文档"),
        "consumes":      ("@学习进化", "minerva knowledge"),
        "configures":    (".ai .agents", "L3入口·Agent运行时"),
        "executes_on":   ("bin ToolBox", "L1运行时·launchd"),
        "archives_for":  ("SharedDisk", "@家庭生活 @个人 @学习进化"),
        "complements":   ("@个人",    "@家庭生活 (我 vs 我们)"),
        "syncs_via":     ("@家庭生活", "SharedConf → iCloud"),
    }
    for rel,(src,dst) in relations.items():
        print(f"  {src:<20} ──{rel}──→  {dst}")
    print()

def cmd_stats(args):
    """全域统计"""
    registry = load_registry()
    by_type = defaultdict(list)
    by_layer = defaultdict(list)
    for d in registry:
        by_type[d.get("domain_type","document")].append(d)
        by_layer[d.get("layer","L4")].append(d)
    
    print(f"\n  ═══ 全域统计 ═══\n")
    print(f"  总域数:   {len(registry)}")
    print(f"  类型数:   {len(by_type)}")
    print(f"\n  按类型:")
    for t in ["document","config","engine","tool","workspace","storage","model","view"]:
        if t in by_type:
            print(f"    {TYPE_ICONS.get(t,'')} {t:<12} {len(by_type[t])}")
    print(f"\n  按层:")
    for l in sorted(by_layer.keys()):
        print(f"    {l:<12} {len(by_layer[l])}")
    
    # Path health
    ok = sum(1 for d in registry if resolve_path(d).exists())
    print(f"\n  路径健康: {ok}/{len(registry)} ({100*ok//len(registry)}%)")
    
    # KEMS health — check document domains
    docs = [d for d in registry if d.get("domain_type","document")=="document"]
    kems_ok = sum(1 for d in docs if resolve_path(d).exists() and all((resolve_path(d)/p).is_dir() for p in KEMS_PLANES.get("document",[])))
    print(f"  KEMS完整:  {kems_ok}/{len(docs)} (document域)")
    if docs and kems_ok<len(docs):
        for d in docs:
            p = resolve_path(d)
            if p.exists():
                missing = [pl for pl in KEMS_PLANES.get("document",[]) if not (p/pl).is_dir()]
                if missing: print(f"    ⚠️  {d.get('name','?')}: 缺 {' '.join(missing)}")
    print()

def cmd_create(args):
    """交互式创建新域"""
    print("\n  ═══ 创建新域 ═══\n")
    
    # 1. Name
    name = input("  域名称 (如: @我的域): ").strip()
    if not name: print("❌ 取消"); return
    if not name.startswith("@"): name = "@"+name
    
    # 2. Type
    print(f"\n  域类型:")
    for i,t in enumerate(["document","config","engine","tool","workspace"],1):
        print(f"    {i}. {TYPE_ICONS.get(t,'')} {t}")
    ti = input("  选择 [1]: ").strip() or "1"
    dtype = ["document","config","engine","tool","workspace"][int(ti)-1] if ti.isdigit() and 1<=int(ti)<=5 else "document"
    
    # 3. Path
    default_path = DOCS / name
    path_str = input(f"  路径 [{default_path}]: ").strip()
    path = Path(path_str) if path_str else default_path
    
    # 4. ID
    domain_id = input(f"  ID [{name.replace('@','').replace(' ','-').lower()}]: ").strip()
    if not domain_id: domain_id = name.replace("@","").replace(" ","-").lower()
    
    # 5. Tier
    tier_str = input("  Tier [1-完整/3-最小] [1]: ").strip() or "1"
    
    # L0 audit: pre-check
    audit = validate_operation(domain_id, "domain_create")
    if not audit["passed"]:
        print(f"  ⚠️  L0审计: {len(audit['violations'])}项违规")
        for v in audit["violations"]:
            print(f"     - {v['constraint']}: {v.get('note','')}")
        if input("  继续? [y/N]: ").strip().lower() != 'y':
            print("❌ 取消"); return
    tier = int(tier_str) if tier_str in ("1","3") else 1
    
    print(f"\n  确认创建:")
    print(f"    名称: {name}  |  ID: {domain_id}  |  类型: {dtype}  |  Tier: {tier}")
    print(f"    路径: {path}")
    ok = input("\n  创建? [Y/n]: ").strip().lower()
    if ok and ok != "y": print("❌ 取消"); return
    
    # Create
    path.mkdir(parents=True, exist_ok=True)
    
    if dtype == "document":
        # Create KEMS structure
        for plane in KEMS_PLANES.get("document",[]):
            (path/plane).mkdir(exist_ok=True)
        (path/"_archive").mkdir(exist_ok=True)
        
        # Create CLAUDE.md
        claude_content = f"""# {name} — 域入口

> L4 | KEMS 六面 | v1.0 | {datetime.now().strftime('%Y-%m-%d')}

## 控制面
- STATE: `_control/STATE.md`
- MEMORY: `_control/MEMORY.md`

## 知识面
- `_knowledge/` — 编号分类

## 维护
创建: {datetime.now().strftime('%Y-%m-%d')}
"""
        (path/"CLAUDE.md").write_text(claude_content)
        
        if tier == 1:
            (path/"_control"/"STATE.md").write_text(f"# STATE — {name}\n\n> 创建: {datetime.now().strftime('%Y-%m-%d')}\n\n## 当前阶段\n\n初始化\n")
            (path/"_control"/"MEMORY.md").write_text(f"# MEMORY — {name}\n\n> 创建: {datetime.now().strftime('%Y-%m-%d')}\n")
            (path/"_entities").mkdir(exist_ok=True)
            (path/"_entities"/"ENTITIES.md").write_text(f"# ENTITIES — {name}\n\n> 创建: {datetime.now().strftime('%Y-%m-%d')}\n")
            (path/"_control"/"TIMELINE.md").write_text(f"# TIMELINE — {name}\n\n> 创建: {datetime.now().strftime('%Y-%m-%d')}\n")
    
    print(f"\n  ✅ 域已创建: {path}")
    print(f"  下一步: ecos domain register {domain_id}  # 注册到L0\n")

def cmd_all_validate(args):
    """校验所有document域"""
    registry = load_registry()
    docs = [d for d in registry if d.get("domain_type","document")=="document"]
    print(f"\n  校验 {len(docs)} 个 document 域:\n")
    
    total_pass = 0; total_fail = 0
    for d in docs:
        p = resolve_path(d)
        if not p.exists():
            print(f"  ❌ {d.get('name',d['id']):<16} 路径不存在")
            total_fail += 1
            continue
        results = validate_domain(p, "document", d.get("governance_tier",1))
        passed = sum(1 for _,ok,_ in results if ok)
        failed = len(results)-passed
        total_pass += passed; total_fail += failed
        icon = "✅" if failed==0 else "⚠️"
        print(f"  {icon} {d.get('name',d['id']):<16} {passed}/{len(results)} passed" + (f"  (缺: {', '.join(n for n,ok,_ in results if not ok)[:50]})" if failed else ""))
    
    print(f"\n  {total_pass}✅  {total_fail}❌\n")

def cmd_register(args):
    """注册新域到L0"""
    if len(args)<1:
        print("用法: ecos domain register <路径> [--type document] [--name 名称] [--id domain-id]")
        return
    
    path = Path(args[0])
    if not path.exists():
        print(f"❌ 路径不存在: {path}"); return
    
    # Parse flags
    dtype = "document"
    name = path.name
    domain_id = name.replace("@","").replace(" ","-").lower()
    for i,a in enumerate(args[1:],1):
        if a=="--type" and i+1<len(args): dtype = args[i+1]
        if a=="--name" and i+1<len(args): name = args[i+1]
        if a=="--id" and i+1<len(args): domain_id = args[i+1]
    
    # Tier auto-detect
    tier = 1 if (path/"_control"/"STATE.md").exists() else 3
    
    # Build entry
    entry = {
        "id": domain_id,
        "name": name,
        "layer": "L4",
        "governance_tier": tier,
        "domain_type": dtype,
        "claude_md": str(path/"CLAUDE.md") if (path/"CLAUDE.md").exists() else None,
        "state_md": str(path/"_control"/"STATE.md") if (path/"_control"/"STATE.md").exists() else None,
        "status": "active",
        "storage": str(path),
        "description": f"注册于 {datetime.now().strftime('%Y-%m-%d')}",
    }
    
    # Read existing registry
    with open(L0_CONSTRAINTS) as f:
        content = f.read()
    
    # Find domain_registry section and append
    marker = "# ── 域注册表 (L4 Domain Registry) ──"
    if marker not in content:
        print("❌ 无法找到 domain_registry 标记"); return
    
    # Check for duplicate
    if f"id: {domain_id}" in content:
        print(f"⚠️  ID '{domain_id}' 已存在"); return
    
    # Simple append after the last registry entry
    yaml_entry = f"""
  - id: {domain_id}
    name: "{name}"
    layer: L4
    governance_tier: {tier}
    domain_type: {dtype}
    claude_md: {f'"{entry["claude_md"]}"' if entry["claude_md"] else "null"}
    state_md: {f'"{entry["state_md"]}"' if entry["state_md"] else "null"}
    status: active
    storage: "{path}"
    description: "{entry['description']}"
"""
    # Insert before # ── 协议注册表
    content = content.replace("# ── 协议注册表", yaml_entry + "\n# ── 协议注册表")
    
    with open(L0_CONSTRAINTS,'w') as f: f.write(content)
    print(f"✅ 已注册: {name} ({domain_id}) → L0-constraints.yaml\n")

def cmd_fix(args):
    """自动修复常见问题"""
    if not args: print("用法: ecos domain fix <域> [--dry-run]"); return
    registry = load_registry()
    d = find_domain(registry, args[0])
    if not d: print(f"❌ '{args[0]}' 未注册"); return
    
    p = resolve_path(d)
    if not p.exists(): print(f"❌ {p}"); return
    
    dry = "--dry-run" in args
    dtype = d.get("domain_type","document")
    tier = d.get("governance_tier",1)
    results = validate_domain(p, dtype, tier)
    fixes = 0
    
    print(f"\n  🔧 修复: {d.get('name',d['id'])} {'(dry-run)' if dry else ''}\n")
    
    for name, ok, detail in results:
        if ok: continue
        
        if name == "KEMS/_archive/":
            if not dry: (p/"_archive").mkdir(exist_ok=True)
            print(f"  ✅ 创建 _archive/")
            fixes += 1
        
        elif name == "_control/TIMELINE.md" and tier==1:
            if not dry: (p/"_control"/"TIMELINE.md").write_text(
                f"# TIMELINE — {d.get('name',d['id'])}\n\n> 创建: {datetime.now().strftime('%Y-%m-%d')}\n\n| 日期 | 事件 |\n|------|------|\n")
            print(f"  ✅ 创建 _control/TIMELINE.md 模板")
            fixes += 1
        
        elif name == "_entities/ENTITIES.md" and tier==1:
            (p/"_entities").mkdir(exist_ok=True)
            if not dry: (p/"_entities"/"ENTITIES.md").write_text(
                f"# ENTITIES — {d.get('name',d['id'])}\n\n> 创建: {datetime.now().strftime('%Y-%m-%d')}\n")
            print(f"  ✅ 创建 _entities/ENTITIES.md 模板")
            fixes += 1
        
        elif "KEMS/" in name:
            plane = name.replace("KEMS/","").replace("/","")
            if not dry: (p/plane).mkdir(exist_ok=True)
            print(f"  ✅ 创建 {plane}/")
            fixes += 1
    
    if fixes==0: print("  ✅ 无需修复")
    elif not dry: print(f"\n  ✅ {fixes} 项已修复 · ecos domain validate 重新校验")
    else: print(f"\n  📋 {fixes} 项待修复 · 去掉 --dry-run 执行")

def cmd_sync(args):
    registry = load_registry()
    by_type = defaultdict(list)
    for d in registry: by_type[d.get("domain_type","document")].append(d)
    
    lines = [
        f"# DOMAIN-INDEX — 全域注册表\n",
        f"> @驾驶舱/_control/ | auto-generated {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n",
        f"## {len(registry)} 域 · {len(by_type)} 类型\n\n",
    ]
    for dtype in ["document","config","engine","tool","workspace","storage","model","view"]:
        items = by_type.get(dtype,[])
        if not items: continue
        lines.append(f"### {TYPE_ICONS.get(dtype,'')} {dtype} ({len(items)})\n\n")
        lines.append("| ID | 名称 | 层 | Tier | 路径 |\n|---|---|---|---|---|\n")
        for d in items:
            p = resolve_path(d)
            lines.append(f"| {d['id']} | {d.get('name','-')} | {d.get('layer','-')} | {d.get('governance_tier','-')} | {p} |\n")
        lines.append("\n")
    
    lines.append(f"---\n*auto: {datetime.now().isoformat()}*\n")
    with open(DOMAIN_INDEX,'w') as f: f.writelines(lines)
    print(f"✅ DOMAIN-INDEX.md ({len(registry)}域)\n")

# ── BOS URI 支持 ──

# 语义化快捷方式 → 物理路径映射
SEMANTIC_MAP = {
    "_state":    ["_control/STATE.md", "DASHBOARD.md", "CLAUDE.md"],
    "_memory":   ["_control/MEMORY.md", "MEMORY.md"],
    "_entities": ["_entities/ENTITIES.md", "_control/ENTITIES.md", "ENTITIES.md"],
    "_timeline": ["_control/TIMELINE.md", "TIMELINE.md"],
    "_claude":   ["CLAUDE.md"],
    "_health":   None,  # 特殊处理: 运行 validate
    "_tree":     None,  # 特殊处理: 目录树
}

def resolve_semantic(domain: dict, shortcut: str) -> str:
    """将 _state/_memory 等语义快捷方式解析为实际文件路径"""
    if shortcut not in SEMANTIC_MAP: return None
    candidates = SEMANTIC_MAP[shortcut]
    if candidates is None: return shortcut  # 特殊处理
    base = resolve_path(domain)
    for c in candidates:
        full = base / c
        if full.exists(): return c
    return candidates[0]  # fallback

def parse_bos_uri(uri: str, registry: list):
    """bos://{domain}[/{path}] → (domain, subpath)  v2格式"""
    if not uri.startswith("bos://"): return None, None
    
    # Strip prefix
    rest = uri.replace("bos://","")
    
    # Handle v1 format (bos://l4/vault/...) → strip layer prefix
    parts = rest.split("/",2)
    if parts[0] in ("l4","l3","l2","l1","l0","storage","model"):
        # v1 format: skip layer
        domain_id = parts[1] if len(parts)>1 else ""
        subpath = parts[2] if len(parts)>2 else ""
    else:
        # v2 format: bos://vault/_control/...
        domain_id = parts[0]
        subpath = "/".join(parts[1:]) if len(parts)>1 else ""
    
    # Unified domain lookup helper
    def match_domain(d, q):
        if d["id"]==q: return True
        name = d.get("name","").replace("@","")
        if name==q or name.replace(" ","")==q: return True
        if name.startswith(q): return True
        if q in d["id"]: return True
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
        subpath_no_ext = subpath[:-3]
    else:
        subpath_no_ext = subpath
    
    # Find domain (unified lookup)
    for d in registry:
        if match_domain(d, domain_id):
            # Try exact subpath first
            p = resolve_path(d)
            if not subpath: return d, ""
            full = p / subpath
            if full.exists(): return d, subpath
            full2 = p / (subpath+".md")
            if full2.exists(): return d, subpath+".md"
            return d, subpath
    
    return None, None

def cmd_resolve(args):
    """BOS URI → 物理路径解析"""
    if not args: print("用法: ecos domain resolve <bos://l4/vault/...>"); return
    registry = load_registry()
    uri = args[0]
    d, sub = parse_bos_uri(uri, registry)
    if not d:
        print(f"❌ 无法解析: {uri}")
        return
    base = resolve_path(d)
    full = base / sub if sub else base
    exists = full.exists()
    print(f"\n  {uri}")
    print(f"  → {full} {'✅' if exists else '❌'}")
    print(f"  域: {d.get('name',d['id'])} | 类型: {d.get('domain_type','?')} | 大小: {full.stat().st_size if exists else 0} bytes\n")

def cmd_bos_validate(args):
    """全量BOS URI健康检查"""
    registry = load_registry()
    print("\n  ═══ BOS URI 全量健康检查 ═══\n")
    
    total = 0; ok = 0; fail = 0
    for d in registry:
        did = d["id"]
        dtype = d.get("domain_type","document")
        
        # Check basic domain URI
        uri = f"bos://{did}"
        dd, ss = parse_bos_uri(uri, registry)
        if not dd: continue
        
        p = resolve_path(dd)
        total += 1
        if p.exists():
            ok += 1
        else:
            fail += 1
            print(f"  ❌ {uri} → {p} (域路径不存在)")
        
        # Semantic shortcuts: only for document domains
        if dtype == "document":
            for shortcut in ["_state","_claude"]:
                suri = f"bos://{did}/{shortcut}"
                sd, ssub = parse_bos_uri(suri, registry)
                if sd:
                    full = resolve_path(sd) / ssub if ssub else resolve_path(sd)
                    total += 1
                    if full.exists():
                        ok += 1
                    else:
                        fail += 1
                        print(f"  ❌ {suri} → {full}")
    
    print(f"\n  {ok}✅  {fail}❌  (共{total} BOS URI)" + ("\n  ✅ 全部健康" if fail==0 else "") + "\n")

def cmd_routes(args):
    """生成 BOS routes.json 缓存"""
    registry = load_registry()
    routes = {}
    for d in registry:
        did = d["id"]
        p = resolve_path(d)
        entry = {
            "path": str(p),
            "type": d.get("domain_type","document"),
            "layer": d.get("layer","L4"),
            "exists": p.exists(),
        }
        # Add semantic shortcuts
        if d.get("domain_type","document") == "document":
            entry["semantic"] = {}
            for shortcut in ["_state","_memory","_entities","_timeline","_claude"]:
                resolved = resolve_semantic(d, shortcut)
                if resolved:
                    entry["semantic"][shortcut] = resolved
        routes[did] = entry
    
    # Also add name aliases
    for d in registry:
        name = d.get("name","").replace("@","")
        if name and name != d["id"]:
            routes[name] = routes[d["id"]]
    
    routes_file = Path.home() / ".ecos" / "bos" / "routes.json"
    routes_file.parent.mkdir(parents=True, exist_ok=True)
    with open(routes_file, 'w') as f:
        json.dump(routes, f, indent=2, ensure_ascii=False)
    print(f"✅ routes.json ({len(routes)} entries) → {routes_file}\n")

def cmd_search(args):
    """跨域搜索"""
    if not args: print("用法: ecos domain search <关键词> [--domains d1,d2] [--max 20]"); return
    query = args[0]
    domains = None
    max_results = 20
    
    for i,a in enumerate(args[1:],1):
        if a == "--domains" and i < len(args)-1: domains = args[i+1].split(",")
        if a == "--max" and i < len(args)-1: max_results = int(args[i+1])
    
    registry = load_registry()
    results = []
    import subprocess
    
    target_domains = set(domains) if domains else None
    
    print(f"\n  🔍 搜索: \"{query}\"\n")
    
    for d in registry:
        did = d["id"]
        if target_domains and did not in target_domains: continue
        p = resolve_path(d)
        if not p.exists(): continue
        
        search_dirs = []
        for sd in ["CLAUDE.md", "_control/STATE.md", "_control/MEMORY.md", "_knowledge"]:
            sp = p / sd
            if sp.exists(): search_dirs.append(str(sp))
        
        for sp in search_dirs:
            try:
                cmd = ["grep", "-rn", "--include=*.md", "--include=*.yaml", "-l", query, sp]
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                for line in r.stdout.strip().split("\n"):
                    if line and len(results) < max_results:
                        rel = Path(line).relative_to(p) if p in Path(line).parents else line
                        results.append((did, str(rel)))
            except: pass
    
    if results:
        for did, fpath in results:
            print(f"  📄 bos://{did}/{fpath}")
        print(f"\n  {len(results)} results\n")
    else:
        print("  ❌ 无结果\n")

def cmd_read(args):
    """通过BOS URI读取域资源"""
    if not args: print("用法: ecos domain read <bos://l4/vault/...>"); return
    registry = load_registry()
    uri = args[0]
    d, sub = parse_bos_uri(uri, registry)
    if not d:
        print(f"❌ 无法解析: {uri}"); return
    base = resolve_path(d)
    full = base / sub if sub else base
    if not full.exists():
        print(f"❌ 不存在: {full}"); return
    if full.is_dir():
        items = os.listdir(full)
        print(f"\n  📁 {uri}/ ({len(items)} items)")
        for i in sorted(items)[:20]:
            ip = full/i
            print(f"    {'📁' if ip.is_dir() else '📄'} {i}")
        if len(items)>20: print(f"    ... +{len(items)-20}")
    else:
        content = full.read_text()
        max_lines = int(args[1]) if len(args)>1 else 50
        lines = content.split("\n")[:max_lines]
        print(f"\n  📄 {uri} ({len(content)} bytes)\n")
        for l in lines: print(f"  {l}")
        if len(content.split("\n"))>max_lines: print(f"\n  ... (共{len(content.split('\n'))}行)")
    print()

def cmd_info(args):
    """域综合报告 (status+validate+tree)"""
    if not args: print("用法: ecos domain info <域>"); return
    cmd_status(args)
    cmd_validate(args)
    cmd_tree(args)

def cmd_workflow(args):
    """BOS工作流编排执行"""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from workflow import list_workflows, execute_workflow
    
    if not args or args[0] == "list":
        wfs = list_workflows()
        if wfs:
            print("\n  可用工作流:\n")
            for w in wfs:
                wf = __import__('workflow', fromlist=['load_workflow']).load_workflow(w)
                if wf:
                    print(f"  📋 {w:<25} {wf.get('description','')}")
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
        print(f"  {icon} {e['timestamp'][:19]} | {e['operation']:<20} | {e.get('domain','?'):<15} | {e.get('uri','')}")
    print()

def cmd_check_refs(args):
    """检查域间路径引用是否可解析"""
    registry = load_registry()
    print("\n  ═══ 域间引用检查 ═══\n")
    
    broken = 0
    for d in registry:
        claude = resolve_path(d) / "CLAUDE.md" if resolve_path(d).exists() else None
        if not claude or not claude.exists(): continue
        
        content = claude.read_text()
        # Find potential path references (words containing /)
        import re
        refs = re.findall(r'`([^`]+/[^`]+)`', content)
        refs += re.findall(r'\]\(([^)]+)\)', content)
        
        for ref in refs:
            # Try resolving relative to domain path
            full = resolve_path(d) / ref
            if full.exists(): continue
            # Try relative to DOCS
            full2 = DOCS / ref
            if full2.exists(): continue
            # Only report if it looks like a domain path
            if any(p in ref for p in ["@","驾驶舱","学习进化","个人","公共","工作文档","家庭生活","_control","_knowledge"]):
                broken += 1
                print(f"  ❌ {d.get('name',d['id'])}: `{ref[:60]}` → 不可解析")
    
    if broken==0: print("  ✅ 所有引用可解析")
    else: print(f"\n  {broken} 个断链引用")
    print()

def cmd_capabilities(args):
    """查询域提供的能力清单"""
    import yaml
    M1_DOMAIN = Path(__file__).resolve().parent.parent / "ssot" / "mof" / "m1" / "domain"
    if not M1_DOMAIN.exists():
        print("⚠️  M1 Domain 节点目录不存在")
        return
    if args:
        target = args[0]
        targets = [target] if not target.startswith("bos://") else [target.replace("bos://","").split("/")[0]]
    else:
        targets = None
    
    found = 0
    for f in sorted(M1_DOMAIN.glob("*.yaml")):
        with open(f) as fh:
            node = yaml.safe_load(fh)
        if not node: continue
        props = node.get("properties",{})
        did = node.get("id","").replace("DOMAIN-","")
        if targets and did not in targets: continue
        found += 1
        caps = props.get("capabilities",[])
        entry = props.get("entry_points",{})
        bos = props.get("bos_uri_pattern","?")
        dtype = props.get("domain_type","?")
        print(f"\n  {did}")
        print(f"    类型: {dtype}  BOS: {bos}")
        if caps:
            print(f"    能力:")
            for c in caps: print(f"      - {c}")
        if entry:
            print(f"    入口:")
            for k,v in entry.items(): print(f"      {k}: {v}")
    if not found:
        print(f"❌ 未找到域: {args[0] if args else 'any'}")

# ── 主入口 ──
def main():
    cmds = {"list":cmd_list,"status":cmd_status,"validate":cmd_validate,"validate-all":cmd_all_validate,"tree":cmd_tree,"audit":cmd_audit,"relations":cmd_relations,"sync":cmd_sync,"stats":cmd_stats,"create":cmd_create,"register":cmd_register,"fix":cmd_fix,"info":cmd_info,"check-refs":cmd_check_refs,"resolve":cmd_resolve,"read":cmd_read,"bos-validate":cmd_bos_validate,"routes":cmd_routes,"search":cmd_search,"audit-log":cmd_audit_log,"workflow":cmd_workflow,"capabilities":cmd_capabilities}
    if len(sys.argv)<2:
        print("\necos domain <cmd> [args]\n")
        for c,f in cmds.items(): print(f"  {c:<12} {f.__doc__ or ''}")
        print()
        return
    cmd = sys.argv[1]; args = sys.argv[2:]
    if cmd in cmds: cmds[cmd](args)
    else: print(f"❌ {cmd}\n可用: {' '.join(cmds)}")

if __name__=="__main__": main()
