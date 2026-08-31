#!/usr/bin/env python3
"""architecture-check.py — 架构合规检查入口."""

from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCENES_DIR = REPO / "docs" / "scene-cards"

VALID_LIFECYCLES = ["draft", "shadow", "assisted", "supervised", "routine"]
VALID_DOMAINS = ["work", "health", "research", "knowledge", "governance"]


def _yaml_load(path: Path) -> dict:
    try:
        import yaml
        text = path.read_text(encoding="utf-8")
        docs = list(yaml.safe_load_all(text))
        result = {}
        for doc in docs:
            if isinstance(doc, dict):
                result.update(doc)
        return result
    except Exception:
        return {}


def check_scene_lifecycle() -> list[str]:
    errors = []
    for f in sorted(SCENES_DIR.glob("*.yaml")):
        data = _yaml_load(f)
        if not data:
            continue
        scene_id = data.get("scene_id", f.stem)
        lifecycle = data.get("lifecycle", "")
        if lifecycle and lifecycle not in VALID_LIFECYCLES:
            errors.append(f"{scene_id}: lifecycle '{lifecycle}' 无效")
    return errors


def check_scene_domain() -> list[str]:
    errors = []
    for f in sorted(SCENES_DIR.glob("*.yaml")):
        data = _yaml_load(f)
        if not data:
            continue
        scene_id = data.get("scene_id", f.stem)
        domain = data.get("domain", "")
        if not domain:
            errors.append(f"{scene_id}: 缺少 domain 字段")
        elif domain not in VALID_DOMAINS:
            errors.append(f"{scene_id}: domain '{domain}' 无效")
    return errors


def check_bin_quota() -> list[str]:
    errors = []
    active = set()
    for f in Path("bin").rglob("*.py"):
        if "_archive" not in str(f) and f.is_file():
            active.add(f.name)
    baseline_file = REPO / ".omo" / "_truth" / "registry" / "governance-checks.yaml"
    if baseline_file.exists():
        content = baseline_file.read_text()
        match = re.search(r"script_baseline:\s*(\d+)", content)
        if match:
            baseline = int(match.group(1))
            if len(active) > baseline:
                errors.append(f"bin/ 脚本 {len(active)} 超基线 {baseline}")
    return errors


def run_check(name: str, check_func) -> dict:
    try:
        errors = check_func()
        return {"name": name, "ok": len(errors) == 0, "errors": errors}
    except Exception as e:
        return {"name": name, "ok": False, "errors": [str(e)]}


def main() -> int:
    parser = argparse.ArgumentParser(description="架构合规检查")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    checks = [
        ("scene_lifecycle", check_scene_lifecycle),
        ("scene_domain", check_scene_domain),
        ("bin_quota", check_bin_quota),
    ]

    results = []
    for name, func in checks:
        results.append(run_check(name, func))

    total_ok = sum(1 for r in results if r["ok"])
    total_fail = len(results) - total_ok

    if args.json:
        print(json.dumps({"total": len(results), "ok": total_ok, "fail": total_fail, "checks": results}, ensure_ascii=False, indent=2))
    else:
        print(f"架构检查: {total_ok}/{len(results)} 通过")
        for r in results:
            status = "PASS" if r["ok"] else "FAIL"
            print(f"  [{status}] {r['name']}")
            if not r["ok"]:
                for e in r["errors"][:5]:
                    print(f"    - {e}")

    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
