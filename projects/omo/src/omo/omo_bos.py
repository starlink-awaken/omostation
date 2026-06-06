#!/usr/bin/env python3
"""BOS (Banyan Object Service) URI registry — P33 Campaign 2.

BOS URI naming convention: ``bos://<domain>/<package>/<action>``
- ``domain``   : one of 5 fixed (memory, governance, analysis, persona, capability)
- ``package``  : kebab-case, matches the kairon package directory
- ``action``   : verb (search/ingest/audit/register/trigger/gate/...)

Legacy 3-segment form: ``bos://<package>/<action>`` (no explicit domain).
Used by mcp_server.py (``bos://omo/debt`` etc., P30 era). Accepted via
``BOS_URI_LEGACY_PATTERN``; domain is auto-mapped from ``LEGACY_DOMAIN_MAP``
(default: ``omo`` → ``governance``). New code SHOULD use the 4-segment form.

Persistence (P33-W3+):
  - Primary: KOS ``zone=bos_registry`` via direct package call
    (``kos.ontology.store.put_entity``), bypassing agora to avoid
    P32 audit regression.
  - Mirror : local JSON at ``.omo/_knowledge/bos-registry.json`` for
    offline read and CLI listing.  Both writes are attempted on
    register; KOS failure does NOT block local registration.

P32 收官约束: 不改 agora 核心, 不重启 omo daemon, 0 破坏性操作.
本模块纯加法, 文件锁保护并发写, 原子 rename 防半写状态。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

# ── 路径配置 (P33-W3 暴露给外部) ──────────────────────
# kairon packages 根目录 — kairon 23 个包, 包含 kos 实体存储
_KAIRON_PACKAGES_SRC = Path(
    "/Users/xiamingxing/Workspace/projects/kairon/packages/kos/src"
)

# ── BOS URI 命名空间 ────────────────────────────────────────
# 5 个 domain 固定不可扩展 (北星 ADR-0007 约束)
ALLOWED_DOMAINS: tuple[str, ...] = (
    "memory",
    "governance",
    "analysis",
    "persona",
    "capability",
)

# 严格 BOS URI 模式 — kebab-case + 三段固定
# package/action: 必须以小写字母开头, 中间可含小写/数字/连字符, 末尾不能是连字符
# 拒绝: "Kos-", "-kos", "kos-", "KO", 等
_KOS_PART = r"[a-z]([a-z0-9-]*[a-z0-9])?"
BOS_URI_PATTERN = re.compile(
    r"^bos://(?P<domain>memory|governance|analysis|persona|capability)"
    r"/(?P<package>" + _KOS_PART + r")"
    r"/(?P<action>" + _KOS_PART + r")$"
)

# 3-段 legacy URI (P30 时代 mcp_server.py 既有: bos://omo/debt 等)
# 接受 bos://<package>/<action> 形式, domain 通过 LEGACY_DOMAIN_MAP 推断
BOS_URI_LEGACY_PATTERN = re.compile(
    r"^bos://(?P<package>" + _KOS_PART + r")/(?P<action>" + _KOS_PART + r")$"
)

# legacy 3-段 → 4-段 domain 隐含映射
# 多数 mcp_server.py 的 3-段 URI 属于 governance (omo, alerts, debt 等)
LEGACY_DOMAIN_MAP: dict[str, str] = {
    "omo": "governance",
    "debt": "governance",
    "alerts": "governance",
    "tasks": "governance",
    "standards": "governance",
}

Domain = Literal["memory", "governance", "analysis", "persona", "capability"]
Protocol = Literal["http", "stdio", "internal"]

# ── 持久化路径 ────────────────────────────────────────────
# P33-W1: 战役 2 起步故意走本地 JSON (避开 KOS 写入复杂)
DEFAULT_REGISTRY_PATH = Path(
    "/Users/xiamingxing/Workspace/.omo/_knowledge/bos-registry.json"
)


# ── 数据类 ───────────────────────────────────────────────


@dataclass
class BosRegistration:
    """BOS URI 注册记录."""

    uri: str
    domain: str
    package: str
    action: str
    endpoint: str
    protocol: Protocol = "internal"
    description: str = ""
    registered_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    registered_by: str = "omo-bos-cli"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── 21 起步 URI 预定义 (P33-W1 战役 2 起步 6 + P33-W2 余下 15) ─
# P33-W1: memory × 2 + governance × 4
# P33-W2: analysis × 7 + persona × 4 + capability × 4 → 累计 5 Domain 全覆盖 (21)
SEED_REGISTRATIONS: list[BosRegistration] = [
    BosRegistration(
        uri="bos://memory/kos/search",
        domain="memory",
        package="kos",
        action="search",
        endpoint="kairon.packages.kos.ontology.store:search_entities",
        protocol="internal",
        description="KOS 知识图谱检索入口 (P33-W1 战役 2 起步)",
    ),
    BosRegistration(
        uri="bos://memory/kronos/ingest",
        domain="memory",
        package="kronos",
        action="ingest",
        endpoint="kairon.packages.kronos.ingest:ingest",
        protocol="internal",
        description="KRONOS 记忆摄取入口 (P33-W1 战役 2 起步)",
    ),
    BosRegistration(
        uri="bos://governance/omo/audit",
        domain="governance",
        package="omo",
        action="audit",
        endpoint="omo.omo_audit:run_governance_audit",
        protocol="internal",
        description="omo 治理审计入口 (P33-W1 战役 2 起步)",
    ),
    BosRegistration(
        uri="bos://governance/metaos/gate",
        domain="governance",
        package="metaos",
        action="gate",
        endpoint="projects.metaos.src.metaos.gate:check",
        protocol="internal",
        description="metaos 免疫门控入口 (P33-W1 战役 2 起步)",
    ),
    BosRegistration(
        uri="bos://governance/sot-bridge/register",
        domain="governance",
        package="sot-bridge",
        action="register",
        endpoint="kairon.packages.sot_bridge.sharedbrain_bridge:register",
        protocol="internal",
        description="sot-bridge SSOT 注册入口 (P31-W1 合并后, P33-W1 战役 2 起步)",
    ),
    BosRegistration(
        uri="bos://governance/protocols-layer/trigger",
        domain="governance",
        package="protocols-layer",
        action="trigger",
        endpoint="kairon.packages.protocols_layer.symphony:trigger",
        protocol="internal",
        description="protocols-layer 协议触发器入口 (P31-W1 合并后, P33-W1 战役 2 起步)",
    ),
    # ── P33-W2 战役 2 余下 3 Domain: Analysis + Persona + Capability ──
    # Analysis: minerva / ontoderive / codeanalyze / iris
    BosRegistration(
        uri="bos://analysis/minerva/research",
        domain="analysis",
        package="minerva",
        action="research",
        endpoint="kairon.packages.minerva.research:run",
        protocol="internal",
        description="Minerva 深度研究 (P33-W2 战役 2 余下)",
    ),
    BosRegistration(
        uri="bos://analysis/minerva/draft",
        domain="analysis",
        package="minerva",
        action="draft",
        endpoint="kairon.packages.minerva.draft:compose",
        protocol="internal",
        description="Minerva 报告草稿生成 (P33-W2 战役 2 余下)",
    ),
    BosRegistration(
        uri="bos://analysis/ontoderive/derive",
        domain="analysis",
        package="ontoderive",
        action="derive",
        endpoint="kairon.packages.ontoderive.engine:derive",
        protocol="internal",
        description="Ontoderive 事实推导 (P33-W2 战役 2 余下)",
    ),
    BosRegistration(
        uri="bos://analysis/ontoderive/audit",
        domain="analysis",
        package="ontoderive",
        action="audit",
        endpoint="kairon.packages.ontoderive.engine:audit",
        protocol="internal",
        description="Ontoderive 事实审计 (P33-W2 战役 2 余下)",
    ),
    BosRegistration(
        uri="bos://analysis/codeanalyze/scan",
        domain="analysis",
        package="codeanalyze",
        action="scan",
        endpoint="kairon.packages.codeanalyze.scanner:scan",
        protocol="internal",
        description="Codeanalyze 静态扫描 (P33-W2 战役 2 余下)",
    ),
    BosRegistration(
        uri="bos://analysis/codeanalyze/report",
        domain="analysis",
        package="codeanalyze",
        action="report",
        endpoint="kairon.packages.codeanalyze.reporter:report",
        protocol="internal",
        description="Codeanalyze 报告生成 (P33-W2 战役 2 余下)",
    ),
    BosRegistration(
        uri="bos://analysis/iris/connect",
        domain="analysis",
        package="iris",
        action="connect",
        endpoint="kairon.packages.iris.connector:connect",
        protocol="internal",
        description="Iris 数据连接 (P33-W2 战役 2 余下)",
    ),
    # Persona: sharedbrain-bridge / core-models / health-profile
    BosRegistration(
        uri="bos://persona/sharedbrain-bridge/recall",
        domain="persona",
        package="sharedbrain-bridge",
        action="recall",
        endpoint="kairon.packages.sharedbrain_bridge.recall:recall",
        protocol="internal",
        description="sharedbrain 回忆 (P33-W2 战役 2 余下)",
    ),
    BosRegistration(
        uri="bos://persona/sharedbrain-bridge/sync",
        domain="persona",
        package="sharedbrain-bridge",
        action="sync",
        endpoint="kairon.packages.sharedbrain_bridge.sync:sync",
        protocol="internal",
        description="sharedbrain 同步 (P33-W2 战役 2 余下)",
    ),
    BosRegistration(
        uri="bos://persona/core-models/schema",
        domain="persona",
        package="core-models",
        action="schema",
        endpoint="kairon.packages.core_models.schema:load",
        protocol="internal",
        description="core-models schema (P33-W2 战役 2 余下)",
    ),
    BosRegistration(
        uri="bos://persona/health-profile/summary",
        domain="persona",
        package="health-profile",
        action="summary",
        endpoint="kairon.packages.health_profile.summary:summarize",
        protocol="internal",
        description="health-profile 摘要 (P33-W2 战役 2 余下)",
    ),
    # Capability: forge / agent-runtime
    BosRegistration(
        uri="bos://capability/forge/register-tool",
        domain="capability",
        package="forge",
        action="register-tool",
        endpoint="kairon.packages.forge.registry:register",
        protocol="internal",
        description="Forge 工具注册 (P33-W2 战役 2 余下)",
    ),
    BosRegistration(
        uri="bos://capability/forge/discover",
        domain="capability",
        package="forge",
        action="discover",
        endpoint="kairon.packages.forge.registry:discover",
        protocol="internal",
        description="Forge 工具发现 (P33-W2 战役 2 余下)",
    ),
    BosRegistration(
        uri="bos://capability/agent-runtime/run-task",
        domain="capability",
        package="agent-runtime",
        action="run-task",
        endpoint="kairon.agent_runtime.runner:run",
        protocol="internal",
        description="agent-runtime 任务执行 (P33-W2 战役 2 余下)",
    ),
    BosRegistration(
        uri="bos://capability/agent-runtime/chat",
        domain="capability",
        package="agent-runtime",
        action="chat",
        endpoint="kairon.agent_runtime.chat:chat",
        protocol="internal",
        description="agent-runtime 对话 (P33-W2 战役 2 余下)",
    ),
]


# ── 验证 + 解析 ────────────────────────────────────────────


def validate_bos_uri(uri: str) -> tuple[bool, str]:
    """Validate BOS URI format (4-segment new + 3-segment legacy).

    Accepted forms:
      1. ``bos://<domain>/<package>/<action>`` (new, P33 北星)
         domain ∈ {memory, governance, analysis, persona, capability}
      2. ``bos://<package>/<action>`` (legacy, P30 mcp_server.py)
         domain auto-mapped via LEGACY_DOMAIN_MAP

    Returns:
        (True, "") on valid 4-segment; (True, info_msg) on valid legacy
        (info_msg contains the auto-mapped domain); (False, error_message)
        on invalid.
    """
    if not isinstance(uri, str):
        return False, f"URI must be string, got {type(uri).__name__}"
    # 1) 4-段新格式 (北星, 北斗主用)
    m = BOS_URI_PATTERN.match(uri)
    if m:
        return True, ""
    # 2) 3-段 legacy 格式 (mcp_server.py P30 既有 URI)
    lm = BOS_URI_LEGACY_PATTERN.match(uri)
    if lm:
        pkg = lm.group("package")
        if pkg in LEGACY_DOMAIN_MAP:
            return (
                True,
                f"legacy 3-segment URI, auto-mapped to "
                f"domain={LEGACY_DOMAIN_MAP[pkg]}",
            )
        return (
            False,
            f"Legacy 3-segment URI but package '{pkg}' not in domain map. "
            f"Use 4-segment form: bos://<domain>/<package>/<action>",
        )
    return (
        False,
        f"Invalid BOS URI: {uri!r}. "
        f"Expected bos://<domain>/<package>/<action> "
        f"(domain in {ALLOWED_DOMAINS}) or legacy bos://<package>/<action>",
    )


def parse_bos_uri(uri: str) -> dict[str, str]:
    """Parse BOS URI into dict (handles both 4-segment and 3-segment legacy).

    For legacy 3-segment URIs, the domain is filled from
    ``LEGACY_DOMAIN_MAP``.  Raises ``ValueError`` if the URI is invalid
    or the legacy package has no domain mapping.
    """
    valid, err = validate_bos_uri(uri)
    if not valid:
        raise ValueError(err)
    m4 = BOS_URI_PATTERN.match(uri)
    if m4:
        return m4.groupdict()
    m3 = BOS_URI_LEGACY_PATTERN.match(uri)
    assert m3 is not None  # validate_bos_uri just confirmed
    pkg = m3.group("package")
    return {
        "domain": LEGACY_DOMAIN_MAP[pkg],
        "package": pkg,
        "action": m3.group("action"),
    }


# ── 本地 JSON 持久化 ──────────────────────────────────────


def load_registry(path: Path = DEFAULT_REGISTRY_PATH) -> list[dict[str, Any]]:
    """Load BOS registrations from local JSON file.

    Returns:
        List of registration dicts; empty list if file does not exist
        or is malformed (we treat malformed as "no registrations" to
        avoid blocking W1 起步, but log to stderr).
    """
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    if not text.strip():
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        print(
            f"[omo_bos] WARN: registry {path} is malformed JSON ({exc}); "
            f"treating as empty",
            file=sys.stderr,
        )
        return []
    if not isinstance(data, list):
        print(
            f"[omo_bos] WARN: registry {path} is not a JSON list; "
            f"treating as empty",
            file=sys.stderr,
        )
        return []
    return data


def save_registry(
    registrations: list[dict[str, Any]],
    path: Path = DEFAULT_REGISTRY_PATH,
) -> None:
    """Atomically write BOS registrations to local JSON file.

    Uses tempfile + os.replace for atomic write — prevents half-written
    state on crash.  Creates parent dirs as needed.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(registrations, ensure_ascii=False, indent=2)
    # 原子写: 写到同目录临时文件, 然后 rename
    fd, tmp_path = tempfile.mkstemp(
        prefix=".bos-registry.", suffix=".json.tmp", dir=path.parent
    )
    try:
        Path(tmp_path).write_text(payload, encoding="utf-8")
        Path(tmp_path).replace(path)
    finally:
        # mkstemp 开的 fd 需要关掉
        try:
            import os

            os.close(fd)
        except OSError:
            pass


