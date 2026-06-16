"""Tests for web/compat.py — stub layer for Agora Dashboard."""

from __future__ import annotations

from web.compat import (
    AuditSubscriber,
    DiscoveryEngine,
    EventBus,
    Pipeline,
    Router,
    Service,
    ServiceRegistry,
    WorkspaceResearch,
    is_safe_url,
    parse_protocol_config,
    parse_tags,
    seed_registry,
    service_to_agent_card,
)

# ── Service ──────────────────────────────────────────────────────────────────


class TestService:
    def test_defaults(self):
        svc = Service()
        assert svc.name == ""
        assert svc.healthy is True
        assert svc.circuit_state == "正常"
        assert svc.failure_count == 0
        assert svc.instances == []
        assert svc.tags == []
        assert svc.protocol == "mcp"

    def test_custom_values(self):
        svc = Service(
            name="test-svc",
            description="A test",
            protocol="http",
            port=8080,
            tags=["l2", "test"],
            healthy=False,
            circuit_state="断路",
            failure_count=3,
        )
        assert svc.name == "test-svc"
        assert svc.port == 8080
        assert svc.healthy is False
        assert svc.circuit_state == "断路"
        assert svc.failure_count == 3


# ── EventBus ─────────────────────────────────────────────────────────────────


class TestEventBus:
    def test_emit_and_log(self):
        bus = EventBus()
        bus.publish("test:event", {"key": "value"}, "test")
        log = bus.get_event_log()
        assert len(log) == 1
        assert log[0]["type"] == "test:event"
        assert log[0]["payload"] == {"key": "value"}
        assert log[0]["source"] == "test"
        assert "id" in log[0]
        assert "timestamp" in log[0]

    def test_get_event_log_limit(self):
        bus = EventBus()
        for i in range(5):
            bus.publish(f"event:{i}", {}, "test")
        assert len(bus.get_event_log(limit=3)) == 3

    def test_get_event_log_returns_reversed(self):
        bus = EventBus()
        bus.publish("first", {}, "test")
        bus.publish("second", {}, "test")
        log = bus.get_event_log()
        assert log[0]["type"] == "second"
        assert log[1]["type"] == "first"

    def test_register_hook_and_emit(self):
        bus = EventBus()
        received = []
        bus.register_hook(lambda e: received.append(e))
        bus.emit({"custom": "event"})
        assert len(received) == 1
        assert received[0]["custom"] == "event"

    def test_emit_always_appends(self):
        bus = EventBus()
        bus.emit({"key": "val"})
        assert len(bus.get_event_log()) == 1

    def test_register_hook_error_tolerance(self):
        bus = EventBus()
        bus.register_hook(lambda e: 1 / 0)
        bus.register_hook(lambda e: e)
        bus.emit({"ok": True})
        assert len(bus._event_log) == 1

    def test_subscribe(self):
        bus = EventBus()
        sub_id = bus.subscribe("user-1", "registry:*", "http://callback")
        assert sub_id.startswith("sub-")
        assert bus.has_push_subscribers() is True

    def test_no_subscribers(self):
        bus = EventBus()
        assert bus.has_push_subscribers() is False

    def test_publish_returns_unique_ids(self):
        bus = EventBus()
        id1 = bus.publish("a", {}, "s")
        id2 = bus.publish("b", {}, "s")
        assert id1 != id2


# ── ServiceRegistry ──────────────────────────────────────────────────────────


class TestServiceRegistry:
    def test_register_service_object(self):
        reg = ServiceRegistry()
        svc = Service(name="test", healthy=True)
        reg.register(svc)
        assert len(reg.list_all()) == 1
        assert reg.list_all()[0].name == "test"

    def test_register_name_and_service(self):
        reg = ServiceRegistry()
        svc = Service(name="my-svc")
        reg.register("my-svc", svc)
        assert len(reg.list_all()) == 1

    def test_list_healthy(self):
        reg = ServiceRegistry()
        reg.register(Service(name="a", healthy=True))
        reg.register(Service(name="b", healthy=False))
        assert len(reg.list_healthy()) == 1
        assert reg.list_healthy()[0].name == "a"

    def test_get_circuit_status_default(self):
        reg = ServiceRegistry()
        reg.register(Service(name="x"))
        assert reg.get_circuit_status("x") == "正常"

    def test_get_circuit_status_unknown(self):
        reg = ServiceRegistry()
        assert reg.get_circuit_status("nonexistent") == "正常"

    def test_get_transitions(self):
        reg = ServiceRegistry()
        reg.register(Service(name="x"))
        reg.register(Service(name="y"))
        transitions = reg.get_transitions()
        assert len(transitions) == 2

    def test_get_transitions_filter_service(self):
        reg = ServiceRegistry()
        reg.register(Service(name="x"))
        reg.register(Service(name="y"))
        t = reg.get_transitions(service="x")
        assert len(t) == 1
        assert t[0]["service"] == "x"

    def test_get_transitions_limit(self):
        reg = ServiceRegistry()
        for i in range(10):
            reg.register(Service(name=f"s{i}"))
        assert len(reg.get_transitions(limit=3)) == 3

    def test_clear_all(self):
        reg = ServiceRegistry()
        reg.register(Service(name="a"))
        reg.register(Service(name="b"))
        count = reg.clear_all()
        assert count == 2
        assert len(reg.list_all()) == 0


