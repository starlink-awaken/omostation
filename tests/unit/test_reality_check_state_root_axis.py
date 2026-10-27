"""E7 —— plist 声明的**写根** (EnvironmentVariables.OMOSTATION_STATE_ROOT) 落在哪个根（BET-Y2Q4-T10-272）。

被测对象: bin/mof/gen-service-configs.py 的 state_root_pins() / reality_check() 的 E7 面
/ validate_service_declaration() 的 require_state_root_partitioned。
契约来源: docs/superpowers/specs/2026-10-26-bet-272-e7-write-root-reality-axis.md §3 §5。

全部用例 hermetic: 两棵树、profile 基座与 LaunchAgents 目录都在 tmp 下，
enumerate 与 measured_base 被注入 —— 不读 ~/Library/LaunchAgents、不调 plutil、不跑子进程。
"""

from __future__ import annotations

import importlib.util
import json
import plistlib
from pathlib import Path

import pytest
import yaml

MODULE_PATH = Path(__file__).parents[2] / "bin" / "mof" / "gen-service-configs.py"

LABEL = "com.l4.resident.execute"


def _module():
    spec = importlib.util.spec_from_file_location("gen_service_e7_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MOD = _module()


@pytest.fixture
def roots(tmp_path):
    checkout = tmp_path / "Workspace"
    install = tmp_path / ".local" / "opt" / "omostation"
    profile = tmp_path / ".local" / "state" / "omostation"
    checkout.mkdir(parents=True)
    install.mkdir(parents=True)
    profile.mkdir(parents=True)
    return {"checkout": checkout, "install": install, "profile_base": profile}


def _svc(**extra) -> dict:
    base = {
        "id": "resident-execute",
        "label": LABEL,
        "scheduler": "launchd",
        "enabled": True,
        "runtime_root": "install",
        "program": {"interpreter": "/bin/bash", "entrypoint": "lib/resident-role-tick.sh"},
    }
    base.update(extra)
    return base


def _row(env: dict | None, label: str = LABEL, launchd_dir: Path | None = None) -> dict:
    """照 enumerate_launchd_plists 的真实形状造一行：argv 指安装位 wrapper，env 由入参给。

    path 必须是一份合法 plist 文件，否则 E3(plist_strict_well_formed) 在 fixture 上红，
    observe-only 那条用例的 `ok is True` 测的就不是 E7 而是别的轴。
    """
    argv_root = (launchd_dir or Path.cwd()).parent / "opt" / "omostation"
    argv = ["/bin/bash", str(argv_root / "lib" / "resident-role-tick.sh"), "execute"]
    payload = {"Label": label, "ProgramArguments": argv}
    if env is not None:
        payload["EnvironmentVariables"] = env
    directory = launchd_dir or Path.cwd()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{label}.plist"
    path.write_bytes(plistlib.dumps(payload))
    return {
        "file": path.name,
        "path": path,
        "label": label,
        "plutil_ok": True,
        "blob": json.dumps(payload, ensure_ascii=False),
        "program_arguments": [str(a) for a in argv],
    }


def _pins(services: list[dict], rows: list[dict], roots: dict) -> list[dict]:
    return MOD.state_root_pins(services, rows, roots)


# ------------------------------------------------------------------ 分类判据


def test_e7_names_a_service_whose_code_moved_but_writes_did_not(roots, tmp_path) -> None:
    """V1 正向落点：argv 在安装位、env 把写根钉回检出 —— 必须点名且分类为 checkout。"""
    row = _row({"OMOSTATION_STATE_ROOT": str(roots["checkout"])}, launchd_dir=tmp_path)
    out = _pins([_svc()], [row], roots)
    assert len(out) == 1, out
    assert out[0]["label"] == LABEL
    assert out[0]["declared_runtime_root"] == "install"
    assert out[0]["state"] == "checkout"
    assert out[0]["declared_state_root"] == str(roots["checkout"])


def test_e7_profile_state_root_counts_as_partitioned(roots, tmp_path) -> None:
    """写根进 XDG profile 根 = 目标形状：分类 profile，且不落进未分区集。"""
    row = _row({"OMOSTATION_STATE_ROOT": str(roots["profile_base"] / "prod")}, launchd_dir=tmp_path)
    out = _pins([_svc()], [row], roots)
    assert out[0]["state"] == "profile"
    assert out[0]["label"] not in [
        r["label"] for r in out if r["state"] not in MOD.STATE_ROOT_OK_STATES["install"]
    ]


def test_e7_env_absent_is_undeclared_and_still_unpartitioned_for_install(roots, tmp_path) -> None:
    """键缺席是合法历史形状（state_root 由 code_root 兜底），但对声明 install 的服务仍未分区。"""
    out = _pins([_svc()], [_row(None, launchd_dir=tmp_path)], roots)
    assert out[0]["state"] == "undeclared"
    assert out[0]["declared_state_root"] is None


def test_e7_empty_env_value_is_not_folded_into_absent(roots, tmp_path) -> None:
    """「键不存在」与「键存在但为空」不得同形 —— 后者是配置错误，不是历史形状。"""
    out = _pins([_svc()], [_row({"OMOSTATION_STATE_ROOT": ""}, launchd_dir=tmp_path)], roots)
    assert out[0]["state"] != "undeclared"
    assert out[0]["state"] == "other"


def test_e7_declared_checkout_writes_to_checkout_is_ok(roots, tmp_path) -> None:
    """码与写都在检出（今日 372 条缺省形状）不是 E7 的命中 —— 过宽的判据会把基线全点亮。"""
    out = _pins(
        [_svc(runtime_root="checkout")],
        [_row({"OMOSTATION_STATE_ROOT": str(roots["checkout"])}, launchd_dir=tmp_path)],
        roots,
    )
    assert out[0]["state"] == "checkout"
    assert out[0]["state"] in MOD.STATE_ROOT_OK_STATES["checkout"]


def test_e7_installed_state_root_is_its_own_state(roots, tmp_path) -> None:
    """写根指安装位既不是 profile 也不是检出 —— 单独分类，不并入 checkout。"""
    out = _pins([_svc()], [_row({"OMOSTATION_STATE_ROOT": str(roots["install"])}, launchd_dir=tmp_path)], roots)
    assert out[0]["state"] == "install"


def test_e7_skips_services_without_runtime_root(roots, tmp_path) -> None:
    """未声明 runtime_root 的条目不进 E7 —— 今日 372 条服务不该被这条轴点名。"""
    svc = _svc()
    del svc["runtime_root"]
    assert _pins([svc], [_row({}, launchd_dir=tmp_path)], roots) == []


def test_e7_uninstalled_service_is_undetermined_not_ok(roots) -> None:
    """注册表声明了根但本机没有那份 plist：不得当成已分区。"""
    out = _pins([_svc()], [], roots)
    assert out[0]["state"] == "undetermined"


def test_e7_detector_is_not_a_no_op(roots, tmp_path) -> None:
    """自证（AGENTS.md §7③）：同一批数据里命中的要点名、合法的不得点名，否则「绿」只是没命中。"""
    hit = _row({"OMOSTATION_STATE_ROOT": str(roots["checkout"])}, label=LABEL, launchd_dir=tmp_path)
    fine = _row(
        {"OMOSTATION_STATE_ROOT": str(roots["profile_base"] / "dev")},
        label="com.l4.resident.promote",
        launchd_dir=tmp_path,
    )
    services = [_svc(), _svc(id="resident-promote", label="com.l4.resident.promote")]
    out = _pins(services, [hit, fine], roots)
    by_state = {r["label"]: r["state"] for r in out}
    assert by_state == {LABEL: "checkout", "com.l4.resident.promote": "profile"}
    non_ok = [r["label"] for r in out if r["state"] not in MOD.STATE_ROOT_OK_STATES[r["declared_runtime_root"]]]
    assert non_ok == [LABEL]


# ------------------------------------------------------------------ 注册表面


def _registry(path: Path, *, strict: bool, services: list[dict] | None = None) -> Path:
    svc = _svc()
    if strict:
        svc["require_state_root_partitioned"] = True
    rows = services if services is not None else [svc]
    # workspace_prefixes 存不带尾点的点段；写成 "com.l4." 会让分区把本仓服务判成
    # unmanaged_unknown —— 那是 fixture 错，E4 会连带把 ok 压成 false。
    path.write_text(
        yaml.safe_dump({"services": rows, "launchd_namespace": {"workspace_prefixes": ["com.l4"]}},
                       allow_unicode=True),
        encoding="utf-8",
    )
    return path


@pytest.fixture
def launchd_dir(tmp_path):
    d = tmp_path / "LaunchAgents"
    d.mkdir()
    return d


def _call_reality(registry: Path, launchd: Path, roots: dict, row: dict, monkeypatch) -> dict:
    def _enumerate(_dir):
        return [row]

    monkeypatch.setattr(MOD, "enumerate_launchd_plists", _enumerate)
    return MOD.reality_check(
        registry,
        launchd,
        e1={"status": "ok", "drift_count": 0, "drifts": []},
        workspace_root=roots["checkout"],
        base={"base_state": "equal", "head": "x", "origin_main": "x",
              "registry_file": registry.name, "registry_sha256": "x"},
        kernel_roots=roots,
    )


def test_e7_default_observe_only_does_not_move_ok_or_findings(roots, tmp_path, launchd_dir, monkeypatch) -> None:
    """缺省（不声明开关）：命中只进返回值, 不进 findings —— 红≠修，改 plist 属逐批授权面。"""
    row = _row({"OMOSTATION_STATE_ROOT": str(roots["checkout"])}, launchd_dir=launchd_dir)
    report = _call_reality(_registry(tmp_path / "services.yaml", strict=False), launchd_dir, roots, row, monkeypatch)
    assert report["e7_non_ok"] == 1
    assert report["e7_checkout"] == 1
    assert report["e7_profile"] == 0
    assert report["e7_states"] == {"checkout": 1}
    assert report["e7_blocking"] == 0
    assert not [f for f in report["findings"] if f.startswith("E7")]
    assert report["ok"] is True


def test_e7_require_state_root_partitioned_promotes_the_same_hit(roots, tmp_path, launchd_dir, monkeypatch) -> None:
    """同一个命中，声明 require_state_root_partitioned: true 之后必须进 findings。"""
    row = _row({"OMOSTATION_STATE_ROOT": str(roots["checkout"])}, launchd_dir=launchd_dir)
    report = _call_reality(_registry(tmp_path / "services.yaml", strict=True), launchd_dir, roots, row, monkeypatch)
    assert report["e7_blocking"] == 1
    e7 = [f for f in report["findings"] if f.startswith("E7")]
    assert len(e7) == 1
    assert LABEL in e7[0]
    assert str(roots["checkout"]) in e7[0]
    assert report["ok"] is False


def test_e7_promotion_does_not_disturb_e1_to_e6(roots, tmp_path, launchd_dir, monkeypatch) -> None:
    """新增一桶不得改动别的桶读数：E1 仍 0、E6 仍按自己的判据走。"""
    row = _row({"OMOSTATION_STATE_ROOT": str(roots["checkout"])}, launchd_dir=launchd_dir)
    report = _call_reality(_registry(tmp_path / "services.yaml", strict=True), launchd_dir, roots, row, monkeypatch)
    assert report["e1_drift"] == 0
    assert report["e6_non_ok"] == 1  # 同一份 fixture：argv 指安装位、内核脚本不存在 → undetermined
    assert [f for f in report["findings"] if f.startswith("E1")] == []


def test_e7_state_breakdown_covers_every_row(roots, tmp_path, launchd_dir, monkeypatch) -> None:
    """全分类字典必须逐行覆盖：只列 checkout/undeclared/profile 三项会把 undetermined
    藏成「未分区但没有分类」。"""
    installed = _row({"OMOSTATION_STATE_ROOT": str(roots["checkout"])}, launchd_dir=launchd_dir)
    registry = _registry(
        tmp_path / "services.yaml",
        strict=False,
        services=[_svc(), _svc(id="resident-promote", label="com.l4.resident.promote")],
    )
    report = _call_reality(registry, launchd_dir, roots, installed, monkeypatch)
    assert report["e7_states"] == {"checkout": 1, "undetermined": 1}
    assert sum(report["e7_states"].values()) == len(report["e7_state_root"]) == 2


# ------------------------------------------------------------------ schema 准入


def test_require_state_root_partitioned_needs_runtime_root() -> None:
    svc = _svc()
    del svc["runtime_root"]
    svc["require_state_root_partitioned"] = True
    violations = MOD.validate_service_declaration(svc)
    assert any("require_state_root_partitioned" in v and "runtime_root" in v for v in violations), violations


def test_require_state_root_partitioned_rejects_false() -> None:
    """写 false 是给「缺省即不声明」造第二个真值来源。"""
    violations = MOD.validate_service_declaration(_svc(require_state_root_partitioned=False))
    assert any("只接受 true" in v for v in violations), violations


def test_require_state_root_partitioned_accepts_true_with_runtime_root() -> None:
    assert MOD.validate_service_declaration(_svc(require_state_root_partitioned=True)) == []


def test_kernel_root_match_rules_are_unchanged() -> None:
    """E6 那颗开关的三条判据不因本次循环化而失效（同一函数、两种键）。"""
    svc = _svc()
    del svc["runtime_root"]
    svc["require_kernel_root_match"] = True
    assert any("require_kernel_root_match" in v for v in MOD.validate_service_declaration(svc))
    assert any("只接受 true" in v for v in MOD.validate_service_declaration(_svc(require_kernel_root_match=False)))
    assert MOD.validate_service_declaration(_svc(require_kernel_root_match=True)) == []
