"""L0 告警引擎 — 基于规则的告警触发"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from .optimization import (
    AlertChannel,
    AlertHandler,
    AlertRule,
    AlertSeverity,
    GovernanceAlert,
)
from .primitives import CheckResult, CheckStatus


class LogHandler(AlertHandler):
    """日志告警处理器"""

    def __init__(self, log_path: str | Path):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def handle(self, alert: GovernanceAlert) -> bool:
        try:
            with open(self.log_path, "a") as f:
                f.write(json.dumps(alert.to_dict()) + "\n")
            return True
        except Exception:  # defensive fallback
            return False


class WebhookHandler(AlertHandler):
    """Webhook 告警处理器"""

    def __init__(self, url: str, timeout: int = 10):
        self.url = url
        self.timeout = timeout

    def handle(self, alert: GovernanceAlert) -> bool:
        try:
            import httpx

            response = httpx.post(
                self.url,
                json=alert.to_dict(),
                timeout=self.timeout,
            )
            return response.status_code == 200
        except Exception:  # defensive fallback
            return False


class AlertEngine:
    """告警引擎"""

    def __init__(self, rules_path: str | Path | None = None):
        self.rules: list[AlertRule] = []
        self.handlers: dict[AlertChannel, AlertHandler] = {}

        if rules_path:
            self.load_rules(rules_path)

    def load_rules(self, rules_path: str | Path) -> None:
        """加载告警规则"""
        path = Path(rules_path)
        if not path.exists():
            return

        with open(path) as f:
            data = yaml.safe_load(f) or {}

        for rule_data in data.get("rules", []):
            rule = AlertRule(
                rule_id=rule_data["id"],
                dimension=rule_data["dimension"],
                condition=rule_data["condition"],
                severity=AlertSeverity(rule_data["severity"]),
                channels=[AlertChannel(c) for c in rule_data.get("channels", ["log"])],
                enabled=rule_data.get("enabled", True),
            )
            self.rules.append(rule)

    def register_handler(self, channel: AlertChannel, handler: AlertHandler):
        """注册告警处理器"""
        self.handlers[channel] = handler

    def evaluate(self, check_results: list[CheckResult]) -> list[GovernanceAlert]:
        """评估检查结果，生成告警"""
        alerts = []

        for result in check_results:
            for rule in self.rules:
                if not rule.enabled:
                    continue
                if rule.dimension != result.dimension:
                    continue
                if self._match_condition(rule.condition, result):
                    alert = GovernanceAlert(
                        alert_id=f"alert-{rule.rule_id}-{result.check_id}",
                        severity=rule.severity,
                        dimension=result.dimension,
                        check_id=result.check_id,
                        message=result.message,
                        channels=rule.channels,
                    )
                    alerts.append(alert)

        return alerts

    def process(self, alerts: list[GovernanceAlert]) -> list[bool]:
        """处理告警"""
        results = []
        for alert in alerts:
            for channel in alert.channels:
                handler = self.handlers.get(channel)
                if handler:
                    success = handler.handle(alert)
                    results.append(success)
        return results

    def _match_condition(self, condition: str, result: CheckResult) -> bool:
        """匹配条件"""
        if condition == "fail" and result.status == CheckStatus.FAIL:
            return True
        if condition == "warn" and result.status == CheckStatus.WARN:
            return True
        if condition == "fail_or_warn" and result.status in [
            CheckStatus.FAIL,
            CheckStatus.WARN,
        ]:
            return True
        return False
