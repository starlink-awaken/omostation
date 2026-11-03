"""lane 拆分工具 (bin/ops/split-commits-by-lane.py) 的合同测试。

**背景**: 工具按 lane 把混 lane 的 commit 拆成多个单 lane commit, 用于消化 ADR-0122
§46「每 commit 单 lane」的历史欠账 (规则此前从未生效)。

**本文件锁住四件事**:
1. **组顺序按引用完整性** —— 拆分产出的每个中间 commit 都是一个**真实存在过**的树。
   若「登记某文件」的组先于「新增该文件」的组落地, 中间态就指向仓内**尚不存在**的文件,
   即 **半份镜像** (AGENTS.md §7 明令禁止)。判据: A 的文件内容引用了 B 的文件名, 则 B 先落。
2. **词边界匹配** —— `collectors.base.py.asset` 里**包含** `base.py.asset` 子串; 无边界
   匹配会造出假依赖边, 组顺序被错误重排。
3. **树逐字节等价** —— 拆分只是重新分组, 不改任何文件内容 (含 mode)。
4. **作者/日期/消息保留** —— 拆出的 commit 是同一份工作。

**判据自证**: 每条用例都跑**真实 git 仓库**, 并做「变异对照」—— 把修复摘掉时用例必须变红
(否则绿可能只是「检测器压根没命中」)。
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOOL = ROOT / "bin" / "ops" / "split-commits-by-lane.py"


def _load():
    spec = importlib.util.spec_from_file_location("split_commits_by_lane", str(TOOL))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["split_commits_by_lane"] = module
    spec.loader.exec_module(module)
    return module


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def _commit(repo: Path, files: dict, message: str) -> str:
    for rel, content in files.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@t.t")
    _git(repo, "config", "user.name", "t")
    return repo


REGISTRATION_BODY = (
    'HOST_FILES = (\n'
    '    ("collectors/orca.py", "collectors.orca.py.asset"),\n'
    ')\n'
)
COLLECTOR_BODY = '"""Orca collector."""\n'


# ── 判据 1: 组顺序按引用完整性 (半份镜像的根因) ──────────────────────────


def test_referenced_group_lands_before_the_referencing_group():
    """A 的内容引用了 B 的文件名, 则 B 必须先落地。

    复刻 mbp 上 fix/collectors-host-managed-20261016 的真实形状: 一个「登记」脚本
    (governance_code) 引用了一批 asset 文件 (other lane), 同一个 commit 里新增这些
    asset。按**字母序**建组时登记组先落, 中间态即半份镜像 (登记项指向尚不存在的文件)。
    """
    module = _load()
    groups = {
        "governance_code": ["bin/gac/host-sync.py"],
        "other": ["bin/panorama/assets/host/collectors.orca.py.asset"],
    }
    contents = {
        "governance_code": [REGISTRATION_BODY],
        "other": [COLLECTOR_BODY],
    }

    ordered = module._order_by_reference(groups, contents)
    assert list(ordered.keys()) == ["other", "governance_code"], (
        "被引用的组必须先落地, 否则中间 commit 是半份镜像"
    )


def test_group_order_is_stable_when_no_references_exist():
    """无引用关系时保持原有相对顺序 (不做无谓重排)。"""
    module = _load()
    groups = {
        "governance_code": ["bin/gac/a.py"],
        "docs": ["docs/b.md"],
        "code": ["bin/c.py"],
    }
    contents = {
        "governance_code": ["# 独立内容\n"],
        "docs": ["# 另一份独立内容\n"],
        "code": ["# 第三份独立内容\n"],
    }
    ordered = module._order_by_reference(groups, contents)
    assert list(ordered.keys()) == ["governance_code", "docs", "code"]


def test_mutual_reference_does_not_crash_and_stays_deterministic():
    """互引 (A 引 B 且 B 引 A) 时退化但不崩, 且结果确定。

    有环时无法同时满足两个依赖, 取原序第一项。判据是「不崩 + 两次跑结果一致」。
    """
    module = _load()
    groups = {
        "governance_code": ["bin/gac/a.py"],
        "other": ["bin/panorama/assets/host/b.asset"],
    }
    contents = {
        "governance_code": ["see b.asset\n"],
        "other": ["see a.py\n"],
    }
    first = list(module._order_by_reference(groups, contents).keys())
    second = list(module._order_by_reference(groups, contents).keys())
    assert first == second, "互引时结果必须确定"
    assert sorted(first) == ["governance_code", "other"]


# ── 判据 2: 词边界匹配 (假依赖边的根因) ─────────────────────────────────


def test_filename_match_respects_word_boundaries():
    """`base.py.asset` 不应命中 `collectors.base.py.asset` 的内部。

    无边界匹配会造出假依赖边, 组顺序被错误重排 (本工具的排序是**内容驱动**的,
    假边直接改变产出)。
    """
    module = _load()
    text = '    ("collectors.base.py.asset"),\n'
    assert not module._file_references(text, "base.py.asset"), "子串命中会造出假依赖边"
    assert module._file_references(text, "collectors.base.py.asset"), "完整文件名必须能命中"


def test_reference_matches_relative_and_bare_filename_forms():
    """引用方写裸文件名/相对路径都要能命中 (不是只认完整仓内路径)。

    真实案例: HOST_FILES 里写 "collectors.orca.py.asset", 而文件在
    bin/panorama/assets/host/ 下, 按完整仓内路径匹配会漏掉真正的引用。
    """
    module = _load()
    assert module._file_references(
        '    ("collectors/orca.py", "collectors.orca.py.asset"),\n',
        "collectors.orca.py.asset",
    )
    assert module._file_references(
        'HOST = "host/collectors.orca.py.asset"\n', "collectors.orca.py.asset"
    )


def test_very_short_names_are_not_treated_as_references():
    """太短的名字不作为依赖判据 —— 极易误命中普通单词/散文里的举例。

    阈值 6 是实测定的: 全仓最短的带扩展名文件名是 6 字符 (bos.md / cli.py /
    dag.md / sla.md), 而 4 字符的名字 (a.py / x.py) 在仓内分别出现于 13 / 51 个
    文件 —— 作为依赖判据只会造出大量假边, 把组顺序错误地重排。
    """
    module = _load()
    assert not module._file_references("a.py is mentioned here\n", "a.py")
    assert not module._file_references("x.py is mentioned here\n", "x.py")


def test_six_char_names_are_still_treated_as_references():
    """6 字符的名字**要**能命中 —— 那是仓内真实存在的一档 (cli.py / sla.md)。

    阈值若取得过大, 真实引用会被漏掉 ⇒ 半份镜像回来了。
    """
    module = _load()
    assert module._file_references('HOST = "cli.py"\n', "cli.py")


# ── 判据 3+4: 端到端 (真实 git 仓库) ────────────────────────────────────


def test_split_preserves_tree_bytes_author_date_and_message(tmp_path):
    """端到端: 拆分后树逐字节等价, 作者/日期/message 保留。

    这是工具对外承诺的三条不变量 (加 PR 号保留)。任一条被破坏, 拆分就是改写历史
    而非重新分组。
    """
    module = _load()
    repo = _make_repo(tmp_path)

    _commit(repo, {"README.md": "base\n"}, "base")
    mixed = _commit(
        repo,
        {
            "bin/gac/host-sync.py": REGISTRATION_BODY,
            "bin/panorama/assets/host/collectors.orca.py.asset": COLLECTOR_BODY,
        },
        "fix(gac): register collector (#1234)",
    )

    old_tree = _git(repo, "rev-parse", mixed + "^{tree}")
    old_author = _git(repo, "log", "-1", "--format=%an <%ae>", mixed)
    old_date = _git(repo, "log", "-1", "--format=%aI", mixed)

    original_workspace = module.WORKSPACE
    module.WORKSPACE = repo
    try:
        clc = module._load_change_lane_check()
        groups = module.lane_groups(mixed, clc)
        assert len(groups) >= 2, "构造的用例必须真的混 lane, 否则本用例恒绿"
        ordered = module.order_groups_by_reference(mixed, groups)
        assert list(ordered.keys())[-1] == "governance_code", (
            "登记组必须最后落地 (被引用的 asset 组先落)"
        )

        parent = _git(repo, "rev-parse", mixed + "^")
        message = _git(repo, "log", "-1", "--format=%B", mixed)
        created = module.split_commit(mixed, ordered, message, parent=parent)
        new_tree = _git(repo, "rev-parse", created[-1] + "^{tree}")
    finally:
        module.WORKSPACE = original_workspace

    assert new_tree == old_tree, "拆分后树必须与原 commit 逐字节等价"
    new_author = _git(repo, "log", "-1", "--format=%an <%ae>", created[-1])
    new_date = _git(repo, "log", "-1", "--format=%aI", created[-1])
    assert new_author == old_author, "作者必须保留"
    assert new_date == old_date, "日期必须保留"
    assert "(#1234)" in _git(repo, "log", "-1", "--format=%B", created[-1]), (
        "原 PR 号必须保留 (可追溯性是 squash 历史的唯一索引)"
    )


def test_each_split_commit_is_single_lane(tmp_path):
    """拆出的每个 commit 只含一个 lane 的文件。

    这是工具的目的本身; 若拆出的 commit 仍混 lane, 工具等于没干活。
    """
    module = _load()
    repo = _make_repo(tmp_path)
    _commit(repo, {"README.md": "base\n"}, "base")
    mixed = _commit(
        repo,
        {
            "bin/gac/host-sync.py": REGISTRATION_BODY,
            "bin/panorama/assets/host/collectors.orca.py.asset": COLLECTOR_BODY,
        },
        "fix(gac): register collector",
    )

    original_workspace = module.WORKSPACE
    module.WORKSPACE = repo
    try:
        clc = module._load_change_lane_check()
        groups = module.lane_groups(mixed, clc)
        ordered = module.order_groups_by_reference(mixed, groups)
        parent = _git(repo, "rev-parse", mixed + "^")
        message = _git(repo, "log", "-1", "--format=%B", mixed)
        created = module.split_commit(mixed, ordered, message, parent=parent)
        assert len(created) == len(groups)
        submodules = clc.submodule_paths()
        for sha, lane in zip(created, ordered.keys()):
            files = [
                f
                for f in _git(repo, "show", "--name-only", "--format=", sha).splitlines()
                if f.strip()
            ]
            lanes = {clc.classify(f, submodules) for f in files}
            assert lanes == {lane}, f"拆出的 commit 必须单 lane, 实得 {lanes}"
    finally:
        module.WORKSPACE = original_workspace


# ── 判据 5: 接线 (变异对照证明这条真的咬得住) ────────────────────────────


def test_main_wires_the_reference_ordering_into_the_split(tmp_path, monkeypatch):
    """端到端跑 main(): 拆出的第一个 commit 必须是**被引用的**那组。

    **为什么必须测 main() 而不是只测纯函数**: 纯函数 `_order_by_reference` 可以
    正确, 而 main() 忘了调用它 —— 那样工具照旧产出半份镜像, 但纯函数用例全绿。
    本用例走完整入口 (main() -> 读组 -> 排序 -> 拆), 是唯一能证明「修复真的接上了」
    的判据。变异对照: 把 main() 里的排序调用摘掉, 本用例当场变红。
    """
    module = _load()
    repo = _make_repo(tmp_path)

    _commit(repo, {"README.md": "base\n"}, "base")
    mixed = _commit(
        repo,
        {
            "bin/gac/host-sync.py": REGISTRATION_BODY,
            "bin/panorama/assets/host/collectors.orca.py.asset": COLLECTOR_BODY,
        },
        "fix(gac): register collector",
    )

    monkeypatch.setattr(module, "WORKSPACE", repo)
    monkeypatch.setattr(sys, "argv", [
        "split-commits-by-lane.py",
        "--from", mixed,
        "--to", mixed,
        "--to-ref", "refs/heads/split-out",
    ])
    assert module.main() == 0

    # 拆出的链: 第一个 commit 必须只含被引用的 asset (other 组)
    tip = _git(repo, "rev-parse", "refs/heads/split-out")
    chain = _git(repo, "rev-list", "--reverse", mixed + ".." + tip).splitlines()
    assert len(chain) == 2, "应拆成两个单 lane commit"

    first_files = [
        f
        for f in _git(repo, "show", "--name-only", "--format=", chain[0]).splitlines()
        if f.strip()
    ]
    assert first_files == ["bin/panorama/assets/host/collectors.orca.py.asset"], (
        f"被引用的 asset 必须先落地, 实得 {first_files}"
    )

    second_files = [
        f
        for f in _git(repo, "show", "--name-only", "--format=", chain[1]).splitlines()
        if f.strip()
    ]
    assert second_files == ["bin/gac/host-sync.py"], (
        f"登记组必须最后落地, 实得 {second_files}"
    )


def test_dry_run_report_shows_the_reference_ordered_groups(tmp_path, monkeypatch):
    """--dry-run 的报告必须给出**排序后**的组序, 不能是原始字母序。

    **为什么**: --dry-run 是使用者预览的唯一依据。若报告里的组序仍是字母序, 使用者
    会以为产物就是那个顺序 (= 半份镜像), 而实跑却给出另一个顺序 ⇒ 预览与实际不符。
    变异对照: 把 dry-run 路径里的排序调用摘掉, 本用例当场变红。
    """
    module = _load()
    repo = _make_repo(tmp_path)

    _commit(repo, {"README.md": "base\n"}, "base")
    mixed = _commit(
        repo,
        {
            "bin/gac/host-sync.py": REGISTRATION_BODY,
            "bin/panorama/assets/host/collectors.orca.py.asset": COLLECTOR_BODY,
        },
        "fix(gac): register collector",
    )

    monkeypatch.setattr(module, "WORKSPACE", repo)
    monkeypatch.setattr(sys, "argv", [
        "split-commits-by-lane.py",
        "--from", mixed,
        "--to", mixed,
        "--dry-run",
        "--json",
    ])

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        assert module.main() == 0
    report = json.loads(buffer.getvalue())
    assert report["split_commits"], "dry-run 必须报告待拆的 commit"
    assert report["split_commits"][0]["group_order"] == ["other", "governance_code"], (
        "dry-run 报告的组序必须是按引用完整性排的, "
        f"实得 {report['split_commits'][0]['group_order']}"
    )
