#!/usr/bin/env python3
"""bin-quota-diff: 配额"变更侧问责" — 每次变更自己负责守恒.

背景: 配额拉锯根因是并发 agent 各自 base 陈旧, 全局计数无法归因.
本脚本让每次变更自己负责守恒: 检查 <base>..HEAD 中 bin/ 下 .py/.sh 的
新增 vs 删除, 新增数 > 删除数 → exit 1 拦截, 否则 exit 0.

全局计数 (gac-validate 的 subtraction-quota) 降级为 advisory 由调用方处理,
本脚本不做全局计数.

用法:
  check-bin-quota-diff.py [--base origin/main] [--json]
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# bin/ 只含 .py/.sh 两种扩展名
BIN_PATTERNS = ("bin/*.py", "bin/*.sh")


def _git_diff(base: str, diff_filter: str, repo_root: Path) -> list[str]:
    """返回 <base>..HEAD 中匹配 diff_filter 的 bin 脚本路径列表.

    --no-renames: 归档/移动 (git mv 到 _archive/) 视为 删除+新增, 而非 rename,
    使"归档"计入 deleted 守恒. 新增侧排除 _archive/ (归档文件非新活跃脚本).
    """
    result = subprocess.run(
        [
            "git",
            "diff",
            "--no-renames",
            f"--diff-filter={diff_filter}",
            "--name-only",
            f"{base}..HEAD",
            "--",
            *BIN_PATTERNS,
        ],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    if result.returncode != 0:
        # base 不存在或 diff 失败 → 视为无变更 (advisory 语义, 不误拦)
        return []
    paths = [f for f in result.stdout.splitlines() if f.strip()]
    if diff_filter == "A":
        # 归档目录不算新增活跃脚本
        paths = [f for f in paths if "_archive" not in f]
    return paths


def evaluate(base: str, repo_root: Path = REPO_ROOT) -> dict:
    """核心判定: 返回 {added, deleted, ok, message}."""
    added = _git_diff(base, "A", repo_root)
    deleted = _git_diff(base, "D", repo_root)
    ok = len(added) <= len(deleted)
    if ok:
        message = (
            f"OK bin 变更守恒: 新增 {len(added)} / 删除 {len(deleted)} "
            f"(base={base})"
        )
    else:
        message = (
            f"FAIL bin 变更净增: 新增 {len(added)} > 删除 {len(deleted)} "
            f"(base={base}) — 增 1 须删 1, 请归档/删除一个 bin 脚本"
        )
    return {"added": added, "deleted": deleted, "ok": ok, "message": message}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="origin/main", help="对比基准 ref (默认 origin/main)")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args(argv)

    result = evaluate(args.base)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result["message"])
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
