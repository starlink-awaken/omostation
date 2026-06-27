#!/usr/bin/env python3
"""gac-hygiene-check — 工作区卫生检查 (GaC CR-HYG-01/02, 报告债务③防复发).

CR-HYG-01: 0 字节文件检查 (防空文件污染仓库)
CR-HYG-02: 大小写 inode 一致 (防 APFS case-insensitive plan/Plans 混淆)

默认只查 git tracked 文件 (最精确, 防扫未跟踪临时文件); git 不可用时降级全扫.

用法:
  python3 bin/gac-hygiene-check.py           # 检测, 有问题返回 1
  python3 bin/gac-hygiene-check.py --json    # 机器可读 JSON (gac-healthcheck 消费)

退出码:
  0 = 通过 (0 卫生问题)
  1 = 有卫生问题 (0 字节文件 / 大小写冲突)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

# CR-HYG-01 跳过后缀 (运行时锁/并发占位, 0 字节是设计而非污染)
# 不混淆范畴: 检查器只抓"空源文件" bug, 运行时锁另算 git 卫生问题
SKIP_SUFFIXES = {".lock", ".lockfile", ".pid"}

# 排除目录 (降级全扫时的噪声过滤; git tracked 模式不需要)
EXCLUDE_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    ".mypy_cache", ".ruff_cache", ".pytest_cache", ".tox",
    ".eggs", "dist", "build", ".omc",  # .omc 是运行时 cache (报告债务②), 非源文件
    "_archived", "archive",
}


def is_excluded(path: Path) -> bool:
    """路径是否落在排除目录下 (降级全扫时用)."""
    for part in path.relative_to(WORKSPACE_ROOT).parts[:-1]:
        if part in EXCLUDE_DIRS:
            return True
    return False


def git_tracked_files() -> set[str] | None:
    """返回 git tracked 文件集合 (失败返回 None, 调用方降级全扫)."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=WORKSPACE_ROOT,
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            return set(result.stdout.splitlines())
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        pass
    return None


def find_zero_byte_files(tracked: set[str] | None) -> list[Path]:
    """CR-HYG-01: 找 0 字节文件 (空文件本身就是异常, KISS 全扫)."""
    findings: list[Path] = []

    def check(fp: Path):
        if not fp.is_file():
            return
        if fp.suffix in SKIP_SUFFIXES:
            return  # 运行时锁/占位 (0 字节是设计, 非污染)
        if tracked is None and is_excluded(fp):
            return
        try:
            if fp.stat().st_size == 0:
                findings.append(fp)
        except OSError:
            pass

    if tracked is not None:
        for rel in tracked:
            check(WORKSPACE_ROOT / rel)
    else:
        for fp in WORKSPACE_ROOT.rglob("*"):
            check(fp)
    return findings


def find_case_conflicts(tracked: set[str] | None) -> list[tuple[Path, Path]]:
    """CR-HYG-02: 找同目录下仅大小写不同的文件名 (APFS case-insensitive 风险).

    返回 [(path_a, path_b), ...] 相邻冲突对 (排序稳定).
    """
    by_dir: dict[Path, dict[str, list[Path]]] = {}

    def collect(fp: Path):
        if not fp.is_file():
            return
        if tracked is None and is_excluded(fp):
            return
        parent = fp.parent
        name_lower = fp.name.lower()
        by_dir.setdefault(parent, {}).setdefault(name_lower, []).append(fp)

    if tracked is not None:
        for rel in tracked:
            collect(WORKSPACE_ROOT / rel)
    else:
        for fp in WORKSPACE_ROOT.rglob("*"):
            collect(fp)

    conflicts: list[tuple[Path, Path]] = []
    for name_map in by_dir.values():
        for paths in name_map.values():
            if len(paths) < 2:
                continue
            # 只报真实大小写差异 (排除完全同名的 glob 重复)
            if len({p.name for p in paths}) < 2:
                continue
            sorted_paths = sorted(paths, key=lambda p: p.name)
            for i in range(len(sorted_paths) - 1):
                conflicts.append((sorted_paths[i], sorted_paths[i + 1]))
    return conflicts


def run_check(as_json: bool = False) -> int:
    """运行卫生检查. 返回 0 (通过) 或 1 (有问题)."""
    tracked = git_tracked_files()
    zero_byte = find_zero_byte_files(tracked)
    case_conflicts = find_case_conflicts(tracked)
    total_issues = len(zero_byte) + len(case_conflicts)

    if as_json:
        payload = {
            "ok": total_issues == 0,
            "issues": total_issues,
            "zero_byte_count": len(zero_byte),
            "case_conflict_count": len(case_conflicts),
            "zero_byte_files": [str(fp.relative_to(WORKSPACE_ROOT)) for fp in zero_byte],
            "case_conflicts": [
                {
                    "a": str(a.relative_to(WORKSPACE_ROOT)),
                    "b": str(b.relative_to(WORKSPACE_ROOT)),
                }
                for a, b in case_conflicts
            ],
            "tracked_mode": tracked is not None,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if payload["ok"] else 1

    # 人类可读报告
    if zero_byte:
        print(f"❌ CR-HYG-01: 检测到 {len(zero_byte)} 个 0 字节文件 (空文件污染):\n")
        for fp in zero_byte[:20]:
            print(f"  {fp.relative_to(WORKSPACE_ROOT)}")
        if len(zero_byte) > 20:
            print(f"  ... 还有 {len(zero_byte) - 20} 个")
        print()

    if case_conflicts:
        print(f"❌ CR-HYG-02: 检测到 {len(case_conflicts)} 对大小写 inode 冲突 (APFS 风险):\n")
        for a, b in case_conflicts[:20]:
            print(f"  {a.relative_to(WORKSPACE_ROOT)}  vs  {b.relative_to(WORKSPACE_ROOT)}")
        if len(case_conflicts) > 20:
            print(f"  ... 还有 {len(case_conflicts) - 20} 对")
        print()

    if total_issues == 0:
        mode = "git tracked" if tracked is not None else "全扫 (降级)"
        print(f"✅ 工作区卫生检查通过 ({mode}, 0 问题)")
        return 0

    print("修复方式: 删除 0 字节文件 / 重命名大小写冲突文件")
    return 1


def main():
    parser = argparse.ArgumentParser(description="工作区卫生检查 (GaC CR-HYG-01/02)")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON (gac-healthcheck 消费)")
    args = parser.parse_args()
    return run_check(as_json=args.json)


if __name__ == "__main__":
    sys.exit(main())
