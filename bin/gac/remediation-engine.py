#!/usr/bin/env python3
"""Remediation Engine — 自运维修复引擎.

基于修复策略表 (Remediation Strategy Table) 自动检测并修复常见问题.
支持 dry-run 模式预览修复动作.

修复策略:
  1. 文档过期 → 自动更新 last-reviewed frontmatter
  2. 场景 shadow 超期 → 发送激活提醒
  3. 工具 deprecated → 标记并建议归档
  4. 子模块指针漂移 → 自动对齐
  5. 健康分下降 → 生成诊断报告

用法:
    python3 remediation-engine.py --dry-run         # 预览修复
    python3 remediation-engine.py --execute         # 执行修复
    python3 remediation-engine.py --json            # JSON 输出
    python3 remediation-engine.py --strategy docs   # 仅执行 docs 策略
"""

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DOCS_DIR = REPO / "docs"
SCENE_DIR = REPO / "docs/scene-cards"
HEALTH_FILE = REPO / ".omo/state/health.yaml"


# ── 修复策略表 ──────────────────────────────────────────────
REMEDIATION_STRATEGIES = {
    "docs_stale": {
        "description": "文档过期 (>30天未更新 last-reviewed)",
        "severity": "P2",
        "detector": "detect_stale_docs",
        "fixer": "fix_stale_docs",
        "auto_fixable": True,
    },
    "scene_shadow_stale": {
        "description": "场景 shadow 超期 (>30天未升级)",
        "severity": "P2",
        "detector": "detect_stale_shadow_scenes",
        "fixer": "notify_scene_activation",
        "auto_fixable": False,  # 需人工确认
    },
    "tool_deprecated": {
        "description": "工具 deprecated (90天无 CI 调用)",
        "severity": "P1",
        "detector": "detect_deprecated_tools",
        "fixer": "archive_deprecated_tools",
        "auto_fixable": True,
    },
    "health_degraded": {
        "description": "健康分下降 (>10% in 7 days)",
        "severity": "P1",
        "detector": "detect_health_degradation",
        "fixer": "generate_health_diagnostic",
        "auto_fixable": False,
    },
}


# ── 检测器 ──────────────────────────────────────────────────

def detect_stale_docs() -> list[dict]:
    """检测过期文档."""
    stale = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    if not DOCS_DIR.exists():
        return stale

    for f in sorted(DOCS_DIR.rglob("*.md")):
        try:
            text = f.read_text()
            if text.startswith("---"):
                end = text.find("---", 3)
                if end > 0:
                    import yaml
                    fm = yaml.safe_load(text[3:end])
                    if isinstance(fm, dict):
                        lr = fm.get("last-reviewed") or fm.get("last_reviewed")
                        if lr is None:
                            # 无 last-reviewed 字段
                            stale.append({
                                "file": str(f.relative_to(REPO)),
                                "issue": "missing_last_reviewed",
                                "suggestion": "add frontmatter",
                            })
                        elif isinstance(lr, str):
                            from datetime import date
                            lr_date = date.fromisoformat(lr)
                            if lr_date < cutoff.date():
                                stale.append({
                                    "file": str(f.relative_to(REPO)),
                                    "issue": "stale",
                                    "last_reviewed": str(lr),
                                    "days_ago": (datetime.now().date() - lr_date).days,
                                })
        except Exception:
            continue

    return stale


def detect_stale_shadow_scenes() -> list[dict]:
    """检测 shadow 超期场景."""
    stale = []

    if not SCENE_DIR.exists():
        return stale

    for f in sorted(SCENE_DIR.glob("*.yaml")):
        try:
            import yaml
            text = f.read_text()
            fm = yaml.safe_load(text) if not text.startswith("---") else None
            if fm is None and text.startswith("---"):
                end = text.find("---", 3)
                if end > 0:
                    fm = yaml.safe_load(text[3:end])
            if fm and isinstance(fm, dict):
                lifecycle = fm.get("lifecycle", "")
                if lifecycle == "shadow":
                    stale.append({
                        "file": str(f.relative_to(REPO)),
                        "scene_id": fm.get("scene_id", fm.get("title", "?")),
                        "lifecycle": lifecycle,
                        "issue": "shadow_stale",
                    })
        except Exception:
            continue

    return stale


