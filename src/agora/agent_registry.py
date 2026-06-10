"""Agent Registry Heartbeat — 轻量级心跳注册与过期检测 + Ed25519 签名验证。

提供:
  - Agent 注册 (register) — Ed25519 密钥对自动生成
  - 心跳续期 (heartbeat) — Ed25519 签名验证可选
  - 僵尸检测 (zombie detection)
  - 本地缓存 + Backup Registry 双缓存

用法:
    from agora.agent_registry import AgentRegistry

    registry = AgentRegistry()
    result = await registry.register("agent-01", {"capabilities": ["read", "write"]})
    # result["identity_secret"] 包含 Ed25519 私钥(PEM)，agent 须安全保存

    # 后续心跳需用私钥签名:
    from agora.agent_registry import sign_challenge, verify_signature
    sig = sign_challenge("agent-01", private_key_pem)
    await registry.heartbeat("agent-01", signature_b64=sig)
"""

from __future__ import annotations

import base64
import json
import logging
import os
import time
from pathlib import Path
from threading import Lock

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

_log = logging.getLogger(__name__)

# ── 配置 ──────────────────────────────────────────────────
HEARTBEAT_TTL = int(os.environ.get("AGENT_HEARTBEAT_TTL", "60"))  # 60s
STALE_AFTER = int(os.environ.get("AGENT_STALE_AFTER", "180"))  # 180s = 3 misses
ZOMBIE_AFTER = int(os.environ.get("AGENT_ZOMBIE_AFTER", "3600"))  # 1h
CACHE_FILE = os.environ.get("AGENT_REGISTRY_CACHE", "/tmp/agent-registry-cache.json")
BACKUP_CACHE_FILE = os.environ.get(
    "AGENT_REGISTRY_BACKUP_CACHE", "/tmp/agent-registry-backup.json"
)
MAX_AGENTS_PER_KEY = int(os.environ.get("AGENT_MAX_PER_KEY", "5"))
CHALLENGE_WINDOW = int(
    os.environ.get("AGENT_CHALLENGE_WINDOW", "30")
)  # 30s 签名挑战时间窗口


# ── Ed25519 辅助函数 ─────────────────────────────────────


def generate_key_pair() -> tuple[str, str]:
    """生成 Ed25519 密钥对。

    Returns:
        (verification_key_b64, private_key_pem)
    """
    private_key = Ed25519PrivateKey.generate()
    private_pem = private_key.private_bytes_raw()
    public_key = private_key.public_key()
    public_raw = public_key.public_bytes_raw()
    return base64.b64encode(public_raw).decode(), base64.b64encode(private_pem).decode()


def sign_challenge(agent_id: str, private_key_b64: str) -> str:
    """用 Ed25519 私钥签名 challenge 消息。

    Challenge 消息: f"{agent_id}:{time_window}"
    其中 time_window = int(time.time() / CHALLENGE_WINDOW)

    Returns:
        base64 编码的签名
    """
    time_window = int(time.time() / CHALLENGE_WINDOW)
    message = f"{agent_id}:{time_window}".encode()
    private_raw = base64.b64decode(private_key_b64)
    private_key = Ed25519PrivateKey.from_private_bytes(private_raw)
    signature = private_key.sign(message)
    return base64.b64encode(signature).decode()


def verify_signature(
    agent_id: str, signature_b64: str, verification_key_b64: str
) -> bool:
    """验证 Ed25519 签名。

    检查当前时间窗口及前后各一个窗口（允许时钟偏差 ±30s）。
    """
    try:
        signature = base64.b64decode(signature_b64)
        public_raw = base64.b64decode(verification_key_b64)
        public_key = Ed25519PublicKey.from_public_bytes(public_raw)

        # 检查 3 个时间窗口: 当前, 上一个, 下一个
        current_window = int(time.time() / CHALLENGE_WINDOW)
        for offset in (0, -1, 1):
            message = f"{agent_id}:{current_window + offset}".encode()
            try:
                public_key.verify(signature, message)
                return True
            except Exception:  # noqa: S112
                continue
        return False
    except Exception as e:
        _log.warning("Signature verification failed: %s", e)
        return False


# ── 数据模型 ──────────────────────────────────────────────


