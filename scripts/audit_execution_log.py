#!/usr/bin/env python3
"""runtime executor AppendOnlyLog audit 脚本 (R52 P0).

读取 executor execution_log.jsonl，验证：
1. 每行是合法 JSON
2. ts 字段以 Z 结尾 (UTC ISO8601)
3. 必填字段存在 (task_id, status, summary)

用法:
  python scripts/audit_execution_log.py [--path <jsonl_path>]

退出码: 0=全部合规, 1=有错误
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED_FIELDS = ["ts", "task_id", "status", "summary"]


def audit_jsonl(path: Path) -> tuple[int, list[str]]:
    errors: list[str] = []
    total = 0
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            total += 1
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as e:
                errors.append(f"  L{lineno}: JSON 解析失败 — {e}")
                continue
            # Z-suffix
            ts = rec.get("ts", "")
            if ts and not ts.endswith("Z"):
                errors.append(f"  L{lineno}: ts={ts!r} 缺 Z 后缀")
            # 必填字段
            for field in REQUIRED_FIELDS:
                if field not in rec:
                    errors.append(f"  L{lineno}: 缺必填字段 {field!r}")
    return total, errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit executor execution_log.jsonl")
    parser.add_argument(
        "--path",
        type=Path,
        default=Path.home() / "runtime" / "execution_log.jsonl",
        help="execution_log.jsonl 路径 (默认 ~/runtime/execution_log.jsonl)",
    )
    args = parser.parse_args()

    if not args.path.exists():
        print(f"ℹ️  {args.path} 不存在 (executor 未运行或无执行记录)")
        return 0

    total, errors = audit_jsonl(args.path)
    print(f"📋 audit {args.path}: {total} records")
    if errors:
        print("❌ 发现问题:")
        for e in errors:
            print(e)
        return 1
    print("✅ 全部合规 (Z-suffix + 必填字段 OK)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