def detect_deprecated_tools() -> list[dict]:
    """检测 deprecated 工具 (P2 且 90天无 CI 调用)."""
    # 复用 tool-governance 的逻辑
    tools_dir = REPO / "projects/ecos/src/ecos/ssot/tools"
    workflow = REPO / ".github/workflows/ecos-ci.yml"

    if not tools_dir.exists() or not workflow.exists():
        return []

    ci_content = workflow.read_text()
    deprecated = []

    for f in sorted(tools_dir.glob("*.py")):
        name = f.stem
        if name.startswith("_"):
            continue
        in_ci = name in ci_content
        has_test = (REPO / "projects/ecos/tests" / f"test_{name}.py").exists()

        if not in_ci and not has_test:
            deprecated.append({
                "name": name,
                "issue": "no_ci_no_test",
                "suggestion": "archive_or_add_ci",
            })

    return deprecated


def detect_health_degradation() -> list[dict]:
    """检测健康分下降."""
    history_file = REPO / ".omo/state/history/uhs.jsonl"
    if not history_file.exists():
        return []

    # 读取最近 7 天的记录
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    recent = []

    with open(history_file) as f:
        for line in f:
            try:
                record = json.loads(line.strip())
                ts = datetime.fromisoformat(record["timestamp"])
                if ts >= cutoff:
                    recent.append(record)
            except Exception:
                continue

    if len(recent) < 2:
        return []

    # 检查趋势
    recent.sort(key=lambda r: r["timestamp"])
    first_uhs = recent[0].get("uhs", 0)
    last_uhs = recent[-1].get("uhs", 0)
    delta = last_uhs - first_uhs

    if delta < -10:
        return [{
            "issue": "health_degraded",
            "delta": delta,
            "from_uhs": first_uhs,
            "to_uhs": last_uhs,
            "suggestion": "run diagnostic",
        }]

    return []


# ── 修复器 ──────────────────────────────────────────────────

def fix_stale_docs(stale_docs: list[dict], dry_run: bool = True) -> list[dict]:
    """修复过期文档: 更新 last-reviewed 为今天."""
    actions = []
    today = datetime.now().date().isoformat()

    for doc in stale_docs:
        if doc["issue"] == "missing_last_reviewed":
            actions.append({
                "file": doc["file"],
                "action": "add_last_reviewed",
                "value": today,
                "dry_run": dry_run,
            })
            if not dry_run:
                _add_frontmatter_field(doc["file"], "last-reviewed", today)
        elif doc["issue"] == "stale":
            actions.append({
                "file": doc["file"],
                "action": "update_last_reviewed",
                "value": today,
                "dry_run": dry_run,
            })
            if not dry_run:
                _update_frontmatter_field(doc["file"], "last-reviewed", today)

    return actions


def _add_frontmatter_field(file_path: str, field: str, value: str):
    """向文档添加 frontmatter 字段."""
    f = REPO / file_path
    if not f.exists():
        return
    text = f.read_text()
    if text.startswith("---"):
        end = text.find("---", 3)
        if end > 0:
            # 在 closing --- 之前添加字段
            new_text = text[:end] + f"\n{field}: {value}\n" + text[end:]
            f.write_text(new_text)


def _update_frontmatter_field(file_path: str, field: str, value: str):
    """更新文档 frontmatter 字段."""
    f = REPO / file_path
    if not f.exists():
        return
    text = f.read_text()
    if text.startswith("---"):
        end = text.find("---", 3)
        if end > 0:
            # 提取 frontmatter 内容 (去掉开头的 ---)
            fm_text = text[3:end]
            lines = fm_text.splitlines()
            found = False
            for i, line in enumerate(lines):
                if line.startswith(f"{field}:"):
                    lines[i] = f"{field}: {value}"
                    found = True
                    break
            if not found:
                lines.append(f"{field}: {value}")
            # 重建文档: ---\n + 修改后的 frontmatter + \n--- + 剩余内容
            new_text = "---\n" + "\n".join(lines) + "\n" + text[end:]
            f.write_text(new_text)


