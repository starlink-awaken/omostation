"""P58-W1 omo audit dedup — 同 (uri, failure_type) 60s 内只 1 条.

P44-W3: audit dedup (避免刷屏)
P49-simplify: OrderedDict LRU 替代 dict.clear() 全清
P58-W1: 从 omo_llm_bos_bridge.py 716 行抽出
"""
from __future__ import annotations

import time
from collections import OrderedDict

_AUDIT_DEDUP_TTL_SEC = 60
_AUDIT_DEDUP_MAX = 1000
_AUDIT_DEDUP_CACHE: OrderedDict[tuple[str, str], float] = OrderedDict()


def _audit_should_record(uri: str, failure_type: str) -> bool:
    """P44-W3: 返回 True 表示可以 record (新 key 或 1 分钟前已过).

    用 in-memory OrderedDict + 60s TTL, 满 1000 条 popitem(last=False) 删最旧, 不全清.
    不持久化. 进程重启后清空.
    """
    key = (uri, failure_type)
    now = time.time()
    last = _AUDIT_DEDUP_CACHE.get(key)
    if last is not None and (now - last) < _AUDIT_DEDUP_TTL_SEC:
        return False
    _AUDIT_DEDUP_CACHE[key] = now
    # LRU 截断: 超过 1000 条删最旧 (保留最近活跃项)
    while len(_AUDIT_DEDUP_CACHE) > _AUDIT_DEDUP_MAX:
        _AUDIT_DEDUP_CACHE.popitem(last=False)
    return True


def record_agora_failure(uri: str, failure_type: str, details: str) -> None:
    """P43-W2: 跨进程 agora 派发失败时 record omo-audit, 让治理 daemon 看到.
    P44-W3: 加 dedup, 同 (uri, failure_type) 1 分钟内只 1 条.
    P58-W1: 提升为 module-level public (供 agora_pool 等外部调).

    失败类型: spawn_failed / non_zero_exit / json_decode_failed / unknown_bos_uri
    """
    if not _audit_should_record(uri, failure_type):
        return
    try:
        from omo.omo_audit import record as audit_record  # type: ignore[import-not-found]

        audit_record(
            action="bos_resolve_failure",
            debt_id=f"BOS-RESOLVE-{failure_type.upper()}",
            actor="omo-bridge",
            details=f"uri={uri} failure={failure_type} {details}",
        )
    except Exception:
        # audit 自身失败不阻塞业务流
        pass


__all__ = [
    "_audit_should_record",
    "record_agora_failure",
    "_record_agora_failure",  # P58-W1 backward compat alias
    "_AUDIT_DEDUP_TTL_SEC",
    "_AUDIT_DEDUP_MAX",
]


# P58-W1: backward compat alias (原 omo_llm_bos_bridge 内部用 _record_agora_failure)
_record_agora_failure = record_agora_failure
