"""双 profile verify 腿的不变量 (BET-Y2Q4-T10-248)。

契约: `docs/superpowers/specs/2026-10-13-dual-profile-verify-leg.md` (I1–I9)
门禁本体: `bin/gac/dual-profile-verify.py`

本文件只测三件容易假装成功的事:

- **正向落点** (I2): 「检出没被写」不是通过证据。所以既测「落点对」也测
  「生成器自称写了却什么都没写」与「写到另一个 root 里」两种必须变红的形状。
- **仪表真被消费** (I3): `OMOSTATION_PROFILE` 实测零消费者; 既做静态反读断言,
  也用 `repo_root --json` 的逐字节对拍证明设与不设它都不改变解析结果。
- **探不到 ≠ 过了** (I5/I6): install_root 缺失、host-only 腿一律 deferred,
  且 deferred 不得进通过数。

用例一律在 `HOME=<tmp>` + 剥掉四条 profile env 下跑, 不读宿主状态
(AGENTS.md §7「hermetic 测试泄漏 host 状态」)。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_REL = Path("bin") / "gac" / "dual-profile-verify.py"
PROFILE_ENV = "OMOSTATION_PROFILE"
FORBIDDEN_XDG = Path(".local") / "state" / "omostation"

# 生成器桩: 只依赖 stdlib, 从注入的 OMOSTATION_STATE_ROOT 派生落点。
#   write  —— 真写, 报 materialized (合法形状)
#   silent —— 报 materialized 但一个字节都不写 (负向判据的照妖镜)
#   fail   —— 写了, 但状态不是「一次写」, 用来单独钉住状态判据
FAKE_GENERATOR = '''
import json
import os
from pathlib import Path

mode = os.environ.get("FAKE_MODE", "write")
root = os.environ["OMOSTATION_STATE_ROOT"]
template = os.environ.get("FAKE_TARGET_TEMPLATE", str(Path(root) / ".omo" / "state" / "system.yaml"))
target = Path(template.replace("{root}", root))
status = "materialized" if mode != "fail" else "failed"
if mode != "silent":
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("generated\\n", encoding="utf-8")
print(json.dumps({"status": status, "target": str(target)}))
'''


def _under(path: Path | str, base: Path | str) -> bool:
    try:
        Path(path).resolve().relative_to(Path(base).resolve())
        return True
    except (ValueError, OSError):
        return False


@pytest.fixture()
def mod():
    import importlib.util

    spec = importlib.util.spec_from_file_location("dual_profile_verify", ROOT / SCRIPT_REL)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def hermetic(tmp_path, monkeypatch):
    """把 profile env 面与 HOME 全部收进 tmp, 用例不读宿主状态。"""
    for name in ("OMOSTATION_ROOT", "OMOSTATION_STATE_ROOT", "OMO_EVENT_LEDGER_DB", PROFILE_ENV, "OMOSTATION_INSTALL_ROOT"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


@pytest.fixture()
def workspace(tmp_path):
    """一个干净的最小 git 检出, 让 isolation 副判据有确定读数。"""
    ws = tmp_path / "checkout"
    ws.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=ws, check=True, timeout=60)
    return ws


@pytest.fixture()
def generator(tmp_path):
    gen = tmp_path / "fake_generator.py"
    gen.write_text(FAKE_GENERATOR, encoding="utf-8")
    return gen


def _invoke(mod, tmp_capsys, argv: list[str]) -> tuple[int, dict]:
    code = mod.main(argv)
    out = tmp_capsys.readouterr().out
    return code, (json.loads(out) if "--json" in argv else {"text": out})


def _argv(workspace: Path, generator: Path, profiles: str, roots: dict[str, Path]) -> list[str]:
    argv = ["--profiles", profiles, "--workspace", str(workspace), "--generator", str(generator), "--json"]
    for label, path in roots.items():
        argv += ["--root", f"{label}={path}"]
    return argv


# ── I1 双根各跑一遍 ─────────────────────────────────────────────────────────


def test_two_profiles_each_land_inside_their_own_declared_root(mod, hermetic, workspace, generator, capsys):
    prod = hermetic / "state" / "prod"
    dev = hermetic / "state" / "dev"
    code, report = _invoke(mod, capsys, _argv(workspace, generator, "prod,dev", {"prod": prod, "dev": dev}))

    assert code == 0 and report["ok"] is True
    assert report["summary"]["pass"] == 2 and report["summary"]["fail"] == 0
    for leg in report["legs"]:
        assert leg["status"] == "pass"
        assert _under(leg["landing"], leg["root"])
        assert Path(leg["landing"]).is_file()
    assert {leg["landing"] for leg in report["legs"]} == {
        str((prod / ".omo/state/system.yaml").resolve()),
        str((dev / ".omo/state/system.yaml").resolve()),
    }


def test_single_profile_is_rejected_not_silently_passed(mod, hermetic, workspace, generator, capsys):
    code, report = _invoke(mod, capsys, _argv(workspace, generator, "prod", {"prod": hermetic / "prod"}))
    assert code != 0
    assert report["ok"] is False
    assert "at least two profiles" in report["legs"][0]["reason"]


def test_two_labels_pointing_at_one_root_is_rejected(mod, hermetic, workspace, generator, capsys):
    shared = hermetic / "one"
    code, report = _invoke(mod, capsys, _argv(workspace, generator, "prod,dev", {"prod": shared, "dev": shared}))
    assert code != 0
    assert "same state root" in report["legs"][0]["reason"]
    assert report["summary"]["pass"] == 0


# ── I2 正向落点, 以及「检出没写」为什么不够 ─────────────────────────────────


def test_landing_in_another_profiles_root_fails_even_though_the_file_was_written(
    mod, hermetic, workspace, generator, capsys, monkeypatch
):
    """spec §1b: 「落在声明 root 之外(含另一 profile 的 root)」即 FAIL。

    把模板指到 dev 的 root: prod 腿写到别人的根里 → 必须红; dev 腿写在自己的根里 →
    必须绿。同一份报告里两种判定共存, 才证明判据是**逐腿**的而不是全局的。
    """
    prod = hermetic / "prod"
    dev = hermetic / "dev"
    monkeypatch.setenv("FAKE_TARGET_TEMPLATE", str(dev / ".omo" / "state" / "system.yaml"))
    code, report = _invoke(mod, capsys, _argv(workspace, generator, "prod,dev", {"prod": prod, "dev": dev}))

    assert code != 0 and report["ok"] is False
    bad = next(leg for leg in report["legs"] if leg["profile"] == "prod")
    good = next(leg for leg in report["legs"] if leg["profile"] == "dev")
    assert bad["status"] == "fail" and "outside the declared root" in bad["reason"]
    assert good["status"] == "pass"
    assert Path(bad["landing"]).is_file(), "变异前提: 文件确实写成了, 只是在别人的 root 里"
    assert _under(bad["landing"], dev) and not _under(bad["landing"], prod)


def test_generator_claiming_a_write_that_never_happened_fails(mod, hermetic, workspace, generator, capsys, monkeypatch):
    """负向判据的照妖镜: 生成器报 materialized, 落点按声明 root 报路径, 但一个字节都没写。

    此时「检出不脏」这条副判据仍然是 True —— 用它当验收就会假绿, 所以本用例同时钉住
    「ok=False」与「isolation 看着没事」两件事同真。
    """
    monkeypatch.setenv("FAKE_MODE", "silent")
    code, report = _invoke(
        mod, capsys, _argv(workspace, generator, "prod,dev", {"prod": hermetic / "prod", "dev": hermetic / "dev"})
    )
    assert code != 0
    assert all(leg["status"] == "fail" for leg in report["legs"])
    assert "does not exist" in report["legs"][0]["reason"]
    assert report["isolation"]["checkout_clean"] is True, "副判据在此案中为真, 却不足以放行"
    assert report["ok"] is False


def test_failed_generator_status_is_not_a_pass(mod, hermetic, workspace, generator, capsys, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "fail")
    code, report = _invoke(
        mod, capsys, _argv(workspace, generator, "prod,dev", {"prod": hermetic / "prod", "dev": hermetic / "dev"})
    )
    assert code != 0
    assert "not a write" in report["legs"][0]["reason"] or "no JSON" in report["legs"][0]["reason"]


# ── I3 仪表必须是被真消费的旋钮 ─────────────────────────────────────────────


def test_leg_script_never_reads_the_unconsumed_profile_env():
    source = (ROOT / SCRIPT_REL).read_text(encoding="utf-8")
    assert 'environ.get("OMOSTATION_PROFILE"' not in source
    assert 'environ["OMOSTATION_PROFILE"]' not in source
    assert "OMOSTATION_STATE_ROOT" in source, "腿必须注入实测被消费的 state 根, 不是别的开关"


def test_repo_root_resolution_is_byte_identical_with_and_without_profile_env(mod, hermetic):
    env = {
        "PATH": __import__("os").environ.get("PATH", ""),
        "HOME": str(hermetic),
        "OMOSTATION_ROOT": str(ROOT),
    }
    argv = [sys.executable, str(ROOT / "bin" / "lib" / "repo_root.py"), "--json"]
    without = subprocess.run(argv, capture_output=True, text=True, env=env, timeout=60, cwd=str(ROOT))
    with_profile = subprocess.run(
        argv, capture_output=True, text=True, env={**env, PROFILE_ENV: "dev"}, timeout=60, cwd=str(ROOT)
    )
    assert without.returncode == 0 and with_profile.returncode == 0
    assert without.stdout == with_profile.stdout, "设了该 env 却改变解析结果 = 它其实是开关, spec 前提须重测"


def test_leg_env_sets_state_root_and_strips_parent_overrides(mod):
    env = mod.leg_env(
        Path("/tmp/x/prod"),
        {"OMOSTATION_ROOT": "/tmp/checkout", "OMO_EVENT_LEDGER_DB": "/tmp/host.db", PROFILE_ENV: "prod", "PATH": "/bin"},
    )
    assert env["OMOSTATION_STATE_ROOT"] == str(Path("/tmp/x/prod").resolve())
    assert "OMOSTATION_ROOT" not in env and "OMO_EVENT_LEDGER_DB" not in env
    assert PROFILE_ENV not in env


# ── I4 隔离: 默认 root 既不在检出里, 也不在任何真权威状态面里 ────────────────


def test_scratch_default_is_not_under_checkout_or_xdg_state(mod, hermetic):
    home = Path(hermetic)
    root, origin = mod.resolve_root(
        "prod", {}, {"HOME": str(home)}, mkdtemp=lambda prefix: str(home / "tmp" / prefix)
    )
    assert origin == "scratch"
    assert root.name.startswith("dual-profile-prod-")
    assert not _under(root, mod.code_root())
    assert not _under(root, home / FORBIDDEN_XDG)


def test_declared_state_root_is_consumed_per_label_subdirectory(mod, hermetic):
    declared = hermetic / "xdg" / "state"
    root, origin = mod.resolve_root("dev", {}, {"OMOSTATION_STATE_ROOT": str(declared)})
    assert origin == "declared"
    assert root == declared / "dev"


def test_explicit_root_override_wins_and_is_reported_as_origin(mod, hermetic):
    root, origin = mod.resolve_root("prod", {"prod": str(hermetic / "given")}, {"OMOSTATION_STATE_ROOT": str(hermetic / "x")})
    assert origin == "--root"
    assert root == hermetic / "given"


def test_root_under_checkout_or_xdg_state_is_rejected(mod, hermetic, workspace, generator, capsys):
    code, report = _invoke(
        mod,
        capsys,
        _argv(workspace, generator, "prod,dev", {"prod": mod.code_root() / "poison", "dev": hermetic / "dev"}),
    )
    assert code != 0
    assert "under the checkout root" in report["legs"][0]["reason"]


# ── I5 install_root 落后即告警, 探不到不得记 pass ───────────────────────────


class _Git:
    def __init__(self, responses: dict[str, tuple[int, str]], default: tuple[int, str] = (1, "")):
        self.responses = responses
        self.default = default
        self.calls: list[list[str]] = []

    def __call__(self, cmd, **kwargs):
        self.calls.append(list(cmd))
        rc, out = self.responses.get(" ".join(cmd[3:]), self.default)
        return subprocess.CompletedProcess(cmd, rc, out, "")


def _git_install(**over) -> _Git:
    responses = {
        "rev-parse HEAD": (0, "1b5f02cb3"),
        "rev-parse --verify --quiet origin/main": (0, "508d64930"),
        "merge-base --is-ancestor HEAD origin/main": (0, ""),
        "rev-list --count HEAD..origin/main": (0, "312"),
    }
    for key, value in over.items():
        if value is None:
            responses.pop(key, None)
        else:
            responses[key] = value
    return _Git(responses)


def test_missing_install_root_is_deferred_and_never_counted_as_pass(mod, hermetic):
    report = mod.install_root_drift(root=None, locator=lambda: None)
    assert report["status"] == "deferred"
    assert report["behind"] is None
    counts = mod.summarize([], report, [])
    assert counts["deferred"] == 1 and counts["pass"] == 0


def test_behind_install_root_is_warn_not_fail(mod, hermetic):
    report = mod.install_root_drift(root=hermetic / "install", runner=_git_install())
    assert report["status"] == "warn"
    assert report["behind"] == 312 and report["is_ancestor"] is True
    assert "312 commits behind" in report["reason"]


def test_non_ancestor_install_root_is_warn(mod, hermetic):
    runner = _git_install(**{"merge-base --is-ancestor HEAD origin/main": (1, "")})
    report = mod.install_root_drift(root=hermetic / "install", runner=runner)
    assert report["status"] == "warn"
    assert "not an ancestor" in report["reason"]


def test_up_to_date_install_root_is_the_only_passing_reading(mod, hermetic):
    runner = _git_install(**{"rev-list --count HEAD..origin/main": (0, "0")})
    report = mod.install_root_drift(root=hermetic / "install", runner=runner)
    assert report["status"] == "pass" and report["reason"] == ""


def test_install_root_without_origin_ref_is_deferred(mod, hermetic):
    runner = _git_install(**{"rev-parse --verify --quiet origin/main": (1, "")})
    report = mod.install_root_drift(root=hermetic / "install", runner=runner)
    assert report["status"] == "deferred"


def test_warn_alone_keeps_the_leg_exit_zero(mod, hermetic, workspace, generator, capsys, monkeypatch):
    monkeypatch.setattr(mod, "install_root_drift", lambda *a, **k: {"status": "warn", "reason": "behind", "head": "x", "is_ancestor": True, "behind": 312, "target": "/x"})
    code, report = _invoke(
        mod, capsys, _argv(workspace, generator, "prod,dev", {"prod": hermetic / "prod", "dev": hermetic / "dev"})
    )
    assert code == 0 and report["ok"] is True
    assert report["summary"]["warn"] == 1 and report["summary"]["pass"] == 2


# ── I6 host-only 腿一律 deferred ────────────────────────────────────────────


@pytest.mark.parametrize(
    "which, expect",
    [
        (lambda name: None, "no launchd surface"),
        (lambda name: "/bin/launchctl", "needs explicit authorization"),
    ],
    ids=["no-launchd", "with-launchd"],
)
def test_host_only_legs_are_deferred_with_a_probed_reason(mod, which, expect):
    legs = mod.host_legs(which=which)
    assert legs and all(item["status"] == "deferred" for item in legs)
    assert all(expect in item["reason"] for item in legs)
    counts = mod.summarize([], {"status": "deferred", "reason": ""}, legs)
    assert counts["pass"] == 0 and counts["deferred"] == len(legs) + 1


# ── 真生成器的端到端一跳 (spec §1 实测过的通道) ─────────────────────────────


def test_real_generator_lands_in_the_declared_root(mod, hermetic, capsys):
    pytest.importorskip("yaml")
    prod = hermetic / "real-prod"
    dev = hermetic / "real-dev"
    argv = ["--profiles", "prod,dev", "--workspace", str(ROOT), "--root", f"prod={prod}", f"--root=dev={dev}", "--json"]
    code, report = _invoke(mod, capsys, argv)
    assert code == 0, report
    assert all(leg["status"] == "pass" for leg in report["legs"])
    assert all(leg["generator_status"] in ("materialized", "skipped") for leg in report["legs"])