# ── WorkspaceResearch ────────────────────────────────────────────────────────


class TestWorkspaceResearch:
    def test_list_recent(self):
        assert WorkspaceResearch.list_recent_research() == []

    def test_search(self):
        assert WorkspaceResearch.search_research(q="test") == []

    def test_get_detail(self):
        assert WorkspaceResearch.get_research_detail(1) is None

    def test_archive(self):
        assert WorkspaceResearch.archive_research(1) is True

    def test_publish(self):
        assert WorkspaceResearch.publish_brief(1) == ""

    def test_sync(self):
        assert WorkspaceResearch.sync_published(1) == ""

    def test_unarchive(self):
        assert WorkspaceResearch.unarchive_research(1) is True

    def test_tag(self):
        assert WorkspaceResearch.tag_research(1, ["a"]) is True

    def test_rename(self):
        assert WorkspaceResearch.rename_research(1, "new") is True


# ── Pipeline / DiscoveryEngine / AuditSubscriber ────────────────────────────


class TestPipeline:
    def test_get_pipeline_empty(self):
        assert Pipeline().get_pipeline("x") == []

    def test_list_pipelines_empty(self):
        assert Pipeline().list_pipelines() == []


class TestDiscoveryEngine:
    def test_auto_register(self):
        reg = ServiceRegistry()
        assert DiscoveryEngine().auto_register(reg) == 0


class TestAuditSubscriber:
    def test_on_event_noop(self):
        AuditSubscriber().on_event({"type": "test"})


# ── Router ───────────────────────────────────────────────────────────────────


class TestRouter:
    def test_add_instance(self):
        r = Router()
        r._add_instance("svc", "http://localhost:8080")
        assert "svc" in r._instances
        assert r._instances["svc"] == ["http://localhost:8080"]

    def test_get_percentiles(self):
        p = Router().get_percentiles()
        assert "p50" in p
        assert "p99" in p


# ── Helper functions ─────────────────────────────────────────────────────────


class TestHelpers:
    def test_is_safe_url(self):
        assert is_safe_url("http://example.com") is True

    def test_parse_protocol_config_valid(self):
        cfg, err = parse_protocol_config('{"key": "value"}')
        assert err is None
        assert cfg["key"] == "value"

    def test_parse_protocol_config_empty(self):
        cfg, err = parse_protocol_config("")
        assert err is None

    def test_parse_protocol_config_invalid(self):
        _, err = parse_protocol_config("not-json")
        assert err is not None

    def test_parse_tags(self):
        assert parse_tags("a,b,c") == ["a", "b", "c"]
        assert parse_tags("") == []
        assert parse_tags(" a , b ") == ["a", "b"]


# ── service_to_agent_card ────────────────────────────────────────────────────


class TestServiceToAgentCard:
    def test_basic(self):
        card = service_to_agent_card(name="test", description="desc", protocol="mcp")
        d = card.to_dict()
        assert d["name"] == "test"
        assert d["description"] == "desc"
        assert d["protocol"] == "mcp"
        assert "capabilities" in d

    def test_with_auth(self):
        card = service_to_agent_card(name="s", has_auth=True, has_push_notifications=True)
        d = card.to_dict()
        assert d["capabilities"]["auth"] is True
        assert d["capabilities"]["push_notifications"] is True


# ── seed_registry ────────────────────────────────────────────────────────────


class TestSeedRegistry:
    def test_seeds_known_services(self):
        reg = ServiceRegistry()
        count = seed_registry(reg)
        assert count == 12
        assert len(reg.list_all()) == 12

    def test_known_service_names(self):
        reg = ServiceRegistry()
        seed_registry(reg)
        names = {s.name for s in reg.list_all()}
        assert "agora" in names
        assert "cockpit" in names
        assert "runtime" in names
        assert "kairon" in names
        assert "gbrain" in names
        assert "l4-kernel" in names

    def test_all_healthy(self):
        reg = ServiceRegistry()
        seed_registry(reg)
        assert len(reg.list_healthy()) == 12
