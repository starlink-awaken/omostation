"""P110-A: ecos domain_manager_cache 子模块 (从 domain_manager.py 提取).

ADR-0108 P110-A 拆解: 9 纯 cache/registry 函数 (~128L) 拆出.

业务 (9 functions):
  - 2-layer cache: _l1_get, _l1_set, _l1_invalidate, _l2_get, _l2_set
  - 缓存 API: _cache_get, _cache_set, _cache_warm
  - 注册表: load_registry, invalidate_registry_cache

模块依赖: (同 domain_manager.py)
  - sys, os, json, yaml (stdlib)
  - pathlib (Path), datetime, collections (defaultdict)
  - l0_audit (optional, try/except)
  - audit_unified (optional, try/except)

向后兼容 (P88-P108 模式):
  domain_manager.py 通过 `from .domain_manager_cache import (...)` re-export,
  保持 `from ecos.services.governance.domain_manager import load_registry` 等不破.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import yaml

# L0 audit integration
try:
    from l0_audit import get_audit_log, validate_operation  # type: ignore[reportMissingImports]

    L0_AUDIT = True
except ImportError:
    L0_AUDIT = False

    def validate_operation(*a, **kw):
        return {"passed": True, "violations": []}

    def get_audit_log(*a, **kw):
        return []


# Unified audit integration
try:
    from audit_unified import log_event, print_audit_report, query_events  # type: ignore[reportMissingImports]

    HAS_AUDIT_UNIFIED = True
except ImportError:
    HAS_AUDIT_UNIFIED = False

    def query_events(**kw):
        return {"events": [], "total": 0}

    def print_audit_report(*a, **kw):
        return ""

    def log_event(*a, **kw):
        return None


# ── 模块级常量（从 domain_manager.py 拆出，ADR-0108 P110-A）──
H = Path.home()
DOCS = H / "Documents"
L0_CONSTRAINTS = (
    Path(__file__).parent.parent.parent / "ssot" / "registry" / "L0-constraints.yaml"
)
L0_CONSTRAINTS_L4 = (
    DOCS / "@学习进化/_knowledge/10-systems/基建架构/L0-constraints.yaml"
)
_L1_CACHE: dict[str, dict] = {}
L1_TTL = 60
BOS_CACHE_FILE = H / ".ecos" / "bos" / "cache.json"
L2_TTL = 300


def _l1_get(key: str) -> any:  # type: ignore[reportGeneralTypeIssues]
    """L1 内存缓存读"""
    entry = _L1_CACHE.get(key)
    if entry and (__import__("time").time() - entry["ts"]) < L1_TTL:
        return entry["data"]
    return None


def _l1_set(key: str, data: any) -> None:  # type: ignore[reportGeneralTypeIssues]
    """L1 内存缓存写"""
    _L1_CACHE[key] = {"data": data, "ts": __import__("time").time()}


def _l1_invalidate(key: str = None) -> None:  # type: ignore[reportArgumentType]
    """L1 缓存失效"""
    if key:
        _L1_CACHE.pop(key, None)
    else:
        _L1_CACHE.clear()


def _l2_get(key: str) -> any:  # type: ignore[reportGeneralTypeIssues]
    """L2 JSON 持久缓存读"""
    try:
        if BOS_CACHE_FILE.exists():
            data = json.loads(BOS_CACHE_FILE.read_text())
            entry = data.get(key)
            if entry and (__import__("time").time() - entry.get("ts", 0)) < L2_TTL:
                return entry["data"]
    except Exception:  # defensive fallback
        pass
    return None


def _l2_set(key: str, data: any) -> None:  # type: ignore[reportGeneralTypeIssues]
    """L2 JSON 持久缓存写 (原子写入: tmp → rename)"""
    try:
        BOS_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        cache_data = {}
        if BOS_CACHE_FILE.exists():
            cache_data = json.loads(BOS_CACHE_FILE.read_text())
        if "_version" not in cache_data:
            cache_data["_version"] = 1
            cache_data["_created"] = datetime.now().isoformat()
        cache_data[key] = {"data": data, "ts": __import__("time").time()}
        cache_data["_updated"] = datetime.now().isoformat()
        # Atomic write: tmp → rename to avoid partial writes on concurrent access
        tmp = BOS_CACHE_FILE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(cache_data, indent=2, ensure_ascii=False))
        tmp.replace(BOS_CACHE_FILE)
    except Exception:  # defensive fallback
        pass


def _cache_get(key: str) -> any:  # type: ignore[reportGeneralTypeIssues]
    """三级缓存读: L1 → L2 → L3 (返回 None = 未命中)"""
    # L1 快速命中
    data = _l1_get(key)
    if data is not None:
        return data
    # L2 持久缓存
    data = _l2_get(key)
    if data is not None:
        _l1_set(key, data)  # 预热 L1
        return data
    return None


def _cache_set(key: str, data: any) -> None:  # type: ignore[reportGeneralTypeIssues]
    """三级缓存写: L1 + L2 同时写入"""
    _l1_set(key, data)
    _l2_set(key, data)


def _cache_warm() -> dict:
    """从 L2 预热 L1 缓存 — 返回预热统计"""
    stats = {"l1_before": len(_L1_CACHE), "l2_items": 0, "warmed": 0}
    try:
        if BOS_CACHE_FILE.exists():
            data = json.loads(BOS_CACHE_FILE.read_text())
            for key, entry in data.items():
                if key.startswith("_"):
                    continue
                if isinstance(entry, dict) and "data" in entry and "ts" in entry:
                    if (__import__("time").time() - entry["ts"]) < L1_TTL:
                        _L1_CACHE[key] = {"data": entry["data"], "ts": entry["ts"]}
                        stats["warmed"] += 1
                    stats["l2_items"] += 1
    except Exception:  # defensive fallback
        pass
    stats["l1_after"] = len(_L1_CACHE)
    return stats


def load_registry(force_reload: bool = False):
    """Load domain registry with 3-tier cache.

    Cache key: "domain_registry"
    L1 → L2 → L3 (YAML SSOT)

    Args:
        force_reload: If True, bypass all caches and reload from SSOT.
    """
    key = "domain_registry"

    if not force_reload:
        data = _cache_get(key)
        if data is not None:
            return data

    # L3: SSOT — 直接从 YAML 读取
    p = L0_CONSTRAINTS if L0_CONSTRAINTS.exists() else L0_CONSTRAINTS_L4
    if not p.exists():
        return []

    with open(p) as f:
        data = yaml.safe_load(f).get("domain_registry", [])

    # 写入 L1 + L2 (仅在有数据时缓存，避免空结果污染 L2)
    if data:
        _cache_set(key, data)
    return data


def invalidate_registry_cache():
    """Force next load_registry() to reload from disk."""
    _l1_invalidate("domain_registry")
