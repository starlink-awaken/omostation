
"""OMO 预测性治理模块"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import yaml


@dataclass
class DebtRisk:
    debt_id: str
    risk_score: float
    predicted_deterioration_days: int
    recommended_action: str
    contributing_factors: list[str] = field(default_factory=list)


@dataclass
class RiskForecast:
    time_horizon_days: int
    high_risks: list[DebtRisk] = field(default_factory=list)
    medium_risks: list[DebtRisk] = field(default_factory=list)
    low_risks: list[DebtRisk] = field(default_factory=list)
    overall_risk_level: str = "unknown"
    key_trends: list[str] = field(default_factory=list)


@dataclass
class ProactiveAction:
    priority: int
    action: str
    rationale: str
    effort_estimate: str
    estimated_impact: str


class PredictiveGovernanceEngine:
    def __init__(self, omo_dir: Path):
        self.omo_dir = omo_dir
        self.debt_registry = self._load_debt_registry()

    def _load_debt_registry(self):
        debt_file = self.omo_dir / "_truth" / "registry" / "debt.yaml"
        if debt_file.exists():
            with open(debt_file, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}

    def predict_debt_deterioration(self, time_horizon_days=30):
        risks = []
        for debt in self.debt_registry.get("debts", []):
            risk_score = self._calculate_risk_score(debt)
            if risk_score > 0.6:
                risk = DebtRisk(
                    debt_id=debt.get("id", "unknown"),
                    risk_score=risk_score,
                    predicted_deterioration_days=7 if risk_score > 0.8 else 14,
                    recommended_action="立即处理" if risk_score &gt; 0.8 else "近期计划",
                    contributing_factors=[]
                )
                risks.append(risk)
        return sorted(risks, key=lambda r: r.risk_score, reverse=True)

    def _calculate_risk_score(self, debt):
        score = 0.5
        priority = debt.get("priority", "medium")
        if priority == "high":
            score += 0.2
        elif priority == "critical":
            score += 0.3
        return min(1.0, max(0.0, score))

    def forecast_governance_risks(self, time_horizon_days=7):
        debt_risks = self.predict_debt_deterioration(time_horizon_days)
        high_risks = [r for r in debt_risks if r.risk_score > 0.8]
        medium_risks = [r for r in debt_risks if 0.6 < r.risk_score <= 0.8]
        low_risks = [r for r in debt_risks if r.risk_score <= 0.6]
        
        if high_risks:
            overall = "high"
        elif medium_risks:
            overall = "medium"
        else:
            overall = "low"
        
        trends = []
        if high_risks:
            trends.append("有高风险债务")
        else:
            trends.append("风险趋势平稳")
        
        return RiskForecast(
            time_horizon_days=time_horizon_days,
            high_risks=high_risks,
            medium_risks=medium_risks,
            low_risks=low_risks,
            overall_risk_level=overall,
            key_trends=trends
        )

    def recommend_proactive_actions(self):
        forecast = self.forecast_governance_risks()
        actions = []
        if forecast.overall_risk_level == "high":
            actions.append(ProactiveAction(1, "处理高风险债务", "检测到高风险", "1-2天", "高"))
        actions.append(ProactiveAction(2, "健康检查", "定期检查", "1小时", "中"))
        return actions

    def generate_early_warning_alerts(self):
        forecast = self.forecast_governance_risks()
        alerts = []
        if forecast.overall_risk_level == "high":
            alerts.append({"severity": "warning", "message": "检测到高风险", "triggered_at": datetime.now(UTC).isoformat()})
        return alerts