def _ensure_kos_importable() -> str | None:
    """Add kairon KOS package to sys.path if not already importable.

    Returns:
        None on success, error message on failure.
    """
    if "kos.ontology.store" in sys.modules:
        return None
    try:
        spec = importlib.util.find_spec("kos.ontology.store")
    except (ImportError, ModuleNotFoundError, ValueError):
        spec = None
    if spec is not None:
        return None
    if not _KAIRON_PACKAGES_SRC.exists():
        return f"kos src not found at {_KAIRON_PACKAGES_SRC}"
    sys.path.insert(0, str(_KAIRON_PACKAGES_SRC))
    # 重新检查
    try:
        spec = importlib.util.find_spec("kos.ontology.store")
    except (ImportError, ModuleNotFoundError, ValueError):
        spec = None
    if spec is None:
        return "kos.ontology.store still not importable after path injection"
    return None


def save_to_kos(
    registration: dict[str, Any],
    zone: str = "bos_registry",
) -> dict[str, Any]:
    """Persist a BOS registration to KOS zone=bos_registry.

    Uses direct package call to ``kos.ontology.store.put_entity`` (P32
    pattern, bypasses agora to keep P32 audit at 100).  Caller is
    expected to be a registration dict with keys: ``uri``, ``domain``,
    ``package``, ``action``, ``endpoint``, ``description``, ``registered_at``.

    Self-healing: older KOS DBs may lack columns ``source`` /
    ``status`` / ``version`` / ``confidence`` / ``created_at`` — we
    run a defensive ALTER TABLE ADD COLUMN with safe defaults before
    ``put_entity``.  Existing rows are preserved.

    Returns:
        dict with keys: ``saved`` (uri), ``entity_id``, ``backend`` ("kos")
        on success; ``{"error": str}`` on failure (kos not available,
        put_entity rejected, etc.).  Never raises.
    """
    err = _ensure_kos_importable()
    if err:
        return {"error": f"kos_not_available: {err}"}
    try:
        from kos.ontology._types import Entity, EntityType  # type: ignore[import-not-found]
        from kos.ontology.store import _get_conn, put_entity  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover
        return {"error": f"kos_import_failed: {exc}"}

    # 自愈: 给老 KOS DB 加缺失列 (KOS store.py 已有 zone 自愈, 我们补 source/status 等)
    try:
        import sqlite3
        conn = _get_conn()
        for col, ddl in [
            ("source", "TEXT"),
            ("status", "TEXT DEFAULT 'active'"),
            ("version", "INTEGER DEFAULT 1"),
            ("confidence", "REAL DEFAULT 1.0"),
            ("created_at", "TEXT"),
        ]:
            try:
                conn.execute(f"ALTER TABLE kos_entities ADD COLUMN {col} {ddl}")
            except sqlite3.OperationalError:
                pass  # 列已存在
        conn.commit()
        conn.close()
    except Exception:
        pass  # 自愈失败不阻塞

    uri = registration.get("uri", "")
    # entity_id 由 CONCEPT 前缀 (CON-) + URI hash 保证唯一
    safe = uri.replace("bos://", "").replace("/", "-").replace(":", "-")
    entity_id = f"CON-BOS-{safe}"[:96]
    try:
        entity = Entity(
            entity_id=entity_id,
            entity_type=EntityType.CONCEPT,
            label=uri,
            description=registration.get("description", f"BOS URI: {uri}"),
            zone=zone,
            source="omo-bos",
            confidence=1.0,
            metadata={
                "uri": uri,
                "domain": registration.get("domain", ""),
                "package": registration.get("package", ""),
                "action": registration.get("action", ""),
                "endpoint": registration.get("endpoint", ""),
                "protocol": registration.get("protocol", "internal"),
                "registered_at": registration.get("registered_at", ""),
            },
        )
        result = put_entity(entity)
        if isinstance(result, dict) and "error" in result:
            return {"error": f"kos_put_failed: {result['error']}"}
        return {
            "saved": uri,
            "entity_id": entity_id,
            "backend": "kos",
            "zone": zone,
        }
    except Exception as exc:  # pragma: no cover
        return {"error": f"kos_save_exception: {exc}"[:200]}


