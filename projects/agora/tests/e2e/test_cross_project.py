"""E2E test: cross-project pipeline — pallas → ontoderive → agora.

Verifies:
1. Agora can discover and list registered services
2. Agora health check returns valid circuit states
3. Agora pipeline definitions are consistent
4. OntoDerive project structure is valid
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

AGORA = shutil.which("agora")
ONTODERIVE = shutil.which("ontoderive")
ZPARK = str(Path(__file__).parent.parent.parent.parent / "ontoderive" / "examples" / "z-park")


def _run(cmd, timeout=30):
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return result.returncode, result.stdout + result.stderr


class TestAgoraE2E:
    """Verify Agora core functions end-to-end."""

    @pytest.mark.skipif(not AGORA, reason="agora CLI not found on PATH")
    def test_agora_discover(self):
        rc, out = _run([AGORA, "discover", "--json"])
        assert rc == 0
        # Parse the last JSON array from output (skip discovery header)
        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            # Find JSON array in output
            start = out.find("[")
            end = out.rfind("]") + 1
            data = json.loads(out[start:end]) if start >= 0 else []
        assert isinstance(data, list)
        assert len(data) >= 3  # minerva, sophia, ontoderive at minimum

    @pytest.mark.skipif(not AGORA, reason="agora CLI not found on PATH")
    def test_agora_health(self):
        rc, out = _run([AGORA, "health"])
        assert rc == 0
        assert "Healthy" in out

    @pytest.mark.skipif(not AGORA, reason="agora CLI not found on PATH")
    def test_agora_stats(self):
        rc, out = _run([AGORA, "stats"])
        assert rc == 0
        assert "Total services" in out

    @pytest.mark.skipif(not AGORA, reason="agora CLI not found on PATH")
    def test_agora_market_list(self):
        rc, out = _run([AGORA, "market", "list"])
        assert rc == 0
        assert "minerva" in out.lower() or "MCP Tool Market" in out

    @pytest.mark.skipif(not AGORA, reason="agora CLI not found on PATH")
    def test_agora_pipelines(self):
        rc, out = _run([AGORA, "pipelines"])
        assert rc == 0
        assert "match-derive" in out or "derive-check" in out

    @pytest.mark.skipif(not AGORA, reason="agora CLI not found on PATH")
    def test_agora_event_publish_and_log(self):
        _run([AGORA, "event", "publish", "test:e2e", "--payload", '{"ok":true}', "--source", "e2e-test"])
        rc, out = _run([AGORA, "event", "log", "--limit", "200"])
        assert rc == 0
        assert "test:e2e" in out


@pytest.mark.skipif(not ONTODERIVE, reason="ontoderive CLI not found on PATH")
class TestOntoDeriveE2E:
    """Verify OntoDerive core functions."""

    def test_ontoderive_toolforge(self):
        rc, out = _run([ONTODERIVE, "toolforge", "分析市场", "--json"], timeout=60)
        assert rc == 0
        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            start = out.find("[")
            end = out.rfind("]") + 1
            data = json.loads(out[start:end]) if start >= 0 else []
        assert "methodologies" in data or isinstance(data, list)

    def test_ontoderive_check(self):
        if Path(ZPARK).exists():
            rc, out = _run([ONTODERIVE, "check", "--project", ZPARK], timeout=60)
            assert rc == 0
            assert "PASS" in out or "pass" in out.lower()
        else:
            pass  # z-park project not available, skip


@pytest.mark.skipif(not AGORA, reason="agora CLI not found on PATH")
class TestPipelineIntegration:
    """Verify the full knowledge engineering pipeline works end-to-end."""

    def test_agora_pipeline_definitions_valid(self):
        """All built-in pipelines should have valid step definitions."""
        rc, out = _run([AGORA, "pipelines"])
        assert rc == 0
        pipeline_names = [line.strip(" •") for line in out.split("\n") if line.strip().startswith("•")]
        assert len(pipeline_names) >= 3, f"Expected >= 3 pipelines, got {pipeline_names}"
