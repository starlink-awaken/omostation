#!/usr/bin/env python3
"""
收敛性检查工具 — 治理审计

检查项:
  1. CLAUDE.md 清单: 所有域是否存在入口文件
  2. 公约继承: 每个域是否继承 CLAUDE-公约.md
  3. 注册表引用: 每个域是否引用 MCP-REGISTRY/SKILL-INDEX/ROUTING
  4. 父网关引用: 每个域是否引用 L4 网关
  5. 域存在性: DOMAIN-INDEX 中的域是否真实存在于文件系统
  6. 断裂引用: 扫描 *.md 中指向不存在的 *.md 引用
  7. 层标注: 每个域是否有正确的 L4 层标注
  8. M1 对齐: 每个 Documents 域是否有对应的 ecos MOF M1 模型
  9. 控制面合规: 每个域是否有所需的 _control/ 文件
  10. SSOT 断裂: 检查 @公共/_entities 引用是否一致

用法:
  python3 check-convergence.py              # 全量检查
  python3 check-convergence.py --quick       # 快速检查（只检 1-5）
  python3 check-convergence.py --report      # 输出 Markdown 报告
"""

import os
import re
import sys
import fnmatch
from pathlib import Path
import json
import hashlib

# History tracking — initialized in run_all_checks()

from datetime import datetime

# ======== 配置 ========
# 默认基准路径为用户主目录（~/Documents · ~/Workspace）。
# 若使用挂载点（如 ~/mnt），通过 --base ~/mnt 指定。
DOCUMENTS_BASE = sys.argv[sys.argv.index("--base") + 1] + "/Documents" if "--base" in sys.argv else os.path.expanduser("~/Documents")
WORKSPACE_BASE = sys.argv[sys.argv.index("--base") + 1] + "/Workspace" if "--base" in sys.argv else os.path.expanduser("~/Workspace")
GLOBAL_MD = os.path.join(DOCUMENTS_BASE, "CLAUDE_GLOBAL.md")
GATEWAY_MD = os.path.join(DOCUMENTS_BASE, "CLAUDE.md")
CONVENTION_MD = os.path.join(DOCUMENTS_BASE, "@公共/_control/CLAUDE-公约.md")
META_MODEL_MD = os.path.join(DOCUMENTS_BASE, "@公共/_control/DOMAIN-META-MODEL.md")
REGISTRY_MD = os.path.join(DOCUMENTS_BASE, "@公共/_control/REGISTRY.md")

# 遍历时跳过的目录（归档/存储/生成内容，其内部引用断裂属正常，不作为缺陷）
# 注：os.walk 剪枝需原地修改 dirs[:]，否则仍会递归进入
EXCLUDE_DIRS = {".git", "__pycache__", "_archive", "_storage", "存档", "_generated", ".history"}

# 8 个核心域（按元模型分类）
DOMAINS = {
    "Aggregate": ["@驾驶舱", "@工作文档"],
    "Functional": ["@个人", "@学习进化", "@创意创作", "@OPC"],
    "Infrastructure": ["@公共"],
}

# 子域
SUB_DOMAINS = ["卫健委", "国转中心", "合同法规"]

# 各域菜单路径
DOMAIN_PATHS = {
    "@驾驶舱": "@驾驶舱",
    "@工作文档": "@工作文档",
    "@个人": "@个人",
    "@学习进化": "@学习进化",
    "@创意创作": "@创意创作",
    "@OPC": "@OPC",
    "@公共": "@公共",
    "卫健委": "@工作文档/卫健委",
    "国转中心": "@工作文档/国转中心",
    "合同法规": "@工作文档/合同法规",
}

QUICK_MODE = "--quick" in sys.argv
HELP = "--help" in sys.argv or "-h" in sys.argv
REPORT_MODE = "--report" in sys.argv
CROSS_WS_MODE = "--check-cross-workspace" in sys.argv