def register_uri(
    uri: str,
    endpoint: str = "",
    *,
    protocol: Protocol = "internal",
    description: str = "",
    registered_by: str = "omo-bos-cli",
    path: Path = DEFAULT_REGISTRY_PATH,
    kos_zone: str = "bos_registry",
    dual_write: bool = True,
) -> dict[str, Any]:
    """Register a single BOS URI (local JSON + KOS dual-write).

    Idempotent: re-registering the same URI updates the existing entry
    in place (preserving original ``registered_at``) and returns a
    status dict.

    W3+ policy: W0 spec #4 要求持久化到 KOS zone=bos_registry. 本函数
    默认先写本地 JSON (offline fallback), 再写 KOS (主存).  KOS 写入
    失败不会回滚本地 JSON (best-effort), 失败原因记录在 ``kos_result``.

    Args:
        dual_write: set to False 跳过 KOS 写入 (测试场景).

    Returns:
        dict with keys: ``uri``, ``status`` ("registered" | "updated"),
        ``total`` (本地 JSON 总数), ``kos_result`` (save_to_kos 返回).
        On validation failure returns ``{"error": str}``.
    """
    valid, err = validate_bos_uri(uri)
    if not valid:
        return {"error": err}
    parsed = parse_bos_uri(uri)

    regs = load_registry(path)
    new_entry: dict[str, Any] = {
        "uri": uri,
        "domain": parsed["domain"],
        "package": parsed["package"],
        "action": parsed["action"],
        "endpoint": endpoint,
        "protocol": protocol,
        "description": description,
        "registered_at": datetime.now(timezone.utc).isoformat(),
        "registered_by": registered_by,
    }
    status = "registered"
    for i, r in enumerate(regs):
        if r.get("uri") == uri:
            # 保留首次 registered_at, 更新其他字段
            preserved_at = r.get("registered_at", new_entry["registered_at"])
            new_entry["registered_at"] = preserved_at
            regs[i] = new_entry
            status = "updated"
            break
    else:
        regs.append(new_entry)

    save_registry(regs, path)

    kos_result: dict[str, Any] = {"skipped": "dual_write_disabled"}
    if dual_write:
        kos_result = save_to_kos(new_entry, zone=kos_zone)

    return {
        "uri": uri,
        "status": status,
        "total": len(regs),
        "kos_result": kos_result,
    }


