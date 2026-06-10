"""Tests for Agent Registry — Ed25519 签名验证 + Backup Registry."""

import json
import os
import tempfile
import time
from pathlib import Path

import pytest
from agora.agent_registry import (
    MAX_AGENTS_PER_KEY,
    AgentInfo,
    AgentRegistry,
    generate_key_pair,
    sign_challenge,
    verify_signature,
)

# ── Fixtures ──────────────────────────────────────────────


@pytest.fixture
def registry():
    """返回一个使用临时缓存的干净注册表。"""
    tmpdir = tempfile.mkdtemp()
    cache = str(Path(tmpdir) / "registry.json")
    backup = str(Path(tmpdir) / "registry-backup.json")
    r = AgentRegistry(cache_file=cache, backup_cache_file=backup)
    yield r
    r.clear()


# ── Ed25519 辅助函数 ─────────────────────────────────────


class TestGenerateKeyPair:
    def test_returns_two_strings(self):
        vk, sk = generate_key_pair()
        assert isinstance(vk, str)
        assert isinstance(sk, str)
        assert len(vk) > 0
        assert len(sk) > 0

    def test_key_pair_is_valid(self):
        vk, sk = generate_key_pair()
        sig = sign_challenge("test-agent", sk)
        assert verify_signature("test-agent", sig, vk)

    def test_different_calls_generate_different_keys(self):
        vk1, sk1 = generate_key_pair()
        vk2, sk2 = generate_key_pair()
        assert vk1 != vk2
        assert sk1 != sk2

    def test_public_key_is_32_bytes_base64(self):
        vk, _ = generate_key_pair()
        raw = __import__("base64").b64decode(vk)
        assert len(raw) == 32

    def test_private_key_is_64_bytes_raw(self):
        _, sk = generate_key_pair()
        raw = __import__("base64").b64decode(sk)
        assert len(raw) == 32


class TestSignChallenge:
    def test_returns_base64_string(self):
        _, sk = generate_key_pair()
        sig = sign_challenge("agent-1", sk)
        assert isinstance(sig, str)
        assert len(sig) > 0

    def test_different_agents_produce_different_signatures(self):
        _, sk1 = generate_key_pair()
        _, sk2 = generate_key_pair()
        sig1 = sign_challenge("agent-a", sk1)
        sig2 = sign_challenge("agent-b", sk2)
        assert sig1 != sig2


class TestVerifySignature:
    def test_valid_signature(self):
        vk, sk = generate_key_pair()
        sig = sign_challenge("test", sk)
        assert verify_signature("test", sig, vk)

    def test_invalid_agent_id(self):
        vk, sk = generate_key_pair()
        sig = sign_challenge("real-agent", sk)
        assert not verify_signature("fake-agent", sig, vk)

    def test_wrong_key(self):
        vk1, sk1 = generate_key_pair()
        vk2, _ = generate_key_pair()
        sig = sign_challenge("test", sk1)
        assert not verify_signature("test", sig, vk2)

    def test_tampered_signature(self):
        vk, sk = generate_key_pair()
        sig = sign_challenge("test", sk)
        raw = __import__("base64").b64decode(sig)
        tampered = bytearray(raw)
        tampered[0] ^= 0xFF
        assert not verify_signature("test", __import__("base64").b64encode(bytes(tampered)).decode(), vk)

    def test_time_window_flexibility(self):
        vk, sk = generate_key_pair()
        sig = sign_challenge("test", sk)
        assert verify_signature("test", sig, vk)

    def test_empty_signature(self):
        vk, _ = generate_key_pair()
        assert not verify_signature("test", "", vk)

    def test_invalid_base64_signature(self):
        vk, _ = generate_key_pair()
        assert not verify_signature("test", "not-base64!!!", vk)


# ── AgentInfo ─────────────────────────────────────────────


