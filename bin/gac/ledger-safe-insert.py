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
import importlib.util
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

LEDGER_REL = "docs/plans/3y-bet-ledger.yaml"
SPEC_BINDING_KEYS = {"spec_ref", "spec_version", "content_digest", "decision_ref"}
COMPLETION_AXES = ("engineering", "operational", "value")
_LEDGER_CONTRACT = None


def _ledger_contract() -> Any:
    global _LEDGER_CONTRACT
    if _LEDGER_CONTRACT is None:
        module_path = Path(__file__).resolve().parents[1] / "plan" / "bet-ledger.py"
        spec = importlib.util.spec_from_file_location("_ledger_structural_contract", module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("LEDGER_STRUCTURAL_CONTRACT_UNAVAILABLE")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _LEDGER_CONTRACT = module
    return _LEDGER_CONTRACT


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
    if not isinstance(bet_id, str) or not bet_id.startswith("BET-"):
        errors.append("id must be a BET-* string")
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


def format_entry_as_list_item(entry: dict, *, indent_units: int = 0) -> str:
    """Render a mapping-shaped entry as one item directly inside ``bets``.

    The public input contract is a mapping, while the Ledger requires a list
    item. Rendering through PyYAML avoids trusting the caller's indentation.
    """
    rendered = yaml.safe_dump(entry, sort_keys=False, allow_unicode=True).rstrip("\n")
    lines = rendered.splitlines()
    if not lines:
        raise SystemExit("entry mapping is empty")
    item_prefix = " " * indent_units
    nested_prefix = " " * (indent_units + 2)
    return (
        "\n".join([f"{item_prefix}- {lines[0]}", *(f"{nested_prefix}{line}" if line else "" for line in lines[1:])])
        + "\n"
    )


def bets_item_indent(ledger: Path) -> int:
    node = yaml.compose(ledger.open(encoding="utf-8"))
    for key_node, value_node in node.value:
        if key_node.value == "bets":
            if not isinstance(value_node, yaml.SequenceNode) or not value_node.value:
                raise SystemExit("bets: is not a non-empty sequence")
            column = value_node.value[0].start_mark.column
            if column < 2:
                raise SystemExit("bets: first item has invalid indentation")
            return column - 2
    raise SystemExit("no bets key found at top level")


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

    contract = _ledger_contract()
    try:
        ledger_data = contract.parse_ledger_text(
            ledger.read_text(encoding="utf-8"),
            source=str(ledger),
        )
    except contract.LedgerStructureError as error:
        for diagnostic in error.diagnostics:
            print(f"ERROR {diagnostic}", file=sys.stderr)
        return 1

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
    existing_ids = {
        item.get("id")
        for item in ledger_data["bets"]
        if isinstance(item, dict)
    }
    if bet_id in existing_ids:
        errors.append(f"duplicate BET id: {bet_id}")

    if errors:
        for e in errors:
            print(f"ERROR {bet_id}: {e}", file=sys.stderr)
        return 1

    if args.dry_run:
        print(f"DRY-RUN OK: {bet_id} would be inserted at line {insert_at + 1}")
        return 0

    entry_lines = format_entry_as_list_item(
        entry,
        indent_units=bets_item_indent(ledger),
    ).splitlines(keepends=True)
    lines[insert_at:insert_at] = entry_lines
    new_text = "".join(lines)

    try:
        candidate = contract.parse_ledger_text(new_text, source=str(ledger))
    except contract.LedgerStructureError as error:
        for diagnostic in error.diagnostics:
            print(f"ERROR {diagnostic}", file=sys.stderr)
        return 1
    candidate_bets = candidate["bets"]
    if (
        not isinstance(candidate_bets, list)
        or len(candidate_bets) != current_total + 1
        or candidate_bets[-1].get("id") != bet_id
    ):
        raise SystemExit("semantic verification failed: inserted entry is not the last bets list item")

    # meta.total_bets 必须由插入后的 len(bets) 绝对派生，禁止 old+1 —
    # 若 meta 已漂移，increment 只会把错误平移一位（GAT-006 / #4189→#4201 实证）。
    actual_total = len(candidate_bets)
    meta_m = re.search(r"^(?P<indent>[ \t]*)total_bets:[ \t]*\d+[ \t]*$", new_text, re.MULTILINE)
    if meta_m is None:
        raise SystemExit("semantic verification failed: meta.total_bets line missing")
    new_text = (
        new_text[: meta_m.start()]
        + f"{meta_m.group('indent')}total_bets: {actual_total}"
        + new_text[meta_m.end() :]
    )
    try:
        candidate = contract.parse_ledger_text(new_text, source=str(ledger))
    except contract.LedgerStructureError as error:
        for diagnostic in error.diagnostics:
            print(f"ERROR {diagnostic}", file=sys.stderr)
        return 1
    declared = candidate.get("meta", {}).get("total_bets")
    if declared != actual_total:
        raise SystemExit(
            f"semantic verification failed: meta.total_bets={declared!r} != len(bets)={actual_total}"
        )

    fd, tmp = tempfile.mkstemp(suffix=".yaml", dir=str(ledger.parent))
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(new_text)
    os.replace(tmp, ledger)

    data = yaml.safe_load(ledger.open(encoding="utf-8"))
    print(f"OK: inserted {bet_id} | bets now {len(data['bets'])} | last={data['bets'][-1]['id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
