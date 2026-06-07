from __future__ import annotations

# ruff: noqa: RUF001, RUF003
from ._compat import _log

"""
---
Type: Infrastructure
Status: ACTIVE
Version: 2.1.0
Owner: '@Sage'
Authority: nucleus/Z-Spore/dna/R0-ACT-SYS-AX01-14_holographic_routing_axiom.md
Layer: L3
Constraint: "[!!] OMNI_BUS_ENFORCER"
---
"""

import importlib
from typing import Any


class MembraneGateway:
    def __init__(self) -> None:
        # 延迟加载依赖以确保微内核启动顺序
        self.metadata_path = "eidos/unknown"
        self.organ_name = "unknown"
        self.organ_id = f"eidos-{id(self):x}"
        self._status = "active"
        self._metabolic_budget = 1000.0
        self._ledger = None
        self._toolkit = None
        self.subscribers: dict[str, list[str]] = {}

    def _get_toolkit(self) -> Any | None:
        if self._toolkit is None:
            try:
                module = importlib.import_module("organs.D_Execution.organs.engine.primordial_toolkit")
                self._toolkit = module.Toolkit
            except ImportError:
                _log.debug("[MembraneGateway] PrimordialToolkit not available (D-Execution not installed)")
        return self._toolkit

    def _get_ledger(self) -> Any | None:
        """[TSK-402] 获取能量账本接口"""
        if self._ledger is None:
            try:
                module = importlib.import_module("organs.D_Economy.organs.energy_ledger")
                self._ledger = module.Ledger
            except (ImportError, AttributeError):
                _log.info("⚠️ [Gateway] 警告: 无法连接 EnergyLedger，代谢税暂缓征收。")
        return self._ledger

    # --- 1. URI 路由 ---
    def _resolve_uri(self, uri: str) -> str | None:
        if not uri.startswith("bos://"):
            return None
        parts = uri.replace("bos://", "").split("/")
        layer, domain = parts[0], parts[1]
        if layer == "l4":
            return f"D-{domain.capitalize()}/organs/{parts[2].split(':')[0]}.py"
        elif layer == "l0":
            return f"Z-Core/L0-Genome/rules/{parts[2].split(':')[0]}.md"
        return None

    # --- 2. 物理调用 ---
    def call(self, uri: str, interface_name: str | None = None, **kwargs: Any) -> str | None:
        target_node_rel = self._resolve_uri(uri)
        if not target_node_rel:
            return None

        _log.info("🌀 [Omni-Bus] 路由请求: {uri}")

        # [TSK-402] 代谢实装：真正扣除 EU
        self._charge_metabolic_tax(uri)

        # 法律审计
        meta = self._get_toolkit()
        if meta is not None:
            meta = meta.get_node_metadata(target_node_rel)
        if not self._audit_call(target_node_rel, meta):
            return None

        # 物理执行...
        return f"Execution_Success: {uri}"

    def _charge_metabolic_tax(self, uri: str) -> None:
        ledger = self._get_ledger()
        if ledger:
            # 基础税费：跨域调用 10 EU
            ledger.consume(10.0, f"Neural Impulse: {uri}")
        else:
            _log.info("  💸 [Tollbooth] 代谢税征收失败: 账本未就绪。")

    def _audit_call(self, path: str, meta: dict[str, object]) -> bool:
        return True

    def publish(self, event_type: str, payload: Any) -> None:
        _log.info("\n📢 [EventBus] 释放激素: [{event_type}]")
        if event_type in self.subscribers:
            for uri in self.subscribers[event_type]:
                self.call(uri, payload=payload)


Gateway = MembraneGateway()
