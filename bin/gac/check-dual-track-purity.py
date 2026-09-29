#!/usr/bin/env python3
"""check-dual-track-purity: enforce P84 dual-track isolation.

The throughput track (real backlog) must never contain scenario-sourced
data. This check scans:

  1. `.omo/state/collab-dualtrack.yaml` — verifies throughput_track
     has no scenario contamination (no 'source: scenario' fields, no
     scenario_total in throughput section).
  2. `BRIEF.md` — scans the throughput section for any references to
     constructed scenarios or scenario sources.

P84 §0: 构造场景只计能力轨, 真实 backlog 只计产能轨.
Violation = 最高级违规.

Output:
  - exit 0 = tracks are pure
  - exit 1 = contamination detected (blocking)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

WORKSPACE = Path(__file__).resolve().parents[2]
DUALTRACK_YAML = WORKSPACE / ".omo" / "state" / "collab-dualtrack.yaml"
sys.path.insert(0, str(WORKSPACE / "bin" / "lib"))
from repo_root import projection_read, state_root as runtime_state_root  # noqa: E402


def brief_md() -> Path:
    """本检出该读的 brief 投影 (BRIEF.md 已摘库, canonical 在 .omo/state/runtime/).

    collab-dualtrack.yaml 是 tracked 治理 SSOT, 不是投影 —— 仍按固定路径读。
    """
    return projection_read(
        WORKSPACE, "brief", registry_root=WORKSPACE, state_root=runtime_state_root()
    )[0]

# Patterns that indicate scenario contamination in throughput track
SCENARIO_LEAK_PATTERNS = [
    re.compile(r"source:\s*scenario", re.IGNORECASE),
    re.compile(r"scenario_total", re.IGNORECASE),
    re.compile(r"构造场景", re.IGNORECASE),
    re.compile(r"collab-scenarios", re.IGNORECASE),
    re.compile(r"adversarial", re.IGNORECASE),
]


def _check_dualtrack_yaml() -> list[dict]:
    findings: list[dict] = []
    if not DUALTRACK_YAML.is_file():
        findings.append(
            {
                "kind": "missing_file",
                "file": str(DUALTRACK_YAML),
                "message": "collab-dualtrack.yaml not found",
            }
        )
        return findings

    data = yaml.safe_load(DUALTRACK_YAML.read_text(encoding="utf-8")) or {}
    throughput = data.get("throughput_track") or {}

    # Check 1: throughput_track should not have scenario-specific fields
    for key in (
        "scenario_total",
        "scenario_passed",
        "adversarial_total",
        "adversarial_failed",
        "adversarial_fail_rate",
        "conflict_resolution_success_rate",
        "avg_resolution_rounds",
    ):
        if key in throughput:
            findings.append(
                {
                    "kind": "throughput_contamination",
                    "field": key,
                    "message": f"throughput_track contains scenario field '{key}' — belongs in capability_track only",
                }
            )

    # Check 2: throughput data_source should not reference scenarios
    ds = str(throughput.get("data_source", ""))
    if "scenario" in ds.lower() or "构造场景" in ds:
        findings.append(
            {
                "kind": "datasource_contamination",
                "field": "data_source",
                "message": f"throughput_track.data_source references scenarios: {ds!r}",
            }
        )

    # Check 3: silent_loss must exist (G3.2 cross-check)
    if "silent_loss" not in throughput:
        findings.append(
            {
                "kind": "missing_silent_loss",
                "message": "throughput_track.silent_loss field missing — cannot verify zero silent loss",
            }
        )

    return findings


def _check_brief_throughput() -> list[dict]:
    """Scan the brief projection's throughput section for scenario leakage."""
    findings: list[dict] = []
    brief = brief_md()
    if not brief.is_file():
        # 未生成 ≠ 违规: brief 是运行态投影, 没跑过 generator 的检出里没有它。
        return findings

    content = brief.read_text(encoding="utf-8")

    # Find the throughput section (### 📦 产能轨 to next ## or end)
    tp_match = re.search(
        r"(###\s*📦\s*产能轨.*?)(?=\n##\s|\Z)",
        content,
        re.DOTALL,
    )
    if not tp_match:
        # No throughput section — not a purity issue, just missing
        return findings

    tp_section = tp_match.group(1)

    for pat in SCENARIO_LEAK_PATTERNS:
        m = pat.search(tp_section)
        if m:
            findings.append(
                {
                    "kind": "brief_throughput_leak",
                    "match": m.group(0),
                    "message": f"BRIEF.md throughput section contains scenario reference: {m.group(0)!r}",
                }
            )

    return findings


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    findings: list[dict] = []
    findings.extend(_check_dualtrack_yaml())
    brief = brief_md()
    brief_missing = not brief.is_file()
    if not brief_missing:
        findings.extend(_check_brief_throughput())

    if args.json:
        print(json.dumps({
            "ok": len(findings) == 0,
            "complete": not brief_missing,
            "status": "skipped" if brief_missing else "fail" if findings else "pass",
            "findings": findings,
        }))
    else:
        if findings:
            for f in findings:
                print(f"  FAIL: [{f['kind']}] {f['message']}")
            print(f"check-dual-track-purity: FAIL ({len(findings)} finding(s))")
        elif brief_missing:
            print("check-dual-track-purity: SKIP (brief projection not generated)")
        else:
            print("check-dual-track-purity: PASS")

    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