class AgentInfo:
    """单个 Agent 的状态信息。"""

    def __init__(
        self,
        agent_id: str,
        verification_key_b64: str = "",
        identity_token: str = "",
        capabilities: list[str] | None = None,
        metadata: dict | None = None,
    ):
        self.agent_id = agent_id
        self.verification_key_b64 = verification_key_b64  # Ed25519 公钥 (base64)
        self.identity_token = identity_token  # 兼容旧版字符串 token
        self.capabilities = capabilities or []
        self.metadata = metadata or {}
        self.last_heartbeat: float = time.time()
        self.registered_at: float = time.time()
        self.status: str = "active"  # active | stale | zombie | dead

    @property
    def age_seconds(self) -> float:
        return time.time() - self.last_heartbeat

    def update_status(self) -> str:
        """根据最后心跳时间更新状态。"""
        age = self.age_seconds
        if age < HEARTBEAT_TTL * 3:  # < 180s
            self.status = "active"
        elif age < ZOMBIE_AFTER:  # < 1h
            self.status = "stale"
        else:
            self.status = "zombie"
        return self.status

    def to_dict(self) -> dict:
        raw = {
            "agent_id": self.agent_id,
            "capabilities": self.capabilities,
            "metadata": self.metadata,
            "last_heartbeat": self.last_heartbeat,
            "registered_at": self.registered_at,
            "status": self.status,
        }
        if self.verification_key_b64:
            raw["verification_key_b64"] = self.verification_key_b64
        if self.identity_token:
            raw["identity_token"] = self.identity_token
        return raw

    @classmethod
    def from_dict(cls, data: dict) -> AgentInfo:
        agent = cls(
            agent_id=data["agent_id"],
            verification_key_b64=data.get("verification_key_b64", ""),
            identity_token=data.get("identity_token", ""),
            capabilities=data.get("capabilities", []),
            metadata=data.get("metadata", {}),
        )
        agent.last_heartbeat = data.get("last_heartbeat", time.time())
        agent.registered_at = data.get("registered_at", time.time())
        agent.status = data.get("status", "active")
        return agent


# ── 注册表 ────────────────────────────────────────────────


