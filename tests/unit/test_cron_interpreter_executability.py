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

import cron_normalize as cn  # noqa: E402
import importlib  # noqa: E402

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
    assert set(res) >= {
        "verdict",
        "blocking_gaps",
        "closure_advisories",
        "undetermined_edges",
        "jobs_off_host",
        "plane",
        "gaps",
        "advisories",
    }