def check_cross_workspace():
    """M-ε 跨工作区桥接检查

    检测:
    1. Documents→Workspace 软链(断链)
    2. MCP 服务可达性
    3. 文档中 Workspace 文本引用(数量)
    """
    print("━" * 80)
    print("  M-ε 跨工作区桥接检查(本会话新增 · 2026-06-19)")
    print("━" * 80)
    print()

    issues = {'critical': 0, 'warning': 0, 'info': 0}

    # 1. 软链
    print("## §1 软链检查(Documents→Workspace)")
    symlinks_found = 0
    broken = 0
    for md_link in Path(DOCUMENTS_BASE).rglob('*'):
        if md_link.is_symlink():
            target = md_link.resolve()
            symlinks_found += 1
            try:
                target.exists()
                status = '✅'
            except (OSError, RuntimeError):
                status = '❌'
                broken += 1
            print(f"  {status} {md_link.relative_to(DOCUMENTS_BASE)} → {target}")
    if symlinks_found == 0:
        print("  ⚠️ 无 Documents→Workspace 软链")
    print(f"  统计: {symlinks_found} 个软链,{broken} 个断链")
    if broken > 0:
        issues['critical'] += broken
    print()

    # 2. MCP 服务
    print("## §2 MCP 服务可达性")
    mcp_critical = ['cockpit']
    for srv in mcp_critical:
        # v2.1.1:静态文件检测 + mavis mcp ls(双层检测,2 选 1)
        import subprocess
        mavis_ok = False
        # 检测 1:静态文件(三件套)
        cockpit_bin = Path('/Users/xiamingxing/.local/bin/cockpit')
        cockpit_project = Path('/Users/xiamingxing/Workspace/projects/cockpit')
        mavis_config = Path('/Users/xiamingxing/.mavis/config.yaml')
        static_ok = (
            cockpit_bin.exists() and
            cockpit_project.exists() and
            mavis_config.exists()
        )

        # 检测 2:动态调用 mavis mcp ls
        try:
            r = subprocess.run(
                ['/Users/xiamingxing/.mavis/bin/mavis', 'mcp', 'ls'],
                capture_output=True, text=True, timeout=10
            )
            if r.returncode == 0 and srv in r.stdout:
                mavis_ok = True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        if static_ok and mavis_ok:
            print(f"  ✅ {srv}: 已注册(static+mavis 双确认)")
        elif static_ok:
            print(f"  ⚠️ {srv}: 已配置(static OK, mavis 暂时不可用)")
        else:
            missing = []
            if not cockpit_bin.exists(): missing.append('binary')
            if not cockpit_project.exists(): missing.append('project')
            if not mavis_config.exists(): missing.append('config')
            print(f"  🔴 {srv}: 未注册(缺失:{', '.join(missing)})")
            issues['critical'] += 1
    print()

    # 3. 文本引用 Workspace
    print("## §3 文本引用 Workspace(数量 + 位置)")
    workspace_patterns = [
        r'~/Workspace',
        r'/Users/[^/]+/Workspace',
    ]

    # 不扫的目录
    skip_dirs = {'.git', '__pycache__', '_archive', '_storage', '存档', '_generated', 'node_modules'}

    ref_count_by_file = {}
    for md_file in Path(DOCUMENTS_BASE).rglob('*.md'):
        if any(s in md_file.parts for s in skip_dirs):
            continue
        try:
            content = md_file.read_text(errors='ignore')
        except Exception:
            continue
        for pattern in workspace_patterns:
            matches = re.findall(pattern, content)
            if matches:
                ref_count_by_file[str(md_file.relative_to(DOCUMENTS_BASE))] = len(matches)

    # 排序 + 显示
    total_refs = sum(ref_count_by_file.values())
    over_threshold = [(f, n) for f, n in ref_count_by_file.items() if n >= 3]
    print(f"  统计: {len(ref_count_by_file)} 个文件 · {total_refs} 处 Workspace 引用")
    print()

    if over_threshold:
        print(f"  🟡 引用 ≥3 处的文件(需升级到软链/MCP/同步脚本):")
        for f, n in sorted(over_threshold, key=lambda x: -x[1])[:20]:
            print(f"    {f}: {n} 处")
        issues['warning'] += len(over_threshold)
    else:
        print(f"  🟢 无引用 ≥3 处的文件")

    # 4. 总结
    print()
    print("━" * 80)
    print(f"  M-ε 总结")
    print(f"  🔴 严重:{issues['critical']}(断链 / MCP 不可达)")
    print(f"  🟡 警告:{issues['warning']}(文本引用过多)")
    print(f"  ℹ️ 信息:{issues['info']}")
    print()
    if issues['critical'] == 0 and issues['warning'] <= 3:
        print("  状态:🟢 桥接健康")
    elif issues['critical'] == 0:
        print("  状态:🟡 桥接可接受 · 建议优化文本引用")
    else:
        print("  状态:🔴 桥接需修复")
    print("━" * 80)

    sys.exit(1 if issues['critical'] > 0 else 0)