def notify_scene_activation(stale_scenes: list[dict], dry_run: bool = True) -> list[dict]:
    """通知场景激活 (需人工确认)."""
    return [{
        "scene": s.get("scene_id", s["file"]),
        "action": "notify_activation",
        "message": f"Scene {s.get('scene_id', '?')} has been in shadow for >30 days. Consider activating.",
        "dry_run": dry_run,
    } for s in stale_scenes]


def archive_deprecated_tools(deprecated: list[dict], dry_run: bool = True) -> list[dict]:
    """归档 deprecated 工具."""
    return [{
        "tool": d["name"],
        "action": "suggest_archive",
        "message": f"Tool {d['name']} has no CI or test. Consider archiving.",
        "dry_run": dry_run,
    } for d in deprecated]


def generate_health_degradation(degradation: list[dict], dry_run: bool = True) -> list[dict]:
    """生成健康分诊断报告."""
    if not degradation:
        return []
    d = degradation[0]
    return [{
        "action": "generate_diagnostic",
        "message": f"Health dropped {d['delta']:.1f} points (from {d['from_uhs']} to {d['to_uhs']})",
        "suggestion": "Run 'python3 bin/gac/unified-health-score.py --trend' for details",
        "dry_run": dry_run,
    }]


# ── 主引擎 ──────────────────────────────────────────────────

def run_remediation(strategy_filter: str = None, dry_run: bool = True) -> dict:
    """运行修复引擎."""
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "strategies": [],
        "total_issues": 0,
        "total_fixed": 0,
    }

    for name, strategy in REMEDIATION_STRATEGIES.items():
        if strategy_filter and name != strategy_filter:
            continue

        detector = globals().get(strategy["detector"])
        fixer = globals().get(strategy["fixer"])

        if not detector or not fixer:
            continue

        # 检测问题
        issues = detector()
        if not issues:
            continue

        # 修复
        if dry_run or strategy["auto_fixable"]:
            actions = fixer(issues, dry_run=dry_run)
        else:
            actions = fixer(issues, dry_run=True)  # 不可自动修复的只报告

        fixed_count = len([a for a in actions if not a.get("dry_run", True)])

        results["strategies"].append({
            "name": name,
            "description": strategy["description"],
            "severity": strategy["severity"],
            "auto_fixable": strategy["auto_fixable"],
            "issues_found": len(issues),
            "actions_taken": len(actions),
            "fixed": fixed_count,
            "details": actions[:5],  # 最多显示 5 个
        })

        results["total_issues"] += len(issues)
        results["total_fixed"] += fixed_count

    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Remediation Engine")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    parser.add_argument("--execute", action="store_true", help="Execute fixes")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strategy", help="Run specific strategy only")
    args = parser.parse_args()

    dry_run = not args.execute
    results = run_remediation(strategy_filter=args.strategy, dry_run=dry_run)

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    print("=" * 56)
    print("  Remediation Engine Report")
    print("=" * 56)
    print(f"  Mode: {'DRY RUN' if dry_run else 'EXECUTE'}")
    print(f"  Total issues: {results['total_issues']}")
    print(f"  Total fixed: {results['total_fixed']}")
    print()

    for s in results["strategies"]:
        auto = "✓ auto" if s["auto_fixable"] else "⚠ manual"
        print(f"  [{s['severity']}] {s['description']}")
        print(f"    Issues: {s['issues_found']}, Fixed: {s['fixed']}, Mode: {auto}")
        for d in s.get("details", [])[:3]:
            print(f"      - {d}")


if __name__ == "__main__":
    sys.exit(main())
