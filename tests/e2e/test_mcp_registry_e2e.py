"""端到端测试：agora MCP registry 全流水线。

验证从服务注册到发现、心跳、熔断、持久化、缓存快照、Agent 注册表、
gRPC 健康检查到配置管理的完整流程。所有测试均离线运行，使用临时目录
和 in-memory 数据库，无网络访问需求。
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from agora.agent_registry import (
    AgentRegistry,
    generate_key_pair,
    sign_challenge,
    verify_signature,
)
from agora.core.registry import KNOWN_PROTOCOLS, Service, ServiceRegistry
from agora.core.service_base import is_safe_url, parse_protocol_config, parse_tags
from agora.mcp.mcp_bootstrap import (
    KNOWN_SERVICES,
    _default_config,
)
from agora.persistence_db import json_load as db_load
from agora.persistence_db import json_save as db_save

# ═══════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════


def _new_registry(tmp_path: Path) -> ServiceRegistry:
    """创建一个使用临时目录的 ServiceRegistry 实例。"""
    return ServiceRegistry(
        storage_path=str(tmp_path / "test-services.json"),
        cb_max_failures=3,
        cb_cooldown=1.0,
        cb_success_threshold=2,
    )


def _make_service(name: str = "minerva", **kwargs) -> Service:
    """创建 Service 实例的快捷方式。"""
    defaults = dict(
        description=f"MCP service: {name}",
        protocol="mcp",
        mcp_endpoint="stdio:test",
        port=0,
        tags=["test", name],
    )
    defaults.update(kwargs)
    return Service(name=name, **defaults)


# ═══════════════════════════════════════════════════════════════
# Phase 1 — ServiceRegistry 完整生命周期
# ═══════════════════════════════════════════════════════════════


class TestServiceRegistryLifecycle:
    """验证服务注册、查询、列表、注销的核心 CRUD 流程。"""

    def test_register_and_get(self, tmp_path: Path):
        """注册服务后可通过 get() 获取。"""
        r = _new_registry(tmp_path)
        svc = _make_service("minerva")
        r.register(svc)
        assert r.get("minerva") is not None
        assert r.get("minerva").name == "minerva"

    def test_register_persists_across_registry_reload(self, tmp_path: Path):
        """注册的数据持久化到 SQLite，重新创建 registry 后依然可用。"""
        path = tmp_path / "test-services.json"
        r1 = ServiceRegistry(storage_path=str(path))
        r1.register(_make_service("minerva"))

        r2 = ServiceRegistry(storage_path=str(path))
        assert r2.get("minerva") is not None
        assert r2.get("minerva").port == 0

    def test_list_all_returns_registered_services(self, tmp_path: Path):
        """list_all() 返回所有已注册的服务。"""
        r = _new_registry(tmp_path)
        r.register(_make_service("minerva"))
        r.register(_make_service("sophia"))
        r.register(_make_service("eidos"))
        services = r.list_all()
        assert len(services) == 3
        names = {s.name for s in services}
        assert names == {"minerva", "sophia", "eidos"}

    def test_unregister_removes_service(self, tmp_path: Path):
        """unregister() 从注册表中移除服务。"""
        r = _new_registry(tmp_path)
        r.register(_make_service("minerva"))
        r.unregister("minerva")
        assert r.get("minerva") is None
        assert len(r.list_all()) == 0

    def test_unregister_nonexistent_does_not_raise(self, tmp_path: Path):
        """注销不存在的服务不抛出异常。"""
        r = _new_registry(tmp_path)
        r.unregister("ghost")  # should not raise

    def test_clear_all_empties_registry(self, tmp_path: Path):
        """clear_all() 清空所有服务。"""
        r = _new_registry(tmp_path)
        r.register(_make_service("a"))
        r.register(_make_service("b"))
        r.register(_make_service("c"))
        count = r.clear_all()
        assert count == 3
        assert r.list_all() == []

    def test_clear_all_empty_returns_zero(self, tmp_path: Path):
        """空注册表的 clear_all() 返回 0。"""
        r = _new_registry(tmp_path)
        assert r.clear_all() == 0

    def test_service_max_limit_enforced(self, tmp_path: Path):
        """超过最大服务限制时抛出 ValueError。"""
        r = _new_registry(tmp_path)
        r._MAX_SERVICES = 3
        r.register(_make_service("a"))
        r.register(_make_service("b"))
        r.register(_make_service("c"))
        with pytest.raises(ValueError, match="Service limit reached"):
            r.register(_make_service("d"))

    def test_register_unknown_protocol_raises(self, tmp_path: Path):
        """注册未知协议的服务时抛出 ValueError。"""
        r = _new_registry(tmp_path)
        with pytest.raises(ValueError, match="Unknown protocol"):
            r.register(_make_service("bad", protocol="invalid_proto"))

    def test_register_valid_protocols(self, tmp_path: Path):
        """所有 KNOWN_PROTOCOLS 均可注册。"""
        r = _new_registry(tmp_path)
        for i, proto in enumerate(KNOWN_PROTOCOLS):
            r.register(_make_service(f"svc-{proto}", protocol=proto))
        assert len(r.list_all()) == len(KNOWN_PROTOCOLS)

    def test_to_dict_includes_all_fields(self, tmp_path: Path):
        """to_dict() 返回完整的服务信息字典。"""
        r = _new_registry(tmp_path)
        r.register(
            _make_service(
                "api",
                protocol="rest",
                protocol_config={"method": "POST"},
                health_endpoint="http://192.0.2.1:3000/health",
                has_auth=True,
                documentation_url="http://example.com/docs",
            )
        )
        d = r.to_dict()
        assert len(d) == 1
        entry = d[0]
        assert entry["name"] == "api"
        assert entry["protocol"] == "rest"
        assert entry["protocol_config"] == {"method": "POST"}
        assert entry["has_auth"] is True
        assert entry["documentation_url"] == "http://example.com/docs"

    def test_list_healthy_filters_unhealthy(self, tmp_path: Path):
        """list_healthy() 只返回可用服务。"""
        r = _new_registry(tmp_path)
        r.register(_make_service("ok"))
        r.register(_make_service("bad"))
        for _ in range(3):
            r.mark_failure("bad")
        healthy = r.list_healthy()
        assert len(healthy) == 1
        assert healthy[0].name == "ok"


# ═══════════════════════════════════════════════════════════════
# Phase 2 — 心跳系统
# ═══════════════════════════════════════════════════════════════


class TestHeartbeatSystem:
    """验证心跳注册、过期检测与身份信息传递。"""

    def test_register_heartbeat_updates_timestamp_and_identity(self, tmp_path: Path):
        """心跳更新最后检查时间和 provider_info。"""
        r = _new_registry(tmp_path)
        r.register(_make_service("worker"))
        result = r.register_heartbeat("worker", {"role": "indexer"}, now=100.0)
        svc = r.get("worker")
        assert result["status"] == "heartbeat_registered"
        assert result["last_heartbeat"] == 100.0
        assert svc.last_health_check == 100.0
        assert svc.healthy is True
        assert svc.provider_info == {"role": "indexer"}

    def test_heartbeat_nonexistent_service_raises(self, tmp_path: Path):
        """对未注册的服务发送心跳抛出 ValueError。"""
        r = _new_registry(tmp_path)
        with pytest.raises(ValueError, match="Unknown service"):
            r.register_heartbeat("ghost")

    def test_stale_heartbeats_identifies_zombies(self, tmp_path: Path):
        """stale_heartbeats() 检测过期心跳。"""
        r = _new_registry(tmp_path)
        r.register(_make_service("fresh"))
        r.register(_make_service("zombie"))
        r.register_heartbeat("fresh", now=190.0)
        r.register_heartbeat("zombie", now=10.0)
        stale = r.stale_heartbeats(max_age_seconds=60.0, now=200.0)
        assert [item["name"] for item in stale] == ["zombie"]
        assert stale[0]["age_seconds"] == 190.0

    def test_no_stale_when_all_recent(self, tmp_path: Path):
        """所有心跳在有效期内时，stale 列表为空。"""
        r = _new_registry(tmp_path)
        r.register(_make_service("a"))
        r.register(_make_service("b"))
        r.register_heartbeat("a", now=195.0)
        r.register_heartbeat("b", now=198.0)
        stale = r.stale_heartbeats(max_age_seconds=60.0, now=200.0)
        assert stale == []

    def test_services_without_heartbeat_not_stale(self, tmp_path: Path):
        """从未发送过心跳的服务不被视为 stale。"""
        r = _new_registry(tmp_path)
        r.register(_make_service("new"))
        stale = r.stale_heartbeats(max_age_seconds=60.0, now=200.0)
        assert stale == []

    def test_heartbeat_persists_identity(self, tmp_path: Path):
        """心跳中传递的身份信息持久化后仍可用。"""
        path = tmp_path / "test-services.json"
        r1 = ServiceRegistry(storage_path=str(path))
        r1.register(_make_service("agent"))
        r1.register_heartbeat("agent", {"version": "1.2.3"}, now=100.0)

        r2 = ServiceRegistry(storage_path=str(path))
        svc = r2.get("agent")
        assert svc.provider_info == {"version": "1.2.3"}
        assert svc.healthy is True


# ═══════════════════════════════════════════════════════════════
# Phase 3 — 熔断器
# ═══════════════════════════════════════════════════════════════


class TestCircuitBreaker:
    """验证熔断器状态流转：CLOSED → OPEN → HALF_OPEN → CLOSED。"""

    def test_closed_on_registration(self, tmp_path: Path):
        """刚注册的服务状态为 CLOSED。"""
        r = _new_registry(tmp_path)
        r.register(_make_service("svc"))
        status = r.get_circuit_status("svc")
        assert status["state"] == "CLOSED"
        assert status["healthy"] is True
        assert status["failure_count"] == 0

    def test_opens_after_max_failures(self, tmp_path: Path):
        """达到最大失败次数后熔断器打开。"""
        r = _new_registry(tmp_path)
        r.register(_make_service("svc"))
        for _ in range(3):
            r.mark_failure("svc")
        status = r.get_circuit_status("svc")
        assert status["state"] == "OPEN"
        assert status["failure_count"] == 3
        assert status["healthy"] is False

    def test_successes_decay_failure_count(self, tmp_path: Path):
        """连续成功逐渐减少失败计数。"""
        r = _new_registry(tmp_path)
        r.register(_make_service("svc"))
        for _ in range(3):
            r.mark_failure("svc")
        assert not r.get("svc").is_available

        # 恢复：连续成功
        r.mark_success("svc")
        assert r.get("svc").failure_count == 2
        r.mark_success("svc")
        assert r.get("svc").failure_count == 1
        assert r.get("svc").is_available

    def test_failure_reopens_after_partial_recovery(self, tmp_path: Path):
        """部分恢复后再次失败，熔断器重新打开。"""
        r = _new_registry(tmp_path)
        r.register(_make_service("svc"))
        for _ in range(3):
            r.mark_failure("svc")  # OPEN

        # 部分恢复
        r.mark_success("svc")  # failure_count → 2
        r.mark_failure("svc")  # failure_count → 3 → OPEN again
        status = r.get_circuit_status("svc")
        assert status["state"] == "OPEN"

    def test_unknown_service_returns_empty_dict(self, tmp_path: Path):
        """查询不存在服务的熔断状态返回空字典。"""
        r = _new_registry(tmp_path)
        assert r.get_circuit_status("ghost") == {}

    def test_is_available_checks_cooldown(self):
        """healthy=False 但 cooldown 已过期的服务可用。"""
        svc = _make_service("test")
        svc.healthy = False
        svc.cooldown_until = 0.0  # cooldown 已过期
        assert svc.is_available is True

    def test_is_available_false_when_in_cooldown(self):
        """healthy=False 且 cooldown 未过期时不可用。"""
        svc = _make_service("test")
        svc.healthy = False
        svc.cooldown_until = time.monotonic() + 3600  # 1h
        assert svc.is_available is False

    def test_circuit_state_half_open(self):
        """half_open 标志位使状态为 HALF_OPEN。"""
        svc = _make_service("test")
        svc.healthy = False
        svc.half_open = True
        assert svc.circuit_state == "HALF_OPEN"


# ═══════════════════════════════════════════════════════════════
# Phase 4 — 缓存快照与降级模式
# ═══════════════════════════════════════════════════════════════


class TestCacheSnapshot:
    """验证缓存快照的保存、加载和过期检测。"""

    def test_save_and_load_snapshot(self, tmp_path: Path):
        """保存快照后可以完整加载。"""
        cache_file = tmp_path / "service-cache.json"
        r = _new_registry(tmp_path)
        r.register(_make_service("cached-worker", protocol="stdio", mcp_endpoint="stdio:worker"))
        r.register_heartbeat("cached-worker", {"role": "worker"}, now=123.0)
        r.save_cache_snapshot(str(cache_file))

        restored = ServiceRegistry.load_cache_snapshot(str(cache_file), max_age_seconds=3600.0, now=124.0)
        assert len(restored) == 1
        assert restored[0].name == "cached-worker"
        assert restored[0].provider_info == {"role": "worker"}

    def test_snapshot_expiry_returns_empty(self, tmp_path: Path):
        """过期快照返回空列表。"""
        cache_file = tmp_path / "stale-cache.json"
        r = _new_registry(tmp_path)
        r.register(_make_service("old"))
        r.save_cache_snapshot(str(cache_file))

        restored = ServiceRegistry.load_cache_snapshot(str(cache_file), max_age_seconds=10.0, now=9999999999.0)
        assert restored == []

    def test_snapshot_with_no_services(self, tmp_path: Path):
        """空注册表的快照保存和加载正常。"""
        cache_file = tmp_path / "empty-cache.json"
        r = _new_registry(tmp_path)
        r.save_cache_snapshot(str(cache_file))

        restored = ServiceRegistry.load_cache_snapshot(str(cache_file), max_age_seconds=3600.0)
        assert restored == []

    def test_snapshot_round_trip_all_fields(self, tmp_path: Path):
        """快照加载后保留所有字段。"""
        cache_file = tmp_path / "full-cache.json"
        r = _new_registry(tmp_path)
        r.register(
            _make_service(
                "full-svc",
                protocol="rest",
                protocol_config={"path": "/api"},
                health_endpoint="http://192.0.2.1:3000/health",
                tags=["important"],
            )
        )
        r.save_cache_snapshot(str(cache_file))

        restored = ServiceRegistry.load_cache_snapshot(str(cache_file), max_age_seconds=3600.0)
        svc = restored[0]
        assert svc.name == "full-svc"
        assert svc.protocol == "rest"
        assert svc.healthy is True

    def test_snapshot_missing_file_returns_empty(self):
        """不存在的快照文件返回空列表。"""
        restored = ServiceRegistry.load_cache_snapshot("/nonexistent/cache.json", max_age_seconds=3600.0)
        assert restored == []


# ═══════════════════════════════════════════════════════════════
# Phase 5 — SQLite 持久化
# ═══════════════════════════════════════════════════════════════


class TestPersistence:
    """验证 SQLite + JSON 双轨持久化的数据可靠性。"""

    def test_db_save_and_load_round_trip(self, tmp_path: Path):
        """数据通过 SQLite 持久化后可以完整读取。"""
        db_path = tmp_path / "test.db"
        payload = {"services": [{"name": "test-svc", "healthy": True}]}
        assert db_save(db_path, payload) is True
        loaded = db_load(db_path)
        assert loaded == payload

    def test_db_load_missing_returns_default(self, tmp_path: Path):
        """不存在的 SQLite 键返回默认值。"""
        db_path = tmp_path / "nosuch.db"
        result = db_load(db_path, default={"empty": True})
        assert result == {"empty": True}

    def test_db_overwrites_existing_key(self, tmp_path: Path):
        """同一个 key 的多次写入是幂等的。"""
        db_path = tmp_path / "test.db"
        db_save(db_path, {"version": 1})
        db_save(db_path, {"version": 2})
        loaded = db_load(db_path)
        assert loaded == {"version": 2}

    def test_auto_migration_from_json_file(self, tmp_path: Path):
        """json_save 写入 SQLite，json_load 自动回退到 JSON 文件。"""
        json_path = tmp_path / "test-services.json"
        original = {"services": [{"name": "legacy", "healthy": True}]}
        json_path.write_text(json.dumps(original))

        # db_load 应先尝试 SQLite（不存在），然后自动迁移 JSON
        loaded = db_load(json_path)
        assert loaded == original

        # 迁移后 SQLite 中也有数据
        reloaded = db_load(json_path)
        assert reloaded == original

    def test_registry_survives_process_restart(self, tmp_path: Path):
        """模拟进程重启：创建→注册→销毁→重建→验证。"""
        storage = tmp_path / "agora-services.json"

        # "进程 1"：注册服务
        r1 = ServiceRegistry(storage_path=str(storage))
        r1.register(_make_service("minerva"))
        r1.register(_make_service("sophia"))
        r1.register_heartbeat("minerva", {"alive": True}, now=100.0)
        del r1

        # "进程 2"：从持久化重新加载
        r2 = ServiceRegistry(storage_path=str(storage))
        assert len(r2.list_all()) == 2
        minerva = r2.get("minerva")
        assert minerva is not None
        assert minerva.provider_info == {"alive": True}
        assert minerva.last_health_check == 100.0

        sophia = r2.get("sophia")
        assert sophia is not None
        assert sophia.healthy is True

    def test_concurrent_sqlite_wal_mode(self, tmp_path: Path):
        """WAL 模式支持并发读写。"""
        db_path = tmp_path / "concurrent.db"

        # 使用 db_save 通过完整的 persistence_db 路径写入（内部使用 _get_db -> agora.db）
        assert db_save(db_path, "data") is True

        # 通过同一个文件路径读取（db_load 内部归一化为 <parent>/agora.db）
        loaded = db_load(db_path)
        assert loaded == "data"


# ═══════════════════════════════════════════════════════════════
# Phase 6 — 转换日志
# ═══════════════════════════════════════════════════════════════


class TestTransitionLog:
    """验证转换日志的记录与查询。"""

    def test_register_adds_transition(self, tmp_path: Path):
        """注册服务会生成 transition 日志。"""
        r = _new_registry(tmp_path)
        r.register(_make_service("svc"))
        transitions = r.get_transitions()
        assert len(transitions) >= 1
        assert transitions[-1]["service"] == "svc"
        assert transitions[-1]["state_from"] == ""
        assert transitions[-1]["state_to"] == "registered"

    def test_heartbeat_adds_transition(self, tmp_path: Path):
        """心跳会生成 transition。"""
        r = _new_registry(tmp_path)
        r.register(_make_service("svc"))
        r.register_heartbeat("svc", now=100.0)
        transitions = r.get_transitions(service="svc")
        heartbeat_entries = [t for t in transitions if t["source"] == "heartbeat"]
        assert len(heartbeat_entries) >= 1

    def test_unregister_adds_transition(self, tmp_path: Path):
        """注销服务会生成 transition。"""
        r = _new_registry(tmp_path)
        r.register(_make_service("svc"))
        r.unregister("svc")
        transitions = r.get_transitions(service="svc")
        unreg_entries = [t for t in transitions if t["state_to"] == "unregistered"]
        assert len(unreg_entries) >= 1

    def test_clear_transitions(self, tmp_path: Path):
        """clear_transitions() 清空日志。"""
        r = _new_registry(tmp_path)
        r.register(_make_service("svc"))
        assert len(r.get_transitions()) > 0
        r.clear_transitions()
        assert r.get_transitions() == []

    def test_transition_limit(self, tmp_path: Path):
        """get_transitions(limit=N) 返回最多 N 条。"""
        r = _new_registry(tmp_path)
        for name in ["a", "b", "c", "d", "e"]:
            r.register(_make_service(name))
        assert len(r.get_transitions(limit=3)) <= 3


# ═══════════════════════════════════════════════════════════════
# Phase 7 — AgentRegistry 完整生命周期
# ═══════════════════════════════════════════════════════════════


class TestAgentRegistry:
    """验证 Agent 注册表（含 Ed25519 签名验证）。"""

    @pytest.fixture
    def agent_registry(self, tmp_path: Path) -> AgentRegistry:
        """创建使用临时缓存的 AgentRegistry。"""
        cache = str(tmp_path / "agent-cache.json")
        backup = str(tmp_path / "agent-backup.json")
        return AgentRegistry(cache_file=cache, backup_cache_file=backup)

    def test_register_with_auto_key_generation(self, agent_registry: AgentRegistry):
        """注册时自动生成 Ed25519 密钥对。"""
        result = agent_registry.register("agent-01", capabilities=["read", "write"])
        assert result["status"] == "registered"
        assert result["agent_id"] == "agent-01"
        assert "identity_secret" in result  # 自动生成的私钥
        assert "verification_key_b64" in result  # 对应的公钥

    def test_register_with_existing_key(self, agent_registry: AgentRegistry):
        """注册时可以指定已有的 Ed25519 公钥。"""
        pub_key, _ = generate_key_pair()
        result = agent_registry.register("agent-02", verification_key_b64=pub_key)
        assert result["status"] == "registered"
        assert result["verification_key_b64"] == pub_key

    def test_ed25519_sign_and_verify(self):
        """Ed25519 签名生成和验证功能正常。"""
        pub_key, priv_key = generate_key_pair()
        sig = sign_challenge("agent-01", priv_key)
        assert verify_signature("agent-01", sig, pub_key) is True
        assert verify_signature("wrong-agent", sig, pub_key) is False

    def test_heartbeat_with_signature(self, agent_registry: AgentRegistry):
        """使用 Ed25519 签名完成心跳。"""
        result = agent_registry.register("agent-03")
        priv_key = result["identity_secret"]
        sig = sign_challenge("agent-03", priv_key)
        hb = agent_registry.heartbeat("agent-03", signature_b64=sig)
        assert hb["status"] == "renewed"
        assert hb["agent_id"] == "agent-03"
        assert "expires_at" in hb

    def test_heartbeat_with_wrong_signature_fails(self, agent_registry: AgentRegistry):
        """错误签名的心跳被拒绝。"""
        agent_registry.register("agent-04")
        # 使用错误的私钥签名
        wrong_priv = generate_key_pair()[1]
        sig = sign_challenge("agent-04", wrong_priv)
        hb = agent_registry.heartbeat("agent-04", signature_b64=sig)
        assert hb["status"] == "error"
        assert "signature" in hb["error"].lower()

    def test_heartbeat_without_signature_required(self, agent_registry: AgentRegistry):
        """有 verification_key 但没有提供签名的心跳失败。"""
        agent_registry.register("agent-05")
        hb = agent_registry.heartbeat("agent-05")
        assert hb["status"] == "error"
        assert "Ed25519 signature required" in hb["error"]

    def test_heartbeat_unregistered_agent(self, agent_registry: AgentRegistry):
        """未注册的 agent 发送心跳失败。"""
        hb = agent_registry.heartbeat("ghost")
        assert hb["status"] == "error"
        assert "not registered" in hb["error"]

    def test_list_agents_returns_all(self, agent_registry: AgentRegistry):
        """list_agents() 返回所有注册的 agent。"""
        agent_registry.register("agent-a")
        agent_registry.register("agent-b")
        agents = agent_registry.list_agents()
        assert len(agents) == 2
        ids = {a["agent_id"] for a in agents}
        assert ids == {"agent-a", "agent-b"}

    def test_get_status(self, agent_registry: AgentRegistry):
        """get_status() 返回 agent 的状态。"""
        agent_registry.register("agent-06")
        status = agent_registry.get_status("agent-06")
        assert status == "active"

    def test_get_status_nonexistent(self, agent_registry: AgentRegistry):
        """不存在的 agent 返回 None。"""
        assert agent_registry.get_status("ghost") is None

    def test_zombie_detection(self, agent_registry: AgentRegistry):
        """reap_zombies() 检测过期 agent。"""
        agent_registry.register("agent-07")
        # 设置一个极小的僵尸阈值
        import time as _time

        _time.sleep(0.01)  # 确保至少过了 0.01s
        zombies = agent_registry.reap_zombies(force_zombie_age=0.001)
        assert "agent-07" in zombies

    def test_identity_verification(self, agent_registry: AgentRegistry):
        """verify_agent_identity() 验证 agent 身份。"""
        result = agent_registry.register("agent-08")
        priv_key = result["identity_secret"]
        sig = sign_challenge("agent-08", priv_key)
        verification = agent_registry.verify_agent_identity("agent-08", sig)
        assert verification["valid"] is True

    def test_identity_verification_fails_for_wrong_agent(self, agent_registry: AgentRegistry):
        """使用其他 agent 的签名验证失败。"""
        r1 = agent_registry.register("agent-a")
        agent_registry.register("agent-b")
        sig = sign_challenge("agent-a", r1["identity_secret"])
        verification = agent_registry.verify_agent_identity("agent-b", sig)
        assert verification["valid"] is False

    def test_max_agents_per_key_limit(self, agent_registry: AgentRegistry):
        """超过 identity_key 限额时注册失败。"""
        from agora.agent_registry import MAX_AGENTS_PER_KEY

        for i in range(MAX_AGENTS_PER_KEY):
            result = agent_registry.register(f"agent-{i}", metadata={"identity_key": "team-a"})
            assert result["status"] == "registered"

        # 第 6 个应该失败
        result = agent_registry.register("agent-overflow", metadata={"identity_key": "team-a"})
        assert result["status"] == "error"
        assert "Max agents per identity" in result["error"]

    def test_restore_from_backup(self, tmp_path: Path):
        """从 backup 缓存恢复。"""
        from agora.agent_registry import AgentRegistry

        cache = str(tmp_path / "primary.json")
        backup = str(tmp_path / "backup.json")

        r1 = AgentRegistry(cache_file=cache, backup_cache_file=backup)
        r1.register("agent-backup")
        del r1

        # 清空主缓存，仅保留 backup
        Path(cache).unlink()

        r2 = AgentRegistry(cache_file=cache, backup_cache_file=backup)
        assert r2.restore_from_backup() == 0
        assert r2.get_status("agent-backup") == "active"


# ═══════════════════════════════════════════════════════════════
# Phase 8 — gRPC 健康检查
# ═══════════════════════════════════════════════════════════════


class TestGrpcHealthEndToEnd:
    """验证 gRPC 健康检查的完整流程。"""

    def test_grpc_healthy_fallback(self, tmp_path: Path):
        """gRPC 服务 TCP 连接失败时回退到 healthy 标志。"""
        r = _new_registry(tmp_path)
        svc = _make_service("grpc-svc", protocol="grpc", mcp_endpoint="http://192.0.2.1:50051")
        r.register(svc)
        assert r.grpc_health_check("grpc-svc") is True

    def test_grpc_unhealthy_fallback(self, tmp_path: Path):
        """gRPC 服务标记为 unhealthy 时返回 False。"""
        r = _new_registry(tmp_path)
        svc = _make_service("grpc-svc", protocol="grpc", mcp_endpoint="http://192.0.2.1:50051")
        r.register(svc)
        svc.healthy = False
        assert r.grpc_health_check("grpc-svc") is False

    def test_non_grpc_returns_false(self, tmp_path: Path):
        """非 gRPC 协议的服务返回 False。"""
        r = _new_registry(tmp_path)
        r.register(_make_service("rest-svc", protocol="rest"))
        assert r.grpc_health_check("rest-svc") is False

    def test_nonexistent_returns_false(self, tmp_path: Path):
        """不存在的服务返回 False。"""
        r = _new_registry(tmp_path)
        assert r.grpc_health_check("ghost") is False

    def test_grpc_no_endpoint_returns_false(self, tmp_path: Path):
        """gRPC 服务没有 mcp_endpoint 时返回 False。"""
        r = _new_registry(tmp_path)
        r.register(_make_service("no-ep", protocol="grpc", mcp_endpoint=""))
        assert r.grpc_health_check("no-ep") is False


# ═══════════════════════════════════════════════════════════════
# Phase 9 — URL 安全校验
# ═══════════════════════════════════════════════════════════════


class TestUrlSafety:
    """验证 is_safe_url 对内部地址的防护。"""

    def test_localhost_is_safe(self):
        """localhost 是安全的（本地开发）。"""
        assert is_safe_url("http://localhost:8765/health") is True

    def test_127_0_0_1_is_safe(self):
        """127.0.0.1 是安全的。"""
        assert is_safe_url("http://127.0.0.1:3000/health") is True

    def test_private_ip_is_blocked(self):
        """私有 IP 地址被拦截。"""
        assert is_safe_url("http://10.0.0.1:8765/health") is False

    def test_192_168_is_blocked(self):
        """192.168.x.x 被拦截。"""
        assert is_safe_url("http://192.168.1.1/health") is False

    def test_public_ip_is_safe(self):
        """公网 IP 通过校验（TEST-NET）。"""
        assert is_safe_url("http://192.0.2.1:8765/health") is True

    def test_register_blocks_unsafe_health_endpoint(self, tmp_path: Path):
        """注册包含不安全 health_endpoint 的服务时抛出 ValueError。"""
        r = _new_registry(tmp_path)
        with pytest.raises(ValueError, match="Health endpoint URL blocked"):
            r.register(_make_service("bad", health_endpoint="http://10.0.0.1/health"))

    def test_register_blocks_unsafe_mcp_endpoint(self, tmp_path: Path):
        """注册包含不安全 mcp_endpoint 的服务时抛出 ValueError。"""
        r = _new_registry(tmp_path)
        with pytest.raises(ValueError, match="Endpoint URL blocked"):
            r.register(_make_service("bad", mcp_endpoint="http://10.0.0.1:8765"))


# ═══════════════════════════════════════════════════════════════
# Phase 10 — MCP Bootstrap 配置管理
# ═══════════════════════════════════════════════════════════════


class TestMcpBootstrapConfig:
    """验证 MCP bootstrap 的配置生成、加载和状态查询。"""

    def test_known_services_contains_kairon_services(self):
        """KNOWN_SERVICES 包含所有核心 kairon MCP 服务。"""
        kairon_services = {k for k, v in KNOWN_SERVICES.items() if v.get("source") == "kairon"}
        expected = {
            "kronos",
            "iris",
            "eidos",
            "sophia",
            "minerva",
            "agent-runtime",
            "codeanalyze",
            "kos",
        }
        for name in expected:
            assert name in kairon_services, f"Missing kairon service: {name}"

    def test_default_config_contains_all_services(self, monkeypatch, tmp_path: Path):
        """_default_config() 包含所有 KNOWN_SERVICES。"""
        # Mock workspace 以通过 kairon 服务可用性检查
        monkeypatch.setattr("agora.mcp.mcp_bootstrap._find_workspace_root", lambda: None)
        # Mock _check_tool_available 返回 False 使所有服务为不可用
        monkeypatch.setattr("agora.mcp.mcp_bootstrap._check_tool_available", lambda name, info: False)
        config = _default_config(workspace=None)
        assert "services" in config
        assert len(config["services"]) == len(KNOWN_SERVICES)

    def test_disabled_services_not_in_enabled_list(self):
        """_build_enabled_services() 过滤掉 disabled 服务。"""
        from agora.mcp.mcp_bootstrap import _build_enabled_services

        config_services = [
            {"name": "enabled-svc", "command": "echo", "args": [], "enabled": True},
            {"name": "disabled-svc", "command": "echo", "args": [], "enabled": False},
        ]
        enabled = _build_enabled_services(config_services)
        names = [s["name"] for s in enabled]
        assert "enabled-svc" in names
        assert "disabled-svc" not in names

    def test_config_load_generates_when_missing(self, monkeypatch, tmp_path: Path):
        """配置文件不存在时自动生成。"""
        agora_dir = tmp_path / ".agora"
        monkeypatch.setenv("AGORA_DATA_DIR", str(agora_dir))
        # 强制重新导入以使用新的 env
        import importlib

        from agora.mcp import mcp_bootstrap

        importlib.reload(mcp_bootstrap)

        monkeypatch.setattr("agora.mcp.mcp_bootstrap._find_workspace_root", lambda: None)
        monkeypatch.setattr("agora.mcp.mcp_bootstrap._check_tool_available", lambda name, info: False)

        services, config_path = mcp_bootstrap.load_or_generate_config()
        assert config_path.exists()
        assert len(services) == len(KNOWN_SERVICES)

    def test_reload_config_regenerates(self, monkeypatch, tmp_path: Path):
        """reload_config() 删除旧配置并重新生成。"""
        agora_dir = tmp_path / ".agora"
        monkeypatch.setenv("AGORA_DATA_DIR", str(agora_dir))
        import importlib

        from agora.mcp import mcp_bootstrap

        importlib.reload(mcp_bootstrap)
        monkeypatch.setattr("agora.mcp.mcp_bootstrap._find_workspace_root", lambda: None)
        monkeypatch.setattr("agora.mcp.mcp_bootstrap._check_tool_available", lambda name, info: False)

        services = mcp_bootstrap.reload_config()
        assert len(services) == len(KNOWN_SERVICES)

    def test_config_status_structure(self, monkeypatch, tmp_path: Path):
        """get_config_status() 返回完整的配置状态。"""
        agora_dir = tmp_path / ".agora"
        monkeypatch.setenv("AGORA_DATA_DIR", str(agora_dir))
        import importlib

        from agora.mcp import mcp_bootstrap

        importlib.reload(mcp_bootstrap)
        monkeypatch.setattr("agora.mcp.mcp_bootstrap._find_workspace_root", lambda: None)
        monkeypatch.setattr("agora.mcp.mcp_bootstrap._check_tool_available", lambda name, info: False)

        status = mcp_bootstrap.get_config_status()
        assert "config_path" in status
        assert "config_exists" in status
        assert "workspace" in status
        assert "uv_available" in status
        assert "services" in status
        assert len(status["services"]) == len(KNOWN_SERVICES)


# ═══════════════════════════════════════════════════════════════
# Phase 11 — 服务注册边界条件
# ═══════════════════════════════════════════════════════════════


class TestServiceEdgeCases:
    """验证服务注册的边界条件和异常场景。"""

    def test_register_duplicate_overwrites(self, tmp_path: Path):
        """重复注册同名服务时覆盖旧记录。"""
        r = _new_registry(tmp_path)
        r.register(_make_service("svc", port=1000))
        r.register(_make_service("svc", port=2000))
        assert r.get("svc").port == 2000
        assert len(r.list_all()) == 1

    def test_service_with_empty_name(self, tmp_path: Path):
        """空名称的服务可以注册（但不推荐）。"""
        r = _new_registry(tmp_path)
        r.register(_make_service(""))
        assert r.get("") is not None

    def test_service_with_instances(self, tmp_path: Path):
        """服务可以包含多实例信息。"""
        r = _new_registry(tmp_path)
        instances = [{"host": "node1", "port": 9001}, {"host": "node2", "port": 9002}]
        r.register(_make_service("cluster", instances=instances))
        svc = r.get("cluster")
        assert len(svc.instances) == 2
        assert svc.instances[0]["host"] == "node1"

    def test_service_tags_round_trip(self, tmp_path: Path):
        """标签列表通过序列化/反序列化保持不变。"""
        r = _new_registry(tmp_path)
        tags = ["production", "critical", "us-east-1"]
        r.register(_make_service("tagged", tags=tags))

        # 重新加载验证持久化
        path = tmp_path / "test-services.json"
        r2 = ServiceRegistry(storage_path=str(path))
        svc = r2.get("tagged")
        assert sorted(svc.tags) == sorted(tags)

    def test_register_with_heartbeat_then_mark_failure(self, tmp_path: Path):
        """心跳后将服务标记为失败，验证 hearteart 状态被覆盖。"""
        r = _new_registry(tmp_path)
        r.register(_make_service("svc"))
        r.register_heartbeat("svc", now=100.0)
        assert r.get("svc").healthy is True

        r.mark_failure("svc")
        r.mark_failure("svc")
        r.mark_failure("svc")
        assert r.get("svc").healthy is False
        # 熔断打开，但 last_health_check 仍然保留
        assert r.get("svc").last_health_check == 100.0


# ═══════════════════════════════════════════════════════════════
# Phase 12 — parse 工具函数
# ═══════════════════════════════════════════════════════════════


class TestParseHelpers:
    """验证 parse_tags 和 parse_protocol_config 工具函数。"""

    def test_parse_tags_single(self):
        assert parse_tags("research") == ["research"]

    def test_parse_tags_multiple(self):
        assert parse_tags("research, search,knowledge") == ["research", "search", "knowledge"]

    def test_parse_tags_empty(self):
        assert parse_tags("") == []

    def test_parse_tags_whitespace_only(self):
        assert parse_tags("  ,  , ") == []

    def test_parse_protocol_config_dict(self):
        cfg, err = parse_protocol_config({"key": "val"})
        assert cfg == {"key": "val"}
        assert err is None

    def test_parse_protocol_config_valid_json(self):
        cfg, err = parse_protocol_config('{"method":"GET"}')
        assert cfg == {"method": "GET"}
        assert err is None

    def test_parse_protocol_config_invalid_json(self):
        cfg, err = parse_protocol_config("not json")
        assert cfg == {}
        assert err is not None

    def test_parse_protocol_config_empty(self):
        cfg, err = parse_protocol_config("{}")
        assert cfg == {}
        assert err is None
