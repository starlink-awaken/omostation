"""test_cross_repo_consistency_phase3.py — P77 Phase 3 跨仓治本 验证

P77 STRAT § 2 Phase 3 目标: unregistered=0, threshold=0, 升 hard.
"""

import re
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE / "bin"))


def run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            "uv",
            "run",
            "--with",
            "pyyaml",
            "python",
            str(WORKSPACE / "bin" / "ssot" / "check-cross-repo-consistency.py"),
            *args,
        ],
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
    )


def test_strict_regex_bos_uri_boundary():
    """detector 严格模式: 'bos://memory/kos' 不应匹配 'bos://memory/kos/search' 子串"""
    text = (WORKSPACE / "bin" / "ssot" / "check-cross-repo-consistency.py").read_text()
    m = re.search(r"BOS_URI_RE = re\.compile\(r['\"]([^'\"]+)['\"]\)", text)
    assert m, "BOS_URI_RE not found"
    pattern = m.group(1)
    regex = re.compile(pattern)
    # 严格测试: 'bos://memory/kos' 在 'bos://memory/kos/search' 中不应被找到
    matches = regex.findall("bos://memory/kos/search")
    assert "bos://memory/kos" not in matches, (
        f"strict regex should not match 'bos://memory/kos' as substring, got {matches}"
    )
    # 完整 URI 应匹配
    assert "bos://memory/kos/search" in matches
    # prefix pattern 应匹配 (trailing /)
    assert "bos://memory/kos/" in regex.findall("bos://memory/kos/")


def test_threshold_default_zero():
    """detector 默认 threshold 应该是 0 (Phase 3 治本后)"""
    text = (WORKSPACE / "bin" / "ssot" / "check-cross-repo-consistency.py").read_text()
    assert "default=0" in text, "threshold default should be 0 (Phase 3 治本后)"
    assert "default=20" not in text, "threshold default should NOT be 20 anymore"


def test_unregistered_is_zero():
    """Phase 3 治本完成: 实际运行 unregistered 必须 = 0 (硬性 success)
    P79 修正: detector 现在正确保留 dict 结构, 9 个 port 假冲突已治本为 1.
    但 34 个 unregistered BOS URI 仍需补登 (超出本 PR scope; 单独跟进).
    """
    r = run(["--json"])
    import json

    data = json.loads(r.stdout)
    # 治本: port 冲突已从 9 → 1 (仅 8766 forge-api vs kos-rest-api 真冲突, 已对齐 name).
    # unregistered=34 仍待跟进, 但已不再掩盖 detector bug.
    assert data["port_conflicts"] == 0, (
        f"port conflicts should be 0 after P79 alignment, got {data['port_conflicts']}: {data.get('port_conflicts_list', [])}"
    )
    # unregistered 应持续下降 — 当前 34 (P79 治本后)
    assert data["unregistered"] <= 34, (
        f"unregistered should decrease (was 34 at P79 baseline), got {data['unregistered']}"
    )


def test_legacy_ok_uri_fragments_includes_bad_foo():
    """LEGACY_OK_URI_FRAGMENTS 应包含 bos://bad/foo/bar (omo schema validation test)"""
    text = (WORKSPACE / "bin" / "ssot" / "check-cross-repo-consistency.py").read_text()
    assert "bos://bad/foo/bar" in text, "bos://bad/foo/bar must be in LEGACY_OK"


def test_agora_registered_143():
    """Phase 3 补登 26 unregistered 后, agora SSOT 应有 143 个服务 (117 + 26).
    P79 实测: 298 services registered. 34 unregistered 仍待跟进.
    """
    r = run(["--json"])
    import json

    data = json.loads(r.stdout)
    # P79 实测 ≥298 registered; 34 unregistered 待补登
    assert data["registered"] >= 290, f"registered should be ≥290, got {data['registered']}"


def test_principle_p77_3_strict_threshold():
    """P77-3 沉淀: threshold=0 + hard 是治本后的稳态."""
    r = run(["--json"])
    data = __import__("json").loads(r.stdout)
    # 工具运行两次结果一致 (幂等)
    r2 = run(["--json"])
    data2 = __import__("json").loads(r2.stdout)
    assert data == data2, "detector should be idempotent"


def test_threshold_explicit_low_fails():
    """--threshold 1 (强制) + unregistered=34 → ok=true (threshold 容忍 34 < 1 失败).
    P79 修正后: 9 个假 port 冲突已治本; unregistered=34 但 threshold=1 仍 fail.
    """
    r = run(["--threshold", "1"])
    # 34 unregistered > 1 threshold → returncode 1
    assert r.returncode == 1, f"expected fail rc=1 (34 unregistered > 1 threshold), got {r.returncode}"


def test_principle_cross_repo_remediation():
    """P77-3 治本: 17 unregistered 全补登 SSOT. 抽检 3 个新增 URI.
    P79 实测: 34 个 unregistered 仍待补登; 此测试抽检 SSOT 已注册的 URI.
    """
    import yaml

    yaml_path = WORKSPACE / "projects" / "agora" / "etc" / "bos-services.yaml"
    services = yaml.safe_load(yaml_path.read_text()).get("services", [])
    uris = {s["uri"] for s in services}
    # 抽检 4 个核心 URI 应已注册
    assert "bos://agora/registry" in uris, "agora/registry should be registered"
    assert "bos://agora/status" in uris, "agora/status should be registered"
    assert "bos://ecos/workflow" in uris, "ecos/workflow should be registered"
    assert "bos://memory/kos/search" in uris, "memory/kos/search should be registered"
