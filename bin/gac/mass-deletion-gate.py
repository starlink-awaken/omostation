#!/usr/bin/env python3
"""批量删除闸门 — 拦住"工作树被清空后 git add -A"这类事故。

背景 (2026-08-08): agora 子模块的 origin/main 被一个 commit 清空 —— 378 个
文件全删, 远端树变成 0 文件。机制不是某个"清理脚本"写错, 而是:

    worktree 里的子模块工作树被 rm -rf / partial init 清空
      → 后续 `git add -A` 把"文件消失"如实记录成删除
      → commit + push, 远端整仓归零

这类事故的共性是**删除量异常**, 与哪个脚本触发无关。所以这里不去修某一个
调用点, 而是在 commit/push 前做一次量级检查。

判定 (任一命中即 block):
  - 删除数 >= abs_floor(默认 30) 且 删除占比 >= ratio(默认 0.5)
  - 删除占比 >= 0.9 (无论绝对数, 覆盖小仓)
  - 删除后剩余文件数 == 0 (整仓归零, 永远拦)

逃生口: MASS_DELETION_OK=1 环境变量, 或 --allow。会在输出里明确记录。
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

# hook 环境下 git 会设这些, 泄漏到 subprocess 会让 `git -C <submodule>` 读错仓
for _env in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_QUARANTINE_PATH"):
    os.environ.pop(_env, None)


def run(args: list[str], cwd: str | None = None) -> str:
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


def counts_staged(cwd: str | None) -> tuple[int, int, list[str]]:
    """已暂存的删除数, 删除前的跟踪文件总数, 样例。"""
    out = run(["git", "diff", "--cached", "--name-status", "--diff-filter=D"], cwd)
    dels = [ln.split("\t", 1)[1] for ln in out.splitlines() if "\t" in ln]
    total = len(run(["git", "ls-files"], cwd).splitlines())
    # ls-files 反映 index(已删的不在里面), 所以总数 = 现存 + 删除
    return len(dels), total + len(dels), dels[:5]


def counts_range(base: str, head: str, cwd: str | None) -> tuple[int, int, list[str]]:
    out = run(["git", "diff", "--name-status", "--diff-filter=D", base, head], cwd)
    dels = [ln.split("\t", 1)[1] for ln in out.splitlines() if "\t" in ln]
    total = len(run(["git", "ls-tree", "-r", base, "--name-only"], cwd).splitlines())
    return len(dels), total, dels[:5]


def submodule_paths(cwd: str | None) -> list[str]:
    out = run(["git", "config", "--file", ".gitmodules", "--get-regexp", r"^submodule\..*\.path$"], cwd)
    return [ln.split(maxsplit=1)[1] for ln in out.splitlines() if ln.strip()]


def gitlink(ref: str, path: str, cwd: str | None) -> str | None:
    out = run(["git", "ls-tree", ref, "--", path], cwd)
    if not out.strip():
        return None
    meta = out.partition("\t")[0].split()
    return meta[2] if len(meta) >= 3 and meta[0] == "160000" else None


def tree_size(sub_dir: str, sha: str) -> int | None:
    """子模块某 commit 的文件数; 对象不在本地则 None(不误判)。"""
    if not subprocess.run(
        ["git", "cat-file", "-e", f"{sha}^{{commit}}"], cwd=sub_dir,
        capture_output=True,
    ).returncode == 0:
        return None
    return len(run(["git", "ls-tree", "-r", sha, "--name-only"], sub_dir).splitlines())


def check_submodule_bumps(base: str, head: str, cwd: str | None, ratio: float) -> list[str]:
    """拦住"把 gitlink 指向一个被清空的子模块 commit"。

    2026-08-08 事故里, 根仓 39f01b90c 就是这样把 agora 指向了 0 文件的 commit。
    只在两端对象都能本地解析时判定, 解析不了一律放过 —— 宁可漏, 不可拦错。
    """
    findings: list[str] = []
    root = cwd or "."
    for p in submodule_paths(cwd):
        old, new = gitlink(base, p, cwd), gitlink(head, p, cwd)
        if not old or not new or old == new:
            continue
        sub = f"{root}/{p}"
        o, n = tree_size(sub, old), tree_size(sub, new)
        if o is None or n is None or o == 0:
            continue
        if n == 0:
            findings.append(f"{p}: gitlink 指向空仓 commit {new[:10]} (原 {o} 文件 → 0)")
        elif (o - n) / o >= ratio:
            findings.append(
                f"{p}: gitlink 指向的 commit 文件数骤降 {o} → {n} "
                f"(-{(o - n) / o:.0%}) {old[:10]}→{new[:10]}"
            )
    return findings


def verdict(dels: int, total: int, abs_floor: int, ratio: float) -> tuple[bool, str]:
    if dels == 0:
        return False, ""
    remaining = total - dels
    pct = dels / total if total else 0.0
    if remaining == 0 and total > 0:
        return True, f"整仓归零: 删除全部 {dels} 个跟踪文件, 提交后仓库将为空"
    if pct >= 0.9:
        return True, f"删除占比 {pct:.0%} ({dels}/{total}) — 超过 90% 阈值"
    if dels >= abs_floor and pct >= ratio:
        return True, f"删除 {dels} 个文件, 占跟踪文件 {pct:.0%} — 超过 {abs_floor} 个且 {ratio:.0%} 双阈值"
    return False, ""


def main() -> int:
    ap = argparse.ArgumentParser(description="拦截异常批量删除")
    ap.add_argument("--staged", action="store_true", help="检查已暂存改动 (pre-commit)")
    ap.add_argument("--range", nargs=2, metavar=("BASE", "HEAD"), help="检查提交区间 (pre-push)")
    ap.add_argument("--cwd", help="在指定仓库目录检查")
    ap.add_argument("--abs-floor", type=int, default=30)
    ap.add_argument("--ratio", type=float, default=0.5)
    ap.add_argument("--submodules", action="store_true",
                    help="额外检查 gitlink 是否被指向被清空的子模块 commit")
    ap.add_argument("--allow", action="store_true", help="仅告警不拦截")
    args = ap.parse_args()

    if args.range:
        dels, total, sample = counts_range(args.range[0], args.range[1], args.cwd)
        scope = f"{args.range[0][:10]}..{args.range[1][:10]}"
    else:
        dels, total, sample = counts_staged(args.cwd)
        scope = "staged"

    sub_findings: list[str] = []
    if args.submodules and args.range:
        sub_findings = check_submodule_bumps(args.range[0], args.range[1], args.cwd, args.ratio)

    blocked, why = verdict(dels, total, args.abs_floor, args.ratio)
    if not blocked and not sub_findings:
        if dels:
            print(f"mass-deletion-gate: OK ({dels} 删除 / {total} 跟踪, {scope})")
        return 0

    if sub_findings and not blocked:
        allow = args.allow or os.environ.get("MASS_DELETION_OK") == "1"
        icon = "⚠️ " if allow else "🛑"
        print(f"\n{icon} mass-deletion-gate: 子模块 gitlink 指向缩水的 commit", file=sys.stderr)
        for s in sub_findings:
            print(f"   - {s}", file=sys.stderr)
        if allow:
            print("   已通过 MASS_DELETION_OK=1 放行。\n", file=sys.stderr)
            return 0
        print(
            "\n   子模块远端可能已被误清空。先在该子模块里核对 `git log` 与文件数,\n"
            "   不要把这个 gitlink 推上去 —— 它会把清空状态固化进主仓历史。\n",
            file=sys.stderr,
        )
        return 1

    allow = args.allow or os.environ.get("MASS_DELETION_OK") == "1"
    icon = "⚠️ " if allow else "🛑"
    print(f"\n{icon} mass-deletion-gate: {why}", file=sys.stderr)
    print(f"   范围: {scope}", file=sys.stderr)
    for f in sample:
        print(f"   - {f}", file=sys.stderr)
    if dels > len(sample):
        print(f"   ... 另有 {dels - len(sample)} 个", file=sys.stderr)
    if allow:
        print("   已通过 MASS_DELETION_OK=1 放行 — 请确认这确实是有意为之。\n", file=sys.stderr)
        return 0
    print(
        "\n   这通常意味着工作树被清空 (rm -rf / 子模块未 init / partial worktree),\n"
        "   而不是你真的想删这些文件。先确认 `git status` 与磁盘内容。\n"
        "   确属有意: MASS_DELETION_OK=1 git commit ...\n",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