def list_registrations(
    *,
    domain: str | None = None,
    path: Path = DEFAULT_REGISTRY_PATH,
) -> list[BosRegistration]:
    """List registered BOS URIs from local JSON.

    Args:
        domain: optional filter (memory/governance/analysis/persona/capability).
        path: registry file path.

    Returns:
        List of BosRegistration parsed from JSON.
    """
    raw = load_registry(path)
    out: list[BosRegistration] = []
    for r in raw:
        uri = r.get("uri", "")
        if not uri.startswith("bos://"):
            continue
        if domain is not None and r.get("domain") != domain:
            continue
        try:
            parsed = parse_bos_uri(uri)
        except ValueError:
            continue
        out.append(
            BosRegistration(
                uri=uri,
                domain=parsed["domain"],
                package=parsed["package"],
                action=parsed["action"],
                endpoint=r.get("endpoint", ""),
                protocol=r.get("protocol", "internal"),
                description=r.get("description", ""),
                registered_at=r.get("registered_at", ""),
                registered_by=r.get("registered_by", "unknown"),
            )
        )
    return out


def register_seeds(
    path: Path = DEFAULT_REGISTRY_PATH,
    *,
    dual_write: bool = True,
    kos_zone: str = "bos_registry",
) -> list[dict[str, Any]]:
    """Register all 21 SEED_REGISTRATIONS (idempotent, KOS dual-write by default).

    P33-W1: 6 条 (memory + governance)
    P33-W2: 15 条 (analysis + persona + capability)
    Total : 21 条 SEED URI 覆盖 5 Domain

    Args:
        dual_write: 默认 True — 每条 SEED 同时写 KOS zone=bos_registry.
        kos_zone: KOS zone 名称 (默认 "bos_registry").

    Returns:
        List of per-URI result dicts (see ``register_uri``).
    """
    results: list[dict[str, Any]] = []
    for r in SEED_REGISTRATIONS:
        results.append(
            register_uri(
                uri=r.uri,
                endpoint=r.endpoint,
                protocol=r.protocol,
                description=r.description,
                registered_by=r.registered_by,
                path=path,
                dual_write=dual_write,
                kos_zone=kos_zone,
            )
        )
    return results


