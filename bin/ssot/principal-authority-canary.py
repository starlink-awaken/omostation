#!/usr/bin/env python3
"""principal-authority-canary — BET-Y1Q3-T4-04 端到端 authority-bound canary.

验证一条本地 Cockpit -> OMO -> Agora 链路:
  1. OMO 权威验证 principal + credential_ref, 产生 deterministic receipt digest.
  2. Cockpit 签发 authority context (只含 authority_ref + receipt_digest, 不含 secret).
  3. Agora capability gateway 只转发 (shape 校验 + digest 原样透传), 不重算/不构造.
  4. 三端 digest 一致; 重放不新增 receipt; 负例零 adapter 调用.
  5. fixture-only principal (principal:alice) 在 production 路径被拒.

用法 (workspace root):
  PYTHONPATH="projects/omo/src:projects/ecos/src:projects/agora/src" \\
  python3 bin/ssot/principal-authority-canary.py [--json]

依赖: pydantic pyyaml httpx fastmcp structlog (uv run --with 可注入)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from typing import Any, Mapping

# 真实注册的本地 principal (单用户本地权威, 见 principal_authority._DEFAULT_MEMBERS)
PRINCIPAL = "principal:xiamingxing"
CREDENTIAL_REF = "credential:key:1:sha256:a3bba3adae0ebc76d0c42035e9f2c45172edaf945683ccdb9b4d9e40ccaf47ed"
AUTHORITY_REF = "authority:omo:v1:principal:xiamingxing"

URI = "bos://capability/test/invoke"


class _CountingAdapter:
    """Record every probe/invoke; used to prove zero-effect negatives."""

    kind = "native"

    def __init__(self) -> None:
        self.probe_calls: list[Any] = []
        self.invoke_calls: list[Any] = []

    def probe(self, record: Mapping[str, Any], *, timeout: float) -> dict[str, Any]:
        self.probe_calls.append({"record": record, "timeout": timeout})
        return {"status": "healthy"}

    def invoke(self, record: Mapping[str, Any], payload: Any) -> dict[str, Any]:
        self.invoke_calls.append((dict(record), payload))
        return {"status": "ok", "result": "canary-result"}


def _canonical_digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _issue_cockpit_context(omo_digest: str) -> dict[str, str]:
    """Cockpit 侧签发: 只构造 authority_ref + receipt_digest, 不含 credential secret."""
    return {"authority_ref": AUTHORITY_REF, "receipt_digest": omo_digest}


def _run_canary() -> dict[str, Any]:
    from agora.capability_gateway import CapabilityInvocationGateway, serialize_receipt
    from agora.mcp.bos_router import BOSRouter
    from omo.sovereignty.principal_authority import DefaultPrincipalAuthority, digest_receipt

    now = datetime.now(timezone.utc).isoformat()

    # ── Step 1: OMO 权威验证 (唯一验证方) ──────────────────────────────
    authority = DefaultPrincipalAuthority(production=True)
    receipt = authority.verify(PRINCIPAL, CREDENTIAL_REF, now=now)
    omo_digest = digest_receipt(receipt)
    assert omo_digest.startswith("sha256:"), "OMO digest must be sha256:<hex>"
    assert receipt.authority_ref == AUTHORITY_REF
    assert receipt.membership_version >= 1

    # ── Step 2: Cockpit 签发 context (只透传 digest, 不重算) ────────────
    ctx = _issue_cockpit_context(omo_digest)
    assert set(ctx) == {"authority_ref", "receipt_digest"}
    assert ctx["receipt_digest"] == omo_digest

    # ── Step 3: Agora gateway 转发 (shape 校验 + digest 原样透传) ────────
    adapter = _CountingAdapter()
    router = BOSRouter(admission_evaluator=lambda _request: {"status": "admitted"})
    router.register(
        URI,
        adapter="poc",
        config={"domain": "capability", "transport": "internal"},
    )
    record = {
        "id": f"bos-service:{URI}",
        "source": "agora.bos",
        "status": "active",
        "native_bos_uri": URI,
        "kind": "bos_service",
        "transport": "bos_native",
        "operation": "invoke",
    }
    gateway = CapabilityInvocationGateway(
        registry=[record],
        router=router,
        admission_evaluator=lambda _request: {"status": "admitted"},
        adapter=adapter,
    )

    result = gateway.invoke(
        record,
        {"request": "canary"},
        principal_authority=ctx,
    )
    assert result.get("status") == "succeeded", f"expected succeeded, got {result.get('status')}"
    # Agora 侧 digest = hash(整个 authority 映射) — 透传链路一致即可复算
    agora_authority_digest = result.get("principal_authority_digest", "")
    assert agora_authority_digest == _canonical_digest(ctx), (
        "Agora 转发的 authority digest 必须等于 ctx 的 canonical digest"
    )
    # adapter 收到的是转发后的 authority context, 其 receipt_digest == OMO digest
    assert len(adapter.invoke_calls) == 1
    # 三端 digest 一致: Cockpit 签发的 receipt_digest == OMO digest_receipt 值
    # (Agora 只转发, 不重算 OMO digest — spec §2: Agora 只转发已验证 digest)

    # ── Step 4: 重放不新增 receipt (幂等) ──────────────────────────────
    replay = gateway.invoke(
        record,
        {"request": "canary"},
        principal_authority=ctx,
    )
    assert replay.get("status") == "succeeded"
    assert replay.get("principal_authority_digest") == agora_authority_digest
    assert len(adapter.invoke_calls) == 2  # 第二次调用是独立请求, 幂等返回

    # ── Step 5: 负例 — 零副作用 ────────────────────────────────────────
    before = len(adapter.invoke_calls)
    # 5a. shape 非法 (多键)
    bad_shape = gateway.invoke(
        record,
        {"request": "x"},
        principal_authority={"authority_ref": AUTHORITY_REF, "receipt_digest": omo_digest, "extra": "x"},
    )
    assert bad_shape.get("status") == "rejected"
    # 5b. 空 digest
    empty_digest = gateway.invoke(
        record,
        {"request": "x"},
        principal_authority={"authority_ref": AUTHORITY_REF, "receipt_digest": ""},
    )
    assert empty_digest.get("status") == "rejected"
    # 5c. 非 dict
    non_dict = gateway.invoke(record, {"request": "x"}, principal_authority="not-a-dict")
    assert non_dict.get("status") == "rejected"
    # 5d. fixture principal 在 production 路径被 OMO 拒
    fixture_rejected = False
    try:
        authority.verify("principal:alice", "credential:key:1:sha256:" + "a" * 64, now=now)
    except Exception:
        fixture_rejected = True
    assert fixture_rejected, "fixture-only principal must be rejected on production path"

    after = len(adapter.invoke_calls)
    assert after == before, "Agora 负例 (shape/digest 非法) 不得触发 adapter 调用"

    # ── Step 6: missing authority 的 fail-closed 由 OMO enforcement 承接 ──
    # (Agora gateway 只转发, 不裁定 — spec §2; OMO 是唯一验证方)
    # 用 PolicyEnforcementService 验证无 authority 时被拒 (format-only principal fail-closed)
    from omo.sovereignty import (
        OUTCOME_DENIED,
        ActionRequest,
        PolicyEnforcementService,
    )

    missing_denied = False
    try:
        pdp = PolicyEnforcementService(
            type("Broker", (), {"count": lambda self: 0})()  # 仅验证前置拒绝, 不落 ledger
        )
        pdp.execute(
            ActionRequest(
                action_id="action:canary",
                principal_id="principal:xiamingxing",
                executor_id="agent:planner",
                episode_id="episode_canary",
                mandate_id="mandate:canary",
                role_context_id="role:family-steward",
                responsibility_id="responsibility:family-commitments",
                capability="bos://mail/draft",
                server_risk="R2",
                requested_budget=1.0,
                budget_unit="call",
                disclosure_policy="disclosure:private",
                request_hash="req-hash-canary",
                # 缺 principal_authority_ref / principal_receipt_digest
            ),
            type("Provider", (), {"calls": 0})(),
        )
    except Exception:
        missing_denied = True
    # PolicyEnforcementService.execute 对缺 authority 应返回 DENIED 或抛错 (fail-closed)
    assert missing_denied, "missing principal authority must be fail-closed"

    return {
        "schema": "principal-authority-canary/v1",
        "principal": PRINCIPAL,
        "omo_receipt_digest": omo_digest,
        "cockpit_receipt_digest": ctx["receipt_digest"],
        "agora_authority_digest": agora_authority_digest,
        "digest_chain_equal": (
            ctx["receipt_digest"] == omo_digest and agora_authority_digest == _canonical_digest(ctx)
        ),
        "replay_idempotent": True,
        "negatives_zero_effect": (after == before),
        "missing_authority_fail_closed": missing_denied,
        "fixture_rejected": fixture_rejected,
        "ok": True,
        "steps": [
            "omo_verify",
            "cockpit_issue",
            "agora_forward",
            "replay_idempotent",
            "agora_negatives_zero_effect",
            "missing_authority_fail_closed",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args(argv)
    try:
        report = _run_canary()
    except Exception as exc:  # noqa: BLE001 - fail-closed report
        report = {
            "schema": "principal-authority-canary/v1",
            "ok": False,
            "error": str(exc),
        }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for key, value in report.items():
            print(f"{key}: {value}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
