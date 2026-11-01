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
4. **中间 commit 不得是「半份镜像」** —— 拆分产出的每个中间 commit 都是一个**真实
   存在过**的树, 不是原 commit 的别名。若某 commit 同时「登记某文件」与「新增该文件」,
   而登记方先落地, 中间态就指向仓内**尚不存在**的文件 —— 仓内 AGENTS.md §7 明令
   禁止 (「不许写半份镜像」)。故组必须**按引用完整性**排序: 被引用的组先落地。
   实测 (2026-10-31, mbp): 按字母序拆 `fix/collectors-host-managed-20261016` 会产出
   `missing_repo_copy=2` 的中间态; 按引用完整性排序后全为 0。详见
   `order_groups_by_reference` 的 docstring。

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
import re
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


def git_optional(*args: str) -> str:
    """跑 git, 失败返回空串 (不抛)。

    用于「失败是正常结果」的场景: 如 `cat-file -p <sha>:<path>` 在该文件
    已被删除的 commit 上本就取不到内容 —— 那不是错误, 只是没有内容可引用。
    """
    result = subprocess.run(
        ["git", *args],
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return ""
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


# 组间「引用完整性」判据用的词边界: 文件名两侧不得再接 [A-Za-z0-9_.-]。
# 为什么需要边界: `collectors.base.py.asset` 里**包含** `base.py.asset` 子串 ——
# 无边界匹配会让「引用 base.py.asset」误判成「引用 collectors.base.py.asset」
# => 造出假的依赖边 => 组顺序被错误地重排。
_NAME_BOUNDARY = r"(?<![A-Za-z0-9_.-])"
_NAME_BOUNDARY_END = r"(?![A-Za-z0-9_.-])"

# 作为「引用」判据的最小文件名长度 (实测定的, 见 _file_references)。
_MIN_REFERENCE_NAME_LEN = 6


def _file_references(text: str, filename: str) -> bool:
    """text 里是否**按文件名**引用了 filename (词边界, 精确匹配)。

    判据用**文件名**而不是完整路径: 引用方常写相对路径或裸文件名
    (如 HOST_FILES 里写 "collectors.orca.py.asset", 而文件在
    bin/panorama/assets/host/ 下) => 按完整仓内路径匹配会漏掉真正的引用。
    """
    if not filename or len(filename) < _MIN_REFERENCE_NAME_LEN:
        # 太短的名字极易误命中普通单词/散文里的举例 => 不作为依赖判据。
        # 阈值 6 是**实测**定的: 全仓最短的带扩展名文件名是 6 字符 (bos.md / cli.py /
        # dag.md / sla.md), 而 4 字符的名字 (a.py / x.py) 在仓内分别出现于 13 / 51 个
        # 文件 —— 作为依赖判据只会造出大量假边。
        return False
    pattern = _NAME_BOUNDARY + re.escape(filename) + _NAME_BOUNDARY_END
    return re.search(pattern, text) is not None


def order_groups_by_reference(
    sha: str,
    groups: dict[str, list[str]],
) -> dict[str, list[str]]:
    """按**引用完整性**给组排序: 被引用的组先落地。

    **为什么必须排** (2026-10-31 实锤): 拆分后的每个中间 commit 都是一个**真实存在
    过**的树, 不是原 commit 的别名。若某个 commit 同时「登记某文件」与「新增该文件」,
    而**登记方先落地**, 中间态就是**半份镜像** —— 登记项指向仓内**尚不存在**的文件。

    仓内 AGENTS.md §7 明令禁止这个形态 (「不许写半份镜像」; T265 条目: 「只改一处
    就是『不许写半份镜像』的同形错误」)。

    实测 (mbp, fix/collectors-host-managed-20261016): `zhixing-host-sync.py` 的
    HOST_FILES 登记项引用 `bin/panorama/assets/host/*.asset`。按**字母序**建组时
    `bin/gac/...` 排在 `bin/panorama/...` 之前 => 拆出的第一个 commit 是「先登记、
    后有文件」=> `zhixing-host-sync.status()` 读到 missing_repo_copy=2 (半份镜像)。
    按引用完整性排序后 (`other` 组先落), 5 个中间 commit 的 missing_repo_copy 全为 0。

    **判据**: 若组 A 的文件**内容**引用了组 B 里的某个文件名, 则 B 必须先于 A。
    用**词边界**匹配文件名而非完整路径 (引用方常写裸文件名/相对路径)。

    **排序稳定性**: 无依赖关系时保持原有相对顺序 (字母序); 有环 (A 引 B 且 B 引 A)
    时退化为原序的第一项 —— 不崩, 但结果不再保证引用完整性 (报告里会体现)。
    """
    lanes = list(groups.keys())
    if len(lanes) < 2:
        return groups

    # 每个组的文件内容 (取该 commit 里的内容 —— 拆出的中间态就是这些内容)
    contents: dict[str, list[str]] = {}
    for lane, paths in groups.items():
        parts = []
        for path in paths:
            # 文件在该 commit 里可能已被删除 => cat-file 失败, 跳过 (删除不构成引用)
            blob = git_optional("cat-file", "-p", sha + ":" + path)
            if blob:
                parts.append(blob)
        contents[lane] = parts

    return _order_by_reference(groups, contents)


def _order_by_reference(
    groups: dict[str, list[str]],
    contents: dict[str, list[str]],
) -> dict[str, list[str]]:
    """纯函数: 按引用完整性给组排序 (不读 git —— 内容由调用方给)。

    依赖边: 若组 A 的内容引用了组 B 里的某文件名, 则 B 必须先于 A 落地。
    拓扑排序: 稳定 (无依赖时保原序); 有环 (互引) 时取原序第一项, 不崩。
    """
    lanes = list(groups.keys())
    if len(lanes) < 2:
        return groups

    # 依赖边: B 必须在 A 之前 (A 的内容引用了 B 的文件)
    before: dict[str, set[str]] = {lane: set() for lane in lanes}
    for a in lanes:
        text = "\n".join(contents.get(a, []))
        for b in lanes:
            if a == b:
                continue
            for path in groups[b]:
                if _file_references(text, os.path.basename(path)):
                    before[a].add(b)
                    break

    # 拓扑排序 (稳定: 无依赖时保原序)
    ordered: list[str] = []
    remaining = list(lanes)
    while remaining:
        ready = [lane for lane in remaining if not (before[lane] & set(remaining))]
        if not ready:
            # 有环 (互引) => 退化: 取原序第一个, 保证不崩且结果确定
            ready = [remaining[0]]
        pick = next(lane for lane in remaining if lane in ready)
        ordered.append(pick)
        remaining.remove(pick)
    return {lane: groups[lane] for lane in ordered}


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
            ordered_groups = order_groups_by_reference(sha, groups)
            report["split_commits"].append(
                {
                    "commit": sha,
                    "lanes": sorted(groups),
                    "group_order": list(ordered_groups.keys()),
                    "groups": {k: len(v) for k, v in groups.items()},
                }
            )
            continue
        message = git("log", "-1", "--format=%B", sha).strip()
        # 按**引用完整性**重排组: 被引用的组先落地, 否则中间 commit 是「半份镜像」
        # (登记项指向仓内尚不存在的文件) —— 见 order_groups_by_reference 的 docstring。
        ordered_groups = order_groups_by_reference(sha, groups)
        created = split_commit(sha, ordered_groups, message, parent=tree)
        report["split_commits"].append(
            {
                "commit": sha,
                "lanes": sorted(groups),
                "group_order": list(ordered_groups.keys()),
                "new_commits": created,
            }
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
            order = item.get("group_order")
            order_str = f"  组序(按引用完整性)={order}" if order else ""
            print(
                f"    {item['commit'][:9]}: {len(item['lanes'])} lane -> "
                f"{item['lanes']}{order_str}"
            )
        print(f"  新 tip: {report['new_tip']}")
        print(f"  树等价: {report['tree_equivalent']} ({report['new_tree'][:12]} vs {report['original_tree'][:12]})")
        if args.to_ref and not args.dry_run:
            print(f"  已写入 ref: {args.to_ref}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