class AgentRegistry:
    """Agent 注册表 — 内存存储 + 本地缓存 + 可选 Backup Registry。

    支持 Ed25519 签名验证和旧版 identity_token 字符串比对两种身份验证方式。
    """

    def __init__(
        self,
        cache_file: str = CACHE_FILE,
        backup_cache_file: str | None = BACKUP_CACHE_FILE,
    ):
        self._agents: dict[str, AgentInfo] = {}
        self._lock = Lock()
        self._cache_file = cache_file
        self._backup_cache_file = backup_cache_file
        self._load_cache()

    # ── 注册 ────────────────────────────────────────────

    def register(
        self,
        agent_id: str,
        capabilities: list[str] | None = None,
        identity_token: str = "",
        verification_key_b64: str = "",
        metadata: dict | None = None,
    ) -> dict:
        """注册一个新 Agent。

        如果未提供 verification_key_b64，自动生成 Ed25519 密钥对。
        返回 identity_secret（私钥，base64 编码），agent 须安全保存。

        Args:
            agent_id: Agent 唯一标识
            capabilities: 能力列表
            identity_token: 兼容旧版字符串 token
            verification_key_b64: 已有 Ed25519 公钥（可选）
            metadata: 元数据（支持 identity_key 限额检查）
        """
        with self._lock:
            # 限额检查
            meta = metadata or {}
            identity_key = meta.get("identity_key", "default")
            count = sum(
                1
                for a in self._agents.values()
                if a.metadata.get("identity_key", "default") == identity_key
            )
            if count >= MAX_AGENTS_PER_KEY:
                return {
                    "status": "error",
                    "error": f"Max agents per identity ({MAX_AGENTS_PER_KEY}) exceeded",
                }

            # Ed25519 密钥处理
            identity_secret = ""
            if not verification_key_b64 and not identity_token:
                # 既无公钥也无 token → 自动生成密钥对
                verification_key_b64, identity_secret = generate_key_pair()
            # 如果 agent 自带了公钥或 token，identity_secret 为空

            agent = AgentInfo(
                agent_id=agent_id,
                verification_key_b64=verification_key_b64,
                identity_token=identity_token,
                capabilities=capabilities,
                metadata=meta,
            )
            self._agents[agent_id] = agent
            self._save_cache()
            result = {"status": "registered", "agent_id": agent_id}
            if identity_secret:
                result["identity_secret"] = identity_secret
            if verification_key_b64:
                result["verification_key_b64"] = verification_key_b64
            return result

    # ── Heartbeat ──────────────────────────────────────

    def heartbeat(
        self,
        agent_id: str,
        identity_token: str = "",
        signature_b64: str = "",
    ) -> dict:
        """更新 Agent 心跳时间。

        支持两种验证方式（按优先级）：
        1. Ed25519 签名验证 — 如果 agent 有 verification_key_b64
        2. 旧版 identity_token 字符串比对

        Args:
            agent_id: Agent 标识
            identity_token: 旧版 token（兼容）
            signature_b64: Ed25519 签名的 base64 编码
        """
        with self._lock:
            agent = self._agents.get(agent_id)
            if not agent:
                return {
                    "status": "error",
                    "error": f"Agent '{agent_id}' not registered",
                }

            # Ed25519 签名验证（优先）
            if agent.verification_key_b64 and signature_b64:
                if not verify_signature(
                    agent_id, signature_b64, agent.verification_key_b64
                ):
                    return {
                        "status": "error",
                        "error": "Ed25519 signature verification failed",
                    }
            # 旧版 token 验证
            elif (
                identity_token
                and agent.identity_token
                and identity_token != agent.identity_token
            ):
                return {"status": "error", "error": "Identity token mismatch"}
            # 如果 agent 有 verification_key 但未提供签名 → 拒绝
            elif (
                agent.verification_key_b64 and not signature_b64 and not identity_token
            ):
                return {
                    "status": "error",
                    "error": "Ed25519 signature required for this agent",
                }

            agent.last_heartbeat = time.time()
            agent.status = "active"
            self._save_cache()
            return {
                "status": "renewed",
                "agent_id": agent_id,
                "expires_at": time.time() + HEARTBEAT_TTL,
            }

    def verify_agent_identity(self, agent_id: str, signature_b64: str) -> dict:
        """独立验证 Agent 身份（用于注册外的场景）。

        Returns:
            {"valid": True/False, "reason": "..."}
        """
        agent = self._agents.get(agent_id)
        if not agent:
            return {"valid": False, "reason": "agent_not_found"}
        if not agent.verification_key_b64:
            return {"valid": False, "reason": "no_verification_key"}
        if verify_signature(agent_id, signature_b64, agent.verification_key_b64):
            return {"valid": True, "reason": "signature_verified"}
        return {"valid": False, "reason": "signature_mismatch"}

    # ── 查询 ────────────────────────────────────────────

    def get_status(self, agent_id: str) -> str | None:
        """获取 Agent 状态。"""
        agent = self._agents.get(agent_id)
        if not agent:
            return None
        agent.update_status()
        return agent.status

    def list_agents(self, status_filter: str | None = None) -> list[dict]:
        """列出 Agent，可选按状态过滤。"""
        result = []
        for agent in self._agents.values():
            agent.update_status()
            if status_filter and agent.status != status_filter:
                continue
            result.append(agent.to_dict())
        return result

    def get_active_count(self) -> int:
        """返回活跃 Agent 数量。"""
        return len([a for a in self._agents.values() if a.update_status() == "active"])

    def get_zombie_count(self) -> int:
        """返回僵尸 Agent 数量。"""
        return len([a for a in self._agents.values() if a.update_status() == "zombie"])

    # ── 僵尸检测 ──────────────────────────────────────

    def reap_zombies(self, force_zombie_age: float | None = None) -> list[str]:
        """检测并标记僵尸 Agent。

        Args:
            force_zombie_age: 覆盖 ZOMBIE_AFTER 的阈值（秒），
                              用于测试或手动触发时灵活调整。
        """
        threshold = force_zombie_age or ZOMBIE_AFTER
        zombies = []
        with self._lock:
            for agent_id, agent in self._agents.items():
                if agent.age_seconds >= threshold:
                    agent.status = "zombie"
                    zombies.append(agent_id)
        return zombies

    # ── Backup Registry ────────────────────────────────

    def is_backup_available(self) -> bool:
        """检查 backup registry 缓存是否可用。"""
        if not self._backup_cache_file:
            return False
        try:
            return os.path.exists(self._backup_cache_file)
        except Exception:
            return False

    def restore_from_backup(self) -> int:
        """从 backup cache 恢复注册表。

        Returns:
            恢复的 agent 数量
        """
        if not self._backup_cache_file or not os.path.exists(self._backup_cache_file):
            return 0
        try:
            with open(self._backup_cache_file) as f:
                data = json.load(f)
            count = 0
            with self._lock:
                for agent_id, agent_data in data.items():
                    if agent_id not in self._agents:
                        self._agents[agent_id] = AgentInfo.from_dict(agent_data)
                        count += 1
                self._save_cache()
            return count
        except Exception as e:
            _log.warning("Failed to restore from backup: %s", e)
            return 0

    def _sync_to_backup(self) -> None:
        """同步数据到 backup cache 文件。"""
        if not self._backup_cache_file:
            return
        try:
            data = {
                agent_id: agent.to_dict() for agent_id, agent in self._agents.items()
            }
            Path(self._backup_cache_file).parent.mkdir(parents=True, exist_ok=True)
            with open(self._backup_cache_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            _log.warning("Failed to sync to backup registry: %s", e)

    # ── 缓存 ────────────────────────────────────────────

    def _save_cache(self) -> None:
        """保存到本地缓存 + 同步 backup。"""
        try:
            data = {
                agent_id: agent.to_dict() for agent_id, agent in self._agents.items()
            }
            Path(self._cache_file).parent.mkdir(parents=True, exist_ok=True)
            with open(self._cache_file, "w") as f:
                json.dump(data, f, indent=2)
            # 同步 backup
            self._sync_to_backup()
        except Exception as e:
            _log.warning("Failed to save agent registry cache: %s", e)

    def _load_cache(self) -> None:
        """从本地缓存文件加载。"""
        # 优先从主缓存加载
        loaded = False
        for cache_path in [self._cache_file, self._backup_cache_file]:
            if not cache_path or not os.path.exists(cache_path):
                continue
            try:
                with open(cache_path) as f:
                    data = json.load(f)
                for agent_id, agent_data in data.items():
                    self._agents[agent_id] = AgentInfo.from_dict(agent_data)
                loaded = True
                _log.info("Loaded %d agents from cache: %s", len(data), cache_path)
                break
            except Exception as e:
                _log.warning("Failed to load cache %s: %s", cache_path, e)
        if not loaded:
            _log.info("No cache found, starting with empty registry")

    def clear(self) -> None:
        """清空注册表（测试用）。"""
        self._agents.clear()
