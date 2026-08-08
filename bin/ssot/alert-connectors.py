#!/usr/bin/env python3
"""告警连接器 (channel kind) — 告警到人 via 外部连接器 (fabric 对齐).

设计: docs/observability-unified-architecture.md §5.1 + external-connection-fabric.md
对齐 external-connection-fabric (channel kind + deliver/receipt/suppress 能力):
  - 连接器实现 external_descriptor() / health_probe() / deliver()
  - deliver 返回 ConnectionReceipt (receipt_id / result_state / provider)
  - 凭据 opaque 引用 (url_ref = env://ALERT_<PROVIDER>_WEBHOOK, secret_policy: credential_ref_only)

用法 (由 observability-events.py notify 调用, 或独立):
  python3 bin/ssot/alert-connectors.py list          # 列出已配置 channel
  python3 bin/ssot/alert-connectors.py health        # 探活所有 channel
  python3 bin/ssot/alert-connectors.py send --provider slack --severity critical --title X --body Y
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[2]
CHANNELS_REGISTRY = WORKSPACE / ".omo" / "_truth" / "registry" / "alert-channels.yaml"
EVENTS_SCRIPT = WORKSPACE / "bin" / "ssot" / "observability-events.py"


def _load_channels() -> list[dict[str, Any]]:
    try:
        import yaml
        docs = [d for d in yaml.safe_load_all(CHANNELS_REGISTRY.read_text(encoding="utf-8")) if d]
        return (docs[-1] if docs else {}).get("channels") or []
    except (OSError, ImportError, yaml.YAMLError):
        return []


def _resolve_url(url_ref: str) -> str:
    """凭据 opaque 引用 → 环境变量 (fabric secret_policy: credential_ref_only)."""
    if url_ref.startswith("env://"):
        return os.environ.get(url_ref[len("env://"):], "")
    return url_ref


def _emit_receipt(channel_id: str, provider: str, result_state: str, alert: dict[str, Any]) -> None:
    """送达回执 → 事件面 (governance:alert_delivered / alert_delivery_failed)."""
    if not EVENTS_SCRIPT.exists():
        return
    try:
        payload = json.dumps({
            "channel": channel_id, "provider": provider, "result_state": result_state,
            "alert": alert,
        }, ensure_ascii=False)
        event_type = "governance:alert_delivered" if result_state == "delivered" else "governance:alert_delivery_failed"
        subprocess_run = [
            "python3", str(EVENTS_SCRIPT), "emit",
            "--domain", "governance", "--type", event_type,
            "--severity", "info" if result_state == "delivered" else "warning",
            "--source", f"alert-connector:{provider}", "--payload", payload,
        ]
        import subprocess
        subprocess.run(subprocess_run, capture_output=True, check=False, timeout=30)
    except Exception:  # noqa: BLE001
        pass


class AlertConnector(ABC):
    """channel kind 连接器抽象 (fabric ExternalResourceDescriptor 对齐)."""

    kind = "channel"
    protocol = "https-webhook"
    capabilities = ("deliver", "receipt", "health")
    provider = ""  # slack / feishu / wecom / generic

    def __init__(self, channel_id: str, url_ref: str, owner: str = "governance-team") -> None:
        self.channel_id = channel_id
        self.url_ref = url_ref
        self.owner = owner

    def external_descriptor(self) -> dict[str, Any]:
        """fabric ExternalResourceDescriptor (required_fields 12 项对齐)."""
        return {
            "id": self.channel_id,
            "kind": self.kind,
            "provider": self.provider,
            "protocol": self.protocol,
            "capabilities": list(self.capabilities),
            "data_classification": "internal",
            "provenance": {"source": "alert-connectors.py", "observed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
            "lifecycle": "active",
            "health": self.health_probe(),
            "owner": self.owner,
            "version": "1.0",
            "permission_ref": f"credential://alert/{self.channel_id}",
            "mode": "approved_delivery",
        }

    def health_probe(self) -> dict[str, Any]:
        """只读探活: 仅检查 URL 已配置 (不发请求)."""
        url = _resolve_url(self.url_ref)
        if not url:
            return {"status": "unhealthy", "source": "alert-connectors", "observed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "latency_ms": 0, "reason": "url not configured"}
        return {"status": "healthy", "source": "alert-connectors", "observed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "latency_ms": 0}

    @abstractmethod
    def deliver(self, alert: dict[str, Any]) -> dict[str, Any]:
        """发送告警到人, 返回 ConnectionReceipt."""

    def _post(self, payload: dict[str, Any], timeout: int = 10) -> dict[str, Any]:
        url = _resolve_url(self.url_ref)
        if not url:
            return {"result_state": "failed", "receipt_id": f"rcpt_{int(time.time())}", "error": "url not configured", "provider": self.provider}
        try:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                resp.read()
            return {"result_state": "delivered", "receipt_id": f"rcpt_{int(time.time())}", "provider": self.provider, "http_status": resp.status}
        except Exception as exc:  # noqa: BLE001
            return {"result_state": "failed", "receipt_id": f"rcpt_{int(time.time())}", "error": str(exc)[:160], "provider": self.provider}


class SlackWebhookConnector(AlertConnector):
    provider = "slack"

    def deliver(self, alert: dict[str, Any]) -> dict[str, Any]:
        return self._post({
            "text": f"[{alert.get('severity', 'info').upper()}] {alert.get('title', 'alert')}\n{alert.get('body', '')}",
        })


class FeishuWebhookConnector(AlertConnector):
    provider = "feishu"

    def deliver(self, alert: dict[str, Any]) -> dict[str, Any]:
        return self._post({
            "msg_type": "text",
            "content": {"text": f"[{alert.get('severity', 'info').upper()}] {alert.get('title', 'alert')}\n{alert.get('body', '')}"},
        })


class WeComWebhookConnector(AlertConnector):
    provider = "wecom"

    def deliver(self, alert: dict[str, Any]) -> dict[str, Any]:
        return self._post({
            "msgtype": "text",
            "text": {"content": f"[{alert.get('severity', 'info').upper()}] {alert.get('title', 'alert')}\n{alert.get('body', '')}"},
        })


class GenericWebhookConnector(AlertConnector):
    provider = "generic"

    def deliver(self, alert: dict[str, Any]) -> dict[str, Any]:
        return self._post({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **alert})


_CONNECTORS: dict[str, type[AlertConnector]] = {
    "slack": SlackWebhookConnector,
    "feishu": FeishuWebhookConnector,
    "wecom": WeComWebhookConnector,
    "generic": GenericWebhookConnector,
}


def build_connectors() -> list[AlertConnector]:
    """从 alert-channels.yaml 构建连接器实例 (enabled 且 URL 可解析)."""
    out: list[AlertConnector] = []
    for ch in _load_channels():
        if not ch.get("enabled", True):
            continue
        provider = str(ch.get("provider", "generic"))
        cls = _CONNECTORS.get(provider, GenericWebhookConnector)
        conn = cls(channel_id=str(ch.get("id", "alert-unknown")), url_ref=str(ch.get("url_ref", "")))
        out.append(conn)
    return out


def route_connector(severity: str, domain: str = "governance") -> AlertConnector | None:
    """按 severity/domain 路由到 channel (alert-channels.yaml routes 匹配)."""
    for ch in _load_channels():
        if not ch.get("enabled", True):
            continue
        routes = ch.get("routes") or {}
        sev_list = routes.get("severity") or []
        dom_list = routes.get("domains") or []
        if severity in sev_list and (not dom_list or domain in dom_list):
            provider = str(ch.get("provider", "generic"))
            cls = _CONNECTORS.get(provider, GenericWebhookConnector)
            return cls(channel_id=str(ch.get("id", "alert-unknown")), url_ref=str(ch.get("url_ref", "")))
    return None


def cmd_list() -> int:
    for ch in _load_channels():
        url = _resolve_url(str(ch.get("url_ref", "")))
        print(f"{ch.get('id', '?'):<20} {ch.get('provider', '?'):<10} "
              f"routes={ch.get('routes', {})} url_configured={'yes' if url else 'NO'}")
    return 0


def cmd_health() -> int:
    ok = True
    for conn in build_connectors():
        h = conn.health_probe()
        mark = "✅" if h.get("status") == "healthy" else "❌"
        print(f"  {mark} {conn.channel_id} ({conn.provider}): {h.get('status')} - {h.get('reason', '')}")
        if h.get("status") != "healthy":
            ok = False
    return 0 if ok else 1


def cmd_send(args: argparse.Namespace) -> int:
    alert = {"severity": args.severity, "title": args.title, "body": args.body}
    conn: AlertConnector | None = None
    if args.channel:
        for c in build_connectors():
            if c.channel_id == args.channel:
                conn = c
                break
    else:
        conn = route_connector(args.severity, args.domain)
    if conn is None:
        print(f"❌ no channel for severity={args.severity} domain={args.domain}", file=sys.stderr)
        return 1
    receipt = conn.deliver(alert)
    print(f"  {conn.channel_id} ({conn.provider}): {receipt.get('result_state')} "
          f"rcpt={receipt.get('receipt_id', '?')} {receipt.get('error', '')}")
    _emit_receipt(conn.channel_id, conn.provider, receipt.get("result_state", "failed"), alert)
    return 0 if receipt.get("result_state") == "delivered" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list").set_defaults(func=lambda _a: cmd_list())
    sub.add_parser("health").set_defaults(func=lambda _a: cmd_health())
    send = sub.add_parser("send")
    send.add_argument("--channel")
    send.add_argument("--severity", default="warning", choices=["info", "warning", "degraded", "critical"])
    send.add_argument("--domain", default="governance")
    send.add_argument("--title", required=True)
    send.add_argument("--body", default="")
    send.set_defaults(func=cmd_send)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
