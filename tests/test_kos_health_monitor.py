"""TDD: Tests for kos_health_monitor — drift detection, no auto-reindex."""

from __future__ import annotations

from ecos.services.kos_health_monitor import (
    BASELINE,
    THRESHOLDS,
    check_drift,
    check_known_docs,
    generate_reindex_request,
    get_baseline,
)


class TestBaseline:
    def test_get_baseline_returns_copy(self):
        b = get_baseline()
        assert b["documents"] == 7327
        assert b["captured_at"] == "2026-05-30"
        # Ensure it's a copy
        b["documents"] = 0
        assert BASELINE["documents"] == 7327

    def test_baseline_has_all_zones(self):
        zones = BASELINE["zones"]
        assert set(zones.keys()) == {"workspace_root", "omo", "kairon", "agentmesh", "gbrain", "sharedbrain"}
        assert sum(zones.values()) == 7327

    def test_baseline_has_10_known_docs(self):
        assert len(BASELINE["known_doc_ids"]) == 10


class TestCheckDrift:
    def test_no_drift_returns_no_alerts(self):
        alerts = check_drift(7327, BASELINE["zones"])
        assert len(alerts) == 0

    def test_warning_drift_detected(self):
        # 5.5% drift (403 docs) — above warning threshold
        alerts = check_drift(7327 + 403, BASELINE["zones"])
        assert len([a for a in alerts if a["level"] == "warning"]) >= 1
        assert len([a for a in alerts if a["level"] == "critical"]) == 0

    def test_critical_drift_detected(self):
        # 12% drift (879 docs) — above critical threshold
        alerts = check_drift(7327 + 879, BASELINE["zones"])
        assert len([a for a in alerts if a["level"] == "critical"]) >= 1
        assert all(
            a.get("action") == "NO_AUTO_REINDEX" or "HUMAN_INVESTIGATE" in a.get("action", "")
            for a in alerts
            if a["level"] == "critical"
        )

    def test_no_auto_reindex_in_any_alert(self):
        alerts = check_drift(
            7327 + 1000,
            {"sharedbrain": 0, "kairon": 2000, "gbrain": 500, "omo": 180, "agentmesh": 40, "workspace_root": 10},
        )
        for a in alerts:
            assert a.get("action") not in ("REINDEX", "AUTO_REINDEX"), f"AUTO_REINDEX found: {a}"
            # "NO_AUTO_REINDEX" contains 'reindex' but is the correct action — it's explicitly preventing it

    def test_missing_zone_raises_critical(self):
        # sharedbrain zone is 0 (missing) — should trigger critical
        alerts = check_drift(
            7327, {"sharedbrain": 0, "kairon": 1886, "gbrain": 506, "omo": 179, "agentmesh": 38, "workspace_root": 8}
        )
        sharedbrain_alert = [a for a in alerts if a.get("metric") == "zone_sharedbrain"]
        assert len(sharedbrain_alert) >= 1
        assert sharedbrain_alert[0]["level"] == "critical"
        assert sharedbrain_alert[0].get("message") == "MISSING_ZONE"

    def test_empty_zones_skips_zone_check(self):
        # Empty dict is falsy — implementation skips zone iteration, no zone alerts
        alerts = check_drift(7327, {})
        zone_alerts = [a for a in alerts if a.get("metric", "").startswith("zone_")]
        assert len(zone_alerts) == 0

    def test_negative_drift(self):
        alerts = check_drift(
            6000, {"sharedbrain": 4000, "kairon": 1500, "gbrain": 400, "omo": 100, "agentmesh": 0, "workspace_root": 0}
        )
        assert len(alerts) > 0

    def test_db_unavailable_returns_critical(self):
        alerts = check_drift(None, {})
        assert any(a["message"] == "DB_UNAVAILABLE" for a in alerts)

    def test_borderline_warning_not_critical(self):
        # 9.9% — warning but not critical
        alerts = check_drift(7327 + 725, BASELINE["zones"])
        critical = [a for a in alerts if a["level"] == "critical"]
        warning = [a for a in alerts if a["level"] == "warning"]
        assert len(critical) == 0
        assert len(warning) >= 1


class TestCheckKnownDocs:
    def test_all_found_returns_ok(self):
        def search_fn(doc_id):
            return True

        result = check_known_docs(search_fn)
        assert result["found"] == 10
        assert result["level"] == "ok"
        assert len(result["failed_ids"]) == 0

    def test_none_found_returns_critical(self):
        def search_fn(doc_id):
            return False

        result = check_known_docs(search_fn)
        assert result["found"] == 0
        assert result["level"] == "critical"

    def test_partial_found_returns_warning(self):
        count = 0

        def search_fn(doc_id):
            nonlocal count
            count += 1
            return count <= 9

        result = check_known_docs(search_fn)
        assert result["found"] == 9
        assert result["level"] == "warning"

    def test_exception_handling(self):
        def search_fn(doc_id):
            raise RuntimeError("search failed")

        result = check_known_docs(search_fn)
        assert result["found"] == 0
        assert result["level"] == "critical"


class TestGenerateReindexRequest:
    def test_always_returns_unconfirmed(self):
        req = generate_reindex_request([])
        assert req["_confirmed"] is False
        assert req["type"] == "reindex_request"

    def test_contains_alerts(self):
        alerts = [{"metric": "total_docs", "level": "critical", "drift_pct": 12.0}]
        req = generate_reindex_request(alerts)
        assert req["alerts"] == alerts
        assert req["baseline"] == 7327

    def test_default_caller(self):
        req = generate_reindex_request([])
        assert req["caller"] == "kos-health-monitor"


class TestThresholdConfig:
    def test_thresholds_are_configured(self):
        assert "total_docs" in THRESHOLDS
        assert "per_zone" in THRESHOLDS
        assert "known_doc" in THRESHOLDS

    def test_threshold_values(self):
        assert THRESHOLDS["total_docs"]["warning"] == 5.0
        assert THRESHOLDS["total_docs"]["critical"] == 10.0
        assert THRESHOLDS["per_zone"]["warning"] == 10.0
        assert THRESHOLDS["per_zone"]["critical"] == 20.0
