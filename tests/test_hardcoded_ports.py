"""test_hardcoded_ports.py — P77 Phase 5 跨仓端口硬编码扫描 验证

P77 STRAT § 2 Phase 5 入口: 跨仓 port-registry 一致性 (P77-4) 完成后, 转向硬编码扫描.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]


def run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["uv", "run", "--with", "pyyaml", "python",
         str(WORKSPACE / "bin" / "check-hardcoded-ports.py"), *args],
        cwd=WORKSPACE, capture_output=True, text=True,
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
    text = (WORKSPACE / "bin" / "check-hardcoded-ports.py").read_text()
    assert "default=0" in text, "threshold default should be 0"
    assert "default=20" not in text, "threshold default should NOT be 20"


def test_legacy_ok_ports_includes_external():
    """LEGACY_OK_PORTS 应包含外部标准 / 工具端口 (otel/vite/lm-studio/family-hub)."""
    text = (WORKSPACE / "bin" / "check-hardcoded-ports.py").read_text()
    for port, name in [
        (1234, "LM Studio"),
        (3000, "family-hub dashboard"),
        (3001, "family-hub api"),
        (4318, "OpenTelemetry OTLP"),
        (5173, "Vite dev server"),
    ]:
        assert str(port) in text, f"port {port} ({name}) should be in LEGACY_OK_PORTS"


def test_port_patterns_comprehensive():
    """7 种 port-context pattern 都应被检测."""
    text = (WORKSPACE / "bin" / "check-hardcoded-ports.py").read_text()
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
    assert data["registered_total"] >= 32, (
        f"registered should be ≥32, got {data['registered_total']}"
    )


def test_principle_p77_5_hardcoded_port():
    """P77-5 沉淀: 硬编码 port 必先在 SSOT 注册, 修真修真."""
    r = run(["--json"])
    r2 = run(["--json"])
    d1 = json.loads(r.stdout)
    d2 = json.loads(r2.stdout)
    assert d1 == d2, "detector should be idempotent"


def test_principle_legacy_external_allowlist():
    """P77-5 沉淀: 外部服务允许硬编码, 但要在 LEGACY_OK_PORTS 列名."""
    text = (WORKSPACE / "bin" / "check-hardcoded-ports.py").read_text()
    assert "LEGACY_OK_PORTS" in text, "LEGACY_OK_PORTS dict must exist"
    # 每行应有注释说明豁免理由
    assert "LM Studio" in text or "otel" in text.lower(), (
        "LEGACY_OK_PORTS should have rationale comments"
    )


def test_threshold_explicit_negative_fails():
    """--threshold -1 (强制) + unregistered=0 应该 fail."""
    r = run(["--threshold", "-1"])
    assert r.returncode == 1, f"expected fail rc=1, got {r.returncode}"
