#!/usr/bin/env python3
"""
织星 MOF — 层合规强制执行器 (mof-enforce)
=============================================
基于 layer-boundary.yaml 检测资产是否在错误的架构层中。
违规项自动创建 CARDS 债务卡片，定期由 daemon 触发。

检测逻辑:
  1. 读 layer-boundary.yaml → 获取每层的 allowed/forbidden 规则
  2. 扫描 Documents(L4) + Workspace(L0-L3+I0) 的全部资产
  3. 匹配规则 → 标记违规项
  4. 自动创建 CARDS DEBT 卡片 (可禁用)
  5. 输出合规报告

用法:
    python3 mof-enforce.py                     # 扫描+报告
    python3 mof-enforce.py --auto-fix-summary  # 仅报告不创建卡片
    python3 mof-enforce.py --no-cards          # 不创建 CARDS
    python3 mof-enforce.py --json              # JSON 输出
    python3 mof-enforce.py --watch             # 持续监听模式 (daemon)
"""

import sys
import json
import yaml
import sqlite3
import argparse
import re
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
DOCS = HOME / "Documents"
WS = HOME / "Workspace"
BOUNDARY_FILE = WS / "projects" / "ecos" / "src" / "ecos" / "ssot" / "layer-boundary.yaml"
CARDS_DB = WS / "data" / "cards" / "cards.db"


def load_boundary() -> dict:
    with open(BOUNDARY_FILE) as f:
        return yaml.safe_load(f)


