#!/usr/bin/env python3
"""scene-card-mini-shadow: shadow 场景卡 3-sample mini-trial 升级路径.

替代 30-sample 校准门 — 主人手勾 3 次 useful 即可升 assisted.
project-strategy-v1 §1 落地工具.

用法:
  python3 bin/gac/scene-card-mini-shadow.py --list
  python3 bin/gac/scene-card-mini-shadow.py --record <scene_id> --outcome useful
  python3 bin/gac/scene-card-mini-shadow.py --eligible
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path
from typing import Any

WS_ROOT = Path(__file__).resolve().parent.parent.parent
SCENES_DIR = WS_ROOT / "docs" / "scene-cards"
MINI_THRESHOLD = 3


def _utc_now_iso() -> str:
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_yaml_simple(path: Path) -> dict[str, Any]:
    try:
        import yaml
        with open(path, encoding="utf-8") as f:
            docs = list(yaml.safe_load_all(f))
        body = docs[-1] if len(docs) > 1 else docs[0]
        return body if isinstance(body, dict) else {}
    except ImportError:
        return {}


def _read_mini_trial(body: dict[str, Any]) -> dict[str, Any]:
    gate = body.get("lifecycle_gate") or {}
    if not isinstance(gate, dict):
        return {}
    return gate.get("mini_trial") or {}


def _is_shadow(body: dict[str, Any]) -> bool:
    return body.get("lifecycle") == "shadow"


def _shadow_age_days(body: dict[str, Any]) -> int:
    gate = body.get("lifecycle_gate") or {}
    if not isinstance(gate, dict):
        return 0
    start = gate.get("shadow_start")
    if not start:
        return 0
    try:
        start_dt = dt.datetime.fromisoformat(str(start).replace("Z", "+00:00"))
        return (dt.datetime.now(dt.UTC) - start_dt).days
    except (ValueError, TypeError):
        return 0


def list_shadow_cards() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for p in sorted(SCENES_DIR.glob("*.yaml")):
        body = _load_yaml_simple(p)
        if not _is_shadow(body):
            continue
        mini = _read_mini_trial(body)
        samples = mini.get("samples") or []
        useful = sum(1 for s in samples if s.get("outcome") == "useful")
        not_useful = sum(1 for s in samples if s.get("outcome") == "not_useful")
        out.append({
            "scene_id": p.stem,
            "path": str(p),
            "lifecycle": body.get("lifecycle"),
            "shadow_age_days": _shadow_age_days(body),
            "mini_samples": useful + not_useful,
            "useful_samples": useful,
            "not_useful_samples": not_useful,
            "threshold": MINI_THRESHOLD,
            "eligible_for_assisted": useful >= MINI_THRESHOLD,
            "last_review_ts": mini.get("last_ts"),
        })
    return out


def record_mini_sample(scene_id: str, outcome: str) -> dict[str, Any]:
    if outcome not in {"useful", "not_useful"}:
        return {"ok": False, "error": f"invalid outcome: {outcome}"}
    path = SCENES_DIR / f"{scene_id}.yaml"
    if not path.is_file():
        return {"ok": False, "error": f"scene card not found: {path}"}
    body = _load_yaml_simple(path)
    if not _is_shadow(body):
        return {"ok": False, "error": f"scene card is not in shadow lifecycle: {path}"}

    gate = body.get("lifecycle_gate") or {}
    mini = gate.get("mini_trial") or {}
    samples = list(mini.get("samples") or [])
    samples.append({"ts": _utc_now_iso(), "outcome": outcome})
    useful = sum(1 for s in samples if s.get("outcome") == "useful")
    not_useful = sum(1 for s in samples if s.get("outcome") == "not_useful")
    mini["samples"] = samples
    mini["useful_count"] = useful
    mini["not_useful_count"] = not_useful
    mini["last_ts"] = samples[-1]["ts"]
    mini["eligible_for_assisted"] = useful >= MINI_THRESHOLD
    gate["mini_trial"] = mini
    body["lifecycle_gate"] = gate

    if useful >= MINI_THRESHOLD and not mini.get("promoted_at"):
        mini["promoted_at"] = _utc_now_iso()
        mini["promotion_recommendation"] = (
            f"mini-shadow 模式: 主人手勾 {useful} 次 useful, "
            f"达到升级门 {MINI_THRESHOLD}. 建议升级到 assisted."
        )

    _write_yaml_simple(path, body)
    return {
        "ok": True,
        "scene_id": scene_id,
        "useful_count": useful,
        "not_useful_count": not_useful,
        "threshold": MINI_THRESHOLD,
        "eligible_for_assisted": useful >= MINI_THRESHOLD,
        "promotion_recommendation": mini.get("promotion_recommendation"),
    }


def _write_yaml_simple(path: Path, body: dict[str, Any]) -> None:
    text = path.read_text(encoding="utf-8")
    mini = (body.get("lifecycle_gate") or {}).get("mini_trial") or {}
    new_mini_text = _format_mini_trial_inner(mini)
    if "lifecycle_gate:" not in text:
        if "lifecycle: shadow" in text:
            text = text.rstrip() + "\n\nlifecycle_gate:\n" + (new_mini_text or "  mini_trial: {}\n")
        path.write_text(text, encoding="utf-8")
        return

    lines = text.splitlines()
    start = end = None
    for i, line in enumerate(lines):
        if line.startswith("lifecycle_gate:"):
            start = i
            for j in range(i + 1, len(lines)):
                ln = lines[j]
                if not ln.strip():
                    continue
                if ln.startswith(" ") or ln.startswith("\t") or ln.lstrip().startswith("#"):
                    continue
                end = j
                break
            if end is None:
                end = len(lines)
            break

    if start is None:
        return

    block_lines = lines[start:end]
    new_block_lines: list[str] = []
    i = 0
    while i < len(block_lines):
        line = block_lines[i]
        if line == "  mini_trial:" or line.startswith("  mini_trial:"):
            i += 1
            while i < len(block_lines):
                sub = block_lines[i]
                if sub.startswith("    ") or sub.startswith("\t"):
                    i += 1
                    continue
                break
            continue
        new_block_lines.append(line)
        i += 1

    if new_mini_text:
        new_block_lines.append("  mini_trial:")
        new_block_lines.append(new_mini_text)

    new_lines = lines[:start] + new_block_lines + lines[end:]
    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def _format_mini_trial_inner(mini: dict[str, Any]) -> str:
    if not mini:
        return ""
    samples = mini.get("samples") or []
    lines: list[str] = []
    lines.append(f"    threshold: {MINI_THRESHOLD}")
    lines.append(f"    useful_count: {mini.get('useful_count', 0)}")
    lines.append(f"    not_useful_count: {mini.get('not_useful_count', 0)}")
    lines.append(f"    eligible_for_assisted: {str(mini.get('eligible_for_assisted', False)).lower()}")
    if mini.get("last_ts"):
        lines.append(f"    last_ts: \"{mini['last_ts']}\"")
    if mini.get("promoted_at"):
        lines.append(f"    promoted_at: \"{mini['promoted_at']}\"")
    if mini.get("promotion_recommendation"):
        lines.append(f"    promotion_recommendation: \"{mini['promotion_recommendation']}\"")
    if samples:
        lines.append("    samples:")
        for s in samples:
            lines.append(f"      - ts: \"{s.get('ts', '')}\"")
            lines.append(f"        outcome: {s.get('outcome', '')}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="scene-card mini-shadow: 3-sample 升级门替代 30-sample 校准门")
    parser.add_argument("--list", action="store_true", help="列出所有 shadow 场景卡")
    parser.add_argument("--eligible", action="store_true", help="列出已达成 mini-trial 门槛 (≥3 useful) 的卡")
    parser.add_argument("--record", help="记录主人对某张卡的勾选 (--outcome 必填)")
    parser.add_argument("--outcome", choices=["useful", "not_useful"], help="主人评估")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    if args.record:
        if not args.outcome:
            print("--outcome required (useful | not_useful)", file=sys.stderr)
            return 1
        result = record_mini_sample(args.record, args.outcome)
        if args.json:
            import json
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            if result["ok"]:
                print(f"✓ {result['scene_id']}: useful={result['useful_count']}/{result['threshold']}")
                if result["eligible_for_assisted"]:
                    print(f"  ⚠ {result['promotion_recommendation']}")
            else:
                print(f"✗ {result['error']}", file=sys.stderr)
                return 1
        return 0

    if args.eligible:
        cards = [c for c in list_shadow_cards() if c["eligible_for_assisted"]]
    else:
        cards = list_shadow_cards()

    if args.json:
        import json
        print(json.dumps(cards, ensure_ascii=False, indent=2))
    else:
        if not cards:
            print("No shadow scene cards found." if not args.eligible else "No eligible cards yet.")
            return 0
        print(f"{'scene_id':<32} {'age(d)':<8} {'useful':<7} {'useful/total':<13} {'eligible'}")
        print("-" * 80)
        for c in cards:
            print(
                f"{c['scene_id']:<32} {c['shadow_age_days']:<8} {c['useful_samples']:<7} "
                f"{c['useful_samples']}/{c['mini_samples']:<11} {'YES' if c['eligible_for_assisted'] else 'no'}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())