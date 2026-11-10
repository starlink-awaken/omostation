"""cron 解释器可执行性门禁的护栏 (CRON-BARE-PYTHON3-PY39-IMPORT-DEATH 决策(3)).

钉住的是**判据形状**而不是当前读数 —— 债条目里三种「扫了却漏」的形状各一条用例：
  1. 死因不在入口文件，而在它 `spec_from_file_location` 动态拉起的兄弟模块；
  2. 换一个没有 3.11+ 解释器的宿主 (mini 形状) 缺口必须报出来，不能静默绿；
  3. warn 期限一到自动转阻断，且限期值与 governance-checks.yaml 里的规则同源。
"""

from __future__ import annotations

import datetime
import json
import sys
import textwrap
from pathlib import Path

import pytest
import yaml

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "bin" / "lib"))
sys.path.insert(0, str(_ROOT / "bin" / "gac"))

import importlib  # noqa: E402

import cron_normalize as cn  # noqa: E402

gate = importlib.import_module("check-cron-interpreter-executability")


def _repo(tmp_path: Path, files: dict[str, str]) -> Path:
    for rel, body in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(textwrap.dedent(body), encoding="utf-8")
    _clear(tmp_path)
    return tmp_path


def _clear(root: Path) -> None:
    """进程内 memo 全清：漏一个就是在拿上一秒的文件系统读数测现在。"""
    cn._repo_local_cache.pop(str(root), None)
    for k in [k for k in cn._closure_cache if k[1] == str(root) or str(root) in k[0]]:
        cn._closure_cache.pop(k, None)
    for k in [k for k in cn._resolve_cache if str(root) in k[0]]:
        cn._resolve_cache.pop(k, None)


# ── 形状 1：死因在动态加载的兄弟模块 ────────────────────────────────────────
def test_closure_follows_dynamic_sibling_load(tmp_path: Path) -> None:
    root = _repo(
        tmp_path,
        {
            "bin/entry.py": """
                from pathlib import Path
                import importlib.util
                ROOT = Path(__file__).resolve().parents[1]
                _p = ROOT / "bin" / "sibling.py"
                _s = importlib.util.spec_from_file_location("sibling", _p)
                """,
            "bin/sibling.py": "import definitely_missing_pkg_abc123  # noqa\n",
        },
    )
    entry = root / "bin" / "entry.py"
    # 发射侧口径看不见：入口自己一个第三方包都不 import
    assert cn.third_party_imports(entry) == []
    # depth 1 只到入口自己那一跳，仍看不见
    assert cn.import_closure(entry, root, max_depth=1) == []
    # depth 2 沿 .py 字面量边把兄弟的依赖取回来
    assert cn.import_closure(entry, root, max_depth=2) == ["definitely_missing_pkg_abc123"]


def test_package_import_is_resolved_through_init_not_read_as_unparseable(tmp_path: Path) -> None:
    """包目录要按 `__init__.py` 解析，不能把目录本身丢去 ast 解析.

    回归形状：worktree 里 `projects/omo/src` 之类未检出 ⇒ 索引命中包目录，旧实现
    `read_text(dir)` 抛 IsADirectoryError，被压成「入口 unparseable」，一次性误报
    14 条作业 —— 判据自己的故障被测成了被检物的故障。
    """
    root = _repo(
        tmp_path,
        {
            "bin/entry.py": "import mypkg\n",
            "mypkg/__init__.py": "from mypkg.inner import thing\n",
            "mypkg/inner.py": "import definitely_missing_pkg_abc123\n",
        },
    )
    entry = root / "bin" / "entry.py"
    # 发射侧口径只减 stdlib；仓内包名在调用点层过滤（`_resolve_invocation` 查索引），
    # 所以这里 mypkg 会出现在原始名单里 —— 「不算缺包」由下面两行的闭包读数保证。
    assert cn.third_party_imports(entry) == ["mypkg"]
    # entry → mypkg/__init__.py → mypkg/inner.py 是两跳，max_depth 数的是「访问到第几层文件」
    assert cn.import_closure(entry, root, max_depth=2) == []
    assert cn.import_closure(entry, root, max_depth=3) == ["definitely_missing_pkg_abc123"]
    assert cn.closure_undetermined(entry, root, max_depth=3) == []