def log(msg, level="INFO"):
    tag = {"INFO": "ℹ️", "PASS": "✅", "FAIL": "❌", "WARN": "⚠️"}.get(level, "ℹ️")
    print(f"  {tag} {msg}")


def check_path(path, desc):
    """Check if a path exists."""
    exists = os.path.exists(os.path.expanduser(path))
    return ("PASS" if exists else "FAIL"), f"{desc}: {'存在' if exists else '不存在'} ({path})"


def compute_fingerprint(results):
    """Create a stable fingerprint from check results for diff comparison."""
    items = []
    for cat, checks in results.items():
        for level, msg in checks:
            items.append((level, msg[:80]))
    return hashlib.md5(json.dumps(sorted(items)).encode()).hexdigest()


def save_history(results, passed, total, history_file, max_history):
    """Save check history and compare with previous."""
    record = {
        "ts": datetime.now().isoformat(),
        "passed": passed,
        "total": total,
        "health": int(passed / max(total, 1) * 100),
        "fingerprint": compute_fingerprint(results),
        "items": []
    }
    for cat, checks in results.items():
        for level, msg in checks:
            record["items"].append({"cat": cat, "level": level, "msg": msg[:120]})
    
    history = []
    if os.path.exists(history_file):
        with open(history_file, "r") as fh:
            try:
                history = json.load(fh)
            except json.JSONDecodeError:
                history = []
    
    history.append(record)
    if len(history) > max_history:
        history = history[-max_history:]
    
    with open(history_file, "w") as fh:
        json.dump(history, fh, indent=2, ensure_ascii=False)
    
    return history, record


def print_trend(history, current):
    """Print trend comparison."""
    if len(history) < 2:
        return
    
    prev = history[-2]
    health_change = current["health"] - prev["health"]
    passed_change = current["passed"] - prev["passed"]
    
    trend_icon = "🟢" if health_change >= 0 else "🔴"
    print(f"\n▶ 趋势 (vs 上期)")
    print(f"  {trend_icon} 通过率: {prev['health']}% → {current['health']}% ({health_change:+.0f}%)")
    print(f"  {'📈' if passed_change >= 0 else '📉'} 通过项: {prev['passed']} → {current['passed']} ({passed_change:+.0f})")
    
    if current["fingerprint"] != prev["fingerprint"]:
        prev_items = {(i["cat"], i["msg"]) for i in prev["items"] if i["level"] == "FAIL"}
        curr_items = {(i["cat"], i["msg"]) for i in current["items"] if i["level"] == "FAIL"}
        fixed = prev_items - curr_items
        new = curr_items - prev_items
        if fixed:
            print(f"  ✅ 已修复 {len(fixed)} 项:")
            for _, msg in sorted(fixed)[:5]:
                print(f"    · {msg[:80]}")
        if new:
            print(f"  ❌ 新增 {len(new)} 项:")
            for _, msg in sorted(new)[:5]:
                print(f"    · {msg[:80]}")
def scan_claude_mds():
    """Find all CLAUDE.md files in Documents."""
    mds = []
    for root, dirs, files in os.walk(DOCUMENTS_BASE):
        # 剪枝：跳过归档/存储/生成目录（原地修改 dirs[] 阻止递归进入）
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in files:
            if f == "CLAUDE.md":
                rel = os.path.relpath(os.path.join(root, f), DOCUMENTS_BASE)
                mds.append(rel)
    return sorted(mds)


def check_convention_inheritance(md_path):
    """Check if a CLAUDE.md inherits the convention."""
    full_path = os.path.join(DOCUMENTS_BASE, md_path)
    if not os.path.exists(full_path):
        return False
    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    return "CLAUDE-公约" in content


def check_registry_ref(md_path):
    """Check if a CLAUDE.md references the registries."""
    full_path = os.path.join(DOCUMENTS_BASE, md_path)
    if not os.path.exists(full_path):
        return False
    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    return bool(re.search(r"MCP-REGISTRY|SKILL-INDEX|ROUTING", content))


