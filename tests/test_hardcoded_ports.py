"""test_hardcoded_ports.py — P77 Phase 5 跨仓端口硬编码扫描 验证

P77 STRAT § 2 Phase 5 入口: 跨仓 port-registry 一致性 (P77-4) 完成后, 转向硬编码扫描.

ADR-0456 B2 追加: dev 端口段 (dev_band / dev_ports) 的一致性由本文件执行 —— 契约是
"contained + injective + disjoint" 三条, 不靠人眼看 YAML.
"""

import importlib.util
import json
import subprocess
from pathlib import Path

import yaml

WORKSPACE = Path(__file__).resolve().parents[1]
REGISTRY = WORKSPACE / "protocols" / "port-registry.yaml"
SCANNER = WORKSPACE / "bin" / "ssot" / "check-hardcoded-ports.py"


def _load_scanner():
    spec = importlib.util.spec_from_file_location("check_hardcoded_ports", SCANNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


scanner = _load_scanner()
registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))


def run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            "uv",
            "run",
            "--with",
            "pyyaml",
            "python",
            str(WORKSPACE / "bin" / "ssot" / "check-hardcoded-ports.py"),
            *args,
        ],
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
    )


def test_detector_runs():
    """detector 可执行."""
    r = run(["--json"])
    assert r.returncode in (0, 1), f"unexpected rc={r.returncode}"
    data = json.loads(r.stdout)
    assert "unregistered" in data


def test_unregistered_is_zero():
    """Phase 5 治本后: 实际运行 unregistered = 0 (修真修真)."""
    r = run(["--json"])
    data = json.loads(r.stdout)
    assert data["unregistered"] == 0, (
        f"unregistered should be 0, got {data['unregistered']}: "
        f"{[u['port'] for u in data.get('unregistered_list', [])]}"
    )


def test_threshold_default_zero():
    """detector 默认 threshold 应该 0 (P77-5 治本后)."""
    text = (WORKSPACE / "bin" / "ssot" / "check-hardcoded-ports.py").read_text()
    assert "default=0" in text, "threshold default should be 0"
    assert "default=20" not in text, "threshold default should NOT be 20"


def test_legacy_ok_ports_includes_external():
    """LEGACY_OK_PORTS 只容纳"不归本仓管"的外部端口 (P77-5 + ADR-0456 B2 准入判据)."""
    assert scanner.LEGACY_OK_PORTS == {
        1234,  # LM Studio
        3000,  # family-hub dashboard (外部仓)
        3001,  # family-hub api (外部仓)
        4318,  # OpenTelemetry OTLP (行业标准)
    }, "LEGACY_OK_PORTS 只允许外部标准/外部仓端口; 本仓自有进程端口必须进 protocols/port-registry.yaml"


def test_vite_port_is_registered_not_exempted():
    """5173 是本仓自己的 dev-profile UI 端口 (vite), 不是外部工具豁免项 (ADR-0456 B2 改判).

    改判前它以 "Vite dev server (工具默认)" 名义躺在 LEGACY_OK_PORTS 里, 于是门禁结构性
    地无法表达"人类 UI 到底由谁承载"。
    """
    assert 5173 not in scanner.LEGACY_OK_PORTS, "5173 不得再走外部工具豁免"
    assert 5173 in scanner.load_registered_ports(), "5173 必须已注册"
    assert "vite" in str(registry["ports"][5173]["name"]).lower()


def test_dev_ports_within_band():
    """C3-1 contained: 每个 dev_ports.port 都落在声明的 dev_band 内."""
    band = registry["dev_band"]
    lo, hi = int(band["from"]), int(band["to"])
    assert lo < hi
    for name, entry in registry["dev_ports"].items():
        assert lo <= int(entry["port"]) <= hi, f"dev_ports.{name}.port {entry['port']} 出段 {lo}-{hi}"


def test_dev_ports_are_injective():
    """C3-2 injective: dev 端口两两不同 —— 算术推导 (15000+p%1000) 正是被这条否证的."""
    ports = [int(e["port"]) for e in registry["dev_ports"].values()]
    assert len(set(ports)) == len(ports), f"dev 端口重复 (非单射): {sorted(ports)}"


def test_dev_ports_disjoint_from_production():
    """C3-3 disjoint: dev 端口不得与任何已注册生产端口或豁免表重叠.

    这条同时保证 dev 端口不会被误当成生产端口 —— 反过来说, 谁把 dev_ports 并进注册
    union, 这里的断言就会失效 (见 test_dev_ports_are_not_registered_ports).
    """
    dev = {int(e["port"]) for e in registry["dev_ports"].values()}
    registered = scanner.load_registered_ports()
    assert not dev & registered, f"dev 端口与注册生产端口重叠: {sorted(dev & registered)}"
    assert not dev & scanner.LEGACY_OK_PORTS, f"dev 端口与豁免表重叠: {sorted(dev & scanner.LEGACY_OK_PORTS)}"


def test_dev_band_is_disjoint_from_registered_band():
    """dev_band 整段与已注册生产端口不重叠 —— 不只是逐个端口, 段边界本身也要干净."""
    lo, hi = int(registry["dev_band"]["from"]), int(registry["dev_band"]["to"])
    clash = sorted(p for p in scanner.load_registered_ports() if lo <= p <= hi)
    assert not clash, f"生产注册端口落进 dev_band {lo}-{hi}: {clash}"


