"""Tests for W3 声明式 BOS URI 注册 + 可观测性.

Covers:
- Pydantic schema (omo_bos_schema.py): 4-segment strict, legacy auto-map, domain mismatch
- Metrics (omo_bos_metrics.py): record, summary, percentile, p95/p99
- CLI: omo bos status / discover / health (subprocess smoke)
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

# 把 src 加入 path (与 omo 现有 tests 同)
OMO_SRC = Path(__file__).resolve().parents[1] / "src"
if str(OMO_SRC) not in sys.path:
    sys.path.insert(0, str(OMO_SRC))


# ── Pydantic schema 测试 ──────────────────────────────────


class TestBosRegistrationModel:
    def test_valid_4_segment(self):
        from omo.omo_bos_schema import BosRegistrationModel
        m = BosRegistrationModel(
            uri="bos://memory/kos/search",
            domain="memory",
            package="kos",
            action="search",
            endpoint="kairon.packages.kos.ontology.store:search_entities",
        )
        assert m.uri == "bos://memory/kos/search"
        assert m.domain == "memory"
        assert m.protocol == "internal"  # default

    def test_invalid_domain_rejected(self):
        from omo.omo_bos_schema import BosRegistrationModel
        from pydantic import ValidationError
        with pytest.raises(ValidationError) as exc_info:
            BosRegistrationModel(
                uri="bos://bad/foo/bar",
                domain="memory",  # 故意与 URI 不匹配也会被 uri 验证拦截
                package="foo",
                action="bar",
            )
        assert "domain" in str(exc_info.value).lower() or "uri" in str(exc_info.value).lower()

    def test_uri_domain_field_mismatch_rejected(self):
        from omo.omo_bos_schema import BosRegistrationModel
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            BosRegistrationModel(
                uri="bos://memory/kos/search",
                domain="governance",  # URI 说 memory, field 说 governance
                package="kos",
                action="search",
            )

    def test_legacy_3_segment_auto_mapped(self):
        from omo.omo_bos_schema import BosRegistrationModel
        m = BosRegistrationModel(
            uri="bos://omo/audit",  # 3-段, LEGACY_DOMAIN_MAP 自动升级
            domain="governance",
            package="omo",
            action="audit",
        )
        # 升级为 4-段
        assert m.uri == "bos://governance/omo/audit"

    def test_endpoint_placeholder_allowed(self):
        from omo.omo_bos_schema import BosRegistrationModel
        m = BosRegistrationModel(
            uri="bos://memory/kos/search",
            domain="memory",
            package="kos",
            action="search",
            endpoint="placeholder://",  # 占位符
        )
        assert m.endpoint == "placeholder://"

    def test_endpoint_http_allowed(self):
        from omo.omo_bos_schema import BosRegistrationModel
        m = BosRegistrationModel(
            uri="bos://memory/kos/search",
            domain="memory",
            package="kos",
            action="search",
            endpoint="http://localhost:9090/search",
        )
        assert m.endpoint == "http://localhost:9090/search"

    def test_endpoint_module_colon_func(self):
        from omo.omo_bos_schema import BosRegistrationModel
        m = BosRegistrationModel(
            uri="bos://memory/kos/search",
            domain="memory",
            package="kos",
            action="search",
            endpoint="kairon.packages.kos.ontology.store:search_entities",
        )
        assert ":" in m.endpoint

    def test_registry_model_groups(self):
        from omo.omo_bos_schema import BosRegistryModel, BosRegistrationModel
        regs = [
            BosRegistrationModel(uri="bos://memory/kos/search", domain="memory", package="kos", action="search"),
            BosRegistrationModel(uri="bos://memory/kos/ingest", domain="memory", package="kos", action="ingest"),
            BosRegistrationModel(uri="bos://governance/omo/audit", domain="governance", package="omo", action="audit"),
        ]
        reg = BosRegistryModel(registrations=regs)
        assert reg.count == 3
        assert len(reg.by_domain("memory")) == 2
        assert len(reg.by_domain("governance")) == 1
        assert len(reg.by_package("kos")) == 2


# ── Metrics 测试 ──────────────────────────────────────────


class TestBosMetrics:
    def test_record_and_summary(self, tmp_path, monkeypatch):
        from omo import omo_bos_metrics
        # 重定向 metrics 路径到 tmp
        metrics_path = tmp_path / "bos-metrics.jsonl"
        monkeypatch.setattr(omo_bos_metrics, "DEFAULT_METRICS_PATH", metrics_path)

        for _ in range(5):
            omo_bos_metrics.record("bos://memory/kos/search", "resolved", 10.0)
        for _ in range(2):
            omo_bos_metrics.record("bos://analysis/minerva/research", "error", 50.0, error="timeout")

        s = omo_bos_metrics.summary(path=metrics_path)
        assert s["total_invocations"] == 7
        assert s["by_status"]["resolved"] == 5
        assert s["by_status"]["error"] == 2
        # by_domain 解析
        assert "memory" in s["by_domain"]
        assert "analysis" in s["by_domain"]
        # by_uri 详细
        assert s["by_uri"]["bos://memory/kos/search"]["count"] == 5
        assert s["by_uri"]["bos://memory/kos/search"]["success_rate"] == 1.0

    def test_get_metrics_filter(self, tmp_path, monkeypatch):
        from omo import omo_bos_metrics
        metrics_path = tmp_path / "bos-metrics.jsonl"
        monkeypatch.setattr(omo_bos_metrics, "DEFAULT_METRICS_PATH", metrics_path)
        omo_bos_metrics.record("bos://memory/kos/search", "resolved", 1.0)
        omo_bos_metrics.record("bos://memory/kos/ingest", "resolved", 2.0)
        omo_bos_metrics.record("bos://analysis/minerva/research", "resolved", 3.0)
        # 单 URI 过滤
        r = omo_bos_metrics.get_metrics(uri="bos://memory/kos/search", path=metrics_path)
        assert len(r) == 1
        assert r[0]["uri"] == "bos://memory/kos/search"
        # 全量
        r = omo_bos_metrics.get_metrics(path=metrics_path)
        assert len(r) == 3

    def test_time_invoke_context_manager(self, tmp_path, monkeypatch):
        from omo import omo_bos_metrics
        metrics_path = tmp_path / "bos-metrics.jsonl"
        monkeypatch.setattr(omo_bos_metrics, "DEFAULT_METRICS_PATH", metrics_path)
        import time
        with omo_bos_metrics.time_invoke("bos://test/foo/bar", transport="stdio") as timer:
            time.sleep(0.001)
        timer.set_status("resolved")
        recs = omo_bos_metrics.get_metrics(path=metrics_path)
        assert len(recs) == 1
        assert recs[0]["uri"] == "bos://test/foo/bar"
        assert recs[0]["status"] == "resolved"
        assert recs[0]["transport"] == "stdio"
        assert recs[0]["elapsed_ms"] >= 1.0  # 至少 1ms (sleep 1ms + 测时开销)

    def test_timestamp_format_uses_z_suffix(self, tmp_path, monkeypatch):
        """Reuse #7 锁: timestamp 格式必须以 'Z' 结尾 (与 omo_audit 对齐, 消灭 3 种格式)."""
        from omo import omo_bos_metrics
        metrics_path = tmp_path / "bos-metrics.jsonl"
        monkeypatch.setattr(omo_bos_metrics, "DEFAULT_METRICS_PATH", metrics_path)
        omo_bos_metrics.record("bos://test/foo", "resolved", 1.0)
        recs = omo_bos_metrics.get_metrics(path=metrics_path)
        ts = recs[0]["recorded_at"]
        # 必须以 'Z' 结尾, 不能是 '+00:00' 或 naive
        assert ts.endswith("Z"), f"timestamp must end with 'Z' (omo_audit convention), got: {ts!r}"
        assert "+00:00" not in ts, f"timestamp must not contain '+00:00' (replaced by 'Z'), got: {ts!r}"

    def test_percentile_calculation(self, tmp_path, monkeypatch):
        from omo import omo_bos_metrics
        metrics_path = tmp_path / "bos-metrics.jsonl"
        monkeypatch.setattr(omo_bos_metrics, "DEFAULT_METRICS_PATH", metrics_path)
        # 100 次调用, 延迟 1-100ms
        for i in range(1, 101):
            omo_bos_metrics.record("bos://test/foo/bar", "resolved", float(i))
        s = omo_bos_metrics.summary(path=metrics_path)
        st = s["by_uri"]["bos://test/foo/bar"]
        # p50 应在 50 附近
        assert 40 <= st["p50_ms"] <= 60
        # p95 应在 95 附近
        assert 90 <= st["p95_ms"] <= 100
        # max 必须是 100
        assert st["max_ms"] == 100.0

    def test_reset_clears_file(self, tmp_path, monkeypatch):
        from omo import omo_bos_metrics
        metrics_path = tmp_path / "bos-metrics.jsonl"
        monkeypatch.setattr(omo_bos_metrics, "DEFAULT_METRICS_PATH", metrics_path)
        omo_bos_metrics.record("bos://test/foo", "resolved", 1.0)
        omo_bos_metrics.record("bos://test/bar", "resolved", 2.0)
        n = omo_bos_metrics.reset(path=metrics_path)
        assert n == 2
        # 清空后 summary 应为 0
        s = omo_bos_metrics.summary(path=metrics_path)
        assert s["total_invocations"] == 0


