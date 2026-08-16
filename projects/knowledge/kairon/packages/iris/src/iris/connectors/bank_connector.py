"""Bank Connector — 银行API访问连接器 (P4-T6, C5级风险).

所有操作走Risk Gate门禁 (bin/ssot/risk-gate.py).
需要银行API认证凭据 (vault://redacted/bank/credentials).
当前为接口stub — 实际API调用需要银行开发者凭证 + 用户授权.

守fabric红线: 不落盘凭据, 所有C5操作必须通过Risk Gate.
"""

from __future__ import annotations

import json
from typing import Any

from iris.base import BaseConnector
from iris.models import Note


class BankConnector(BaseConnector):
    """银行连接器 — 收支查询/转账/投资追踪 (C5级, 受Risk Gate约束)."""

    name = "bank"
    display_name = "银行/财务"
    connection_kind = "data_source"
    protocol = "bank.api/v1"
    capabilities = ("discover", "read", "snapshot")
    data_classification = "confidential"

    def is_available(self) -> bool:
        """Check if bank API credentials are configured."""
        # TODO: Check vault://redacted/bank/credentials
        return False  # Stub: requires real credentials

    def status(self) -> dict[str, Any]:
        return {
            "available": self.is_available(),
            "note": "需银行API凭证 + Risk Gate授权 (C5级操作)",
            "protocol": self.protocol,
        }

    def list_items(self, limit: int = 20, **kwargs: Any) -> list[Note]:
        """List recent transactions (read-only, C1 level)."""
        if not self.is_available():
            return []
        # TODO: Call bank API for transaction history
        # Risk Gate check: C1 (read) → auto-permit
        return []

    def check_balance(self, account: str = "") -> dict[str, Any]:
        """Check account balance (C1 read, auto-permit)."""
        if not self.is_available():
            return {"status": "unavailable", "detail": "bank API not configured"}
        # TODO: Call bank API
        return {"status": "not_implemented", "detail": "needs bank API credentials"}

    def transfer(self, *, to: str, amount: float, **kwargs: Any) -> dict[str, Any]:
        """Transfer money (C5, MUST go through Risk Gate).

        Risk Gate evaluates: amount tier, recipient whitelist,
        daily limit, frequency, reversibility.
        """
        if not self.is_available():
            return {"status": "unavailable", "detail": "bank API not configured"}

        # TODO: Call Risk Gate before executing
        # from bin.ssot.risk_gate import assess_risk
        # risk = assess_risk(action_type="transfer", amount=amount, recipient=to)
        # if risk["decision"] != "permit": return {"status": "blocked", "risk": risk}

        return {"status": "not_implemented", "detail": "needs bank API + Risk Gate authorization"}

    def search(self, query: str, limit: int = 10) -> list[Note]:
        """Search transactions."""
        return self.list_items(limit=limit)