class TestAgentInfo:
    def test_default_status_is_active(self):
        info = AgentInfo("agent-1")
        assert info.status == "active"

    def test_age_seconds_increases(self):
        info = AgentInfo("agent-1")
        t1 = info.age_seconds
        time.sleep(0.01)
        t2 = info.age_seconds
        assert t2 > t1

    def test_age_seconds_is_non_negative(self):
        info = AgentInfo("agent-1")
        assert info.age_seconds >= 0

    def test_to_dict_contains_verification_key(self):
        info = AgentInfo("agent-1", verification_key_b64="abc123")
        d = info.to_dict()
        assert d["verification_key_b64"] == "abc123"

    def test_to_dict_omits_empty_verification_key(self):
        info = AgentInfo("agent-1")
        d = info.to_dict()
        assert "verification_key_b64" not in d

    def test_to_dict_omits_empty_identity_token(self):
        info = AgentInfo("agent-1")
        d = info.to_dict()
        assert "identity_token" not in d

    def test_to_dict_includes_identity_token(self):
        info = AgentInfo("agent-1", identity_token="tok_123")  # noqa: S106
        d = info.to_dict()
        assert d["identity_token"] == "tok_123"  # noqa: S105

    def test_round_trip_to_from_dict(self):
        info = AgentInfo(
            "agent-1",
            verification_key_b64="vk123",
            identity_token="tok_abc",  # noqa: S106
            capabilities=["read", "write"],
            metadata={"version": "1.0"},
        )
        d = info.to_dict()
        restored = AgentInfo.from_dict(d)
        assert restored.agent_id == "agent-1"
        assert restored.verification_key_b64 == "vk123"
        assert restored.identity_token == "tok_abc"  # noqa: S105
        assert restored.capabilities == ["read", "write"]
        assert restored.metadata == {"version": "1.0"}

    def test_update_status_active(self):
        info = AgentInfo("agent-1")
        info.last_heartbeat = time.time()
        assert info.update_status() == "active"

    def test_update_status_stale(self):
        info = AgentInfo("agent-1")
        info.last_heartbeat = time.time() - 300
        assert info.update_status() == "stale"

    def test_update_status_zombie(self):
        info = AgentInfo("agent-1")
        info.last_heartbeat = time.time() - 7200
        assert info.update_status() == "zombie"


# ── 注册 ─────────────────────────────────────────────────


class TestRegister:
    def test_register_returns_success(self, registry):
        result = registry.register("agent-1")
        assert result["status"] == "registered"
        assert result["agent_id"] == "agent-1"

    def test_register_generates_key_pair(self, registry):
        result = registry.register("agent-1")
        assert "identity_secret" in result
        assert "verification_key_b64" in result

    def test_register_with_verification_key(self, registry):
        vk, sk = generate_key_pair()
        result = registry.register("agent-1", verification_key_b64=vk)
        assert result["status"] == "registered"
        assert result["verification_key_b64"] == vk
        assert "identity_secret" not in result

    def test_register_with_custom_identity_token(self, registry):
        result = registry.register("agent-1", identity_token="custom-token")  # noqa: S106
        assert result["status"] == "registered"

    def test_register_with_capabilities(self, registry):
        result = registry.register("agent-1", capabilities=["read", "write", "research"])
        assert result["status"] == "registered"

    def test_register_appears_in_list(self, registry):
        registry.register("agent-1")
        agents = registry.list_agents()
        assert len(agents) == 1
        assert agents[0]["agent_id"] == "agent-1"

    def test_register_multiple_agents(self, registry):
        registry.register("agent-1")
        registry.register("agent-2")
        assert len(registry.list_agents()) == 2

    def test_register_exceeds_max_per_key(self, registry):
        for i in range(MAX_AGENTS_PER_KEY):
            registry.register(f"agent-{i}", metadata={"identity_key": "key1"})
        result = registry.register("extra-agent", metadata={"identity_key": "key1"})
        assert result["status"] == "error"
        assert "exceeded" in result["error"]

    def test_register_different_keys_not_affected(self, registry):
        for i in range(MAX_AGENTS_PER_KEY):
            registry.register(f"agent-{i}", metadata={"identity_key": "key-a"})
        result = registry.register("other-agent", metadata={"identity_key": "key-b"})
        assert result["status"] == "registered"

    def test_register_with_metadata(self, registry):
        registry.register("agent-1", metadata={"version": "2.0", "env": "prod"})
        agents = registry.list_agents()
        assert agents[0]["metadata"]["version"] == "2.0"
        assert agents[0]["metadata"]["env"] == "prod"


