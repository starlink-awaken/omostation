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
- **扫描面是全仓，不收窄**（实测 2026-10-08）: `ROOT.rglob("*.py")` 会 descend 进
  `.git`/`node_modules`/`.venv`，在完整检出里数出 151,970 个文件、5.4 s；改成**剪枝遍历**
  （只跳这五个目录名，逐目录剪而不是先收集再过滤）后同一仓只剩 1,552 个文件、0.06 s。
  代价因此不构成收窄的理由 —— 收窄到 `bin/` 会漏掉别的平面里同形状的 `parents[K]`，
  而 `test_scan_plane_is_the_whole_checkout` 钉住"面没被收窄"这件事本身。
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


def _py_files(root: Path = ROOT) -> list[Path]:
    """剪枝遍历：被剪掉的目录不 descend，所以返回值就是扫描面。"""
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        out.extend(Path(dirpath) / f for f in filenames if f.endswith(".py"))
    return sorted(out)


def _reachable(base: Path, sub: str, name: str) -> bool:
    d = base / sub if sub else base
    return (d / f"{name}.py").is_file() or (d / name / "__init__.py").is_file()


def _sites(root: Path = ROOT) -> list[tuple[Path, int, str, str]]:
    out = []
    for p in _py_files(root):
        text = p.read_text(encoding="utf-8", errors="replace")
        for m in INSERT.finditer(text):
            idx, sub = int(m.group(1)), "/".join(SEG.findall(m.group(2)))
            nxt = ABS_IMPORT.search(text[m.end():], )
            if nxt:
                out.append((p, idx, sub, nxt.group(1).split(".")[0]))
    return out


def _classify(p: Path, idx: int, sub: str, name: str) -> str:
    if idx >= len(p.parents):
        return "arith-bug"
    if _reachable(p.parents[idx], sub, name):
        return "ok"
    return "arith-bug" if any(_reachable(p.parents[k], sub, name) for k in range(len(p.parents))) else "unresolvable-here"


def test_syspath_arith_is_correct_at_every_site():
    bugs = [
        f"{p.relative_to(ROOT)}: parents[{idx}]/{sub!r} 引不到 {name}"
        for p, idx, sub, name in _sites()
        if _classify(p, idx, sub, name) == "arith-bug"
    ]
    assert bugs == [], "\n".join(bugs)


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
        assert _classify(victim, 2, "lib", "repo_root") == "arith-bug"
        assert _classify(victim, 1, "lib", "repo_root") == "ok"

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
    nxt = ABS_IMPORT.search(text[m.end():])
    cls = _classify(site, int(m.group(1)), "/".join(SEG.findall(m.group(2))),
                    nxt.group(1).split(".")[0])
    assert cls in {"ok", "unresolvable-here"}, cls


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
    assert all(name != "apple_health_csv" for _, _, _, name in mine), mine
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
            _, idx, sub, name = hits[0]
            assert (idx, sub, name) == (want_idx, want_sub, "repo_root"), hits[0]
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