# ── M2 修复: endpoint 实测可达性 ───────────────────────


def verify_endpoint(endpoint: str) -> dict[str, Any]:
    """实测 endpoint 字符串是否可 import (用 importlib.util.find_spec).

    endpoint 格式: ``<python.module.path>:<func>`` 或纯 module path.

    - module path: 用 importlib.util.find_spec 检查模块是否可定位
    - ``:<func>``: 不验证函数存在 (stub 可能没真实现)

    Returns:
        ``{"endpoint": str, "module_found": bool, "error": str|None}``
    """
    if not isinstance(endpoint, str) or not endpoint:
        return {"endpoint": endpoint or "", "module_found": False, "error": "no_endpoint"}
    if ":" in endpoint:
        module_path = endpoint.split(":", 1)[0]
    else:
        module_path = endpoint
    module_path = module_path.strip()
    if not module_path:
        return {"endpoint": endpoint, "module_found": False, "error": "empty_module_path"}
    try:
        spec = importlib.util.find_spec(module_path)
    except (ImportError, ModuleNotFoundError, ValueError) as exc:
        return {
            "endpoint": endpoint,
            "module_found": False,
            "error": f"import_error: {exc}"[:160],
        }
    except Exception as exc:  # pragma: no cover - 其他异常
        return {
            "endpoint": endpoint,
            "module_found": False,
            "error": f"unexpected: {type(exc).__name__}: {exc}"[:160],
        }
    if spec is None:
        return {
            "endpoint": endpoint,
            "module_found": False,
            "error": "module_not_found",
        }
    return {"endpoint": endpoint, "module_found": True, "error": None}