# ── Heartbeat ────────────────────────────────────────────


class TestHeartbeat:
    def test_heartbeat_renews_status(self, registry):
        registry.register("agent-1", identity_token="tok")  # noqa: S106
        result = registry.heartbeat("agent-1")
        assert result["status"] == "renewed"
        assert "expires_at" in result

    def test_heartbeat_unregistered_agent(self, registry):
        result = registry.heartbeat("ghost")
        assert result["status"] == "error"

    def test_heartbeat_with_valid_signature(self, registry):
        result = registry.register("agent-1")
        sk = result["identity_secret"]
        sig = sign_challenge("agent-1", sk)
        hb_result = registry.heartbeat("agent-1", signature_b64=sig)
        assert hb_result["status"] == "renewed"

    def test_heartbeat_with_invalid_signature(self, registry):
        registry.register("agent-1")
        _, wrong_sk = generate_key_pair()
        bad_sig = sign_challenge("agent-1", wrong_sk)
        hb_result = registry.heartbeat("agent-1", signature_b64=bad_sig)
        assert hb_result["status"] == "error"
        assert "signature" in hb_result["error"]

    def test_heartbeat_with_wrong_agent_signature(self, registry):
        r1 = registry.register("agent-1")
        registry.register("agent-2", identity_token="tok2")  # noqa: S106
        sig = sign_challenge("agent-2", r1["identity_secret"])
        hb_result = registry.heartbeat("agent-1", signature_b64=sig)
        assert hb_result["status"] == "error"

    def test_heartbeat_without_signature_when_key_exists(self, registry):
        registry.register("agent-1")
        result = registry.heartbeat("agent-1")
        assert result["status"] == "error"
        assert "signature required" in result["error"]

    def test_heartbeat_with_identity_token(self, registry):
        registry.register("agent-1", identity_token="my-token")  # noqa: S106
        result = registry.heartbeat("agent-1", identity_token="my-token")  # noqa: S106
        assert result["status"] == "renewed"

    def test_heartbeat_with_wrong_identity_token(self, registry):
        registry.register("agent-1", identity_token="correct-token")  # noqa: S106
        result = registry.heartbeat("agent-1", identity_token="wrong-token")  # noqa: S106
        assert result["status"] == "error"
        assert "mismatch" in result["error"]

    def test_heartbeat_updates_last_heartbeat(self, registry):
        registry.register("agent-1", identity_token="tok")  # noqa: S106
        t1 = registry._agents["agent-1"].last_heartbeat
        time.sleep(0.01)
        registry.heartbeat("agent-1", identity_token="tok")  # noqa: S106
        t2 = registry._agents["agent-1"].last_heartbeat
        assert t2 > t1

    def test_heartbeat_resets_to_active(self, registry):
        registry.register("agent-1", identity_token="tok")  # noqa: S106
        registry._agents["agent-1"].status = "stale"
        registry.heartbeat("agent-1", identity_token="tok")  # noqa: S106
        assert registry._agents["agent-1"].status == "active"


# ── 身份验证 ─────────────────────────────────────────────


class TestVerifyAgentIdentity:
    def test_verify_identity_with_valid_signature(self, registry):
        reg = registry.register("agent-1")
        sig = sign_challenge("agent-1", reg["identity_secret"])
        result = registry.verify_agent_identity("agent-1", sig)
        assert result["valid"] is True

    def test_verify_identity_with_invalid_signature(self, registry):
        registry.register("agent-1")
        _, wrong_sk = generate_key_pair()
        bad_sig = sign_challenge("agent-1", wrong_sk)
        result = registry.verify_agent_identity("agent-1", bad_sig)
        assert result["valid"] is False

    def test_verify_identity_unknown_agent(self, registry):
        result = registry.verify_agent_identity("ghost", "some-sig")
        assert result["valid"] is False
        assert result["reason"] == "agent_not_found"

    def test_verify_identity_no_key(self, registry):
        registry.register("agent-1", identity_token="tok")  # noqa: S106
        result = registry.verify_agent_identity("agent-1", "some-sig")
        assert result["valid"] is False
        assert result["reason"] == "no_verification_key"