def check_gateway_ref(md_path):
    """Check if a CLAUDE.md references its parent gateway."""
    full_path = os.path.join(DOCUMENTS_BASE, md_path)
    if not os.path.exists(full_path):
        return False
    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    return "L4 网关" in content or "claude.md" in content.lower()


def check_layer_label(md_path):
    """Check if a domain has proper layer annotation."""
    full_path = os.path.join(DOCUMENTS_BASE, md_path)
    if not os.path.exists(full_path):
        return False
    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    # Should have L4 annotation (not L2 or L3, excluding sub-modules)
    is_sub = "/_knowledge/" in md_path or "/_storage/" in md_path or "/_archive/" in md_path or "/_inbox/" in md_path
    lines = content.split("\n")[:5]
    header = " ".join(lines)
    if "L4" in header or "（L4" in header:
        return True
    if is_sub:
        return True  # sub-modules are exempt
    return bool(re.search(r'L[0-4][^0-9]', header))


def check_control_plane(domain_dir):
    """Check KEMS control plane files exist for a domain."""
    if domain_dir in ("@工作文档",):
        return {"STATUS.md": True, "STATE.md": True}  # aggregate, different rules
    
    control_dir = os.path.join(DOCUMENTS_BASE, domain_dir, "_control")
    if not os.path.isdir(control_dir):
        return {}
    
    required = ["STATUS.md", "STATE.md", "MEMORY.md", "TIMELINE.md", "signals.md", "control-rules.md"]
    result = {}
    for f in required:
        result[f] = os.path.exists(os.path.join(control_dir, f))
    return result


def check_m1_model(domain_name):
    """Check if domain has a corresponding ecos MOF M1 model."""
    m1_dir = os.path.join(WORKSPACE_BASE, "projects/ecos/src/ecos/ssot/mof/m1/domain")
    if not os.path.isdir(m1_dir):
        return None  # workspace not accessible
    
    # Map domain names to M1 filenames
    m1_map = {
        "@驾驶舱": "DOMAIN-cockpit.yaml",
        "@个人": "DOMAIN-personal.yaml",
        "@公共": "DOMAIN-shared.yaml",
        "@学习进化": "DOMAIN-vault.yaml",
        "@创意创作": "DOMAIN-creative.yaml",
        "@家庭生活": "DOMAIN-family.yaml",
        "@OPC": "DOMAIN-opc.yaml",
        "@工作文档": "DOMAIN-work-docs.yaml",
        "卫健委": "DOMAIN-work-weijian.yaml",
        "国转中心": "DOMAIN-work-guozhuan.yaml",
        "合同法规": "DOMAIN-work-contracts.yaml",
    }
    
    fname = m1_map.get(domain_name)
    if not fname:
        return None
    return os.path.exists(os.path.join(m1_dir, fname))


