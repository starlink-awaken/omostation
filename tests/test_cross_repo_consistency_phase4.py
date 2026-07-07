"""test_cross_repo_consistency_phase4.py — P77 Phase 4 跨仓端口冲突扫描 验证

P77 STRAT § 2 Phase 4 入口: 跨仓 unregistered 治本完成, 转向 port-registry 一致性.
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
         str(WORKSPACE / "bin" / "check-cross-repo-consistency.py"), *args],
        cwd=WORKSPACE, capture_output=True, text=True,
    )


def test_load_ecos_ports_real_count():
    """ecos port-registry 真加载 9 个端口 (load_ecos_ports 修 bug 后)."""
    r = run(["--json"])
    import json
    data = json.loads(r.stdout)
    assert data["port_count_ecos"] == 9, (
        f"ecos should have 9 ports, got {data['port_count_ecos']}"
    )


def test_load_protocols_ports():
    """protocols port-registry 加载 25+ 端口."""
    r = run(["--json"])
    data = json.loads(r.stdout)
    assert data["port_count_protocols"] >= 20, (
        f"protocols should have ≥20 ports, got {data['port_count_protocols']}"
    )


def test_yaml_comment_stripping():
    """'name  # comment' 解析后应只剩 'name' (修真修真)"""
    text = (WORKSPACE / "bin" / "check-cross-repo-consistency.py").read_text()
    assert "_strip_yaml_comment" in text, "helper _strip_yaml_comment must exist"
    # 6 个原本是 conflicts 的应该都变 duplicate (探测)
    r = run(["--json"])
    import json
    data = json.loads(r.stdout)
    real_conflicts = [c for c in data["port_conflicts_list"] if c["type"] == "conflict"]
    assert len(real_conflicts) == 0, (
        f"real port conflicts should be 0 (after alignment), got {real_conflicts}"
    )


def test_port_8080_aligned():
    """port 8080 在两个 registry 都应是 'ontoderive-web' (治本后)."""
    r = run(["--json"])
    import json
    data = json.loads(r.stdout)
    port_8080 = next((c for c in data["port_conflicts_list"] if c["port"] == 8080), None)
    assert port_8080 is not None, "port 8080 should be tracked"
    assert port_8080["type"] == "duplicate", (
        f"port 8080 should be duplicate (aligned), got {port_8080}"
    )
    assert port_8080["ecos"] == port_8080["protocols"] == "ontoderive-web", (
        f"port 8080 name mismatch: {port_8080}"
    )


def test_port_9290_aligned():
    """port 9290 在两个 registry 都应是 'llm-gateway'."""
    r = run(["--json"])
    data = json.loads(r.stdout)
    p = next((c for c in data["port_conflicts_list"] if c["port"] == 9290), None)
    assert p is not None
    assert p["type"] == "duplicate", f"port 9290 should be duplicate, got {p}"
    assert p["ecos"] == p["protocols"] == "llm-gateway", f"port 9290 name: {p}"


def test_principle_p77_4_port_consistency():
    """P77-4 沉淀: 跨仓端口一致性靠 detector 守护."""
    r = run(["--json"])
    r2 = run(["--json"])
    import json
    d1 = json.loads(r.stdout)
    d2 = json.loads(r2.stdout)
    assert d1 == d2, "detector should be idempotent"
    assert d1["port_conflicts"] == 0, "port conflicts should be 0 (治本后)"


def test_principle_yaml_comment_strip():
    """P77-4 沉淀: YAML inline comment 解析器必须 strip (# P77-3-1 boundary 思路延伸)."""
    text = (WORKSPACE / "bin" / "check-cross-repo-consistency.py").read_text()
    # _strip_yaml_comment 函数必须存在
    assert "def _strip_yaml_comment" in text, "_strip_yaml_comment function not found"
    # 必须有 '  #' 或 '\t#' 解析
    assert '"  #"' in text or "'  #'" in text, (
        "_strip_yaml_comment must check for 2-space + # pattern"
    )
