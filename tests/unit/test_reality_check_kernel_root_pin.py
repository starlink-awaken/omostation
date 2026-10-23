"""E6 —— 入口脚本**内核**钉住的根是否等于声明的 `runtime_root`（BET-Y2Q4-T10-266）。

被测对象: bin/mof/gen-service-configs.py 的 kernel_root_pins() / _entrypoint_script()
/ reality_check() 的 E6 面 / validate_service_declaration() 的 require_kernel_root_match。
契约来源: docs/superpowers/specs/2026-10-23-resident-entrypoint-kernel-root.md §3。

全部用例 hermetic: 两棵树与 LaunchAgents 目录都在 tmp 下, enumerate 与 measured_base
被注入, 不读 ~/Library/LaunchAgents、不调 plutil、不跑子进程。
"""

from __future__ import annotations

import importlib.util
import json
import plistlib
from pathlib import Path

import pytest
import yaml

MODULE_PATH = Path(__file__).parents[2] / "bin" / "mof" / "gen-service-configs.py"

LABEL = "com.l4.resident.decision"


def _module():
    spec = importlib.util.spec_from_file_location("gen_service_e6_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MOD = _module()


def _tree(root: Path, body: str) -> Path:
    """在 `root` 下造一份 lib/resident-role-tick.sh, 内容是 `body` 里的 {ROOT} 展开。"""
    other = body  # placeholder; callers format themselves
    script = root / "lib" / "resident-role-tick.sh"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(other, encoding="utf-8")
    return script


def _pins(services: list[dict], rows: list[dict], roots: dict) -> list[dict]:
    return MOD.kernel_root_pins(services, rows, roots)


def _svc(**extra) -> dict:
    base = {
        "id": "resident-decision",
        "label": LABEL,
        "scheduler": "launchd",
        "runtime_root": "install",
        # launchd 生成面的必填项：缺了它 validate 报的是「条目本身不合法」，
        # 而不是「require_kernel_root_match 合法」—— 正反面会混在同一份返回值里。
        "program": {"interpreter": "/bin/bash", "entrypoint": "lib/resident-role-tick.sh"},
    }
    base.update(extra)
    return base


def _row(script: Path, label: str = LABEL, launchd_dir: Path | None = None) -> dict:
    """照 enumerate_launchd_plists 的真实形状造一行：path 是一份合法 plist 文件。

    把 path 指向 wrapper 脚本会让 E3(plist_strict_well_formed) 在 fixture 上红，
    于是 observe-only 那条用例的 `ok is True` 测的就不是 E6 而是别的轴。
    """
    argv = ["/bin/bash", str(script), "decision"]
    payload = {"Label": label, "ProgramArguments": argv}
    path = (launchd_dir or script.parent) / f"{label}.plist"
    path.write_bytes(plistlib.dumps(payload))
    return {
        "file": path.name,
        "path": path,
        "label": label,
        "plutil_ok": True,
        "blob": json.dumps(payload, ensure_ascii=False),
        "program_arguments": [str(a) for a in argv],
    }


@pytest.fixture
def roots(tmp_path):
    checkout = tmp_path / "checkout"
    install = tmp_path / "install"
    for d in (checkout, install):
        (d / "lib").mkdir(parents=True)
    return {"checkout": checkout, "install": install}


# ---------------------------------------------------------------- 检测器本体

def test_e6_names_wrapper_that_pins_the_other_root(roots) -> None:
    """入口 argv 合法地落在安装位, 但 wrapper 里 exec 的是检出 —— 必须点名。"""
    script = _tree(roots["install"], f"exec uv run --project {roots['checkout']}/projects/omo python -m omo\n")
    out = _pins([_svc()], [_row(script)], roots)
    assert out == [
        {
            "label": LABEL,
            "declared_root": "install",
            "script": str(script),
            "state": "pinned_other_root",
            "pinned_root": "checkout",
            "pin_count": 1,
        }
    ]


def test_e6_wrapper_mentioning_only_declared_root_is_ok(roots) -> None:
    script = _tree(roots["install"], f"exec uv run --project {roots['install']}/projects/omo python -m omo\n")
    out = _pins([_svc()], [_row(script)], roots)
    assert out[0]["state"] == "ok"
    assert out[0]["pin_count"] == 0


def test_e6_detector_is_not_a_no_op(roots) -> None:
    """空绿反证: 同一 label、同一 argv, 只改脚本内容 ⇒ state 必须翻转。

    若检测器结构性看不见字面量（例如只比 argv），这两次读数会相同而「绿」。
    """
    script = _tree(roots["install"], f"exec uv run --project {roots['install']}/projects/omo\n")
    before = _pins([_svc()], [_row(script)], roots)[0]
    script.write_text(f"exec uv run --project {roots['checkout']}/projects/omo\n", encoding="utf-8")
    after = _pins([_svc()], [_row(script)], roots)[0]
    assert (before["state"], after["state"]) == ("ok", "pinned_other_root")
    assert after["pin_count"] >= 1


@pytest.mark.parametrize("shape", ["not-installed", "argv-without-script", "script-outside-declared-root"])
def test_e6_unidentifiable_entrypoint_is_undetermined_never_ok(roots, shape) -> None:
    """认不出入口不得算通过（spec §3.1）——「没查到」与「查过且合规」必须不同形。"""
    script = _tree(roots["install"], f"exec uv run --project {roots['install']}/projects/omo\n")
    services, rows = [_svc()], []
    if shape == "not-installed":
        rows = []
    elif shape == "argv-without-script":
        rows = [{**_row(script), "program_arguments": ["/usr/bin/python3", "-c", "pass"]}]
    else:
        foreign = _tree(roots["checkout"], "echo hi\n")
        rows = [_row(foreign)]
    out = _pins(services, rows, roots)
    assert out[0]["state"] == "undetermined"
    assert out[0]["script"] is None


def test_e6_missing_install_root_is_undetermined(tmp_path) -> None:
    """声明 install 而这台机器没有安装位 ⇒ undetermined，不得退回检出根算 ok。"""
    checkout = tmp_path / "checkout"
    (checkout / "lib").mkdir(parents=True)
    script = _tree(checkout, "echo hi\n")
    out = _pins([_svc()], [_row(script)], {"checkout": checkout, "install": None})
    assert out[0]["state"] == "undetermined"


def test_e6_declared_checkout_pinning_install_is_also_a_hit(roots) -> None:
    """反方向同形：声明检出却把内核钉在安装位，同样是 pinned_other_root。"""
    script = _tree(roots["checkout"], f"exec uv run --project {roots['install']}/projects/omo\n")
    out = _pins([_svc(runtime_root="checkout")], [_row(script)], roots)
    assert out[0]["state"] == "pinned_other_root"
    assert out[0]["pinned_root"] == "install"


def test_e6_skips_services_without_runtime_root(roots) -> None:
    """缺省条目（未声明 runtime_root）不进 E6 —— 今天 372 条服务不该被这条轴点名。"""
    script = _tree(roots["install"], f"exec uv run --project {roots['checkout']}/x\n")
    svc = _svc()
    del svc["runtime_root"]
    assert _pins([svc], [_row(script)], roots) == []


# ---------------------------------------------------------------- 注册表面

def _registry(path: Path, *, strict: bool) -> Path:
    svc = {
        "id": "resident-decision",
        "label": LABEL,
        "scheduler": "launchd",
        "enabled": True,
        "runtime_root": "install",
    }
    if strict:
        svc["require_kernel_root_match"] = True
    # workspace_prefixes 存**不带尾点**的点段（match_workspace_prefix 按点段边界匹配）；
    # 写成 "com.l4." 会让分区把本仓服务判成 unmanaged_unknown —— 那是 fixture 错，
    # 不是 E6 的判定。
    path.write_text(
        yaml.safe_dump({"services": [svc], "launchd_namespace": {"workspace_prefixes": ["com.l4"]}},
                       allow_unicode=True),
        encoding="utf-8",
    )
    return path


@pytest.fixture
def launchd_dir(tmp_path):
    d = tmp_path / "LaunchAgents"
    d.mkdir()
    return d


def _call_reality(registry: Path, launchd: Path, roots: dict, script: Path, monkeypatch,
                  argv: list[str] | None = None) -> dict:
    def _enumerate(_dir):
        row = _row(script, launchd_dir=launchd)
        if argv is not None:
            row = {**row, "program_arguments": argv}
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


def test_e6_default_observe_only_does_not_move_ok_or_findings(roots, tmp_path, launchd_dir, monkeypatch) -> None:
    """缺省（不声明开关）：6 条命中也只进返回值, 不进 findings —— 红≠修。"""
    script = _tree(roots["install"], f"exec uv run --project {roots['checkout']}/projects/omo\n")
    report = _call_reality(_registry(tmp_path / "services.yaml", strict=False), launchd_dir, roots, script, monkeypatch)
    assert report["e6_non_ok"] == 1
    assert report["e6_blocking"] == 0
    assert not [f for f in report["findings"] if f.startswith("E6")]
    assert report["ok"] is True


def test_e6_require_kernel_root_match_promotes_the_same_hit(roots, tmp_path, launchd_dir, monkeypatch) -> None:
    """同一个命中, 声明 require_kernel_root_match: true 之后必须进 findings。"""
    script = _tree(roots["install"], f"exec uv run --project {roots['checkout']}/projects/omo\n")
    report = _call_reality(_registry(tmp_path / "services.yaml", strict=True), launchd_dir, roots, script, monkeypatch)
    assert report["e6_blocking"] == 1
    e6 = [f for f in report["findings"] if f.startswith("E6")]
    assert len(e6) == 1
    assert LABEL in e6[0]
    assert report["ok"] is False


def test_e6_strict_promotes_undetermined_too(roots, tmp_path, launchd_dir, monkeypatch) -> None:
    """开关打开时「认不出入口」也阻塞：否则把 argv 改成认不出的形状就等于关掉这道闸。

    spec §3.4 的阻塞条件是 `state != "ok"`，不是「只拦字面量命中」。
    """
    script = _tree(roots["install"], f"exec uv run --project {roots['install']}/projects/omo\n")
    report = _call_reality(
        _registry(tmp_path / "services.yaml", strict=True), launchd_dir, roots, script, monkeypatch,
        argv=["/usr/bin/python3", "-c", "pass"],
    )
    assert report["e6_non_ok"] == 1
    assert report["e6_blocking"] == 1
    assert report["e6_kernel_pin"][0]["state"] == "undetermined"
    assert report["ok"] is False


def test_e6_undetermined_is_also_observe_only_without_the_switch(roots, tmp_path, launchd_dir, monkeypatch) -> None:
    """反面对：同一条 undetermined，不声明开关时不进 findings、ok 不变。"""
    script = _tree(roots["install"], f"exec uv run --project {roots['install']}/projects/omo\n")
    report = _call_reality(
        _registry(tmp_path / "services.yaml", strict=False), launchd_dir, roots, script, monkeypatch,
        argv=["/usr/bin/python3", "-c", "pass"],
    )
    assert report["e6_non_ok"] == 1
    assert report["e6_blocking"] == 0
    assert report["ok"] is True


# ---------------------------------------------------------------- schema 面

def test_validate_rejects_require_kernel_root_match_without_runtime_root() -> None:
    violations = MOD.validate_service_declaration(
        {"id": "s", "scheduler": "launchd", "require_kernel_root_match": True}
    )
    assert any("require_kernel_root_match 需要条目先声明 runtime_root" in v for v in violations)


def test_validate_rejects_require_kernel_root_match_false() -> None:
    """只接受 true：写 false 就是给「缺省即不声明」造第二个真值来源。"""
    violations = MOD.validate_service_declaration(
        {"id": "s", "scheduler": "launchd", "runtime_root": "install", "require_kernel_root_match": False}
    )
    assert any("只接受 true" in v for v in violations)


def test_validate_accepts_require_kernel_root_match_on_declared_root() -> None:
    assert MOD.validate_service_declaration(_svc(require_kernel_root_match=True)) == []


# ---------------------------------------------------------------- argv 侧缝

def test_entrypoint_script_requires_absolute_matching_root(roots) -> None:
    script = _tree(roots["install"], "echo hi\n")
    assert MOD._entrypoint_script(["/bin/bash", str(script)], roots["install"]) == script.resolve()
    assert MOD._entrypoint_script(["/bin/bash", str(script)], roots["checkout"]) is None
    assert MOD._entrypoint_script(["lib/resident-role-tick.sh"], roots["install"]) is None


def test_plist_rows_shape_is_consumed_from_program_arguments(tmp_path) -> None:
    """枚举器给的 program_arguments 是 str 列表 —— E6 只读这一项, 不重新解析 plist。"""
    payload = {"Label": LABEL, "ProgramArguments": ["/bin/bash", "/x/y.sh", "decision"]}
    path = tmp_path / f"{LABEL}.plist"
    path.write_bytes(plistlib.dumps(payload))
    loaded = plistlib.loads(path.read_bytes())
    assert MOD._entrypoint_script([str(a) for a in loaded["ProgramArguments"]], tmp_path) is None