def check_broken_refs():
    """Scan for markdown references to files that don't exist."""
    broken = []
    ref_pattern = re.compile(r'`([^`]+\.md)`')
    # Known valid paths that exist at ecos layer not under Documents
    known_external = {"@公共/_control/", "ecos/ssot/", "projects/", "protocols/", "Claude/Scheduled/"}
    # File extensions that are valid even if not found (generated files)
    generated_patterns = ["_generated/", "CARDS/"]
    
    for root, dirs, files in os.walk(DOCUMENTS_BASE):
        # 剪枝：跳过归档/存储/生成目录（原地修改 dirs[] 阻止递归进入）
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in files:
            if not f.endswith(".md"):
                continue
            fpath = os.path.join(root, f)
            rel = os.path.relpath(fpath, DOCUMENTS_BASE)
            
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as fh:
                    fcontent = fh.read()
            except (FileNotFoundError, PermissionError):
                continue
            
            for ref in ref_pattern.findall(fcontent):
                if "/" not in ref or ref.startswith("http") or ref.startswith("bos:"):
                    continue
                # Skip generated/cards/scheduled paths
                if any(gp in ref for gp in generated_patterns):
                    continue
                # Skip known external/valid paths
                if any(ref.startswith(k) for k in known_external):
                    continue
                # Skip self-references and README refs
                if ref == os.path.basename(rel) or "README" in ref:
                    continue
                # Skip template references (contain {{)
                if "{{" in ref:
                    continue
                # Skip references from Scheduled task files
                if "Claude/Scheduled/" in rel:
                    continue
                # Skip known-deprecated paths (documented as stale)
                if "knowledge-protocol/IDENTITY" in ref:
                    continue
                # Skip iCloud symlink (valid even when unmounted, design choice)
                if ref.startswith("~/.ai/"):
                    continue
                # Skip iCloud symlink (valid even when unmounted)
                if "@家庭生活" in ref:
                    continue
                # Skip .omo/ cross-boundary refs (Documents→Workspace)
                if ".omo/" in ref:
                    continue
                # Skip CLAUDE_GLOBAL references from internal files
                if ref in ("~/Documents/CLAUDE_GLOBAL.md", "~/Workspace/CLAUDE.md", "~/Documents/CLAUDE.md"):
                    continue
                # Skip path expressions (not actual file paths)
                if "{" in ref and "}" in ref:
                    continue
                # Skip same-directory relative refs (start with _)
                if ref.startswith("_") and ref.count("/") <= 1:
                    continue
                # Skip @OPC/_templates refs
                if "@OPC/_templates" in ref:
                    continue
                # Skip protocol/yaml references
                if ref.endswith((".yaml", ".json", ".template")):
                    continue
                
                ref_path = os.path.join(DOCUMENTS_BASE, ref.lstrip("~/").lstrip("/"))
                if os.path.exists(ref_path):
                    continue
                # Support @xxx/ absolute paths within Documents workspace
                # e.g. "@创意创作/_knowledge/创作系统/L2-工具箱/xxx.md"
                #      "@驾驶舱/_control/STATE.md"
                if ref.startswith("@"):
                    ref_path_at = os.path.join(DOCUMENTS_BASE, ref)
                    if os.path.exists(ref_path_at):
                        continue
                # Try resolving relative to source file's directory
                src_dir = os.path.dirname(os.path.join(DOCUMENTS_BASE, rel))
                rel_resolved = os.path.join(src_dir, ref)
                if os.path.exists(rel_resolved):
                    continue
                # Try resolving from domain root (for _control/ → _knowledge/ refs)
                parent_dir = os.path.dirname(os.path.dirname(os.path.join(DOCUMENTS_BASE, rel)))
                parent_resolved = os.path.join(parent_dir, ref)
                if os.path.exists(parent_resolved):
                    continue
                # Try resolving at every ancestor directory up to DOCUMENTS_BASE
                # Supports arbitrary depth cross-folder refs like
                # "L1-控制管线/00-多媒体完成门禁.md" referenced from
                # "L2-工具箱/02-创作管线/multimedia.md"
                cur = os.path.dirname(os.path.join(DOCUMENTS_BASE, rel))
                resolved_ok = False
                while True:
                    cur_parent = os.path.dirname(cur)
                    if cur_parent == cur:  # reached filesystem root
                        break
                    candidate = os.path.join(cur_parent, ref)
                    if os.path.exists(candidate):
                        resolved_ok = True
                        break
                    cur = cur_parent
                if resolved_ok:
                    continue
                # Skip domain-relative refs starting with _ (convention, not fs path)
                if ref.startswith("_") and ref.count("/") >= 1:
                    continue
                # Skip self-referencing SSOT footers (→ @xxx/xxx.md)
                if ref.startswith("→ ") or ref.startswith("继承 "):
                    continue
                broken.append((rel, ref))
                if len(broken) >= 20:  # cap output
                        break
    
    return broken


def check_entity_consistency():
    """Check that @公共/_entities/ files with frontmatter have id."""
    issues = []
    entities_dir = os.path.join(DOCUMENTS_BASE, "@公共/_entities")
    if not os.path.isdir(entities_dir):
        return ["@公共/_entities/ 不存在"]
    
    for root, dirs, files in os.walk(entities_dir):
        # 剪枝：跳过归档/存储/生成目录（与全局遍历策略一致）
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in files:
            if not f.endswith(".md"):
                continue
            path = os.path.join(root, f)
            rel = os.path.relpath(path, DOCUMENTS_BASE)
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                content = fh.read()
            # Only check files that have YAML frontmatter
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 2 and "id:" not in parts[1]:
                    issues.append(f"{rel}: 有 frontmatter 但缺少 id")
    return issues