# ── 查询 ─────────────────────────────────────────────────


class TestQuery:
    def test_get_status_active(self, registry):
        registry.register("agent-1")
        assert registry.get_status("agent-1") == "active"

    def test_get_status_unknown(self, registry):
        assert registry.get_status("ghost") is None

    def test_get_status_stale(self, registry):
        registry.register("agent-1", identity_token="tok")  # noqa: S106
        registry._agents["agent-1"].last_heartbeat = time.time() - 300
        assert registry.get_status("agent-1") == "stale"

    def test_list_agents_with_status_filter(self, registry):
        registry.register("agent-1", identity_token="tok")  # noqa: S106
        registry.register("agent-2", identity_token="tok")  # noqa: S106
        registry._agents["agent-2"].last_heartbeat = time.time() - 7200
        active = registry.list_agents(status_filter="active")
        registry.list_agents(status_filter="stale")
        assert len(active) == 1
        assert active[0]["agent_id"] == "agent-1"

    def test_list_agents_no_filter(self, registry):
        registry.register("agent-1")
        registry.register("agent-2")
        assert len(registry.list_agents()) == 2

    def test_get_active_count(self, registry):
        registry.register("agent-1", identity_token="tok")  # noqa: S106
        registry.register("agent-2", identity_token="tok")  # noqa: S106
        registry._agents["agent-2"].last_heartbeat = time.time() - 7200
        assert registry.get_active_count() == 1
        assert registry.get_zombie_count() == 1


# ── 僵尸检测 ────────────────────────────────────────────


class TestReapZombies:
    def test_reap_detects_zombies(self, registry):
        registry.register("agent-1", identity_token="tok")  # noqa: S106
        registry._agents["agent-1"].last_heartbeat = time.time() - 7200
        zombies = registry.reap_zombies()
        assert "agent-1" in zombies

    def test_reap_returns_empty_for_active(self, registry):
        registry.register("agent-1", identity_token="tok")  # noqa: S106
        zombies = registry.reap_zombies()
        assert len(zombies) == 0

    def test_reap_with_custom_threshold(self, registry):
        registry.register("agent-1", identity_token="tok")  # noqa: S106
        registry._agents["agent-1"].last_heartbeat = time.time() - 180
        zombies = registry.reap_zombies(force_zombie_age=120)
        assert "agent-1" in zombies

    def test_reap_multiple_zombies(self, registry):
        for i in range(3):
            registry.register(f"zombie-{i}", identity_token="tok")  # noqa: S106
            registry._agents[f"zombie-{i}"].last_heartbeat = time.time() - 7200
        registry.register("live-agent", identity_token="tok")  # noqa: S106
        zombies = registry.reap_zombies()
        assert len(zombies) == 3
        assert "live-agent" not in zombies


# ── Backup Registry ──────────────────────────────────────


class TestBackupRegistry:
    def test_backup_available_after_registration(self, registry):
        registry.register("agent-1")
        assert registry.is_backup_available()

    def test_backup_not_available_without_file(self):
        r = AgentRegistry(backup_cache_file=None)
        assert not r.is_backup_available()

    def test_restore_from_backup(self, registry):
        registry.register("agent-1")
        registry.register("agent-2")
        backup_file = registry._backup_cache_file
        cache_file = registry._cache_file

        r2 = AgentRegistry(cache_file=cache_file, backup_cache_file=backup_file)
        r2.clear()
        count = r2.restore_from_backup()
        assert count == 2
        assert r2.get_status("agent-1") is not None
        assert r2.get_status("agent-2") is not None

    def test_restore_from_backup_does_not_overwrite_existing(self, registry):
        registry.register("agent-1")
        orig_agents = len(registry._agents)
        count = registry.restore_from_backup()
        assert count == 0
        assert len(registry._agents) == orig_agents

    def test_restore_no_backup_file(self):
        r = AgentRegistry(backup_cache_file="/tmp/nonexistent-backup.json")
        count = r.restore_from_backup()
        assert count == 0

    def test_backup_file_contains_same_data(self, registry):
        registry.register("agent-1")
        registry.register("agent-2")
        with open(registry._backup_cache_file) as f:
            data = json.load(f)
        assert "agent-1" in data
        assert "agent-2" in data

    def test_cache_loading_falls_back_to_backup(self, registry):
        registry.register("agent-1")
        with open(registry._cache_file, "w") as f:
            f.write("corrupted data")
        r2 = AgentRegistry(cache_file=registry._cache_file, backup_cache_file=registry._backup_cache_file)
        assert len(r2.list_agents()) == 1
        assert r2.get_status("agent-1") is not None


