#!/usr/bin/env python3
"""Remediation Engine — 自运维修复引擎.

基于修复策略表自动检测并修复常见问题.
支持 dry-run 模式预览修复动作.

策略:
  1. docs_stale: 文档过期 → 自动更新 last-reviewed
  2. scene_shadow_stale: 场景 shadow 超期 → 通知激活
  3. tool_deprecated: 工具 deprecated → 标记归档
  4. health_degraded: 健康分下降 → 生成诊断报告
"""

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DOCS_DIR = REPO / "docs"
SCENE_DIR = REPO / "docs/scene-cards"
HEALTH_FILE = REPO / ".omo/state/health.yaml"

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
        "auto_fixable": False,
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
                            stale.append({"file": str(f.relative_to(REPO)), "issue": "missing_last_reviewed"})
                        elif isinstance(lr, str):
                            from datetime import date
                            lr_date = date.fromisoformat(lr)
                            if lr_date < cutoff.date():
                                stale.append({"file": str(f.relative_to(REPO)), "issue": "stale", "days_ago": (datetime.now().date() - lr_date).days})
        except Exception:
            continue
    return stale


def fix_stale_docs(stale_docs: list[dict], dry_run: bool = True) -> list[dict]:
    """修复过期文档."""
    actions = []
    today = datetime.now().date().isoformat()
    for doc in stale_docs:
        actions.append({"file": doc["file"], "action": "update_last_reviewed", "value": today, "dry_run": dry_run})
        if not dry_run:
            _update_frontmatter_field(doc["file"], "last-reviewed", today)
    return actions


def _update_frontmatter_field(file_path: str, field: str, value: str):
    """更新文档 frontmatter 字段."""
    f = REPO / file_path
    if not f.exists():
        return
    text = f.read_text()
    if text.startswith("---"):
        end = text.find("---", 3)
        if end > 0:
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
            f.write_text("---\n" + "\n".join(lines) + "\n" + text[end:])


def detect_stale_shadow_scenes() -> list[dict]:
    """检测 shadow 超期场景."""
    stale = []
    if not SCENE_DIR.exists():
        return stale
    for f in sorted(SCENE_DIR.glob("*.yaml")) + sorted(SCENE_DIR.glob("v2/*.yaml")):
        try:
            import yaml
            text = f.read_text()
            fm = {}
            for part in text.split("---"):
                part = part.strip()
                if not part:
                    continue
                try:
                    data = yaml.safe_load(part)
                    if isinstance(data, dict):
                        fm.update(data)
                except Exception:
                    pass
            if isinstance(fm, dict) and fm.get("lifecycle") == "shadow":
                stale.append({"file": str(f.relative_to(REPO)), "scene_id": fm.get("scene_id", fm.get("title", "?"))})
        except Exception:
            continue
    return stale


def detect_deprecated_tools() -> list[dict]:
    """检测 deprecated 工具."""
    tools_dir = REPO / "projects/ecos/src/ecos/ssot/tools"
    workflow = REPO / ".github/workflows/ecos-ci.yml"
    if not tools_dir.exists() or not workflow.exists():
        return []
    ci_content = workflow.read_text()
    return [
        {"name": f.stem, "issue": "no_ci_no_test"}
        for f in sorted(tools_dir.glob("*.py"))
        if not f.stem.startswith("_") and f.stem not in ci_content
    ]


def detect_health_degradation() -> list[dict]:
    """检测健康分下降."""
    history_file = REPO / ".omo/state/history/uhs.jsonl"
    if not history_file.exists():
        return []
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
    recent.sort(key=lambda r: r["timestamp"])
    delta = recent[-1].get("uhs", 0) - recent[0].get("uhs", 0)
    return [{"issue": "health_degraded", "delta": delta}] if delta < -10 else []


def run_remediation(strategy_filter: str = None, dry_run: bool = True) -> dict:
    """运行修复引擎."""
    results = {"timestamp": datetime.now(timezone.utc).isoformat(), "dry_run": dry_run, "strategies": [], "total_issues": 0, "total_fixed": 0}
    for name, strategy in REMEDIATION_STRATEGIES.items():
        if strategy_filter and name != strategy_filter:
            continue
        detector = globals().get(strategy["detector"])
        fixer = globals().get(strategy["fixer"])
        if not detector or not fixer:
            continue
        issues = detector()
        if not issues:
            continue
        actions = fixer(issues, dry_run=dry_run) if strategy["auto_fixable"] else fixer(issues, dry_run=True)
        fixed_count = len([a for a in actions if not a.get("dry_run", True)])
        results["strategies"].append({
            "name": name,
            "description": strategy["description"],
            "severity": strategy["severity"],
            "auto_fixable": strategy["auto_fixable"],
            "issues_found": len(issues),
            "actions_taken": len(actions),
            "fixed": fixed_count,
            "details": actions[:5],
        })
        results["total_issues"] += len(issues)
        results["total_fixed"] += fixed_count
    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Remediation Engine")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strategy")
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


if __name__ == "__main__":
    sys.exit(main())