def scan_assets() -> list[dict]:
    """扫描全量资产"""
    assets = []

    # Scan Documents (L4)
    if DOCS.exists():
        for f in DOCS.rglob("*"):
            if f.is_file() and not any(s in str(f) for s in [".git", ".obsidian", "node_modules", ".venv", "Zotero", "__pycache__", ".pytest_cache", ".ruff_cache"]):
                assets.append({"path": str(f), "layer": "L4", "type": f.suffix, "name": f.name, "size": f.stat().st_size})

    # Scan Workspace (L0-L3+I0)
    if WS.exists():
        ws_projects = WS / "projects"
        scan_dirs = [WS / "agora", WS / "cockpit", WS / "ecos", WS / "runtime", WS / "kairon", WS / "gbrain"]
        if ws_projects.exists():
            scan_dirs.append(ws_projects)
        
        for scan_dir in scan_dirs:
            if not scan_dir.exists():
                continue
            # Infer layer
            layer = "L2"
            name = scan_dir.name
            if name in ["ecos"]: layer = "L0"
            elif name in ["runtime", "agent-runtime"]: layer = "L1"
            elif name in ["cockpit", "hermes-console"]: layer = "L3"
            elif name in ["agora"]: layer = "I0"
            
            for f in scan_dir.rglob("*"):
                if f.is_file() and not any(s in str(f) for s in [".git", "node_modules", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache", "dist/"]):
                    assets.append({"path": str(f), "layer": layer, "type": f.suffix, "name": f.name, "size": f.stat().st_size})

    return assets


def check_violation(asset: dict, boundary: dict) -> dict | None:
    """检查单个资产是否违规"""
    name = asset["name"]
    layer = asset["layer"]
    path = asset["path"]

    layer_rules = boundary.get("layers", {}).get(layer)
    if not layer_rules:
        return None

    # Check forbidden patterns
    for rule in layer_rules.get("forbidden", []):
        pattern = rule.get("pattern", "")
        unless = rule.get("unless", "")
        note = rule.get("note", "")

        # Match pattern
        if re.search(pattern.replace("*", ".*"), name):
            # Check unless
            if unless and re.search(unless.replace("*", ".*"), path):
                continue
            return {
                "asset": name,
                "path": str(Path(path).relative_to(HOME)) if str(path).startswith(str(HOME)) else path,
                "current_layer": layer,
                "violation": f"禁止在 {layer} 中存放: {note}",
                "suggested_layer": suggest_layer(name, path),
                "severity": "high" if layer == "L4" and name.endswith(".py") else "medium",
            }

    # Check if L4 Python script is on the exclusion list
    if layer == "L4" and asset["type"] == ".py":
        allowed = layer_rules.get("allowed", [])
        is_allowed = False
        for rule in allowed:
            if rule.get("type") != "*.py":
                continue
            cond = rule.get("condition", "")
            if re.search(cond.replace("*", ".*"), name):
                is_allowed = True
                break
        if not is_allowed:
            return {
                "asset": name,
                "path": str(Path(path).relative_to(HOME)) if str(path).startswith(str(HOME)) else path,
                "current_layer": layer,
                "violation": "L4 Python 脚本不在允许列表中——应下沉到 L0/L1/L3",
                "suggested_layer": suggest_layer(name, path),
                "severity": "high",
            }

    return None


def suggest_layer(name: str, path: str) -> str:
    """根据文件名推断正确层级"""
    if any(k in name for k in ["mof-", "constraint", "compiler", "protocol", "topology", "pattern"]):
        return "L0"
    if any(k in name for k in ["daemon", "healer", "sla", "runtime", "matrix"]):
        return "L1"
    if any(k in name for k in ["engine", "planner", "index", "ontology", "derive"]):
        return "L2"
    if any(k in name for k in ["mcp", "server", "adapter", "gateway", "entry"]):
        return "L3"
    return "L1"


def create_debt_card(violation: dict) -> bool:
    """为违规创建 CARDS 债务卡片"""
    if not CARDS_DB.exists():
        return False
    try:
        conn = sqlite3.connect(str(CARDS_DB))
        now = datetime.now(timezone.utc).isoformat()
        debt_id = f"DEBT-ENFORCE-{now[:10]}-{violation['asset'][:20]}"
        debt_id = re.sub(r'[^a-zA-Z0-9_\-]', '-', debt_id)[:50]
        
        cur = conn.execute("SELECT id FROM cards WHERE id = ?", (debt_id,))
        if cur.fetchone():
            conn.close()
            return False  # Already exists
        
        title = f"层违规: {violation['asset']} 在 {violation['current_layer']} → 应下沉到 {violation['suggested_layer']}"
        conn.execute("""
            INSERT INTO cards (id, type, status, title, domain, priority, summary, content, created_at, updated_at)
            VALUES (?, 'debt', 'identified', ?, 'meta', 'P2', ?, ?, ?, ?)
        """, (debt_id, title[:100],
              f"{violation['violation']} | 建议: {violation['suggested_layer']}",
              f"## mof-enforce 自动检测\n- 资产: {violation['path']}\n- 当前层: {violation['current_layer']}\n- 建议层: {violation['suggested_layer']}\n- 违规: {violation['violation']}",
              now, now))
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def format_report(violations: list[dict]) -> str:
    now = datetime.now(timezone.utc)
    lines = ["=" * 64, "  织星 MOF — 层合规报告", "=" * 64,
             f"  时间: {now.strftime('%Y-%m-%d %H:%M:%S')}",
             f"  违规: {len(violations)} 项", ""]

    if not violations:
        lines.append("  ✅ 全部资产在正确的架构层中")
    else:
        by_layer = {}
        for v in violations:
            l = v["current_layer"]
            by_layer.setdefault(l, []).append(v)
        for layer in sorted(by_layer):
            lines.append(f"  [{layer}] {len(by_layer[layer])} 项:")
            for v in by_layer[layer]:
                icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(v["severity"], "⚪")
                lines.append(f"    {icon} {v['asset']:30s} → {v['suggested_layer']}")
                lines.append(f"       {v['violation'][:70]}")

    lines.append("=" * 64)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-cards", action="store_true", help="不创建 CARDS")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--watch", action="store_true", help="监听模式 (daemon用)")
    args = parser.parse_args()

    if not BOUNDARY_FILE.exists():
        print(f"❌ 边界规则不存在: {BOUNDARY_FILE}")
        sys.exit(2)

    boundary = load_boundary()
    assets = scan_assets()
    
    violations = []
    for asset in assets:
        v = check_violation(asset, boundary)
        if v:
            violations.append(v)

    if args.json:
        print(json.dumps({"violations": len(violations), "items": violations}, ensure_ascii=False, indent=2))
    else:
        print(format_report(violations))

    if not args.no_cards and violations:
        created = 0
        for v in violations:
            if create_debt_card(v):
                created += 1
        if created > 0:
            print(f"\n  📋 CARDS 自动创建: {created} 张 DEBT 卡片")


if __name__ == "__main__":
    main()
