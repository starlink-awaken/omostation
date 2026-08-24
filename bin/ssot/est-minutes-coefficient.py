#!/usr/bin/env python3
"""est-minutes-coefficient — 时间账本估算系数表 读取/校验/建议 (骨架).

SSOT: protocols/est-minutes-coefficient.yaml (schema: est-minutes-coefficient/v1)

子命令:
  --validate          校验 YAML 结构与 floor/cap 边界, 退出码 0=pass / 1=fail
  --get <type>        输出指定类型的分钟数 (纯数字, 便于脚本管道)
  --suggest           骨架: 读 stdin JSON ({type, count, ...}) 输出建议分钟数
                      本期为 stub: 直接返回 type 系数 × count, 不做复杂推断
  --list              列出全部系数 (type minutes basis首行)

用法:
  python3 bin/ssot/est-minutes-coefficient.py --validate
  python3 bin/ssot/est-minutes-coefficient.py --get pr_merge
  echo '{"type":"pr_merge","count":3}' | python3 bin/ssot/est-minutes-coefficient.py --suggest
  python3 bin/ssot/est-minutes-coefficient.py --list

设计原则 (D7): 宁低估勿高估。系数变更必须走 PR (L2 半自动)。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

try:
    from _shared import ROOT  # type: ignore[import-not-found]
except ImportError:
    # 直接运行时 sys.path[0] 是脚本目录, _shared 可导入; 兜底:
    ROOT = Path(__file__).resolve().parents[2]

SSOT_PATH = ROOT / "protocols" / "est-minutes-coefficient.yaml"
EXPECTED_VERSION = "est-minutes-coefficient/v1"
REQUIRED_COEFFICIENT_KEYS = {"type", "minutes", "basis"}


def load_ssot(path: Path = SSOT_PATH) -> dict:
    """Load the coefficient SSOT YAML. Returns dict."""
    if not path.exists():
        raise FileNotFoundError(f"SSOT not found: {path}")
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"SSOT root must be a dict, got {type(data).__name__}")
    return data


def validate(data: dict) -> tuple[bool, list[str]]:
    """Validate SSOT structure and floor/cap boundaries.

    Returns (ok, errors). ok=True means the file is structurally sound and
    every coefficient sits within [floor, cap].
    """
    errors: list[str] = []

    # version
    version = data.get("version")
    if version != EXPECTED_VERSION:
        errors.append(f"version must be {EXPECTED_VERSION!r}, got {version!r}")

    # updated_at
    if not data.get("updated_at"):
        errors.append("updated_at is missing or empty")

    # floor / cap
    floor = data.get("floor_minutes")
    cap = data.get("cap_minutes")
    if not isinstance(floor, (int, float)) or floor < 0:
        errors.append(f"floor_minutes must be a non-negative number, got {floor!r}")
        floor = 0
    if not isinstance(cap, (int, float)) or cap <= 0:
        errors.append(f"cap_minutes must be a positive number, got {cap!r}")
        cap = float("inf")
    if isinstance(floor, (int, float)) and isinstance(cap, (int, float)) and floor > cap:
        errors.append(f"floor_minutes ({floor}) > cap_minutes ({cap})")

    # review_policy
    rp = data.get("review_policy")
    if not isinstance(rp, dict):
        errors.append("review_policy must be a dict")
    else:
        if rp.get("level") != "L2":
            errors.append(f"review_policy.level must be 'L2', got {rp.get('level')!r}")
        if rp.get("gate") != "pr-required":
            errors.append(f"review_policy.gate must be 'pr-required', got {rp.get('gate')!r}")

    # coefficients
    coeffs = data.get("coefficients")
    if not isinstance(coeffs, list) or len(coeffs) < 8:
        errors.append(f"coefficients must be a list with >=8 entries, got {len(coeffs) if isinstance(coeffs, list) else 'non-list'}")

    seen_types: set[str] = set()
    required_types = {
        "pr_merge", "debt_close", "doc_write", "scene_activation",
        "infra_fix", "research_digest", "attestation_review", "default",
    }
    if isinstance(coeffs, list):
        for i, c in enumerate(coeffs):
            if not isinstance(c, dict):
                errors.append(f"coefficients[{i}] must be a dict")
                continue
            missing = REQUIRED_COEFFICIENT_KEYS - set(c.keys())
            if missing:
                errors.append(f"coefficients[{i}] missing keys: {sorted(missing)}")
                continue
            ctype = c.get("type")
            if not isinstance(ctype, str) or not ctype:
                errors.append(f"coefficients[{i}].type must be a non-empty string")
                continue
            if ctype in seen_types:
                errors.append(f"coefficients[{i}].type {ctype!r} duplicated")
            seen_types.add(ctype)

            minutes = c.get("minutes")
            if not isinstance(minutes, (int, float)) or minutes <= 0:
                errors.append(f"coefficients[{i}] ({ctype}): minutes must be a positive number, got {minutes!r}")
                continue
            if minutes < floor:
                errors.append(f"coefficients[{i}] ({ctype}): minutes={minutes} < floor={floor}")
            if minutes > cap:
                errors.append(f"coefficients[{i}] ({ctype}): minutes={minutes} > cap={cap}")

            basis = c.get("basis")
            if not isinstance(basis, str) or len(basis.strip()) < 10:
                errors.append(f"coefficients[{i}] ({ctype}): basis must be a non-trivial string (>=10 chars)")

        missing_types = required_types - seen_types
        if missing_types:
            errors.append(f"missing required types: {sorted(missing_types)}")

    return (len(errors) == 0), errors


def get_minutes(ctype: str, data: dict | None = None) -> int | None:
    """Return minutes for a type, or None if not found."""
    if data is None:
        data = load_ssot()
    for c in data.get("coefficients", []):
        if c.get("type") == ctype:
            return c.get("minutes")
    return None


def suggest(payload: dict, data: dict | None = None) -> dict:
    """Skeleton suggest: return type_minutes * count.

   本期 stub: no complex inference. Reads {type, count} from payload.
    Falls back to 'default' type if type unknown.
    """
    if data is None:
        data = load_ssot()
    ctype = payload.get("type", "default")
    count = payload.get("count", 1)
    if not isinstance(count, (int, float)) or count < 0:
        count = 1
    minutes = get_minutes(ctype, data)
    if minutes is None:
        ctype_used = "default"
        minutes = get_minutes("default", data) or 15
    else:
        ctype_used = ctype
    total = minutes * int(count)
    return {
        "type": ctype_used,
        "count": int(count),
        "minutes_per_item": minutes,
        "total_minutes": total,
        "source": str(SSOT_PATH.relative_to(ROOT)) if SSOT_PATH.is_relative_to(ROOT) else str(SSOT_PATH),
        "note": "stub: total = minutes_per_item * count; L2 evolution pending",
    }


def list_coefficients(data: dict | None = None) -> list[dict]:
    """Return a compact list of all coefficients."""
    if data is None:
        data = load_ssot()
    out = []
    for c in data.get("coefficients", []):
        basis = c.get("basis", "")
        first_line = basis.strip().split("\n")[0][:80] if isinstance(basis, str) else ""
        out.append({
            "type": c.get("type"),
            "minutes": c.get("minutes"),
            "basis_head": first_line,
        })
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="est-minutes-coefficient SSOT reader/validator (v1)",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--validate", action="store_true", help="validate SSOT structure and boundaries")
    group.add_argument("--get", metavar="TYPE", help="print minutes for TYPE")
    group.add_argument("--suggest", action="store_true", help="read stdin JSON, output suggested minutes (stub)")
    group.add_argument("--list", action="store_true", help="list all coefficients")
    parser.add_argument("--path", default=str(SSOT_PATH), help="override SSOT path (debug)")
    args = parser.parse_args(argv)

    ssot_path = Path(args.path)
    try:
        data = load_ssot(ssot_path)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.validate:
        ok, errors = validate(data)
        if ok:
            print(f"OK: {ssot_path} valid (version={data.get('version')}, {len(data.get('coefficients', []))} coefficients)")
            return 0
        print(f"FAIL: {ssot_path} has {len(errors)} error(s):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    if args.get:
        m = get_minutes(args.get, data)
        if m is None:
            print(f"ERROR: type {args.get!r} not found", file=sys.stderr)
            return 1
        print(m)
        return 0

    if args.suggest:
        raw = sys.stdin.read().strip()
        if not raw:
            print("ERROR: --suggest requires JSON on stdin", file=sys.stderr)
            return 1
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            print(f"ERROR: invalid JSON: {exc}", file=sys.stderr)
            return 1
        result = suggest(payload, data)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.list:
        rows = list_coefficients(data)
        print(f"{'type':<22} {'minutes':>8}  basis")
        print("-" * 70)
        for r in rows:
            print(f"{r['type']:<22} {r['minutes']:>8}  {r['basis_head']}")
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
