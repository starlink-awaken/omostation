"""Tests for BOS declaration/execution alignment (D 调研闭环).

任务: TASK-AB15691F — 28 deprecated BOS 声明对齐真实位置.
到期: 2026-07-25 (过期未对齐升级为真实鸿沟).

不变量:
- bos.deprecated_count == 0 (所有 BOS 声明要么有真实实现, 要么已删)
- bos.gap == 0 (无真实鸿沟, 残留 deprecated 不计分)
- bos.resolve_rate == 1.0 (100% 声明可 resolve)

实现来源: bin/evidence-smoke.py 的 KNOWN_GAP_PREFIXES 应保持为空
(prefixes 重新出现意味着对齐回退).
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from datetime import datetime, UTC
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_SMOKE = ROOT / "bin" / "evidence-smoke.py"


def _run_evidence_smoke() -> dict:
    """运行 evidence-smoke.py 拿回 JSON 报告 (无副作用模式)."""
    result = subprocess.run(
        [sys.executable, str(EVIDENCE_SMOKE), "--quiet"],
        cwd=ROOT, capture_output=True, text=True, timeout=120, check=False,
    )
    # evidence-smoke 不支持 --json, 走 quiet 模式后从最新 .omo/_delivery 读 JSON
    out_dir = ROOT / ".omo" / "_delivery" / "evidence-smoke"
    candidates = sorted(out_dir.glob("*.json"), reverse=True)
    assert candidates, f"no evidence-smoke report under {out_dir}"
    return json.loads(candidates[0].read_text(encoding="utf-8"))


class TestNoDeprecatedBosDeclarations:
    """TASK-AB15691F 锁定不变量: 0 deprecated, 0 real gap."""

    @pytest.fixture(scope="module")
    def report(self) -> dict:
        return _run_evidence_smoke()

    def test_deprecated_count_zero(self, report):
        # 核心不变量: 所有 28 项 deprecated 已对齐
        assert report["bos"]["deprecated_count"] == 0, (
            f"BOS deprecated 出现回归: {report['bos']['deprecated_count']} 项. "
            f"需重新跑 D 调研对齐 (TASK-AB15691F). 见 KNOWN_GAP_PREFIXES 注释."
        )

    def test_deprecated_list_empty(self, report):
        # deprecated 列表 (URI + reason) 应为空
        assert report["deprecated"] == [], (
            f"deprecated URI 列表非空: {report['deprecated']}"
        )

    def test_no_real_gap(self, report):
        # 真实鸿沟 = 0 (residuel deprecated 不算 gap)
        assert report["bos"]["gap"] == 0, (
            f"真实 BOS 鸿沟出现: gap={report['bos']['gap']}, "
            f"failure_buckets={report['bos'].get('failure_buckets')}"
        )

    def test_resolve_rate_complete(self, report):
        assert report["bos"]["resolve_rate"] == 1.0, (
            f"resolve rate 不满 100%: {report['bos']['resolve_rate']}"
        )

    def test_declaration_count_matches_yaml(self, report):
        # 100 是 bos-services.yaml 的当前声明数; 若以后变更需同步
        bos_yaml = ROOT / "projects" / "agora" / "etc" / "bos-services.yaml"
        if not bos_yaml.exists():
            pytest.skip("bos-services.yaml not found")
        import re
        yaml_count = len(re.findall(r"^\s+- uri:", bos_yaml.read_text(), re.MULTILINE))
        assert report["bos"]["declaration_count"] == yaml_count, (
            f"声明数 {report['bos']['declaration_count']} != yaml 实际 {yaml_count}"
        )


class TestEvidenceSmokeCli:
    """evidence-smoke.py 自身不退化."""

    def test_quiet_mode_exits_zero(self):
        result = subprocess.run(
            [sys.executable, str(EVIDENCE_SMOKE), "--quiet"],
            cwd=ROOT, capture_output=True, text=True, timeout=120, check=False,
        )
        assert result.returncode == 0, (
            f"evidence-smoke --quiet failed: rc={result.returncode}\n"
            f"stdout: {result.stdout[-500:]}\nstderr: {result.stderr[-500:]}"
        )

    def test_gate_mode_emits_known_gap_expiry(self):
        """evidence-smoke 报告应含 KNOWN_GAP_EXPIRES 用于 D 调研到期跟踪."""
        report = _run_evidence_smoke()
        expires = report["bos"].get("deprecated_expires")
        assert expires is not None, "deprecated_expires 缺失"
        # 到期日不应在过去 (任务 2026-07-25 到期)
        exp_date = datetime.fromisoformat(expires).replace(tzinfo=UTC)
        assert exp_date >= datetime.now(UTC), (
            f"KNOWN_GAP_EXPIRES 已过 ({expires}), 应清理 KNOWN_GAP_PREFIXES"
        )


class TestBosYamlHasNoDeprecatedMarkers:
    """bos-services.yaml 不应残留 [DEPRECATED] 标记 (per 2026-06-26 alignment)."""

    def test_no_deprecated_description_in_yaml(self):
        yaml_path = ROOT / "projects" / "agora" / "etc" / "bos-services.yaml"
        if not yaml_path.exists():
            pytest.skip("bos-services.yaml not found")
        text = yaml_path.read_text(encoding="utf-8")
        deprecated_lines = [
            ln for ln in text.splitlines() if "[DEPRECATED]" in ln
        ]
        assert deprecated_lines == [], (
            f"bos-services.yaml 残留 [DEPRECATED] 标记:\n"
            + "\n".join(deprecated_lines)
        )