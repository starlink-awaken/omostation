"""`sys.path.insert(0, Path(__file__).resolve().parents[K] / "<sub>")` 的 K 必须算对。

BET: BET-Y2Q4-T10-235（收尾轮）
起因: #4671 给 `bin/gac/` 下两个脚本加了 `from repo_root import state_file_read`，
却按 `bin/` 顶层脚本的拼法写 `parents[2]`。`bin/gac/x.py` 的 parents[2] 是**仓库根**，
仓库根下又真有一个 `lib/`（另一批 helper）—— 目录存在、模块不在里面，于是这两个脚本
在 main 上**每次调用都 ModuleNotFoundError**。唯一跑到它们的本地用例
`tests/test_m1_closeout_report.py` 不在 CI 白名单内，这条判据因此结构性失明。

判据形状（为什么不"import 失败即红"）:
- 区分**算错**与**环境没检出**。`projects/omo/src` 这类在未 init 子模块的 worktree 里
  任何 K 都不可达 —— 那是环境，不是回归。算错的特征是"某个别的 K 可达而当前 K 不可达"。
- detector 必须自证: 造一份真实深度的合成违规文件，断言整条扫描点名它。
- **扫描面是全仓，不收窄**（实测 2026-10-08，同一棵树两侧对照）: `ROOT.rglob("*.py")` 会
  descend 进 `.git`/`node_modules`/`.venv`/`__pycache__` —— 本检出 11,700 个文件、剪枝遍历
  4,940 个；canonical 全量检出 151,970 个 / 5.0 s vs 22,073 个 / 0.24 s。改成**剪枝遍历**
  （只跳这五个目录名，逐目录剪而不是先收集再过滤）省下的代价不构成收窄的理由 ——
  收窄到 `bin/` 会漏掉别的平面里同形状的 `parents[K]`，而
  `test_scan_plane_is_the_whole_checkout` 钉住"面没被收窄"这件事本身。
- **面的大小取决于子模块检出完整度，读数会随对齐而变**（同一轮实测）: 子模块未 init 时
  这棵树只有 1,552 个文件 / 36 个站点 / **0 个 arith-bug**；`git submodule update --init
  --force` 对齐到全仓后 4,940 个文件 / 57 个站点 / **1 个 arith-bug**（在 `projects/omo`
  里）。也就是说"绿"完全可能是空目录造成的 —— 判据不许靠记忆里的读数，跑之前先确认
  扫描面真的整了。gitlink 侧那条按归属**裁定进名单**（见
  `GITLINK_OWNED_ARITH_BUGS`），不是把面收窄，也不是替别人的仓改代码。
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# 只认这一种形状，且**段数不限**：`parents[K] / "a"` 与 `parents[K] / "a" / "b"` 都要命中。
# 2026-10-08 实测: 旧式写法（单一 `"([^"]*)"`) 在 `/"bin"/"lib"` 上静默不匹配 ——
# 那种形状下的算错会伪装成"没有站点"，所以段数必须展开，并由
# test_detector_covers_both_join_shapes 自证。
INSERT = re.compile(
    r'sys\.path\.insert\(0,\s*str\(Path\(__file__\)\.resolve\(\)\.parents\[(\d+)\]'
    r'((?:\s*/\s*"[^"]*")*)\s*\)\)'
)
SEG = re.compile(r'"([^"]*)"')
# 消费方只认**绝对 import**：`from .x import y` 是包内相对导入，根本不经过 sys.path，
# 拿它当名字判据会既漏又假报（2026-10-08 实测：domain-cartridges 里 3 处
# `parents[2]` + `from .apple_health_csv` 被空名判成 arith-bug）。
# 因此"后面只剩相对导入"的站点是本判据的**已知不可判面**，由
# test_relative_import_sites_are_not_judged 钉住它"不判"而非"误判"。
ABS_IMPORT = re.compile(r"^\s*(?:from|import)\s+([A-Za-z_]\w*(?:\.\w*)*)", re.M)
# 精确目录名匹配 —— 不用 startswith(".git")，那会把 .github/ 一起剪掉。
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__"}
GITMODULES = re.compile(r"^\s*path\s*=\s*(\S+)\s*$", re.M)

# gitlink 依赖里**已裁定归别人修**的算数错站点，逐条 (相对路径, K, 子路径, 消费方名)。
# 名单只能收**位于 .gitmodules 声明路径之下**的站点（由
# test_dependency_allowlist_cannot_exempt_root_plane 当场钉住），所以它不构成把
# root 平面摘出去的后门；而实测集合与名单**相等**才算绿，依赖上游修好后这条会因
# 名单陈旧而红，逼下一轮删掉它。
#
# 2026-10-08 实测这一条: `projects/omo/tests/unit/test_workflow_cli_bet_gate.py:15`
# 写 parents[1]/"src"（= tests/src，不存在），而该仓 3 个用例**今天全绿** ——
# 承载它的是 omo 作为已安装包在 venv 里，不是这条 insert。所以它是 #4671 同形状的
# **潜伏**算数错，归属 omo 仓（pinned 7942831 == 该仓 origin/main，上游未自愈）；
# root 在此只**报**不**判红**，否则一次子模块 bump 就能让 root CI 因别人的代码红。
GITLINK_OWNED_ARITH_BUGS: set[tuple[str, int, str, tuple[str, ...]]] = {
    ("projects/omo/tests/unit/test_workflow_cli_bet_gate.py", 1, "src",
     ("omo.workflow", "omo.workflow.core")),
}


def _py_files(root: Path = ROOT) -> list[Path]:
    """剪枝遍历：被剪掉的目录不 descend，所以返回值就是扫描面。"""
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        out.extend(Path(dirpath) / f for f in filenames if f.endswith(".py"))
    return sorted(out)


def _gitlink_paths() -> set[str]:
    """`.gitmodules` 声明的 gitlink 相对路径集合（tracked 文件，不读本机状态）。"""
    f = ROOT / ".gitmodules"
    return set(GITMODULES.findall(f.read_text(encoding="utf-8"))) if f.is_file() else set()


def _under_gitlink(rel: str) -> bool:
    return any(rel == p or rel.startswith(p + "/") for p in _gitlink_paths())


def _resolves(base: Path, sub: str, parts: list[str]) -> bool:
    """点号全路径逐项解析，**容忍 PEP-420 命名空间包**（目录在即算可达）。

    旧判据只查 `<name>.py` 或 `<name>/__init__.py`，于是 `from bin.panorama.x import y`
    这种"中间层无 __init__.py"的真能跑的写法会被算成 unresolvable —— 而 unresolvable
    是**宽容**的一侧，等于给真缺陷留了藏身处（2026-10-08 实测 bin/panorama/sunset-redirector.py
    就是这么被放过的，它 --help rc=0 实际可用）。
    """
    d = base / sub if sub else base
    for part in parts[:-1]:
        d = d / part
        if not d.is_dir():
            return False
    leaf = d / parts[-1]
    return leaf.with_suffix(".py").is_file() or leaf.is_dir()


def _reachable(base: Path, sub: str, name: str) -> bool:
    return _resolves(base, sub, name.split("."))


def _consumers(text: str, start: int) -> list[str]:
    """insert 之后**全部**绝对 import 的点号全路径。

    只取第一条会让判据拿 `import pytest`/`datetime` 这类与这条 insert 无关的名字
    去解路径（2026-10-08 实测：10 处 unresolvable 里有 4 处是这么来的，包括本文件
    自己的合成字符串）。取全集后"任一可解即 ok"，判别力不减：算错的基底下
    **没有一条**可解 —— 那里根本没有对应的模块树，这点由 mutation 复算证明。
    """
    return [m.group(1) for m in ABS_IMPORT.finditer(text, start)]


def _sites(root: Path = ROOT) -> list[tuple[Path, int, str, tuple[str, ...]]]:
    """站点 = (文件, K, 拼接子路径, 消费方点号全路径集合)。

    集合按字典序稳定化，好让名单比对与断言消息可复算。
    """
    out = []
    files = [root] if root.is_file() else _py_files(root)
    for p in files:
        text = p.read_text(encoding="utf-8", errors="replace")
        for m in INSERT.finditer(text):
            idx, sub = int(m.group(1)), "/".join(SEG.findall(m.group(2)))
            names = tuple(sorted(set(_consumers(text, m.end()))))
            if names:
                out.append((p, idx, sub, names))
    return out


def _classify(p: Path, idx: int, sub: str, names: tuple[str, ...]) -> str:
    def hit(base: Path) -> bool:
        return any(_resolves(base, sub, n.split(".")) for n in names)

    if idx >= len(p.parents):
        return "arith-bug"
    if hit(p.parents[idx]):
        return "ok"
    return "arith-bug" if any(hit(p.parents[k]) for k in range(len(p.parents))) else "unresolvable-here"


def test_syspath_arith_is_correct_at_every_site():
    bugs, owned = [], []
    for p, idx, sub, names in _sites():
        if _classify(p, idx, sub, names) != "arith-bug":
            continue
        rel = p.relative_to(ROOT).as_posix()
        line = f"{rel}: parents[{idx}]/{sub!r} 引不到 {names[0]}"
        (owned if _under_gitlink(rel) else bugs).append(
            (rel, idx, sub, names, line))
    assert [b[4] for b in bugs] == [], "\n".join(b[4] for b in bugs)
    # gitlink 侧的算数错**必须逐条对上名单**：多一条 = 新缺陷要指认归属，
    # 少一条 = 上游已修、名单该删。两种情况都不许静默通过。
    measured = {(b[0], b[1], b[2], b[3]) for b in owned}
    assert measured == GITLINK_OWNED_ARITH_BUGS, (
        f"新增未裁定的依赖缺陷: {sorted(measured - GITLINK_OWNED_ARITH_BUGS)}; "
        f"已消失的陈旧豁免: {sorted(GITLINK_OWNED_ARITH_BUGS - measured)}")


def test_dependency_allowlist_cannot_exempt_root_plane():
    """名单只能收 gitlink 下的站点 —— 否则它就是"把 root 平面摘出去"的后门。

    并且每条都必须**当下仍是缺陷**（在实测站点里命中），防止改成函数式豁免。
    """
    gitlinks = _gitlink_paths()
    assert gitlinks, ".gitmodules 读不到，这条判据会按构造绿"
    for rel, idx, sub, name in GITLINK_OWNED_ARITH_BUGS:
        assert _under_gitlink(rel), f"{rel} 不在任何 gitlink 下，不许进名单"
        site = ROOT / rel
        assert site.is_file(), f"{rel} 已不存在，名单陈旧"
        hits = [(i, s, n) for p, i, s, n in _sites(site) if p == site]
        assert (idx, sub, name) in hits, f"{rel} 的这条站点已变，名单要跟着改"
        assert _classify(site, idx, sub, name) == "arith-bug", f"{rel} 不再是缺陷"

    # 反向: 把同形状的违规放进 root 平面，必须**不被名单放过**
    victim = ROOT / "bin" / "gac" / "_synthetic_owned_exempt_probe.py"
    good = (
        "import sys\n"
        "from pathlib import Path\n"
        'sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))\n'
        "from repo_root import state_file_read  # noqa: E402, F401\n"
    )
    try:
        victim.write_text(good.replace("parents[1]", "parents[2]"), encoding="utf-8")
        rel = victim.relative_to(ROOT).as_posix()
        assert not _under_gitlink(rel), "root 站点被算成了 gitlink —— 判据失效"
        assert rel not in GITLINK_OWNED_ARITH_BUGS
        bugs = [
            p.relative_to(ROOT).as_posix()
            for p, idx, sub, name in _sites()
            if _classify(p, idx, sub, name) == "arith-bug" and not _under_gitlink(
                p.relative_to(ROOT).as_posix())
        ]
        assert rel in bugs, "注入的 root 违规被放过 —— 名单成了后门"
    finally:
        victim.unlink(missing_ok=True)


def test_the_two_scripts_4671_broke_are_invocable():
    """直接执行，不靠静态推断 —— 这是那条判据漏掉的形状。"""
    for rel in ("bin/gac/m1-closeout-report.py", "bin/gac/session-recovery.py"):
        r = subprocess.run([sys.executable, str(ROOT / rel), "--help"],
                           capture_output=True, text=True)
        assert r.returncode == 0, f"{rel} 不可调用:\n{r.stderr[-400:]}"


def test_detector_is_not_a_no_op(tmp_path):
    """合成违规落在**真实深度**上（bin/gac/），整条扫描必须点名它，且修回后必须闭嘴。"""
    victim = ROOT / "bin" / "gac" / "_synthetic_syspath_probe.py"
    good = (
        "import sys\n"
        "from pathlib import Path\n"
        'sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))\n'
        "from repo_root import state_file_read  # noqa: E402, F401\n"
    )
    bad = good.replace("parents[1]", "parents[2]")
    try:
        victim.write_text(bad, encoding="utf-8")
        hits = [s for s in _sites() if s[0] == victim and _classify(*s) == "arith-bug"]
        assert hits, "检测器没点名注入的违规 —— 空绿"
        assert _classify(victim, 2, "lib", ("repo_root",)) == "arith-bug"
        assert _classify(victim, 1, "lib", ("repo_root",)) == "ok"

        victim.write_text(good, encoding="utf-8")
        assert not [s for s in _sites() if s[0] == victim and _classify(*s) == "arith-bug"]
    finally:
        victim.unlink(missing_ok=True)


def test_absent_submodule_is_not_reported_as_arith_bug(tmp_path):
    """环境类与回归类必须可分: 子模块未 init 时不得判成算错。"""
    site = ROOT / "bin" / "bc-os" / "signal_router.py"
    if not site.is_file():
        import pytest

        pytest.skip("signal_router.py 不在此检出")
    text = site.read_text(encoding="utf-8")
    m = INSERT.search(text)
    assert m, "锚点变了，判据要跟着改"
    names = tuple(sorted(set(_consumers(text, m.end()))))
    assert names, "取不到消费方，这条判据会按构造绿"
    cls = _classify(site, int(m.group(1)), "/".join(SEG.findall(m.group(2))), names)
    assert cls in {"ok", "unresolvable-here"}, cls


def test_namespace_package_sites_are_not_misjudged_as_unreachable():
    """`bin/` 这类**无 `__init__.py`** 的命名空间包，`from bin.panorama.x import y` 真能跑。

    2026-10-08 实测 `bin/panorama/sunset-redirector.py:19`（parents[2] = 仓库根）就是这么被
    旧判据算成 unresolvable 的 —— 而 unresolvable 是宽容侧，真缺陷能藏在里面。这条把
    "命名空间层也算可达"钉成判据，并对照"要求 `__init__.py`"的严格谓词确实会拒它，
    否则这条绿只是因为两种实现都给 ok。
    """
    site = ROOT / "bin" / "panorama" / "sunset-redirector.py"
    if not site.is_file():
        import pytest

        pytest.skip("sunset-redirector 不在此检出")
    hits = [s for s in _sites() if s[0] == site]
    assert hits, "锚点变了，判据要跟着改"
    p, idx, sub, names = hits[0]
    assert _classify(p, idx, sub, names) == "ok", (idx, sub, names)
    base = p.parents[idx] / sub if sub else p.parents[idx]
    for part in names[0].split(".")[:-1]:
        base = base / part
    assert base.is_dir() and not (base / "__init__.py").is_file(), \
        "中间层其实有 __init__.py，这条就没在测命名空间容忍性了"
    assert (base / (names[0].split(".")[-1] + ".py")).is_file()

    def strict(b: Path, s: str, n: str) -> bool:
        d = b / s if s else b
        for part in n.split(".")[:-1]:
            d = d / part
            if not (d.is_dir() and (d / "__init__.py").is_file()):
                return False
        leaf = d / n.split(".")[-1]
        return leaf.with_suffix(".py").is_file()

    assert not any(strict(p.parents[idx], sub, n) for n in names), \
        "严格谓词也给 ok —— 上面那条 ok 不是靠容忍性得到的"


def test_namespace_package_dir_leaf_is_reachable():
    """`import tests` 这种**叶子是目录**的写法也算可达 —— 实测有 3 处 ok 靠它。

    2026-10-08 复算：去掉"叶子是目录"这一支，`projects/cockpit/.../test_cli_dashboard.py`、
    kairon 两处当场从 ok 掉成 unresolvable；而这一支同时覆盖命名空间包（`tests/` 无
    `__init__.py`）和普通包。这条用**合成站点**钉它，并断言 witness 目录确实没有
    `__init__.py` —— 否则"绿"可能只是普通包路径给的，命名空间那一半仍是无主之地。
    """
    assert not (ROOT / "tests" / "__init__.py").is_file(), \
        "tests/ 有了 __init__.py，这条不再测命名空间叶子"
    assert _resolves(ROOT, "", ["tests"])
    victim = ROOT / "bin" / "gac" / "_synthetic_ns_leaf_probe.py"
    try:
        victim.write_text(
            "import sys\n"
            "from pathlib import Path\n"
            'sys.path.insert(0, str(Path(__file__).resolve().parents[2]))\n'
            "import tests  # noqa: E402, F401\n", encoding="utf-8")
        hits = [s for s in _sites() if s[0] == victim]
        assert len(hits) == 1, hits
        assert _classify(*hits[0]) == "ok", "叶子目录不可达 → 真能跑的写法被算成缺陷"
    finally:
        victim.unlink(missing_ok=True)


def test_relative_import_sites_are_not_judged():
    """已知不可判面必须**静默**，不能误判。

    实测对象: projects/domain-cartridges/health/domain/health/test_monitor_pipeline.py:25
    `sys.path.insert(0, str(Path(__file__).resolve().parents[2]))` 后接
    `from .apple_health_csv import ...`（包内相对导入，不经 sys.path）。
    该文件更远处还有 `import datetime`，所以"完全不产生站点"是过强断言；真正的不变式是
    ① 相对模块名绝不作为消费方出现 ② 该文件不得被判成 arith-bug。
    """
    site = ROOT / "projects" / "domain-cartridges" / "health" / "domain" / "health" / \
        "test_monitor_pipeline.py"
    if not site.is_file():
        import pytest

        pytest.skip("domain-cartridge 不在此检出")
    inserts = INSERT.findall(site.read_text(encoding="utf-8"))
    assert inserts, "锚点变了，判据要跟着改"
    mine = [s for s in _sites() if s[0] == site]
    assert all("apple_health_csv" not in n
               for _, _, _, names in mine for n in names), mine
    assert [_classify(*s) for s in mine] == ["unresolvable-here"] * len(mine), mine


def test_detector_covers_both_join_shapes():
    """段的形状不是假设：`/"a"` 与 `/"a"/"b"` 都必须命中，且 sub 要展平成 `a/b`。

    这是"detector 自证"的第二个面 —— 上一条自证管**深度**，这条管**写法**。
    2026-10-08 实测：把 INSERT 退回单段写法，`/"bin"/"lib"` 那份合成文件当场漏检。
    """
    victim = ROOT / "bin" / "gac" / "_synthetic_syspath_shape_probe.py"
    one = 'sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))\n'
    two = 'sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "bin" / "lib"))\n'
    tail = "from repo_root import state_file_read  # noqa: E402, F401\n"
    try:
        for line, want_idx, want_sub in ((one, 1, "lib"), (two, 2, "bin/lib")):
            victim.write_text("import sys\nfrom pathlib import Path\n" + line + tail,
                              encoding="utf-8")
            hits = [s for s in _sites() if s[0] == victim]
            assert len(hits) == 1, f"{want_sub!r} 形状没被命中（hits={hits}）—— 写法盲区"
            _, idx, sub, names = hits[0]
            assert (idx, sub, names) == (want_idx, want_sub, ("repo_root",)), hits[0]
    finally:
        victim.unlink(missing_ok=True)


def test_scan_plane_is_the_whole_checkout():
    """扫描面不收窄的正面证据：`bin/` 之外的违规也必须被点名。

    和"文件数 == 剪枝遍历数"这种自指断言不同源 —— 那条只证明实现和实现对账，
    这一条证明面真的越出了 bug 出现的那个平面（把 `_sites` 写死成 `bin/**` 就当场红）。
    """
    for anchor in ("bin/lib/repo_root.py", "tests/unit/test_bin_syspath_resolution.py"):
        assert (ROOT / anchor) in set(_py_files()), anchor

    outside = ROOT / "tests" / "_synthetic_syspath_probe_outside_bin.py"
    good = (
        "import sys\n"
        "from pathlib import Path\n"
        'sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin/lib"))\n'
        "from repo_root import state_file_read  # noqa: E402, F401\n"
    )
    try:
        outside.write_text(good.replace("parents[1]", "parents[6]"), encoding="utf-8")
        hits = [s for s in _sites() if s[0] == outside]
        assert hits, "扫描面漏掉了 tests/ —— 面被收窄了"
        assert _classify(*hits[0]) == "arith-bug"
    finally:
        outside.unlink(missing_ok=True)
