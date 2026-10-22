"""`runtime_root` (per-service 运行根选择器) 的契约用例 — BET-Y2Q4-T10-265。

被测对象: bin/mof/gen-service-configs.py 的 service_root() / _resolve_path() /
validate_service_declaration() / main() 的 --only。
契约来源: docs/superpowers/specs/2026-10-22-b4b-resident-runtime-root.md C1-C8，
每条用例对应 spec §3 表的 ①-⑦。

全部用例 hermetic: 检出根与安装位都是 tmp 目录, cwd 与 profile env 指向诱饵,
不读 ~/Library/LaunchAgents, 不写机器级配置。
"""

from __future__ import annotations

import ast
import contextlib
import importlib.util
import inspect
import io
import sys
import types
from pathlib import Path

import pytest
import yaml

MODULE_PATH = Path(__file__).parents[2] / "bin" / "mof" / "gen-service-configs.py"
REPO_ROOT = Path(__file__).parents[2]
REGISTRY_PATH = REPO_ROOT / ".omo" / "_truth" / "registry" / "services.yaml"

RESIDENT_ENABLED = {
    "com.l4.resident.decision",
    "com.l4.resident.execute",
    "com.l4.resident.signals",
    "com.l4.resident.inbox",
    "com.l4.resident.promote",
    "com.l4.resident.event-ingest",
}


