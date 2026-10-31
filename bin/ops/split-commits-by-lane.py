#!/usr/bin/env python3
"""把混 lane 的 commit 按 lane 拆成多个单 lane commit (历史欠账消化工具)。

**背景**: lane 隔离规则「每 commit 单 lane」(ADR-0122 §46) 在 2026-10-30 之前从未真正
生效过 (三条执行路径全空转), 期间 main 上积累了 53 个混 lane 的 commit。规则接上后
(PR #4979 CI / #4980 pre-commit / #4981 pre-push), 新提交会被正确拦住, 但**历史欠账
仍在 git 历史里** —— 而 main 历史是 squash 合并的, 每个 squash commit = 一个 PR 的全部内容。

**为什么 pre-push 拦不住历史欠账**: push 范围从 `merge-base(origin/<branch>, local_sha)`
起算 —— 历史 commit 在 merge-base **之前**, 不在范围内 (实测: 一个基于 30 个 commit 前
main 的 stale 分支, 加一个新 commit 后 push 范围只有 1 个 commit)。所以历史欠账不会
挡住 push, 但它让 main 历史本身持续混 lane。

**本工具做什么**: 把一个混 lane 的 commit 拆成 N 个 commit, 每个只含一个 lane 的文件。

**关键不变量 (逐字节等价)**:
1. **树 sha 必须与原 commit 完全相同** —— 拆分只是重新分组, 不改任何文件内容。
   实测踩过的坑: `git update-index --cacheinfo` 若写死 mode `100644`, 会把可执行脚本
   (`100755`) 降级为不可执行 ⇒ 树不等价。**必须用 `git ls-tree` 读原 commit 里的真实
   mode**。
2. **commit message 必须保留原 PR 号** —— 本仓 120/120 个 commit message 都带
   `(#NNNN)`, 拆分后必须仍在 (可追溯性是 squash 历史的唯一索引)。
3. **作者与日期必须保留** —— 拆出来的 commit 是同一个人的同一份工作。

**用法**:
    # 预览 (不写任何东西)
    python3 bin/ops/split-commits-by-lane.py --from <sha> --dry-run

    # 实际改写: 产出新 tip 到 stdout, 原分支不动
    python3 bin/ops/split-commits-by-lane.py --from <sha> --to-ref refs/heads/split-result

**范围**: 默认只处理「从 --from 到 HEAD」区间的 commit。
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
CHANGE_LANE_CHECK = WORKSPACE / "bin" / "change-lane-check.py"


def _load_change_lane_check():
    spec = importlib.util.spec_from_file_location("change_lane_check", str(CHANGE_LANE_CHECK))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["change_lane_check"] = module
    spec.loader.exec_module(module)
    return module


def git(*args: str, env: dict | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=WORKSPACE,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} 失败: {(result.stderr or result.stdout).strip()[:300]}"
        )
    return result.stdout


def commit_files(sha: str) -> list[str]:
    out = git("show", "--name-only", "--format=", sha)
    return [line.strip() for line in out.splitlines() if line.strip()]


def lane_groups(sha: str, clc) -> dict[str, list[str]]:
    """该 commit 的文件按 lane 分组 (组内保持原有相对顺序)。"""
    submodules = clc.submodule_paths()
    groups: dict[str, list[str]] = {}
    for path in commit_files(sha):
        groups.setdefault(clc.classify(path, submodules), []).append(path)
    return groups


def split_commit(
    sha: str,
    groups: dict[str, list[str]],
    message: str,
    parent: str,
) -> list[str]:
    """把一个 commit 拆成多个单 lane commit, 返回新 commit sha 列表 (按原顺序)。

    parent 是**当前链上的父 commit** (不是原 commit 的父) —— 改写历史时每个 commit
    都必须在新链上重建, 否则链会断 (后续 commit 的 parent 指向旧历史 ⇒ 改写失效)。
    """
    # 作者/日期/committer 从原 commit 取 —— 拆出来的 commit 是同一份工作
    author = git("log", "-1", "--format=%an%n%ae%n%aI", sha).strip().splitlines()
    tree = parent
    created: list[str] = []
    for lane, paths in groups.items():
        index_file = str(WORKSPACE / f".git/lane-split-index-{lane.replace('/', '_')}")
        if os.path.exists(index_file):
            os.remove(index_file)
        env = dict(os.environ)
        env["GIT_INDEX_FILE"] = index_file
        try:
            git("read-tree", tree, env=env)
            for path in paths:
                # 必须读原 commit 里的真实 mode (100644/100755): 写死 100644 会把
                # 可执行脚本降级为不可执行 ⇒ 拆分后的树与原树不等价 (实测踩过)
                entry = git("ls-tree", sha, "--", path).split()
                if len(entry) < 3:
                    # 该文件在原 commit 的树里**不存在** ⇒ 这是一次「删除」
                    # (`git show --name-only` 会把被删的文件也列进来)。
                    # 删除必须落到**它实际被删掉的那个 lane 组**里, 否则中间状态的树
                    # 会残留该文件 ⇒ 拆分后的最终树与原树不等价 (实测 3 个 commit
                    # 命中: constraint-validation.yml / cross-deps-enforce.yml /
                    # bos-metrics.jsonl)。
                    git("update-index", "--force-remove", path, env=env)
                    continue
                mode, blob = entry[0], entry[2]
                git("update-index", "--add", "--cacheinfo", mode, blob, path, env=env)
            new_tree = git("write-tree", env=env).strip()
            body = (
                f"{message.strip()}\n\n"
                f"[lane-split] 本 commit 由 lane 拆分工具从 {sha[:9]} 拆出: "
                f"本提交只含 {lane} lane 的文件 ({len(paths)} 个)。\n"
                f"拆分理由: lane 隔离规则「每 commit 单 lane」(ADR-0122 §46)。\n"
                f"内容与拆分前逐字节等价 (树 sha 不变)。"
            )
            new_commit = git(
                "commit-tree",
                new_tree,
                "-p",
                tree,
                "-m",
                body,
                env={
                    **env,
                    "GIT_AUTHOR_NAME": author[0],
                    "GIT_AUTHOR_EMAIL": author[1],
                    "GIT_AUTHOR_DATE": author[2],
                    "GIT_COMMITTER_NAME": author[0],
                    "GIT_COMMITTER_EMAIL": author[1],
                },
            ).strip()
        finally:
            if os.path.exists(index_file):
                os.remove(index_file)
        created.append(new_commit)
        tree = new_commit
    return created


def rebuild_commit(sha: str, parent: str) -> str:
    """把一个**合规** commit 在新链上重建 (内容等价, 只换 parent)。

    改写历史时, 合规 commit 也必须重建 —— 否则它仍指向旧历史里的 parent,
    链会断成两截 (实测: 直接 `tree = sha` 导致改写后区间只剩 120 个 commit
    而非 272 个, 且旧违规 commit 原样留在链上)。
    """
    tree = git("rev-parse", f"{sha}^{{tree}}").strip()
    message = git("log", "-1", "--format=%B", sha).strip()
    author = git("log", "-1", "--format=%an%n%ae%n%aI", sha).strip().splitlines()
    return git(
        "commit-tree",
        tree,
        "-p",
        parent,
        "-m",
        message,
        env={
            "GIT_AUTHOR_NAME": author[0],
            "GIT_AUTHOR_EMAIL": author[1],
            "GIT_AUTHOR_DATE": author[2],
            "GIT_COMMITTER_NAME": author[0],
            "GIT_COMMITTER_EMAIL": author[1],
        },
    ).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from", dest="from_sha", required=True, help="区间的最早 commit (含)")
    parser.add_argument("--to", dest="to_sha", default="HEAD", help="区间的最晚 commit (含), 默认 HEAD")
    parser.add_argument("--to-ref", default="", help="把结果写到该 ref (不写则只打印)")
    parser.add_argument("--dry-run", action="store_true", help="只报告, 不构造任何 commit")
    parser.add_argument("--json", action="store_true", help="机器可读输出")
    args = parser.parse_args()

    clc = _load_change_lane_check()

    # 区间内的 commit (旧 → 新)
    rev = git("rev-list", "--reverse", f"{args.from_sha}..{args.to_sha}").strip().splitlines()
    boundary = git("rev-parse", args.from_sha).strip()
    ordered = [boundary] + [line.strip() for line in rev]
    # 链起点是**边界 commit 的父** —— 边界 commit 自己也要被处理 (它同样可能混 lane)。
    # 早先把它当链起点 ⇒ 边界 commit 自身未被拆分, 改写后仍留一个违规 commit (实测)。
    chain_start = git("rev-parse", f"{boundary}^").strip()

    report = {
        "range": f"{args.from_sha}..{args.to_sha}",
        "commits_in_range": len(ordered),
        "chain_start": chain_start,
        "split_commits": [],
        "kept_commits": [],
        "new_tip": None,
        "original_tip": git("rev-parse", args.to_sha).strip(),
        "original_tree": git("rev-parse", f"{args.to_sha}^{{tree}}").strip(),
    }

    tree = chain_start
    for sha in ordered:
        groups = lane_groups(sha, clc)
        if len(groups) <= 1:
            report["kept_commits"].append(sha)
            if args.dry_run:
                continue
            # 合规 commit 也要在**新链上重建** —— 见 rebuild_commit 的 docstring。
            tree = rebuild_commit(sha, tree)
            continue
        if args.dry_run:
            report["split_commits"].append(
                {"commit": sha, "lanes": sorted(groups), "groups": {k: len(v) for k, v in groups.items()}}
            )
            continue
        message = git("log", "-1", "--format=%B", sha).strip()
        created = split_commit(sha, groups, message, parent=tree)
        report["split_commits"].append(
            {"commit": sha, "lanes": sorted(groups), "new_commits": created}
        )
        tree = created[-1]

    report["new_tip"] = tree
    report["new_tree"] = git("rev-parse", f"{tree}^{{tree}}").strip()
    report["tree_equivalent"] = report["new_tree"] == report["original_tree"]

    if args.to_ref and not args.dry_run:
        git("update-ref", args.to_ref, tree)
        report["written_ref"] = args.to_ref

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"区间 {report['range']}: {report['commits_in_range']} 个 commit")
        print(f"  需拆分: {len(report['split_commits'])} | 保持原样: {len(report['kept_commits'])}")
        for item in report["split_commits"]:
            print(f"    {item['commit'][:9]}: {len(item['lanes'])} lane -> {item['lanes']}")
        print(f"  新 tip: {report['new_tip']}")
        print(f"  树等价: {report['tree_equivalent']} ({report['new_tree'][:12]} vs {report['original_tree'][:12]})")
        if args.to_ref and not args.dry_run:
            print(f"  已写入 ref: {args.to_ref}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
