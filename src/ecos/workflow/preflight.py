"""Workflow preflight context — fabric 校验通过后发给 backend 的通行证 (ADR-0181 Phase 2).

设计:
- L0 fabric (executor) 在 validate_workflow 通过后 issue token
- 受保护 backend (metaos 等) 必须 verify，防止绕过治理管线直调
- secret 默认开发值；生产设 ECOS_WF_PREFLIGHT_SECRET
- 关闭校验: ECOS_WF_REQUIRE_PREFLIGHT=0
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from typing import Any

PREFLIGHT_KEY = "_ecos_preflight"
_DEFAULT_SECRET = "ecos-dev-preflight"
_DEFAULT_MAX_AGE = 3600


def _secret() -> bytes:
    return os.environ.get("ECOS_WF_PREFLIGHT_SECRET", _DEFAULT_SECRET).encode()


def require_preflight_enabled() -> bool:
    return os.environ.get("ECOS_WF_REQUIRE_PREFLIGHT", "1").strip() != "0"


def issue_preflight(
    workflow: str, *, extra: dict[str, Any] | None = None
) -> dict[str, Any]:
    """签发 preflight 上下文（附在 params 上）。"""
    ts = int(time.time())
    msg = f"{workflow}:{ts}".encode()
    sig = hmac.new(_secret(), msg, hashlib.sha256).hexdigest()[:32]
    ctx: dict[str, Any] = {
        "version": 1,
        "workflow": workflow,
        "issued_at": ts,
        "token": f"{ts}.{sig}",
    }
    if extra:
        ctx["extra"] = extra
    return ctx


def inject_preflight(
    params: dict[str, Any] | None, workflow: str, **extra: Any
) -> dict[str, Any]:
    """返回带 preflight 的 params 副本。"""
    out = dict(params or {})
    out[PREFLIGHT_KEY] = issue_preflight(workflow, extra=extra or None)
    return out


def verify_preflight(
    params: dict[str, Any] | None,
    *,
    workflow: str | None = None,
    max_age: int = _DEFAULT_MAX_AGE,
) -> tuple[bool, str]:
    """校验 params 中的 preflight。返回 (ok, reason)。"""
    if not require_preflight_enabled():
        return True, "preflight_requirement_disabled"

    if not params or PREFLIGHT_KEY not in params:
        return False, "missing_preflight_context"

    ctx = params.get(PREFLIGHT_KEY)
    if not isinstance(ctx, dict):
        return False, "invalid_preflight_shape"

    token = str(ctx.get("token", ""))
    if "." not in token:
        return False, "invalid_preflight_token"

    ts_s, sig = token.split(".", 1)
    try:
        ts = int(ts_s)
    except ValueError:
        return False, "invalid_preflight_timestamp"

    if abs(int(time.time()) - ts) > max_age:
        return False, "preflight_expired"

    # Prefer token-embedded workflow for HMAC; optional caller hint for mismatch detect
    wf = str(ctx.get("workflow") or workflow or "")
    if workflow and ctx.get("workflow") and str(ctx.get("workflow")) != str(workflow):
        return False, "preflight_workflow_mismatch"

    expected = hmac.new(_secret(), f"{wf}:{ts}".encode(), hashlib.sha256).hexdigest()[
        :32
    ]
    if not hmac.compare_digest(expected, sig):
        return False, "preflight_signature_invalid"

    return True, "ok"


def assert_preflight(
    params: dict[str, Any] | None, *, workflow: str | None = None
) -> dict[str, Any] | None:
    """若校验失败返回 error 结果 dict；成功返回 None。"""
    ok, reason = verify_preflight(params, workflow=workflow)
    if ok:
        return None
    return {
        "steps": [],
        "passed": 0,
        "failed": 1,
        "error": f"preflight_rejected: {reason}",
        "preflight_ok": False,
    }
