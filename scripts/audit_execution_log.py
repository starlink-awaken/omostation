#!/usr/bin/env python3
"""runtime executor AppendOnlyLog audit 脚本 (R52 P0 + R53 P0).

R52 P0: 读取 executor execution_log.jsonl，验证 JSON + Z-suffix + 必填字段
R53 P0: 加 --metrics flag，输出 §17 风格健康度 JSON

用法:
  python scripts/audit_execution_log.py [--path <jsonl_path>] [--metrics]

退出码: 0=全部合规, 1=有错误
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


REQUIRED_FIELDS = ["ts", "task_id", "status", "summary"]


def audit_jsonl(path: Path) -> tuple[int, int, list[str]]:
    """审计 JSONL，返回 (total, drift, errors)。

    drift = 缺 Z-suffix 或缺必填字段的记录数。
    """
    errors: list[str] = []
    total = 0
    drift = 0
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            total += 1
            line_drift = False
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as e:
                errors.append(f"  L{lineno}: JSON 解析失败 — {e}")
                drift += 1
                continue
            ts = rec.get("ts", "")
            if ts and not ts.endswith("Z"):
                errors.append(f"  L{lineno}: ts={ts!r} 缺 Z 后缀")
                line_drift = True
            for field in REQUIRED_FIELDS:
                if field not in rec:
                    errors.append(f"  L{lineno}: 缺必填字段 {field!r}")
                    line_drift = True
            if line_drift:
                drift += 1
    return total, drift, errors


def _health_grade(density: float) -> str:
    if density <= 0.01:
        return "R0"
    elif density <= 0.05:
        return "R1"
    elif density <= 0.10:
        return "R2"
    elif density <= 0.30:
        return "R3"
    elif density <= 0.50:
        return "R4"
    return "R5"


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit executor execution_log.jsonl")
    parser.add_argument(
        "--path",
        type=Path,
        default=Path.home() / "runtime" / "execution_log.jsonl",
        help="execution_log.jsonl 路径 (默认 ~/runtime/execution_log.jsonl)",
    )
    parser.add_argument(
        "--metrics",
        action="store_true",
        help="R53 P0: 输出 §17 metrics JSON (health_grade + debt_density)",
    )
    args = parser.parse_args()

    if not args.path.exists():
        print(f"ℹ️  {args.path} 不存在 (executor 未运行或无执行记录)")
        return 0

    total, drift, errors = audit_jsonl(args.path)

    # R53 P0: --metrics 输出 §17 风格 JSON
    if args.metrics:
        density = drift / total if total > 0 else 0.0
        grade = _health_grade(density)
        payload = {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "drift_count": drift,
            "total_records": total,
            "debt_density": round(density, 6),
            "health_grade": grade,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
        return 2 if _health_grade_rank(grade) >= 3 else 0

    # 普通 audit 模式
    print(f"📋 audit {args.path}: {total} records")
    if errors:
        print("❌ 发现问题:")
        for e in errors:
            print(e)
        return 1
    print("✅ 全部合规 (Z-suffix + 必填字段 OK)")
    return 0


def _health_grade_rank(grade: str) -> int:
    return {"R0": 0, "R1": 1, "R2": 2, "R3": 3, "R4": 4, "R5": 5}.get(grade, 99)


if __name__ == "__main__":
    raise SystemExit(main())
