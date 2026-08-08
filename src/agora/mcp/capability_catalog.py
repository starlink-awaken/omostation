"""能力目录 (B1: 能力使用度量深化)。

从 etc/bos-services.yaml 构建 capability 索引, 结合 bos_metrics 的使用统计,
提供能力视角的观测: 每个 capability 的声明 (description/status) + 使用 (calls/
success_rate/stale_days) + 僵尸能力识别 (active 但长期零调用)。

用法:
    from agora.mcp.capability_catalog import capability_catalog

    catalog = capability_catalog.build()      # 从 bos-services.yaml 构建
    report = capability_catalog.report()      # 能力使用报告 + 僵尸候选
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

# capability 目录数据源: etc/bos-services.yaml (默认)
# src/agora/mcp/ → parents[3] = projects/agora 项目根
_DEFAULT_BOS_YAML = str(
    Path(__file__).resolve().parents[3] / "etc" / "bos-services.yaml"
)


class CapabilityCatalog:
    """能力目录: bos-services.yaml 声明 + metrics 使用统计。"""

    def __init__(self, bos_yaml: str = "") -> None:
        self._bos_yaml = bos_yaml or os.environ.get(
            "AGORA_BOS_REGISTRY", _DEFAULT_BOS_YAML
        )
        self._services: list[dict[str, Any]] = []
        self._capabilities: dict[str, dict[str, Any]] = {}
        self._loaded = False

    def load(self) -> dict[str, dict[str, Any]]:
        """从 bos-services.yaml 加载能力声明。"""
        try:
            path = Path(self._bos_yaml)
            if not path.exists():
                return {}
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            self._services = data.get("services", []) if data else []
            caps: dict[str, dict[str, Any]] = {}
            for svc in self._services:
                uri = svc.get("uri", "")
                if not uri or not uri.startswith("bos://"):
                    continue
                caps[uri] = {
                    "uri": uri,
                    "domain": svc.get("domain", ""),
                    "package": svc.get("package", ""),
                    "action": svc.get("action", ""),
                    "description": svc.get("description", ""),
                    "status": svc.get("status", "active"),
                    "transport": svc.get("transport", ""),
                }
            self._capabilities = caps
            self._loaded = True
            return caps
        except Exception:  # noqa: BLE001 — YAML 加载失败返回空 (defensive fallback, 对齐 bos_metrics)
            return {}

    def get(self, uri: str, stale_days: float = 7.0) -> dict[str, Any] | None:
        """获取单个能力声明 (B2: 语义路由准入校验用)。

        返回**有效状态** — active 声明但使用度量显示僵尸
        (超过 stale_days 零调用) 时, status 覆写为 deprecated 并附 zombie: true,
        使语义路由 (resolve_with_capability) 自动拦截僵尸能力 (闭环)。
        """
        if not self._loaded:
            self.load()
        decl = self._capabilities.get(uri)
        if decl is None or decl.get("status") != "active":
            return decl
        # 延迟取模块属性: 使测试 monkeypatch bos_metrics 生效 (from-import 是值绑定)
        from agora.mcp import bos_metrics as _bm

        usage = _bm.bos_metrics.capability_status().get("capabilities", {}).get(uri, {})
        # 僵尸判定: 仅当 metrics 有该能力的历史记录 (stale_days 为实际值)
        # 且超过阈值才判定。无记录 = 未开始使用, 不视为僵尸 (避免误杀新能力)。
        sd = usage.get("stale_days")
        if sd is not None and sd > stale_days:
            effective = dict(decl)
            effective["status"] = "deprecated"
            effective["zombie"] = True
            effective["stale_days"] = sd
            effective["calls"] = usage.get("calls", 0)
            return effective
        return decl

    def report(self, stale_days: float = 7.0, min_calls: int = 0) -> dict[str, Any]:
        """能力使用报告。

        Args:
            stale_days: 僵尸判定阈值 (active 且 N 天零调用)
            min_calls: 最少调用数过滤 (0 = 全返回)

        Returns:
            { capabilities: {...}, count, stale_candidates: [...], total }
        """
        if not self._loaded:
            self.load()
        # 延迟取模块属性: 使测试 monkeypatch bos_metrics 生效 (from-import 是值绑定)
        from agora.mcp import bos_metrics as _bm

        usage = _bm.bos_metrics.capability_status().get("capabilities", {})

        report: dict[str, dict[str, Any]] = {}
        for uri, decl in self._capabilities.items():
            entry = dict(decl)
            entry["usage"] = usage.get(uri, {})
            entry["calls"] = usage.get(uri, {}).get("calls", 0)
            report[uri] = entry

        # 僵尸能力: active 声明但超过 stale_days 无调用 (或从未被调用)
        stale_candidates = [
            {
                "uri": uri,
                "description": e.get("description", ""),
                "calls": e["calls"],
                "status": e.get("status", ""),
            }
            for uri, e in report.items()
            if e.get("status") == "active"
            and e["calls"] <= min_calls
            and e.get("usage", {}).get("stale_days", stale_days + 1) > stale_days
        ]

        return {
            "capabilities": report,
            "count": len(report),
            "active": len([e for e in report.values() if e.get("status") == "active"]),
            "stale_candidates": stale_candidates,
            "stale_count": len(stale_candidates),
            "bos_yaml": self._bos_yaml,
        }

    # ── P3: 能力目录写闭环 (add/save/retire) ─────────────────────

    def add(self, uri: str, description: str = "", status: str = "active") -> None:
        """新增能力声明 (内存 + 写回 bos-services.yaml).

        P3: bos_capability_admit 的死代码修复 — CapabilityCatalog 此前无 add/save。
        """
        if not self._loaded:
            self.load()
        self._capabilities[uri] = {
            "uri": uri,
            "domain": uri.split("/")[2] if uri.count("/") >= 2 else "capability",
            "package": uri.split("/")[3] if uri.count("/") >= 3 else "",
            "action": uri.split("/")[4] if uri.count("/") >= 4 else "",
            "description": description,
            "status": status,
            "transport": "internal",
        }
        self.save()

    def retire(self, uri: str, reason: str = "") -> bool:
        """将能力标记为 deprecated (写回 YAML).

        P3: bos_capability_retire 的支持方法 — 显式改状态 + 持久化。
        """
        if not self._loaded:
            self.load()
        decl = self._capabilities.get(uri)
        if decl is None:
            return False
        decl["status"] = "deprecated"
        if reason:
            decl["retire_reason"] = reason
        self.save()
        return True

    def save(self) -> bool:
        """将能力目录写回 bos-services.yaml (持久化).

        保留原有 services 顺序与字段, 更新/追加 changed 条目。
        失败 (文件不可写/解析错误) 返回 False, 不抛异常 (内存目录仍生效)。
        """
        try:
            path = Path(self._bos_yaml)
            if not path.exists():
                return False
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            services = data.get("services", [])
            # uri → index
            by_uri = {s.get("uri"): i for i, s in enumerate(services) if s.get("uri")}
            for uri, cap in self._capabilities.items():
                entry = {
                    "uri": uri,
                    "domain": cap.get("domain", ""),
                    "package": cap.get("package", ""),
                    "action": cap.get("action", ""),
                    "description": cap.get("description", ""),
                    "status": cap.get("status", "active"),
                    "transport": cap.get("transport", "internal"),
                }
                if uri in by_uri:
                    services[by_uri[uri]] = entry
                else:
                    services.append(entry)
                    by_uri[uri] = len(services) - 1
            data["services"] = services
            with path.open("w", encoding="utf-8") as f:
                yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
            return True
        except Exception:  # noqa: BLE001 — 写失败不阻塞 (内存目录仍可用)
            return False


# ── 全局单例 ──
capability_catalog = CapabilityCatalog()