def test_unreadable_sibling_is_listed_not_silently_skipped(tmp_path: Path) -> None:
    """兄弟模块物理读不到时，列进「判不出」清单，而不是静默当它没有依赖。"""
    root = _repo(
        tmp_path,
        {"bin/entry.py": "import mypkg\n", "mypkg/__init__.py": "import os\n"},
    )
    entry = root / "bin" / "entry.py"
    assert cn.import_closure(entry, root, max_depth=2) == []
    # 索引已缓存后把 __init__.py 删掉 —— 子模块被并发 agent 清空的实测形状
    (root / "mypkg" / "__init__.py").unlink()
    # 只清闭包 memo，**保留**索引 —— 索引里 mypkg 仍是仓内包、磁盘上入口文件已消失,
    # 就是并发 agent 清空子模块检出后门禁看到的状态 (AGENTS.md 的 worktree 子模块告诫)。
    # 若把索引也重建, mypkg 直接掉出仓内包集合被当第三方, 走的是另一条判据。
    for k in [k for k in cn._closure_cache if k[1] == str(root)]:
        cn._closure_cache.pop(k, None)
    und = cn.closure_undetermined(entry, root, max_depth=2)
    assert any("mypkg" in u for u in und), f"兄弟判不出必须如实列出，实际: {und}"


def test_unparseable_entry_is_undetermined(tmp_path: Path) -> None:
    root = _repo(tmp_path, {"bin/bad.py": "def broken(:\n"})
    assert cn.import_closure(root / "bin" / "bad.py", root) is None


# ── 形状 2：宿主没有可用解释器时必须报缺口 ─────────────────────────────────
def _registry(tmp_path: Path, *, dep: str = "definitely_missing_pkg_abc123") -> Path:
    root = _repo(
        tmp_path,
        {
            ".omo/cron/registry.yaml": yaml.safe_dump(
                {
                    "jobs": [
                        {
                            "name": "needs-missing-pkg",
                            "schedule": "17 3 * * *",
                            "command": f"cd {tmp_path} && python3 bin/job.py",
                            "owner": "platform-team",
                            "status": "active",
                            "planes": ["crontab"],
                        },
                        {
                            "name": "shell-only-job",
                            "schedule": "7 4 * * *",
                            "command": f"cd {tmp_path} && /bin/echo hi",
                            "owner": "platform-team",
                            "status": "active",
                            "planes": ["crontab"],
                        },
                    ]
                },
                allow_unicode=True,
            ),
            "bin/job.py": f"import {dep}  # noqa\n",
        },
    )
    return root / ".omo" / "cron" / "registry.yaml"