def _module():
    spec = importlib.util.spec_from_file_location("gen_service_runtime_root_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def env(tmp_path, monkeypatch):
    """检出根 / 安装位 / 诱饵三棵树 —— cwd 与 profile env 全部指向诱饵。"""
    module = _module()
    checkout = tmp_path / "checkout"
    install = tmp_path / "install"
    decoy = tmp_path / "decoy"
    for d in (checkout, install, decoy):
        d.mkdir()
    monkeypatch.setattr(module, "_WORKSPACE_CACHE", checkout)
    monkeypatch.setattr(module, "install_root", lambda: install)
    monkeypatch.chdir(decoy)
    monkeypatch.setenv("OMOSTATION_ROOT", str(decoy))
    monkeypatch.setenv("OMOSTATION_STATE_ROOT", str(decoy))
    monkeypatch.setenv("OMO_EVENT_LEDGER_DB", str(decoy / "ledger.sqlite3"))
    return types.SimpleNamespace(module=module, checkout=checkout, install=install, decoy=decoy, tmp=tmp_path)


def make_svc(**overrides) -> dict:
    """一条最小但字段齐备的 launchd 服务（形状取自常驻族真实条目）。"""
    svc = {
        "id": "resident.decision",
        "enabled": True,
        "scheduler": "launchd",
        "trigger": "interval",
        "interval_sec": 120,
        "label": "com.l4.resident.decision",
        "program": {
            "interpreter": "/bin/bash",
            "entrypoint": "lib/resident-role-tick.sh",
            "args": ["decision"],
        },
        "resilience": {"keepalive": "crashed", "throttle_interval": 120},
        "run_at_load": True,
        "notes": "fixture",
    }
    svc.update(overrides)
    return svc


# ① C1 缺省即 checkout，语义与改动前逐字节等价。
def test_default_selector_is_checkout_root_and_byte_identical(env):
    m = env.module
    undeclaring = make_svc()
    explicit = make_svc(runtime_root="checkout")

    assert m.service_root(undeclaring) == env.checkout
    assert m.service_root(explicit) == env.checkout
    assert m.gen_launchd_plist(undeclaring) == m.gen_launchd_plist(explicit)
    plist = m.gen_launchd_plist(undeclaring)
    assert f"        <string>{env.checkout / 'lib/resident-role-tick.sh'}</string>\n" in plist
    assert str(env.install) not in plist


# ①b 真实注册表里未声明字段的条目，解析根仍是 workspace()（本轮没碰它们）。
def test_undeclaring_registry_entries_still_resolve_to_checkout_root(env):
    services = env.module.load_services(REGISTRY_PATH)
    assert services, "注册表解析出 0 条 —— 尺没命中，不得当作通过"
    declaring = [s for s in services if "runtime_root" in s]
    assert len(declaring) == 6, f"声明运行根的条目应为 6，实为 {len(declaring)}"
    assert {s["label"] for s in declaring} == RESIDENT_ENABLED
    assert {s["runtime_root"] for s in declaring} == {"install"}
    for svc in services:
        if "runtime_root" not in svc:
            assert env.module.service_root(svc) == env.checkout


# ② C2/C3 install 命中：每个相对字段都落进安装位，不留半镜像。
def test_install_selector_resolves_every_relative_field_to_install_root(env):
    svc = make_svc(
        runtime_root="install",
        watch_paths=["runtime/queue/inbox.jsonl"],
        outputs={"stdout": "runtime/logs/resident.log", "stderr": "~/Library/Logs/resident.err"},
    )
    plist = env.module.gen_launchd_plist(svc)

    assert f"        <string>{env.install / 'lib/resident-role-tick.sh'}</string>\n" in plist
    assert f"        <string>{env.install / 'runtime/queue/inbox.jsonl'}</string>\n" in plist
    # stdout 相对安装位；stderr 带 ~ 仍按用户目录展开（绝对/波浪号语义不变）。
    assert f"    <string>{env.install / 'runtime/logs/resident.log'}</string>" in plist
    assert f"    <string>{Path.home() / 'Library/Logs/resident.err'}</string>" in plist
    assert str(env.checkout) not in plist
    assert str(env.decoy) not in plist


# ③ C4 fail-closed：安装位缺席时报错，绝不静默退回检出根。
def test_missing_install_root_fails_closed_instead_of_falling_back(env, monkeypatch):
    monkeypatch.setattr(env.module, "install_root", lambda: None)
    svc = make_svc(runtime_root="install")
    with pytest.raises(ValueError) as excinfo:
        env.module.service_root(svc)
    assert "拒绝退回检出根" in str(excinfo.value)
    assert "com.l4.resident.decision" in str(excinfo.value)
    with pytest.raises(ValueError):
        env.module.gen_launchd_plist(svc)


# ④ C2 无调用侧泄漏：根不由 env / cwd / 参数决定。
def test_root_is_not_selectable_from_env_cwd_or_argument(env, monkeypatch):
    m = env.module
    assert list(inspect.signature(m.gen_launchd_plist).parameters) == ["svc"]

    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    e1 = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "run_e1_drift")
    calls = [n for n in ast.walk(e1) if isinstance(n, ast.Call) and ast.unparse(n.func) == "subprocess.run"]
    assert len(calls) == 1, "run_e1_drift 的 subprocess.run 数量变了，本用例判据需同步"
    assert "env" not in {kw.arg for kw in calls[0].keywords}, "E1 判据不得传 env —— 那是给 --check 选根"
    cmd_assigns = [
        n for n in ast.walk(e1)
        if isinstance(n, ast.Assign) and any(getattr(t, "id", None) == "cmd" for t in n.targets)
    ]
    assert len(cmd_assigns) == 1, "E1 判据的命令构造点变了，本用例判据需同步"
    flags = [
        c.value
        for c in ast.walk(cmd_assigns[0].value)
        if isinstance(c, ast.Constant) and isinstance(c.value, str) and c.value.startswith("--")
    ]
    assert flags == ["--check", "--json"], f"E1 判据必须逐字节沿用无参 --check --json，实为 {flags}"
    e1_src = "\n".join(ast.unparse(s) for s in e1.body[1:])  # body[0] 是 docstring（它本来就写着"不传 OMOSTATION_ROOT"）
    for leak in ("--only", "--registry", "OMOSTATION_ROOT", "environ"):
        assert leak not in e1_src, f"run_e1_drift 出现了调用侧选根的形状: {leak}"

    # 清掉诱饵 env、把 cwd 换到检出根之后，输出逐字节不变。
    svc = make_svc(runtime_root="install")
    with_env = m.gen_launchd_plist(svc)
    for name in ("OMOSTATION_ROOT", "OMOSTATION_STATE_ROOT", "OMO_EVENT_LEDGER_DB"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(env.checkout)
    assert m.gen_launchd_plist(svc) == with_env


# ⑤ C5 校验面：拒绝未知取值，且只允许 scheduler=launchd 条目携带该字段。
def test_validator_rejects_unknown_value_and_non_launchd_declaration(env):
    m = env.module
    assert m.validate_service_declaration(make_svc(runtime_root="install")) == []

    bad_value = m.validate_service_declaration(make_svc(runtime_root="/opt/omostation"))
    assert any("runtime_root 取值非法" in v for v in bad_value), bad_value

    cron_entry = make_svc(scheduler="cron", runtime_root="install", schedule_ref=".github/workflows/x.yml")
    cron_violations = m.validate_service_declaration(cron_entry)
    assert any("只适用于 scheduler=launchd" in v for v in cron_violations), cron_violations

    assert not any("runtime_root" in v for v in m.validate_service_declaration(make_svc()))


# ⑥ 尺自身反证：真实注册表整体无 runtime_root 违规；注入一条坏值必须被点名。
def test_detector_fires_on_synthetic_violating_entry(env):
    m = env.module
    services = m.load_services(REGISTRY_PATH)
    baseline = [v for s in services for v in m.validate_service_declaration(s) if "runtime_root" in v]
    assert baseline == [], f"真实注册表已有 runtime_root 违规，反证用例失去意义: {baseline}"

    poisoned = make_svc(id="resident.poisoned", label="com.l4.resident.poisoned", runtime_root="maybe")
    fired = [v for v in m.validate_service_declaration(poisoned) if "runtime_root" in v]
    assert len(fired) == 1, fired
    assert "resident.poisoned" in fired[0]


# ⑦ C6 --only：只写指名条目；拼错的 label 当场拒绝而非静默不写。
def run_main(m, argv, fake_launchd: Path) -> tuple[int, str, str]:
    original_launchd_dir = m._launchd_dir
    m._launchd_dir = lambda: fake_launchd
    out, err = io.StringIO(), io.StringIO()
    old_argv = sys.argv
    sys.argv = [str(MODULE_PATH), *argv]
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = m.main()
    finally:
        sys.argv = old_argv
        m._launchd_dir = original_launchd_dir
    return rc, out.getvalue(), err.getvalue()


def write_fixture_registry(checkout: Path, services: list[dict]) -> Path:
    reg = checkout / ".omo" / "_truth" / "registry" / "services.yaml"
    reg.parent.mkdir(parents=True, exist_ok=True)
    reg.write_text(
        "---\nstatus: active\n---\n" + yaml.safe_dump({"services": services}, sort_keys=False),
        encoding="utf-8",
    )
    return reg


def test_only_flag_scopes_write_and_rejects_unknown_label(env):
    m = env.module
    a = make_svc(id="resident.decision", label="com.l4.resident.decision", runtime_root="install")
    b = make_svc(id="resident.execute", label="com.l4.resident.execute", runtime_root="install")
    (env.install / "lib").mkdir(parents=True, exist_ok=True)
    (env.install / "lib" / "resident-role-tick.sh").write_text("#!/bin/bash\n", encoding="utf-8")
    write_fixture_registry(env.checkout, [a, b])
    fake_launchd = env.tmp / "LaunchAgents"
    fake_launchd.mkdir()

    rc, _, _ = run_main(m, ["--write", "--only", "com.l4.resident.decision"], fake_launchd)
    assert rc == 0
    assert sorted(p.name for p in fake_launchd.glob("*.plist")) == ["com.l4.resident.decision.plist"]
    plist = (fake_launchd / "com.l4.resident.decision.plist").read_text(encoding="utf-8")
    assert str(env.install / "lib" / "resident-role-tick.sh") in plist

    rc, _, err = run_main(m, ["--write", "--only", "com.l4.resident.decisionn"], fake_launchd)
    assert rc == 1
    assert "不是生成器自有 launchd 服务" in err
    assert sorted(p.name for p in fake_launchd.glob("*.plist")) == ["com.l4.resident.decision.plist"]

    # 不带 --only 时行为与今日一致：不窄化，两条全写。
    rc, _, _ = run_main(m, ["--write"], fake_launchd)
    assert rc == 0
    assert sorted(p.name for p in fake_launchd.glob("*.plist")) == [
        "com.l4.resident.decision.plist",
        "com.l4.resident.execute.plist",
    ]


# 附带 C2 的一半：--registry 只喂 --reality-check，--check/--write 的注册表来源仍是规范检出那份。
def test_registry_flag_feeds_only_reality_check(env):
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    main_fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")

    assignments = [
        n for n in ast.walk(main_fn)
        if isinstance(n, ast.Assign) and any(getattr(t, "id", None) == "registry_path" for t in n.targets)
    ]
    assert len(assignments) == 1, "registry_path 的赋值点数量变了，本用例判据需同步"
    registry_path_src = ast.unparse(assignments[0])
    assert "services_yaml_path()" in registry_path_src
    assert "args.registry" not in registry_path_src

    rc_returns = [
        s for s in ast.walk(main_fn)
        if isinstance(s, ast.Return) and "reality_check_main" in ast.unparse(s)
    ]
    assert len(rc_returns) == 1, "--reality-check 的分支结构变了，本用例判据需同步"
    inside = [n for n in ast.walk(rc_returns[0]) if isinstance(n, ast.Attribute) and n.attr == "registry"]
    everywhere = [n for n in ast.walk(main_fn) if isinstance(n, ast.Attribute) and n.attr == "registry"]
    assert inside, "args.registry 无人读取 —— --registry 是死参数"
    assert len(everywhere) == len(inside), "有 args.registry 的读者不在 --reality-check 分支里 —— 根选择器泄漏到 --check/--write"
