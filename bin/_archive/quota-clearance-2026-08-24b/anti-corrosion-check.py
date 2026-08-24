#!/usr/bin/env python3
"""Anti-Corrosion Check — 防腐检查.

基于减法配额 (subtraction-quota.yaml) 检查系统健康状态,
检测工具堆积、文档腐烂、场景僵化等腐蚀信号.

用法:
    python3 anti-corrosion-check.py              # 检查报告
    python3 anti-corrosion-check.py --json        # JSON 输出
    python3 anti-corrosion-check.py --enforce     # CI 模式: 违规 exit 1
"""

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]  # bin/gac/ → Workspace/
QUOTA_FILE = REPO / ".omo/_truth/registry/subtraction-quota.yaml"


def load_quota() -> dict:
    """加载减法配额配置."""
    if not QUOTA_FILE.exists():
        return {}
    try:
        import yaml
        content = QUOTA_FILE.read_text()
        # 支持两种格式: 纯 YAML 或 frontmatter + 数据
        if content.startswith("---"):
            end = content.find("---", 3)
            if end > 0:
                data = yaml.safe_load(content[end + 3:])
                return data
        else:
            # 尝试找到第一个 --- 分隔符
            lines = content.splitlines()
            for i, line in enumerate(lines):
                if line.strip() == "---":
                    data_str = "\n".join(lines[i + 1:])
                    data = yaml.safe_load(data_str)
                    return data if data else {}
            # 没有分隔符, 尝试直接解析
            data = yaml.safe_load(content)
            return data if data else {}
    except Exception:
        pass
    return {}


def check_tool_bloat(quota: dict) -> dict:
    """检查工具堆积."""
    tools_dir = REPO / "projects/ecos/src/ecos/ssot/tools"
    if not tools_dir.exists():
        return {"ok": True, "message": "No tools directory"}

    tools = [f for f in tools_dir.glob("*.py") if not f.stem.startswith("_")]
    total = len(tools)
    max_total = quota.get("quota", {}).get("tools", {}).get("max_total", 300)

    # 检查 deprecated (无 CI 无 test)
    workflow = REPO / ".github/workflows/ecos-ci.yml"
    ci_content = workflow.read_text() if workflow.exists() else ""
    deprecated = []
    for f in tools:
        name = f.stem
        in_ci = name in ci_content
        has_test = (REPO / "projects/ecos/tests" / f"test_{name}").exists()
        if not in_ci and not has_test:
            deprecated.append(name)

    violations = []
    if total > max_total:
        violations.append(f"Tools total {total} exceeds max {max_total}")
    if len(deprecated) > 0:
        violations.append(f"{len(deprecated)} deprecated tools need archival")

    return {
        "ok": len(violations) == 0,
        "total": total,
        "max_total": max_total,
        "deprecated_count": len(deprecated),
        "deprecated_tools": deprecated[:10],
        "violations": violations,
    }


def check_doc_decay(quota: dict) -> dict:
    """检查文档腐烂."""
    docs_dir = REPO / "docs"
    if not docs_dir.exists():
        return {"ok": True, "message": "No docs directory"}

    max_stale_ratio = quota.get("quota", {}).get("docs", {}).get("max_stale_ratio", 0.1)
    stale_threshold = datetime.now(timezone.utc) - timedelta(days=30)

    total = 0
    stale = 0
    stale_files = []

    for f in sorted(docs_dir.rglob("*.md")):
        try:
            text = f.read_text()
            if text.startswith("---"):
                end = text.find("---", 3)
                if end > 0:
                    import yaml
                    fm = yaml.safe_load(text[3:end])
                    if isinstance(fm, dict) and "last-reviewed" in fm:
                        total += 1
                        lr = fm["last-reviewed"]
                        if isinstance(lr, str):
                            from datetime import date
                            lr = date.fromisoformat(lr)
                        if isinstance(lr, datetime):
                            if lr < stale_threshold:
                                stale += 1
                                stale_files.append(str(f.relative_to(REPO)))
                        elif isinstance(lr, type(stale_threshold.date())):
                            if lr < stale_threshold.date():
                                stale += 1
                                stale_files.append(str(f.relative_to(REPO)))
        except Exception:
            continue

    stale_ratio = stale / total if total > 0 else 0
    violations = []
    if stale_ratio > max_stale_ratio:
        violations.append(f"Stale ratio {stale_ratio:.1%} exceeds max {max_stale_ratio:.1%}")

    return {
        "ok": len(violations) == 0,
        "total": total,
        "stale": stale,
        "stale_ratio": round(stale_ratio, 3),
        "max_stale_ratio": max_stale_ratio,
        "stale_files": stale_files[:10],
        "violations": violations,
    }


def check_scene_stagnation(quota: dict) -> dict:
    """检查场景僵化."""
    scene_dir = REPO / "docs/scene-cards"
    if not scene_dir.exists():
        return {"ok": True, "message": "No scene cards"}

    max_shadow_days = quota.get("quota", {}).get("scenes", {}).get("max_shadow_days", 30)

    shadow_scenes = []
    for f in sorted(scene_dir.glob("*.yaml")):
        try:
            import yaml
            text = f.read_text()
            fm = yaml.safe_load(text) if not text.startswith("---") else None
            if fm is None and text.startswith("---"):
                end = text.find("---", 3)
                if end > 0:
                    fm = yaml.safe_load(text[3:end])
            if fm and isinstance(fm, dict) and fm.get("lifecycle") == "shadow":
                shadow_scenes.append(fm.get("scene_id", fm.get("title", "?")))
        except Exception:
            continue

    violations = []
    if shadow_scenes:
        violations.append(f"{len(shadow_scenes)} scenes stuck in shadow")

    return {
        "ok": len(violations) == 0,
        "shadow_scenes": shadow_scenes,
        "violations": violations,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Anti-Corrosion Check")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--enforce", action="store_true")
    args = parser.parse_args()

    quota = load_quota()
    if not quota:
        print("Warning: subtraction-quota.yaml not found", file=sys.stderr)

    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": {},
        "violations": [],
        "ok": True,
    }

    # 执行检查
    checks = {
        "tool_bloat": check_tool_bloat(quota),
        "doc_decay": check_doc_decay(quota),
        "scene_stagnation": check_scene_stagnation(quota),
    }

    for name, check_result in checks.items():
        results["checks"][name] = check_result
        if not check_result.get("ok", True):
            results["ok"] = False
            results["violations"].extend(check_result.get("violations", []))

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print("=" * 56)
        print("  Anti-Corrosion Check")
        print("=" * 56)
        print(f"  Status: {'PASS' if results['ok'] else 'FAIL'}")
        print()

        for name, check_result in checks.items():
            status = "✓" if check_result.get("ok") else "✗"
            print(f"  {status} {name}:")
            for k, v in check_result.items():
                if k not in ("ok", "violations") and not isinstance(v, list):
                    print(f"      {k}: {v}")
            for v in check_result.get("violations", []):
                print(f"      ✗ {v}")

        if results["violations"]:
            print()
            print("  Violations:")
            for v in results["violations"]:
                print(f"    ✗ {v}")

    if args.enforce and not results["ok"]:
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())