# ── 缓存持久化 ──────────────────────────────────────────


class TestCachePersistence:
    def test_registry_survives_recreation(self, registry):
        registry.register("agent-1", identity_token="tok")  # noqa: S106
        cache = registry._cache_file
        backup = registry._backup_cache_file

        r2 = AgentRegistry(cache_file=cache, backup_cache_file=backup)
        assert r2.get_status("agent-1") is not None
        agents = r2.list_agents()
        assert len(agents) == 1

    def test_cache_includes_verification_key(self, registry):
        result = registry.register("agent-1")
        vk = result["verification_key_b64"]
        cache = registry._cache_file
        backup = registry._backup_cache_file

        r2 = AgentRegistry(cache_file=cache, backup_cache_file=backup)
        loaded_vk = r2._agents["agent-1"].verification_key_b64
        assert loaded_vk == vk

    def test_clear_removes_all(self, registry):
        registry.register("agent-1")
        registry.clear()
        assert len(registry.list_agents()) == 0


# ── 集成测试 ────────────────────────────────────────────


class TestIntegration:
    def test_full_lifecycle_with_ed25519(self, registry):
        r = registry

        reg = r.register("worker-1", capabilities=["research", "index"])
        assert reg["status"] == "registered"
        sk = reg["identity_secret"]
        vk = reg["verification_key_b64"]
        assert vk
        assert sk

        sig = sign_challenge("worker-1", sk)
        assert verify_signature("worker-1", sig, vk)

        hb = r.heartbeat("worker-1", signature_b64=sig)
        assert hb["status"] == "renewed"

        ident = r.verify_agent_identity("worker-1", sig)
        assert ident["valid"] is True

        assert r.get_status("worker-1") == "active"
        assert r.is_backup_available()

    def test_multiple_agents_with_different_auth_methods(self, registry):
        r = registry

        reg = r.register("ed25519-agent")
        sk = reg["identity_secret"]
        sig = sign_challenge("ed25519-agent", sk)

        r.register("token-agent", identity_token="my-token")  # noqa: S106

        hb1 = r.heartbeat("ed25519-agent", signature_b64=sig)
        hb2 = r.heartbeat("token-agent", identity_token="my-token")  # noqa: S106

        assert hb1["status"] == "renewed"
        assert hb2["status"] == "renewed"
        assert r.get_status("ed25519-agent") == "active"
        assert r.get_status("token-agent") == "active"

    def test_backup_failover_scenario(self, registry):
        r = registry
        r.register("agent-1")
        r.register("agent-2", identity_token="tok2")  # noqa: S106

        os.remove(r._cache_file)
        assert not os.path.exists(r._cache_file)
        assert r.is_backup_available()

        r2 = AgentRegistry(cache_file=r._cache_file, backup_cache_file=r._backup_cache_file)
        assert len(r2.list_agents()) == 2

    def test_re_regeneration_gets_new_key(self, registry):
        r = registry
        r1 = r.register("agent-1")
        r.clear()
        r2 = r.register("agent-1")
        assert r1["verification_key_b64"] != r2["verification_key_b64"]
        assert r1["identity_secret"] != r2["identity_secret"]

    def test_token_agent_heartbeat_works_without_signature(self, registry):
        """Token agent 不需要 Ed25519 签名即可心跳。"""
        registry.register("agent-1", identity_token="tok")  # noqa: S106
        result = registry.heartbeat("agent-1", identity_token="tok")  # noqa: S106
        assert result["status"] == "renewed"
