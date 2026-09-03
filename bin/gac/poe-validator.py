#!/usr/bin/env python3
"""Proof of Execution (PoE) Validator — 物理测量收据校验器.

验证 Agent 提交的执行收据必须具备真实物理测量凭证 (exit_code, sha256 proof_hash, execution_ms, verdict).
严禁纯自然语言描述作为验收凭证 (Measurement > Narration).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REQUIRED_POE_FIELDS = [
    "actor_id",
    "target_node",
    "fact_type",
    "exit_code",
    "proof_hash",
    "execution_ms",
    "verdict",
]

ALLOWED_VERDICTS = ["pass", "fail", "corroded", "skipped"]


def validate_poe_receipt(receipt: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate a single Proof of Execution receipt."""
    errors = []
    for f in REQUIRED_POE_FIELDS:
        if f not in receipt:
            errors.append(f"Missing required field: '{f}'")

    if "exit_code" in receipt and not isinstance(receipt["exit_code"], int):
        errors.append(f"'exit_code' must be an integer, got {type(receipt['exit_code']).__name__}")

    if "execution_ms" in receipt:
        if not isinstance(receipt["execution_ms"], (int, float)) or receipt["execution_ms"] < 0:
            errors.append(f"'execution_ms' must be a non-negative number, got {receipt['execution_ms']}")

    if "proof_hash" in receipt:
        h = str(receipt["proof_hash"]).strip()
        if len(h) < 8:
            errors.append(f"'proof_hash' must be at least 8 characters hash/digest, got '{h}'")

    if "verdict" in receipt and receipt["verdict"] not in ALLOWED_VERDICTS:
        errors.append(f"'verdict' must be one of {ALLOWED_VERDICTS}, got '{receipt['verdict']}'")

    return len(errors) == 0, errors


def selftest() -> bool:
    """Run self-test on PoE validator."""
    valid_receipt = {
        "actor_id": "devil:gov",
        "target_node": "proj:omo",
        "fact_type": "health_check",
        "exit_code": 0,
        "proof_hash": hashlib.sha256(b"ok").hexdigest(),
        "execution_ms": 25,
        "verdict": "pass",
        "details": {"test": True},
    }
    ok, errors = validate_poe_receipt(valid_receipt)
    assert ok, f"Self-test valid receipt failed: {errors}"

    invalid_receipt = {
        "actor_id": "agent-lazy",
        "verdict": "pass",
    }
    ok_inv, errors_inv = validate_poe_receipt(invalid_receipt)
    assert not ok_inv, "Self-test invalid receipt unexpectedly passed"
    assert len(errors_inv) >= 5

    return True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=str, help="JSON or JSONL receipt file to validate")
    parser.add_argument("--selftest", action="store_true", help="Run validator self-test")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args(argv)

    if args.selftest:
        success = selftest()
        if args.json:
            print(json.dumps({"selftest": "pass", "ok": success}))
        else:
            print("✅ PoE Validator 自检通过 (PASS)")
        return 0

    if not args.file:
        parser.print_help()
        return 1

    p = Path(args.file)
    if not p.exists():
        print(f"❌ 收据文件不存在: {p}", file=sys.stderr)
        return 2

    content = p.read_text(encoding="utf-8").strip()
    receipts = []
    if content.startswith("[") or content.startswith("{"):
        data = json.loads(content)
        receipts = data if isinstance(data, list) else [data]
    else:
        for line in content.splitlines():
            line = line.strip()
            if line:
                receipts.append(json.loads(line))

    all_valid = True
    results = []
    for idx, r in enumerate(receipts):
        valid, errors = validate_poe_receipt(r)
        if not valid:
            all_valid = False
        results.append({"index": idx, "valid": valid, "errors": errors, "receipt": r})

    if args.json:
        print(json.dumps({"ok": all_valid, "total": len(receipts), "results": results}, ensure_ascii=False, indent=2))
    else:
        print(f"=== PoE 物理测量收据校验 (共 {len(receipts)} 条) ===")
        for res in results:
            icon = "✅" if res["valid"] else "❌"
            actor = res["receipt"].get("actor_id", "unknown")
            node = res["receipt"].get("target_node", "unknown")
            print(f"  {icon} #{res['index']} [{actor} -> {node}] {'VALID' if res['valid'] else 'INVALID'}")
            if res["errors"]:
                for err in res["errors"]:
                    print(f"      • {err}")

    return 0 if all_valid else 1


if __name__ == "__main__":
    sys.exit(main())
