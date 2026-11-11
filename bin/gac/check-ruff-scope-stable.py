#!/usr/bin/env python3
"""CR-RUFF-SCOPE-STABLE: 验证 ruff scope 未漂移。

ADR-0388: ruff-check.yml 已删除 (并入 quality.yml ruff-lint, G16 完整落地).
检查 .github/workflows/quality.yml 中 ruff-lint job 的 src 参数是否保持有界范围,
防止 X-Plane 项目意外扩展 ruff 检查面导致 lint 面漂移.

预期: src 参数非空、非 null、非全仓覆盖 (如 "." 或 "").
"""

import re
import sys
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[2] / ".github/workflows/quality.yml"


def main() -> int:
    if not WORKFLOW.is_file():
        print(f"FAIL quality.yml not found: {WORKFLOW}")
        return 1

    text = WORKFLOW.read_text(encoding="utf-8")

    # 只锚定 ruff-lint job 内的 src —— 全文首个 `src:` 可能落在别的 job 里
    # (判据自述就是「ruff-lint job 的 src 参数」, 实现必须真的限定在那个块内)。
    m_job = re.search(r"^  ruff-lint:[ \t]*$(.*?)(?=^  \S|\Z)", text, re.MULTILINE | re.DOTALL)
    if not m_job:
        print("FAIL 未找到 quality.yml 的 ruff-lint job")
        return 1

    match = re.search(r'^\s+src:\s*["\']?(.+?)["\']?\s*$', m_job.group(1), re.MULTILINE)
    if not match:
        print("FAIL 未找到 ruff-lint job 内的 src 参数")
        return 1

    scope = match.group(1).strip()

    # 无效范围检查
    invalid_scopes = {"", ".", "./", "src", "projects", "..."}
    if scope in invalid_scopes:
        print(f"FAIL ruff scope 为无界值 '{scope}', 可能包含全仓")
        return 1

    print(f"OK ruff scope 稳定: '{scope}'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