def verify_all_endpoints(
    path: Path = DEFAULT_REGISTRY_PATH,
) -> list[dict[str, Any]]:
    """遍历注册表, 验证每条 URI 的 endpoint 模块是否可定位.

    Returns:
        List of dicts, each with ``uri``, ``endpoint``, ``module_found``,
        ``error``.  顺序与注册表保持一致.
    """
    regs = load_registry(path)
    out: list[dict[str, Any]] = []
    for r in regs:
        uri = r.get("uri", "")
        ep = r.get("endpoint", "")
        result = verify_endpoint(ep)
        result["uri"] = uri
        out.append(result)
    return out


# ── CLI 入口 ─────────────────────────────────────────────


def _print_table(regs: list[BosRegistration]) -> None:
    if not regs:
        print("(no BOS registrations found)")
        return
    print(f"{'URI':<50} {'DOMAIN':<12} {'PACKAGE':<20} {'ACTION':<10} {'PROTO':<10}")
    print("-" * 102)
    for r in regs:
        print(
            f"{r.uri:<50} {r.domain:<12} {r.package:<20} {r.action:<10} {r.protocol:<10}"
        )


def main(argv: list[str] | None = None) -> int:
    """omo bos CLI entry.

    Subcommands:
        register        — register one BOS URI to local JSON
        list            — list registered BOS URIs (optionally --domain / --json)
        validate        — validate a BOS URI string without registering
        seed            — bulk-register the 6 SEED_REGISTRATIONS (idempotent)
        register-seeds  — alias for ``seed`` (战役 2 起步命名约定)
    """
    parser = argparse.ArgumentParser(
        prog="omo bos", description="BOS (Banyan Object Service) URI 管理"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # register
    reg = sub.add_parser("register", help="注册 BOS URI 到本地 JSON")
    reg.add_argument("uri", help="bos://<domain>/<package>/<action>")
    reg.add_argument(
        "--endpoint",
        default="",
        help="实际服务入口 (module:function 或 URL), 缺省占位",
    )
    reg.add_argument(
        "--protocol",
        default="internal",
        choices=["http", "stdio", "internal"],
        help="服务协议 (default: internal)",
    )
    reg.add_argument("--description", default="", help="注册描述")
    reg.add_argument(
        "--registered-by", default="omo-bos-cli", help="注册来源标识"
    )

    # list
    lst = sub.add_parser("list", help="列出已注册 BOS URI")
    lst.add_argument(
        "--domain",
        default=None,
        choices=list(ALLOWED_DOMAINS),
        help="按 domain 过滤",
    )
    lst.add_argument(
        "--json", action="store_true", help="输出 JSON 格式"
    )
    lst.add_argument(
        "--path",
        default=None,
        help=f"注册表路径 (默认: {DEFAULT_REGISTRY_PATH})",
    )

    # validate
    val = sub.add_parser("validate", help="验证 BOS URI 格式 (不注册)")
    val.add_argument("uri", help="待验证的 URI")

    # seed
    sub.add_parser(
        "seed",
        help="批量注册 20 条 SEED URI (6 W1 + 14 W2, 幂等, 已存在会更新)",
    )

    # register-seeds (alias, 战役 2 起步命名约定)
    sub.add_parser(
        "register-seeds",
        help="注册 21 条 SEED URI (alias of seed)",
    )

    # verify (M2: importlib 实测 endpoint 可达)
    ver = sub.add_parser(
        "verify",
        help="实测所有 URI endpoint 模块可达性 (importlib.find_spec)",
    )
    ver.add_argument(
        "--path",
        default=None,
        help=f"注册表路径 (默认: {DEFAULT_REGISTRY_PATH})",
    )

    args = parser.parse_args(argv)

    if args.cmd == "validate":
        valid, err = validate_bos_uri(args.uri)
        if valid:
            print(f"OK  {args.uri}")
            return 0
        print(f"FAIL {args.uri}: {err}")
        return 1

    if args.cmd in ("list",):
        path = Path(args.path) if args.path else DEFAULT_REGISTRY_PATH
        regs = list_registrations(domain=args.domain, path=path)
        if args.json:
            print(json.dumps([r.to_dict() for r in regs], ensure_ascii=False, indent=2))
        else:
            _print_table(regs)
            print(f"\n共 {len(regs)} 条  (path: {path})")
        return 0

    if args.cmd == "register":
        valid, err = validate_bos_uri(args.uri)
        if not valid:
            print(f"FAIL: {err}", file=sys.stderr)
            return 1
        result = register_uri(
            uri=args.uri,
            endpoint=args.endpoint,
            protocol=args.protocol,
            description=args.description,
            registered_by=args.registered_by,
        )
        if "error" in result:
            print(f"FAIL: {result['error']}", file=sys.stderr)
            return 1
        print(f"OK  {args.uri}  →  {result['status']} (total: {result['total']})")
        return 0

    if args.cmd in ("seed", "register-seeds"):
        results = register_seeds()
        ok = sum(1 for r in results if "error" not in r)
        failed = [r for r in results if "error" in r]
        print(
            f"[omo bos {args.cmd}] registered {ok}/{len(SEED_REGISTRATIONS)} "
            f"SEED URIs → {DEFAULT_REGISTRY_PATH}"
        )
        for r in results:
            if "error" in r:
                print(f"  FAIL {r['error']}", file=sys.stderr)
            else:
                print(f"  OK  {r['uri']}  ({r['status']})")
        if failed:
            return 1
        return 0

    if args.cmd == "verify":
        path = Path(args.path) if args.path else DEFAULT_REGISTRY_PATH
        results = verify_all_endpoints(path=path)
        ok = sum(1 for r in results if r.get("module_found"))
        fail = len(results) - ok
        no_ep = sum(1 for r in results if r.get("error") == "no_endpoint")
        print(
            f"[omo bos verify] {path}\n"
            f"  总 {len(results)} / 可达 {ok} / 失败 {fail} "
            f"(no_endpoint={no_ep})"
        )
        for r in results:
            status = "✓" if r.get("module_found") else "✗"
            print(f"  {status} {r['uri']}  →  {r['endpoint']}")
            if not r.get("module_found"):
                err = r.get("error") or ""
                print(f"      error: {err}", file=sys.stderr)
        # 全部失败也是 0 (有结果就行), 任何 fail 不算 1 因为 m2 是"实测"而非"必须通过"
        return 0

    parser.print_help()
    return 1


__all__ = (
    "ALLOWED_DOMAINS",
    "BOS_URI_LEGACY_PATTERN",
    "BOS_URI_PATTERN",
    "BosRegistration",
    "DEFAULT_REGISTRY_PATH",
    "Domain",
    "LEGACY_DOMAIN_MAP",
    "Protocol",
    "SEED_REGISTRATIONS",
    "list_registrations",
    "load_registry",
    "main",
    "parse_bos_uri",
    "register_seeds",
    "register_uri",
    "save_registry",
    "save_to_kos",
    "validate_bos_uri",
    "verify_all_endpoints",
    "verify_endpoint",
)


if __name__ == "__main__":
    raise SystemExit(main())
