#!/usr/bin/env python3
"""ledger-safe-insert.py — 3y-bet-ledger.yaml BET 条目安全插入工具 (批次 19-30 复盘固化).

解决手工插入 BET 条目的三类高频事故:
  A. 插入点错位: bets 序列被顶层键 (campaigns/disciplines/concurrency) 切断,
     按行号盲插会把条目塞进错误的顶层段落。
  B. schema 违规: binding 四键/三轴/digest 不一致 → lint 失败。
  C. id 冲突: 与现有条目重复。

用法:
  python3 bin/gac/ledger-safe-insert.py --file <entry.yaml> [--dry-run]
  python3 bin/gac/ledger-safe-insert.py --show-bounds
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
import tempfile
from pathlib import Path

import yaml

LEDGER_REL = "docs/plans/3y-bet-ledger.yaml"
SPEC_BINDING_KEYS = {"spec_ref", "spec_version", "content_digest", "decision_ref"}
COMPLETION_AXES = ("engineering", "operational", "value")


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def compose_bounds(ledger: Path) -> tuple[int, int, str]:
    """Return (insert_line_0based, total_bets, last_bet_id) via yaml.compose."""
    node = yaml.compose(ledger.open(encoding="utf-8"))
    for key_node, value_node in node.value:
        if key_node.value == "bets":
            if not isinstance(value_node, yaml.SequenceNode):
                raise SystemExit("bets: is not a sequence")
            bets = value_node.value
            if not bets:
                raise SystemExit("bets sequence is empty")
            last_mapping = bets[-1]
            last_id = ""
            for k_node, v_node in last_mapping.value:
                if k_node.value == "id":
                    last_id = str(v_node.value)
                    break
            return value_node.end_mark.line, len(bets), last_id
    raise SystemExit("no bets key found at top level")


def validate_entry(entry: dict, root: Path, bet_id: str) -> list[str]:
    errors: list[str] = []
    specs = entry.get("accepted_specifications")
    if not isinstance(specs, list) or len(specs) != 1:
        errors.append("accepted_specifications must contain exactly one binding")
    else:
        binding = specs[0]
        if set(binding.keys()) != SPEC_BINDING_KEYS:
            errors.append(f"binding keys must be {sorted(SPEC_BINDING_KEYS)}")
        spec_ref = binding.get("spec_ref", "")
        if spec_ref.startswith("repo://"):
            spec_path = root / spec_ref.removeprefix("repo://")
            if not spec_path.is_file():
                errors.append(f"SPEC_FILE_MISSING: {spec_path}")
            else:
                actual = sha256_file(spec_path)
                if binding.get("content_digest") != actual:
                    errors.append(
                        f"SPEC_DIGEST_MISMATCH: declared={str(binding.get('content_digest'))[:23]}..."
                        f" actual={actual[:23]}..."
                    )
        expected_decision = f"decision://accepted/{bet_id}"
        if binding.get("decision_ref") != expected_decision:
            errors.append(f"decision_ref must equal {expected_decision}")

    ce = entry.get("completion_evidence") or {}
    axes = ce.get("axes") or {}
    if set(axes.keys()) != set(COMPLETION_AXES):
        errors.append(f"completion_evidence axes must be exactly {sorted(COMPLETION_AXES)}")
    if not ce.get("overall_state"):
        errors.append("completion_evidence.overall_state is required")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", help="YAML file containing a single BET entry mapping")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--show-bounds", action="store_true")
    parser.add_argument("--ledger", default=LEDGER_REL)
    args = parser.parse_args()

    root = Path.cwd()
    ledger = root / args.ledger
    if not ledger.is_file():
        raise SystemExit(f"ledger not found: {ledger}")

    insert_at, total, last_id = compose_bounds(ledger)
    if args.show_bounds:
        print(f"bets: {total} | insert before 1-based line {insert_at + 1} | last: {last_id}")
        return 0

    if not args.file:
        parser.error("--file required unless --show-bounds")

    entry_text = Path(args.file).read_text(encoding="utf-8")
    entry = yaml.safe_load(entry_text)
    if not isinstance(entry, dict) or "id" not in entry:
        raise SystemExit("entry must be a single BET mapping with an id")
    bet_id = entry["id"]

    lines = ledger.read_text(encoding="utf-8").splitlines(keepends=True)
    insert_at, current_total, _ = compose_bounds(ledger)

    errors = validate_entry(entry, root, bet_id)
    dup = sum(
        1 for line_item in lines if line_item.strip() == f"id: {bet_id}"
    )
    if dup:
        errors.append(f"id conflict: {bet_id} already in ledger")

    if errors:
        for e in errors:
            print(f"ERROR {bet_id}: {e}", file=sys.stderr)
        return 1

    if args.dry_run:
        print(f"DRY-RUN OK: {bet_id} would be inserted at line {insert_at + 1}")
        return 0

    entry_lines = [l + "\n" for l in entry_text.rstrip("\n").split("\n")]
    lines[insert_at:insert_at] = entry_lines
    new_text = "".join(lines)

    for cfg_line in lines:
        stripped = cfg_line.strip()
        if stripped.startswith("total_bets:"):
            old_total = int(stripped.split(":")[1].strip())
            new_text = new_text.replace(
                f"  total_bets: {old_total}", f"  total_bets: {old_total + 1}", 1
            )
            break

    fd, tmp = tempfile.mkstemp(suffix=".yaml", dir=str(ledger.parent))
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(new_text)
    os.replace(tmp, ledger)

    data = yaml.safe_load(ledger.open(encoding="utf-8"))
    print(f"OK: inserted {bet_id} | bets now {len(data['bets'])} | last={data['bets'][-1]['id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