def test_missing_dependency_is_reported_per_call_site(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    jobs = yaml.safe_load(registry.read_text(encoding="utf-8"))["jobs"]
    rec = cn.interpreter_executability_jobs(jobs, candidates=[], repo_root=registry.parents[2])
    by_name = {r["name"]: r for r in rec}
    # 没有 python 调用点的作业不进判据（既不算通过也不算缺口）
    assert set(by_name) == {"needs-missing-pkg"}, sorted(by_name)
    assert by_name["needs-missing-pkg"]["install_reason"]
    assert "definitely_missing_pkg_abc123" in by_name["needs-missing-pkg"]["install_reason"]


def test_empty_candidate_list_is_a_gap_not_a_pass(tmp_path: Path) -> None:
    """候选解不出 ⇒ 安装侧把裸 `python3` 原样留下 —— 那正是 2026-10-22 的死法。"""
    registry = _registry(tmp_path)
    jobs = yaml.safe_load(registry.read_text(encoding="utf-8"))["jobs"]
    cmd = jobs[0]["command"]
    _new, reason = cn.resolve_python_command(cmd, candidates=[], repo_root=registry.parents[2])
    assert reason is not None
    # 原样返回：宁可在既有失败形态上留作业，也不换成新失败形态（库不变量 3）
    assert "python3 bin/job.py" in _new


def test_absent_declared_workspace_is_not_judged_on_this_host(tmp_path: Path) -> None:
    """作业 `cd` 的目录不在本机 ⇒ 整条不进判定（CI / 非 cron 宿主的形状）。

    钉住的是限期那天 CI 的行为：若按兜底根解析，登记面的作业会全部拿 CI 的解释器判成
    阻断缺口，让每个 PR 因为一个与本机无关的理由变红 —— 那是把「宿主差异」读成「缺陷」。
    """
    elsewhere = tmp_path / "other-host-workspace"  # 故意不存在
    registry = _repo(
        tmp_path,
        {
            ".omo/cron/registry.yaml": yaml.safe_dump(
                {
                    "jobs": [
                        {
                            "name": "foreign-host-job",
                            "schedule": "3 5 * * *",
                            "command": f"cd {elsewhere} && python3 bin/job.py",
                            "owner": "platform-team",
                            "status": "active",
                            "planes": ["crontab"],
                        }
                    ]
                },
                allow_unicode=True,
            ),
            "bin/job.py": "import definitely_missing_pkg_abc123  # noqa\n",
        },
    ) / ".omo/cron/registry.yaml"
    root = registry.parents[2]
    jobs = yaml.safe_load(registry.read_text(encoding="utf-8"))["jobs"]
    # 已过限期也不 FAIL：非本机不是缺口
    res = _evaluate(registry, root, candidates=[], now=datetime.date(2026, 12, 1))
    assert (res["jobs_scanned"], res["jobs_off_host"], res["blocking_gaps"]) == (0, 1, 0)
    assert res["verdict"] == "OK"

    # 正控制：同一份登记面，工作区一旦在本机存在就照判 —— 上面那个绿不是恒真
    (elsewhere / "bin").mkdir(parents=True)
    (elsewhere / "bin" / "job.py").write_text("import definitely_missing_pkg_abc123  # noqa\n", encoding="utf-8")
    _clear(root)
    _clear(elsewhere)
    res = _evaluate(registry, root, candidates=[], now=datetime.date(2026, 12, 1))
    assert (res["jobs_scanned"], res["jobs_off_host"], res["blocking_gaps"]) == (1, 0, 1)
    assert res["verdict"] == "FAIL"


def test_effective_workspace_is_the_last_cd(tmp_path: Path) -> None:
    """复合命令里第二个 `cd` 覆盖第一个 —— 调用点按 shell 语义解析，不按第一个。

    登记面 59 条 active 作业今天 0 条命中多 `cd`，钉的是潜伏形状：拿第一个 `cd` 当有效
    工作区会把其后的脚本解析到错的根，宿主判定跟着一起错。
    """
    a, b, gone = tmp_path / "A", tmp_path / "B", tmp_path / "gone"
    for d in (a, b):
        (d / "bin").mkdir(parents=True)
        (d / "bin" / "job.py").write_text("import os  # noqa\n", encoding="utf-8")
    sites = cn.python_call_sites(
        f"cd {a} && python3 bin/job.py && cd {b} && python3 bin/job.py", repo_root=tmp_path
    )
    assert len(sites) == 2
    assert [Path(s["workspace"]) for s in sites] == [a, b]
    assert [Path(s["script"]) for s in sites] == [a / "bin" / "job.py", b / "bin" / "job.py"]
    assert [s["host_assessable"] for s in sites] == [True, True]
    # 第二个 cd 指向不在本机的目录: 只有其后那个调用点不判, 前一个照判
    sites = cn.python_call_sites(
        f"cd {a} && python3 bin/job.py && cd {gone} && python3 bin/job.py", repo_root=tmp_path
    )
    assert [s["host_assessable"] for s in sites] == [True, False]


# ── 形状 3：warn → 限期 → 阻断 ────────────────────────────────────────────
def _evaluate(registry: Path, root: Path, **kw):
    jobs = yaml.safe_load(registry.read_text(encoding="utf-8"))["jobs"]
    kw.setdefault("repo_root", root)
    # 「本机装了 cron 平面」是本判据的外部前提，单测必须自己声明它：在没有 crontab 的机器
    # (CI 的 ubuntu-latest) 上整批判据会判成「不适用」，那些用例就会以假绿通过。
    kw.setdefault("installed_plane", ["*/5 * * * * probe"])
    return gate.evaluate(jobs, registry=registry, **kw)


def test_host_without_cron_plane_is_not_judged(tmp_path: Path) -> None:
    """本机没有 cron 平面 ⇒ 不判、不报缺口（CI 形状），限期那天也不会红。

    钉住的形状：CI ubuntu-latest 上 `.venv`/homebrew 都不存在，`crontab -l` 报
    `no crontab for runner`。若照判，登记面里 `$HOME/...` 拼法的作业会全部报
    「target script not found」，让每个 PR 因为与交付无关的理由变红。
    """
    registry = _registry(tmp_path)
    res = _evaluate(registry, tmp_path, candidates=[], installed_plane=[], now=datetime.date(2026, 12, 1))
    assert (res["plane"], res["jobs_scanned"], res["blocking_gaps"], res["verdict"]) == (
        "absent",
        0,
        0,
        "OK",
    )
    # 读不出 ≠ 没装：仪器故障不能算成被检物的清白，照判并如实标状态
    res = _evaluate(registry, tmp_path, candidates=[], installed_plane=None, now=datetime.date(2026, 12, 1))
    assert res["plane"] == "unreadable"
    assert res["blocking_gaps"] == 1
    # 正控制：同一份登记面，平面装上就照判（上面的绿不是恒真）
    res = _evaluate(registry, tmp_path, candidates=[], installed_plane=["*/5 * * * * x"], now=datetime.date(2026, 12, 1))
    assert (res["plane"], res["jobs_scanned"], res["blocking_gaps"]) == ("present", 1, 1)


def test_warn_period_does_not_flip_gate(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    res = _evaluate(registry, tmp_path, candidates=[], now=datetime.date(2026, 11, 11))
    assert res["blocking_gaps"] == 1
    assert res["verdict"] == "WARN"
    assert res["enforcement"] == "warn-only"


def test_after_deadline_same_gap_becomes_blocking(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    res = _evaluate(registry, tmp_path, candidates=[], now=datetime.date(2026, 11, 25))
    assert res["verdict"] == "FAIL"
    assert res["enforcement"] == "blocking"


def test_strict_flag_escalates_regardless_of_deadline(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    res = _evaluate(registry, tmp_path, candidates=[], now=datetime.date(2026, 11, 11), strict=True)
    assert res["verdict"] == "FAIL"


def test_clean_registry_exits_zero(tmp_path: Path) -> None:
    registry = _registry(tmp_path, dep="os")
    res = _evaluate(registry, tmp_path, now=datetime.date(2026, 12, 1))
    assert res["blocking_gaps"] == 0
    assert res["verdict"] == "OK"


def test_main_exit_codes_follow_verdict(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    registry = _registry(tmp_path)
    # 走 main 的用例必须自己声明 cron 平面：CI 的 ubuntu-latest 没装 crontab，
    # 不注入就会拿到「不适用 ⇒ 0」，把退出码用例变成恒过。
    monkeypatch.setattr(gate, "installed_crontab_lines", lambda: ["*/5 * * * * probe"])
    warn = gate.main(["--registry", str(registry), "--candidate", "/nonexistent/python3", "--now", "2026-11-11", "--json"])
    fail = gate.main(["--registry", str(registry), "--candidate", "/nonexistent/python3", "--now", "2026-11-25", "--json"])
    assert (warn, fail) == (0, 1)


def test_missing_registry_is_exit_two(tmp_path: Path) -> None:
    assert gate.main(["--registry", str(tmp_path / "nope.yaml")]) == 2


# ── 形状 4：已装面（决策(2) 改判 B′）─────────────────────────────────────
# 登记面判的是「声明的解释器能不能跑」，已装面判的是「cron 实际执行的那一行里的解释器
# 还在不在」。安装侧按宿主重写解释器，所以两者不是同一个对象：venv 被删、homebrew 换了
# 版本号、手工 crontab -e 钉一个不存在的路径，整行折回比较(--check)一律判 ok。
def _plane_repo(tmp_path: Path, interp_in_registry: str = "python3") -> Path:
    return _repo(
        tmp_path,
        {
            ".omo/cron/registry.yaml": yaml.safe_dump(
                {
                    "jobs": [
                        {
                            "name": "plane-job",
                            "schedule": "17 3 * * *",
                            "command": f"cd {tmp_path} && {interp_in_registry} bin/plain.py",
                            "owner": "platform-team",
                            "status": "active",
                            "planes": ["crontab"],
                        }
                    ]
                },
                allow_unicode=True,
            ),
            "bin/plain.py": "import os  # noqa\n",
        },
    )


def _plane_jobs(root: Path) -> list[dict]:
    return yaml.safe_load((root / ".omo/cron/registry.yaml").read_text(encoding="utf-8"))["jobs"]


def test_dead_interpreter_in_installed_line_is_a_plane_gap(tmp_path: Path) -> None:
    """已装行钉了不存在的解释器 ⇒ 缺口，即使登记面一个字没改、写法被折成同一个键。

    配对用 `normalize_interpreter` 的整行折回 —— 那正是它本来的用途，不另发明匹配：
    登记面 `python3` 与已装行 `/no-such-venv/bin/python3` 折回后同键 ⇒ 认定同一个作业。
    """
    root = _plane_repo(tmp_path)
    jobs = _plane_jobs(root)
    dead = f"17 3 * * * cd {tmp_path} && {tmp_path}/no-such-venv/bin/python3 bin/plain.py"
    res = gate.evaluate(jobs, registry=root / ".omo/cron/registry.yaml", repo_root=root,
                        now=datetime.date(2026, 12, 1), installed_plane=[dead])
    # 配对非零才证明判据真跑了：配不上也会得到 0 缺口，那是恒真绿
    assert (res["plane_lines_scanned"], res["plane_paired_lines"]) == (1, 1)
    assert (res["plane_gaps"], res["verdict"]) == (1, "FAIL")
    assert res["blocking_gaps"] == res["registry_gaps"] + res["plane_gaps"]
    assert "已不存在" in res["plane_gap_details"][0]["reason"]


@pytest.mark.skipif(sys.version_info < (3, 11), reason="正控制需要一个过版本下限的真解释器")
def test_same_installed_line_with_live_interpreter_is_not_a_gap(tmp_path: Path) -> None:
    """正控制：只把解释器换成真的，其余一字不动 ⇒ 0 缺口（上面那条红不是恒真）。"""
    root = _plane_repo(tmp_path, interp_in_registry=sys.executable)
    jobs = _plane_jobs(root)
    live = f"17 3 * * * cd {tmp_path} && {sys.executable} bin/plain.py"
    res = gate.evaluate(jobs, registry=root / ".omo/cron/registry.yaml", repo_root=root,
                        now=datetime.date(2026, 12, 1), installed_plane=[live])
    assert (res["plane_paired_lines"], res["plane_gaps"], res["verdict"]) == (1, 0, "OK")


def test_unregistered_installed_line_is_counted_not_gapped(tmp_path: Path) -> None:
    """未登记的已装行（手工装的、known_orphans 那类）坏掉照记，不计入本仓缺口。

    把「未登记」报成「跑不了」是把归属问题读成健康问题；但悄悄丢掉这条信息就又回到
    「--check 绿而作业死」。
    """
    root = _plane_repo(tmp_path)
    jobs = _plane_jobs(root)
    foreign = f"5 6 * * * {tmp_path}/who-put-this-here/bin/python3 bin/plain.py"
    res = gate.evaluate(jobs, registry=root / ".omo/cron/registry.yaml", repo_root=root,
                        now=datetime.date(2026, 12, 1), installed_plane=[foreign])
    # 配不上任何登记条目时，自证标记一起亮 —— 已装面看得见调用点却认不出归属，
    # 这时「0 缺口」不能算干净的绿（WARN 级，不翻退出码）。
    assert (res["plane_paired_lines"], res["plane_gaps"], res["plane_pairing_suspicious"]) == (0, 0, 1)
    assert res["verdict"] == "WARN"
    assert res["plane_unregistered_broken"] == 1
    assert "who-put-this-here" in res["plane_unregistered_details"][0]["interpreter"]


def test_bare_python3_in_installed_plane_is_counted_not_judged(tmp_path: Path) -> None:
    """裸 `python3` 写法只计数不判定 —— 判它要建模 cron 的 PATH，本判据不假装能做到。"""
    root = _plane_repo(tmp_path)
    jobs = _plane_jobs(root)
    bare = f"17 3 * * * cd {tmp_path} && python3 bin/plain.py"
    res = gate.evaluate(jobs, registry=root / ".omo/cron/registry.yaml", repo_root=root,
                        now=datetime.date(2026, 12, 1), installed_plane=[bare])
    assert (res["plane_paired_lines"], res["plane_bare_tokens"], res["plane_gaps"]) == (1, 1, 0)


def test_plane_gap_also_waits_for_the_deadline(tmp_path: Path) -> None:
    """已装面缺口与登记面缺口共用同一条限期，不另开第二个日子。"""
    root = _plane_repo(tmp_path)
    jobs = _plane_jobs(root)
    dead = f"17 3 * * * cd {tmp_path} && {tmp_path}/no-such-venv/bin/python3 bin/plain.py"
    kw = dict(registry=root / ".omo/cron/registry.yaml", repo_root=root, installed_plane=[dead])
    warn = gate.evaluate(jobs, now=datetime.date(2026, 11, 11), **kw)
    hard = gate.evaluate(jobs, now=datetime.date(2026, 12, 1), **kw)
    assert (warn["verdict"], warn["plane_gaps"]) == ("WARN", 1)
    assert (hard["verdict"], hard["plane_gaps"]) == ("FAIL", 1)


def test_no_cron_plane_host_scans_no_installed_lines(tmp_path: Path) -> None:
    """没装 cron 平面的宿主(CI)：已装面 0 行、0 配对、0 缺口 —— 宿主差异不是缺陷。"""
    root = _plane_repo(tmp_path)
    jobs = _plane_jobs(root)
    res = gate.evaluate(jobs, registry=root / ".omo/cron/registry.yaml", repo_root=root,
                        now=datetime.date(2026, 12, 1), installed_plane=[])
    assert (res["plane"], res["plane_lines_scanned"], res["plane_paired_lines"], res["blocking_gaps"]) == (
        "absent", 0, 0, 0,
    )


def test_plane_pairing_failure_is_reported_not_silently_green(tmp_path: Path) -> None:
    """已装面有 python 调用点却一行都配不上 ⇒ 报「配对全空」，而不是 0 缺口的绿。

    钉的是判据自己的失效形状：折回口径一改（或登记面的 schedule/command 写法漂移），
    整条已装面扫描会静默空转 —— 那种绿比红更危险，因为它长得和「本机干净」一模一样。
    """
    root = _plane_repo(tmp_path)
    jobs = _plane_jobs(root)
    orphanish = f"17 3 * * * cd {tmp_path} && {tmp_path}/no-such-venv/bin/python3 bin/plain.py"
    # 把登记条目的 schedule 改掉 ⇒ 已装行再也配不上，但调用点还在
    reg = root / ".omo/cron/registry.yaml"
    data = yaml.safe_load(reg.read_text(encoding="utf-8"))
    data["jobs"][0]["schedule"] = "1 1 2 3 *"
    reg.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    res = gate.evaluate(_plane_jobs(root), registry=reg, repo_root=root,
                        now=datetime.date(2026, 12, 1), installed_plane=[orphanish])
    assert (res["plane_python_sites"], res["plane_paired_lines"], res["plane_pairing_suspicious"]) == (1, 0, 1)
    assert res["verdict"] == "WARN"  # advisory 级：不翻退出码，但不静默
    # 正控制：schedule 改回去 ⇒ 配对恢复，可疑标记消失
    data["jobs"][0]["schedule"] = "17 3 * * *"
    reg.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    res = gate.evaluate(_plane_jobs(root), registry=reg, repo_root=root,
                        now=datetime.date(2026, 12, 1), installed_plane=[orphanish])
    assert (res["plane_paired_lines"], res["plane_pairing_suspicious"], res["plane_gaps"]) == (1, 0, 1)


# ── 同源约束：限期不能有两份值 ─────────────────────────────────────────────
def test_deadline_matches_governance_rule():
    checks = yaml.safe_load((_ROOT / ".omo/_truth/registry/governance-checks.yaml").read_text(encoding="utf-8"))
    rule = [r for r in checks["gac"]["rules"] if r.get("id") == "CR-X2-CRON-INTERP-EXECUTABILITY"]
    assert rule, "规则未登记 ⇒ 门禁没有治理出处"
    assert str(rule[0]["review_before"]) == gate.ENFORCE_AFTER, (
        f"脚本限期 {gate.ENFORCE_AFTER} 与规则 review_before {rule[0]['review_before']} 分叉"
    )
    assert rule[0]["enforcement"] == "advisory", "warn 期规则必须是 advisory"
    assert rule[0]["source_ref"] == "bin/gac/check-cron-interpreter-executability.py"


def test_gate_is_wired_into_local_gate():
    text = (_ROOT / "bin/gac/gac-local-gate.py").read_text(encoding="utf-8")
    assert '"id": "cron-interpreter-executability"' in text
    # SOFT_CHECKS 会取消限期（软检查失败永不翻转 gate），门禁不得躺在里面
    assert "cron-interpreter-executability" not in text[text.index("SOFT_CHECKS = {"):]


def test_run_record_has_six_fields(tmp_path: Path, capsys) -> None:
    registry = _registry(tmp_path)
    assert gate.main(["--registry", str(registry), "--candidate", "/nonexistent/python3", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert sorted(payload["run_record"]) == [
        "approver",
        "basis",
        "duration_ms",
        "inputs",
        "model_usage",
        "result",
    ]


def test_real_registry_is_assessable() -> None:
    """真登记面必须跑得动判据本身（不锁读数 —— 读数是宿主相关的）。"""
    registry = _ROOT / ".omo/cron/registry.yaml"
    jobs = yaml.safe_load(registry.read_text(encoding="utf-8"))["jobs"]
    res = gate.evaluate(
        jobs,
        registry=registry,
        now=datetime.date(2026, 11, 11),
        installed_plane=["*/5 * * * * probe"],
    )
    # 本机不是 cron 宿主时作业会整批落到 jobs_off_host（CI 的形状）；两个数之和才证明
    # 「调用点看得见」，只扫 jobs_scanned 会让这台机器上的绿依赖宿主身份。
    assert res["jobs_scanned"] + res["jobs_off_host"] > 0
    # 已装面的非空转由 test_plane_pairing_failure_is_reported 钉；这里注入的是玩具 plane，
    # 拿它断言配对非零会红，所以只断言计数之间的关系：有调用点就必须给出配对数或可疑标记。
    assert res["plane_python_sites"] >= res["plane_paired_lines"]
    assert set(res) >= {
        "verdict",
        "blocking_gaps",
        "closure_advisories",
        "undetermined_edges",
        "jobs_off_host",
        "plane",
        "plane_lines_scanned",
        "plane_paired_lines",
        "plane_gaps",
        "plane_unregistered_broken",
        "plane_bare_tokens",
        "plane_python_sites",
        "plane_pairing_suspicious",
        "gaps",
        "advisories",
    }