def test_dev_ports_bind_registered_prod_ports_and_env_seams():
    """每个 dev 条目覆盖的 prod 端口必须已注册, 且 env 名与注册表 env_vars 一致.

    否则 --dev-env 打印的是一个没人读的变量名, 覆盖会在静默中失效。
    """
    ports = registry["ports"]
    env_vars = {int(k): v for k, v in (registry.get("env_vars") or {}).items()}
    for name, entry in registry["dev_ports"].items():
        prod = int(entry["prod_port"])
        assert prod in ports, f"dev_ports.{name}.prod_port {prod} 未在 ports: 注册"
        assert env_vars.get(prod) == entry["env"], (
            f"dev_ports.{name}.env {entry['env']} 与 env_vars[{prod}]={env_vars.get(prod)} 不一致"
        )


def test_dev_ports_are_not_registered_ports():
    """C4: dev 端口故意不进注册 union —— 源码里写 dev 端口字面量必须仍被判为未注册."""
    dev = {int(e["port"]) for e in registry["dev_ports"].values()}
    assert dev, "dev_ports 表不应为空"
    assert not dev & scanner.load_registered_ports(), "dev 端口不得被并入注册 union"


def test_dev_env_print_mode():
    """--dev-env --profile dev: 每条 dev_ports 一行 NAME=PORT; prod 不打印任何东西."""
    dev = run(["--dev-env", "--profile", "dev"])
    assert dev.returncode == 0, dev.stderr
    lines = [ln for ln in dev.stdout.strip().splitlines() if ln]
    assert len(lines) == len(registry["dev_ports"]), f"应每条目一行: {lines}"
    for line in lines:
        assignment = line.split("#", 1)[0].strip()
        name, _, value = assignment.partition("=")
        assert name.isupper(), f"变量名应为大写 ENV: {line}"
        assert int(value) in {int(e["port"]) for e in registry["dev_ports"].values()}, line
    prod = run(["--dev-env", "--profile", "prod"])
    assert prod.returncode == 0 and not prod.stdout.strip(), "prod profile 不得打印 dev 覆盖"


def test_dev_env_requires_explicit_profile():
    """--dev-env 必须显式带 --profile: OMOSTATION_PROFILE 的首个消费者是 B3, 不由端口打印抢顺序."""
    r = run(["--dev-env"])
    assert r.returncode != 0, "--dev-env 无 --profile 必须失败, 不能猜默认值"


def test_dev_port_collision_is_rejected(tmp_path, monkeypatch):
    """C3 的三条不是装饰: 造一个越段 + 重叠的 dev 表, 打印模式必须 fail 而不是静默生效."""
    bad = json.loads(json.dumps(registry))  # deep copy
    bad["dev_ports"]["bogus"] = {"env": "BOGUS_PORT", "port": 8090, "prod_port": 8090}
    bad["dev_ports"]["out_of_band"] = {"env": "OUT_OF_BAND_PORT", "port": 20001, "prod_port": 9100}
    root = tmp_path / "ws"
    (root / "protocols").mkdir(parents=True)
    (root / "protocols" / "port-registry.yaml").write_text(
        yaml.safe_dump(bad, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    monkeypatch.setattr(scanner, "WORKSPACE", root)
    rc = scanner.render_dev_env("dev", scanner.load_registered_ports())
    assert rc == 1, "重叠/越段的 dev 表必须 exit 1"


def test_port_patterns_comprehensive():
    """7 种 port-context pattern 都应被检测."""
    text = (WORKSPACE / "bin" / "ssot" / "check-hardcoded-ports.py").read_text()
    for pattern_name in [
        "PORT = NNNN",
        "port=NNNN",
        "--port NNNN",
        "host:port",
        "localhost:port",
        "127.0.0.1:port",
        "0.0.0.0:port",
    ]:
        assert pattern_name in text, f"pattern '{pattern_name}' missing"


def test_excludes_test_directories():
    """test 目录下的 port 不算 consumed."""
    r = run(["--json"])
    data = json.loads(r.stdout)
    # c2g/tests 里 'bos://custom/path' 等, port 不会被计入
    # 这是一个反例测试: 我们只需要 detector 不 throw exception
    assert "hardcoded_distinct_ports" in data


def test_registered_total_ge_32():
    """Phase 5 补登 4 port 后, SSOT union 应 ≥ 32 (P77-4 收口 28 + 4 new)."""
    r = run(["--json"])
    data = json.loads(r.stdout)
    assert data["registered_total"] >= 32, f"registered should be ≥32, got {data['registered_total']}"


def test_principle_p77_5_hardcoded_port():
    """P77-5 沉淀: 硬编码 port 必先在 SSOT 注册, 修真修真."""
    r = run(["--json"])
    r2 = run(["--json"])
    d1 = json.loads(r.stdout)
    d2 = json.loads(r2.stdout)
    assert d1 == d2, "detector should be idempotent"


def test_principle_legacy_external_allowlist():
    """P77-5 沉淀: 外部服务允许硬编码, 但要在 LEGACY_OK_PORTS 列名."""
    text = (WORKSPACE / "bin" / "ssot" / "check-hardcoded-ports.py").read_text()
    assert "LEGACY_OK_PORTS" in text, "LEGACY_OK_PORTS dict must exist"
    # 每行应有注释说明豁免理由
    assert "LM Studio" in text or "otel" in text.lower(), "LEGACY_OK_PORTS should have rationale comments"


def test_threshold_explicit_negative_fails():
    """--threshold -1 (强制) + unregistered=0 应该 fail."""
    r = run(["--threshold", "-1"])
    assert r.returncode == 1, f"expected fail rc=1, got {r.returncode}"
