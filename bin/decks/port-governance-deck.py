#!/usr/bin/env python3
"""decks/port-governance-deck.py — P78 Foundry v2: 端口治理 deck

在 foundry cron 的 9-deck 中加入第 10 个 deck:
- 检测硬编码端口未注册
- 检测 deprecated 端口使用
- 输出 metrics 到 runtime/omo/_delivery/foundry/
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
RUNTIME_DIR = WORKSPACE / "runtime" / "omo" / "_delivery" / "foundry"
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)


def run_check(label: str, cmd: list[str]) -> dict:
    """run check, return {label, ok, summary}."""
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    ok = result.returncode == 0 and "❌" not in result.stdout
    return {
        "label": label,
        "ok": ok,
        "returncode": result.returncode,
        "summary": result.stdout.strip().split("\n")[-1] if result.stdout else "",
        "stderr": result.stderr.strip()[:200] if result.stderr else "",
    }


def main() -> int:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    checks = []

    # Deck 1: hardcoded ports
    checks.append(run_check(
        "hardcoded-ports",
        [sys.executable, str(WORKSPACE / "bin" / "check-hardcoded-ports.py")],
    ))

    # Deck 2: env-var check (env-only ports)
    checks.append(run_check(
        "env-var-check",
        [sys.executable, str(WORKSPACE / "bin" / "check-hardcoded-ports.py"), "--env-var-check"],
    ))

    # Deck 3: cross-repo consistency
    checks.append(run_check(
        "cross-repo-consistency",
        [sys.executable, str(WORKSPACE / "bin" / "check-cross-repo-consistency.py")],
    ))

    # Deck 4: catalog health (principle count, GaC rule count)
    catalog = WORKSPACE / ".omo" / "standards" / "p76-principles.md"
    gac = WORKSPACE / ".omo" / "_truth" / "registry" / "governance-checks.yaml"
    import re
    principle_count = len(set(re.findall(r"\b(P\d+-\d+-\d+|P\d+-\d+)\b", catalog.read_text())))
    gac_rule_count = gac.read_text().count("- id: CR-") if gac.exists() else 0

    result = {
        "run_id": f"port-gov-{run_id}",
        "timestamp": run_id,
        "decks": [
            {
                "name": f"port-governance-{i+1}",
                "check": c["label"],
                "ok": c["ok"],
                "detail": c["summary"],
            }
            for i, c in enumerate(checks)
        ],
        "catalog_metrics": {
            "principle_count": principle_count,
            "gac_rule_count": gac_rule_count,
        },
        "deck_count": len(checks) + 1,  # +1 catalog health
        "health": all(c["ok"] for c in checks),
    }

    # Write to runtime
    report = RUNTIME_DIR / f"port-governance-{run_id}.yaml"
    import yaml
    report.write_text(yaml.dump(result, default_flow_style=False, allow_unicode=True))

    # Print summary
    for c in checks:
        icon = "✅" if c["ok"] else "❌"
        print(f"  {icon} {c['label']}: {c['summary'][:80]}")
    print(f"  📊 catalog: {principle_count} principles, {gac_rule_count} GaC rules")
    print(f"  📝 report: {report.relative_to(WORKSPACE)}")

    return 0 if result["health"] else 1


if __name__ == "__main__":
    sys.exit(main())