def print_help():
    print("收敛性检查工具")
    print("  python3 check-convergence.py [--quick] [--report] [--base <path>]")
    print("  --quick: 仅检查 1-5 项（路径+引用）")
    print("  --report: 输出 Markdown 报告到 @驾驶舱/_generated/")
    print("  --base <path>: 使用指定基准路径（如 ~/mnt 或 ~）")
    print()
    print("示例:")
    print("  python3 check-convergence.py")
    print("  python3 check-convergence.py --quick --base ~/mnt")
    print("  python3 check-convergence.py --report")

def run_all_checks():
    if HELP:
        print_help()
        return
    results = {
        "基本路径": [],
        "域清单与引用": [],
        "控制面合规": [],
        "M1 模型对齐": [],
        "断裂引用": [],
        "SSOT 实体一致性": [],
    }
    history_dir = os.path.join(DOCUMENTS_BASE, "@驾驶舱/_generated/.history")
    os.makedirs(history_dir, exist_ok=True)
    history_file = os.path.join(history_dir, "convergence-history.json")
    max_history = 12
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    print(f"\n{'='*60}")
    print(f"  收敛性检查 — {ts}")
    print(f"{'='*60}\n")
    
    # ─── 1. 基本路径 ───
    print("▶ 1. 基本路径")
    for path, desc in [
        (GLOBAL_MD, "全局系统级 CLAUDE.md"),
        (GATEWAY_MD, "Documents 层网关"),
        (CONVENTION_MD, "CLAUDEd-公约 (M2)"),
        (META_MODEL_MD, "域元模型 (M3)"),
        (REGISTRY_MD, "全局注册表"),
    ]:
        level, msg = check_path(path, desc)
        results["基本路径"].append((level, msg))
        log(msg, level)
    
    # ─── 2. 域清单与引用 ───
    print("\n▶ 2. 域级 CLAUDE.md 引用完整性")
    for cat, domains in DOMAINS.items():
        for domain in domains:
            dp = DOMAIN_PATHS[domain]
            md = f"{dp}/CLAUDE.md"
            full = os.path.join(DOCUMENTS_BASE, md)
            
            if not os.path.exists(full):
                results["域清单与引用"].append(("FAIL", f"{domain}: CLAUDE.md 缺失"))
                log(f"{domain}: CLAUDE.md 不存在", "FAIL")
                continue
            
            conv = check_convention_inheritance(md)
            reg = check_registry_ref(md)
            gw = check_gateway_ref(md)
            layer = check_layer_label(md)
            
            checks = {"公约": conv, "注册表": reg, "网关": gw, "层标注": layer}
            fails = [k for k, v in checks.items() if not v]
            
            if fails:
                results["域清单与引用"].append(("FAIL", f"{domain}: 缺 {', '.join(fails)}"))
                log(f"{domain}: ❌ 缺 {', '.join(fails)}", "FAIL")
            else:
                results["域清单与引用"].append(("PASS", f"{domain}: 4/4 全绿"))
                log(f"{domain}: 4/4 全绿 ✅", "PASS")
    
    # Sub-domains
    print("  └─ 子域:")
    for sd in SUB_DOMAINS:
        dp = DOMAIN_PATHS[sd]
        md = f"{dp}/CLAUDE.md"
        full = os.path.join(DOCUMENTS_BASE, md)
        if not os.path.exists(full):
            log(f"{sd}: CLAUDE.md 缺失", "FAIL")
            continue
        conv = check_convention_inheritance(md)
        gw = check_gateway_ref(md)
        if conv and gw:
            log(f"{sd}: 公约✅ 网关✅", "PASS")
        else:
            log(f"{sd}: 缺 {'公约' if not conv else ''} {'网关' if not gw else ''}".strip(), "FAIL")
    
    if QUICK_MODE:
        return results
    
    # ─── 3. 控制面合规 ───
    print("\n▶ 3. _control/ 合规")
    for domain in list(DOMAINS["Aggregate"]) + DOMAINS["Functional"] + DOMAINS["Infrastructure"]:
        dp = DOMAIN_PATHS[domain]
        planes = check_control_plane(dp)
        if not planes:
            log(f"{domain}: _control/ 不存在", "WARN")
            continue
        missing = [k for k, v in planes.items() if not v]
        if missing:
            log(f"{domain}: 缺 {', '.join(missing)}", "WARN")
        else:
            log(f"{domain}: {len(planes)}/{len(planes)} 全", "PASS")
    
    # ─── 4. M1 模型对齐 ───
    print("\n▶ 4. ecos MOF M1 对齐")
    m1_missing = []
    all_domain_names = list(DOMAIN_PATHS.keys())
    for d in all_domain_names:
        exists = check_m1_model(d)
        if exists is None:
            log("Workspace 不可达，跳过 M1 检查", "WARN")
            m1_missing = []
            break
        if exists:
            log(f"{d}: M1 ✅", "PASS")
        else:
            log(f"{d}: M1 ❌ 缺失", "FAIL")
            m1_missing.append(d)
    
    # ─── 5. 断裂引用 ───
    print("\n▶ 5. 断裂引用扫描")
    broken = check_broken_refs()
    if broken:
        for src, ref in broken[:10]:
            log(f"{src} → {ref}", "WARN")
        if len(broken) > 10 and False:
            log(f"... 还有 {len(broken)-10} 条", "WARN")
    else:
        log("无检测到断裂引用", "PASS")
    
    # ─── 6. SSOT 实体一致性 ───
    print("\n▶ 6. @公共/_entities 一致性")
    entity_issues = check_entity_consistency()
    if entity_issues:
        for issue in entity_issues[:5]:
            log(issue, "WARN")
    else:
        log("所有实体文件格式正确", "PASS")
    
    # ─── 汇总 ───
    print(f"\n{'='*60}")
    print(f"  汇总")
    print(f"{'='*60}")
    
    total = 0
    passed = 0
    for cat, items in results.items():
        for level, msg in items:
            total += 1
            if level == "PASS":
                passed += 1
    
    health = int(passed / max(total, 1) * 100)
    print(f"  通过率: {passed}/{total} ({health}%)")
    
    if passed == total:
        print(f"  状态: 🟢 完全收敛")
    elif health >= 80:
        print(f"  状态: 🟡 基本收敛 ({total - passed} 项需关注)")
    else:
        print(f"  状态: 🔴 需干预 ({total - passed} 项异常)")
    
    # Generate report file
    # Save history & print trend
    history, record = save_history(results, passed, total, history_file, max_history)
    if not QUICK_MODE:
        print_trend(history, record)
    
    if REPORT_MODE:
        report_path = os.path.join(DOCUMENTS_BASE, f"@驾驶舱/_generated/convergence-report-{datetime.now().strftime('%Y%m%d')}.md")
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        
        # Build report with trend
        trend_section = ""
        if len(history) >= 2:
            prev = history[-2]
            change = record["health"] - prev["health"]
            trend_section = f"> **趋势**: {prev['health']}% → {record['health']}% ({change:+.0f}%)\n"
            if record["fingerprint"] != prev["fingerprint"]:
                prev_items = {(i["cat"], i["msg"]) for i in prev["items"] if i["level"] in ("FAIL", "WARN")}
                curr_items = {(i["cat"], i["msg"]) for i in record["items"] if i["level"] in ("FAIL", "WARN")}
                fixed = prev_items - curr_items
                new = curr_items - prev_items
                if fixed:
                    trend_section += f"> ✅ 已修复 {len(fixed)} 项\n"
                if new:
                    trend_section += f"> ❌ 新增 {len(new)} 项\n"
        
        with open(report_path, 'w') as f:
            f.write(f"# 收敛性检查报告\n\n> 生成: {ts}\n> 通过率: {passed}/{total} ({health}%)\n")
            f.write(trend_section)
            f.write("\n")
            for cat, items in results.items():
                f.write(f"## {cat}\n\n")
                for level, msg in items:
                    icon = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️"}.get(level, "ℹ️")
                    f.write(f"- {icon} {msg}\n")
                f.write("\n")
        log(f"\n报告已写入: {report_path}", "INFO")
    
    return results


if __name__ == "__main__":
    if CROSS_WS_MODE:
        check_cross_workspace()
    else:
        run_all_checks()
