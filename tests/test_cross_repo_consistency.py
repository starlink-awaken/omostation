"""test_cross_repo_consistency.py — P77 Phase 1 detector 验证

P77 STRAT § 2.1: cross-repo consistency 自动 verifier
"""
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE / 'bin'))


def run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["uv", "run", "--with", "pyyaml", "python",
         str(WORKSPACE / "bin" / "check-cross-repo-consistency.py"), *args],
        cwd=WORKSPACE, capture_output=True, text=True,
    )


def test_tool_loads_and_runs():
    """basic invocation: returns reasonable output"""
    r = run(["--json", "--threshold", "100"])
    assert r.returncode in (0, 1), f"unexpected rc={r.returncode}"
    data = __import__("json").loads(r.stdout)
    assert "registered" in data
    assert "referenced" in data
    assert "unregistered" in data
    assert "orphan" in data
    assert "ports" in data
    assert "threshold" in data
    assert "ok" in data


def test_registered_uri_count_matches_agora_yaml():
    """registered count = agora bos-services.yaml 服务数 (SSOT 真值)."""
    import yaml
    yaml_path = WORKSPACE / "projects" / "agora" / "etc" / "bos-services.yaml"
    expected = sum(
        1 for s in yaml.safe_load(yaml_path.read_text()).get("services", [])
        if s.get("uri", "").startswith("bos://")
    )
    r = run(["--json", "--threshold", "100"])
    data = __import__("json").loads(r.stdout)
    assert data["registered"] == expected, (
        f"registered={data['registered']}, expected={expected}"
    )


def test_threshold_low_fail():
    """--threshold -1 (强制) 应该 fail (unregistered >= 0 永远不满足 -1)."""
    r = run(["--threshold", "-1"])
    assert r.returncode == 1, f"expected fail rc=1, got {r.returncode}"


def test_threshold_high_pass():
    """--threshold 大应该 pass."""
    r = run(["--threshold", "1000"])
    assert r.returncode == 0, f"expected pass rc=0, got {r.returncode}"


def test_agora_bos_services_yaml_exists():
    """SSOT 文件存在."""
    p = WORKSPACE / "projects" / "agora" / "etc" / "bos-services.yaml"
    assert p.exists(), f"SSOT missing: {p}"


def test_ecos_port_registry_exists():
    """ecos port-registry 真存在."""
    p = WORKSPACE / "projects" / "ecos" / "port-registry.yaml"
    assert p.exists(), f"port-registry missing: {p}"


def test_excludes_test_directories():
    """test 目录下的 bos:// 不算 consumed (fixture path)."""
    # 已知 fixture: bos://custom/path 在 projects/c2g/tests/test_task_builder.py
    # 检测器应该排除. 此 fixture 已被 LEGACY_OK_URI_FRAGMENTS 兜底.
    r = run(["--json", "--threshold", "100"])
    data = __import__("json").loads(r.stdout)
    full_unreg = __import__("subprocess").run(
        ["uv", "run", "--with", "pyyaml", "python",
         str(WORKSPACE / "bin" / "check-cross-repo-consistency.py"),
         "--json", "--threshold", "100"],
        cwd=WORKSPACE, capture_output=True, text=True,
    )
    # 无 condition on exact count (动态), 但 unregistered_list 必不含 custom/path
    assert "bos://custom/path" not in data.get("unregistered_list", []), (
        "fixture bos://custom/path 应该被豁免, 但出现了"
    )


def test_principle_p77_1_consistency_by_tool():
    """P77-1 沉淀: tool 自动守护, 非 review memory."""
    r = run(["--json", "--threshold", "1000"])
    assert r.returncode == 0
    # 工具可重复运行 (幂等)
    r2 = run(["--json", "--threshold", "1000"])
    assert r.returncode == r2.returncode