# ── Dispatcher 集成测试 ──────────────────────────────────


class TestDispatcherInstrumentation:
    def test_dispatcher_records_metric(self, tmp_path, monkeypatch):
        from omo import omo_bos_metrics
        metrics_path = tmp_path / "bos-metrics.jsonl"
        monkeypatch.setattr(omo_bos_metrics, "DEFAULT_METRICS_PATH", metrics_path)
        # 触发 invoke
        from omo.omo_bos_dispatcher import TOOL_DISPATCHER
        TOOL_DISPATCHER["invoke_bos_uri"](
            {"uri": "bos://memory/kos/search", "args": {"query": "test"}}
        )
        # 验证: metric 应被记录
        recs = omo_bos_metrics.get_metrics(path=metrics_path)
        assert len(recs) >= 1
        assert recs[-1]["uri"] == "bos://memory/kos/search"
        # status 应是 resolved 或 agora_unavailable (实际跑会触发这俩之一)
        assert recs[-1]["status"] in ("resolved", "agora_unavailable", "error")

    def test_dispatcher_records_invalid(self, tmp_path, monkeypatch):
        from omo import omo_bos_metrics
        metrics_path = tmp_path / "bos-metrics.jsonl"
        monkeypatch.setattr(omo_bos_metrics, "DEFAULT_METRICS_PATH", metrics_path)
        from omo.omo_bos_dispatcher import TOOL_DISPATCHER
        TOOL_DISPATCHER["invoke_bos_uri"]({"uri": "bos://bad/foo/bar", "args": {}})
        recs = omo_bos_metrics.get_metrics(path=metrics_path)
        assert len(recs) >= 1
        assert recs[-1]["uri"] == "bos://bad/foo/bar"


# ── CLI smoke 测试 ──────────────────────────────────────


class TestCli:
    def test_bos_status_runs(self):
        """omo bos status 子进程测试."""
        result = subprocess.run(
            [sys.executable, "-m", "omo.cli", "bos", "status"],
            capture_output=True, text=True, timeout=30,
            cwd=OMO_SRC.parent.parent,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "BOS Metrics" in result.stdout

    def test_bos_discover_json(self):
        result = subprocess.run(
            [sys.executable, "-m", "omo.cli", "bos", "discover", "--json"],
            capture_output=True, text=True, timeout=30,
            cwd=OMO_SRC.parent.parent,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(result.stdout)
        assert data["count"] >= 21  # 至少 21 SEED URI
        assert all("uri" in r for r in data["registrations"])
