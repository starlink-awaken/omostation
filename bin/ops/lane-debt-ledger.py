#!/usr/bin/env python3
"""生成 lane 隔离的欠账台账 (ADR-0122 §46 欠账显形面)。

**背景**: lane 隔离规则「每 commit 单 lane」(ADR-0122 §46) 在 2026-10-30 之前从未真正
生效过 —— 三条执行路径全空转:

1. **CI**: `sgf-policy.yaml` 登记 `bin/change-lane-check.py --staged`, 而 CI 干净检出里
   没有 staged 文件 => 读到空集 => 恒 PASS (实测 `PASS (0 files, lanes=-)`)。
2. **PUSH_RANGE 分支**: 按-push-commit-范围判定的分支在 `.githooks/` 里无导出点
   => 从未触发。
3. **pre-commit**: `hook-runner.sh` 的检查清单里没有它 => 从未触发。

规则接上后 (PR #4979 CI / #4980 pre-commit / #4981 pre-push) 新提交会被正确拦住。

**关键区分: main 上的「混 lane commit」不是欠账指标**。本仓全 squash 合并 => main 的
每个 commit = 一个 PR 的全部内容 => 一个跨多 lane 的 PR 必然产出「混 lane commit」。
那是 squash 的结构性产物, 改写它等于改写历史, 而 main 是受保护分支
(`allow_force_pushes: False` + `enforce_admins: True`), 且仓库明文决策「main 分支保护
已启用」+「squash merge 所有 main 变更」(docs/generated/architecture-deep-analysis.md
§17.2) —— pre-rebase hook 亦指明授权通道是 merge/PR 合流。改写需先解除保护, 那是
治理决策。工具 bin/ops/split-commits-by-lane.py 已就绪 (四项验证: 树/内容逐字节等价、
每 commit 单 lane、PR 号全保留), 待授权后可执行。

实测 (2026-10-31): 全历史 8198 个 commit 里 3939 个「混 lane」, 但最近 40 个 PR 里
**只有 18 个 commit 自身混 lane** (在 PR 分支上就是) —— 后者才是真正的提交形态缺陷。
逐 PR 登记需扫 `refs/pull/*`, 每个 PR 多次 git 调用 (4972 个 PR 跑 40 秒以上) => 成本
不适合做常规门禁, 本台账不逐 PR 登记; 专项排查时用 `git log --name-only` 扫 PR 分支的
`merge-base..head` 区间。

**本台账不被任何门禁消费** —— 纯记录面, 不是豁免 (做成豁免就成了新提交的逃逸口)。

**用法**:
    python3 bin/ops/lane-debt-ledger.py --check    # 校验台账内在自洽
    python3 bin/ops/lane-debt-ledger.py --write    # 重新生成台账
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
CHANGE_LANE_CHECK = WORKSPACE / "bin" / "change-lane-check.py"
LEDGER = WORKSPACE / ".omo" / "_truth" / "registry" / "lane-debt-ledger.yaml"

# 违规成因分类 —— 决定「这笔该由谁消化」
CAUSE_RULES = [
    ("classifier-gap-other", lambda ls: "other" in ls and len(ls) == 2 and "code" in ls),
    ("boundary-governance-registration", lambda ls: ls == {"governance_code", "governance_state"}),
    ("boundary-code-vs-governance-code", lambda ls: "code" in ls and "governance_code" in ls),
    ("boundary-code-vs-config", lambda ls: "code" in ls and "config" in ls),
    ("submodule-pointer-mixed", lambda ls: "submodule_pointer" in ls),
    ("multi-surface", lambda ls: True),
]


def _load_change_lane_check():
    spec = importlib.util.spec_from_file_location("change_lane_check", str(CHANGE_LANE_CHECK))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["change_lane_check"] = module
    spec.loader.exec_module(module)
    return module


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=WORKSPACE, capture_output=True, text=True, check=False
    )
    return result.stdout


def classify_cause(lanes: set[str]) -> str:
    for label, predicate in CAUSE_RULES:
        if predicate(lanes):
            return label
    return "unknown"


def scan_main_commits() -> list[dict]:
    """main 上每个 commit 的 lane 集合。

    **性能**: 单次 `git log --name-only` 解析全历史 (0.6s / 8198 commit); 分类靠
    change-lane-check 的 lru_cache —— 未缓存时 10 万次 YAML 解析跑不完 (实测踩过)。
    """
    clc = _load_change_lane_check()
    submodules = clc.submodule_paths()
    # 口径固定为 origin/main —— 否则数字随当前检出分支变化 (实测: 在 feature 分支上
    # 跑会少算/多算), 台账就没有可比性。origin/main 不存在时退回 HEAD。
    base = "origin/main" if _git("rev-parse", "--verify", "--quiet", "origin/main").strip() else "HEAD"
    raw = _git("log", base, "--format=%H", "--name-only")

    commits: list[tuple[str, list[str]]] = []
    current: list | None = None
    for line in raw.splitlines():
        s = line.strip()
        if not s:
            continue
        if len(s) == 40 and all(c in "0123456789abcdef" for c in s):
            if current is not None:
                commits.append((current[0], current[1]))
            current = [s, []]
        elif current is not None:
            current[1].append(s)
    if current is not None:
        commits.append((current[0], current[1]))

    out: list[dict] = []
    for sha, files in commits:
        if not files:
            continue
        lanes = sorted({clc.classify(p, submodules) for p in files})
        out.append({"commit": sha, "lanes": lanes, "files": len(files)})
    return out


def render(main_commits: list[dict]) -> str:
    main_mixed = [c for c in main_commits if len(c["lanes"]) > 1]
    cause_dist = Counter()
    for c in main_mixed:
        cause_dist[classify_cause(set(c["lanes"]))] += 1

    header = [
        "# lane 隔离欠账台账 (ADR-0122 §46) —— 生成面, 请勿手改",
        "#",
        "# 由 bin/ops/lane-debt-ledger.py 生成 (`--write` 重建, `--check` 校验)。",
        "#",
        "# **背景**: lane 隔离规则「每 commit 单 lane」(ADR-0122 §46) 在 2026-10-30 之前",
        "# 从未真正生效过 —— 三条执行路径全空转:",
        "#   1. CI: sgf-policy 登记 `--staged`, 干净检出无 staged 文件 => 读到空集 => 恒 PASS;",
        "#   2. PUSH_RANGE 分支: .githooks/ 无导出点 => 从未触发;",
        "#   3. pre-commit: hook-runner 的检查清单里没有它 => 从未触发。",
        "# 规则接上后 (PR #4979 CI / #4980 pre-commit / #4981 pre-push) 新提交会被正确拦住。",
        "#",
        "# **关键区分: main 上的「混 lane commit」不是欠账指标**。本仓全 squash 合并 => main 的",
        "# 每个 commit = 一个 PR 的全部内容 => 一个跨多 lane 的 PR 必然产出「混 lane commit」。",
        "# 那是 squash 的结构性产物, 改写它等于改写历史, 而 main 是受保护分支",
        "# (allow_force_pushes: False + enforce_admins: True), 且仓库明文决策「main 分支保护",
        "# 已启用」+「squash merge 所有 main 变更」(docs/generated/architecture-deep-analysis.md",
        "# §17.2) —— pre-rebase hook 亦指明授权通道是 merge/PR 合流。改写需先解除保护, 那是",
        "# 治理决策。工具 bin/ops/split-commits-by-lane.py 已就绪 (四项验证: 树/内容逐字节",
        "# 等价、每 commit 单 lane、PR 号全保留), 待授权后可执行。",
        "#",
        "# 实测 (2026-10-31): 全历史 8198 个 commit 里 3939 个「混 lane」, 但最近 40 个 PR 里",
        "# **只有 18 个 commit 自身混 lane** (在 PR 分支上就是) —— 后者才是真正的提交形态缺陷。",
        "# 逐 PR 登记需扫 refs/pull/* (每个 PR 多次 git 调用, 4972 个 PR 跑 40 秒以上) => 成本",
        "# 不适合做常规门禁, 本台账不逐 PR 登记; 专项排查时用 `git log --name-only` 扫 PR 分支的",
        "# merge-base..head 区间。",
        "#",
        "# 本台账**不被任何门禁消费** —— 纯记录面, 不是豁免 (做成豁免就成了新提交的逃逸口)。",
        "",
        "version: 3",
        "ssot_ref: ADR-0122-lane-debt",
        "generated_by: bin/ops/lane-debt-ledger.py",
        "advisory_only: true  # 纯记录面, 不被门禁消费, 不构成任何豁免",
        "",
        "main_commits_total: {}".format(len(main_commits)),
        "main_commits_mixed_lane: {}  # squash 结构性产物, 非欠账指标".format(len(main_mixed)),
        "mixed_lane_causes:",
    ]
    for cause, count in sorted(cause_dist.items(), key=lambda kv: (-kv[1], kv[0])):
        header.append("  {}: {}".format(cause, count))
    header.append("")
    header.append("# main 上混 lane commit 的成因分布 —— 用于判断「哪些是分类器边界偏碎」,")
    header.append("# 「哪些是真正的多面混合」。分类器侧的修正方向 (而非改写历史) 见 ADR-0122 未闭合项。")
    return "\n".join(header) + "\n"


def _check_ledger() -> int:
    """校验台账的**内在自洽性** (不依赖外部状态)。

    为什么不做「台账 == 实际」的等值校验: main 侧数据依赖完整历史 (CI 的 checkout 默认
    depth=1 拿不到) => 等值校验在 CI 上必然误报。本检查只验内在结构, 保证台账本身没坏。
    完整的重新生成随时可做: `python3 bin/ops/lane-debt-ledger.py --write`。
    """
    if not LEDGER.is_file():
        print("FAIL 台账不存在: {}".format(LEDGER.relative_to(WORKSPACE)))
        return 1
    try:
        import yaml

        data = yaml.safe_load(LEDGER.read_text(encoding="utf-8"))
    except Exception as exc:
        print("FAIL 台账 YAML 解析失败: {}".format(exc))
        return 1
    if not isinstance(data, dict):
        print("FAIL 台账不是映射")
        return 1
    for key in ("main_commits_total", "main_commits_mixed_lane"):
        if key not in data:
            print("FAIL 缺指标 {}".format(key))
            return 1
        if not isinstance(data[key], int) or data[key] < 0:
            print("FAIL 指标 {} 不是非负整数".format(key))
            return 1
    if data.get("advisory_only") is not True:
        print("FAIL advisory_only 必须为 true (台账是记录面, 不是豁免)")
        return 1
    if data["main_commits_mixed_lane"] > data["main_commits_total"]:
        print("FAIL main_commits_mixed_lane > main_commits_total")
        return 1
    causes = data.get("mixed_lane_causes") or {}
    if not isinstance(causes, dict):
        print("FAIL mixed_lane_causes 不是映射")
        return 1
    if sum(int(v) for v in causes.values()) != data["main_commits_mixed_lane"]:
        print(
            "FAIL causes 汇总({}) != main_commits_mixed_lane({})".format(
                sum(int(v) for v in causes.values()), data["main_commits_mixed_lane"]
            )
        )
        return 1
    print(
        "OK 台账自洽 (main {} commit, {} 混 lane (squash 结构性产物), {} 个成因)".format(
            data["main_commits_total"],
            data["main_commits_mixed_lane"],
            len(causes),
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="校验台账内在自洽")
    parser.add_argument("--write", action="store_true", help="重新生成台账")
    args = parser.parse_args()

    if args.check:
        return _check_ledger()

    main_commits = scan_main_commits()
    content = render(main_commits)

    if args.write:
        LEDGER.write_text(content, encoding="utf-8")
        print(
            "已写入 {} (main {} commit, {} 混 lane)".format(
                LEDGER.relative_to(WORKSPACE),
                len(main_commits),
                sum(1 for c in main_commits if len(c["lanes"]) > 1),
            )
        )
        return 0

    print(
        json.dumps(
            {
                "main_commits_total": len(main_commits),
                "main_commits_mixed_lane": sum(
                    1 for c in main_commits if len(c["lanes"]) > 1
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
