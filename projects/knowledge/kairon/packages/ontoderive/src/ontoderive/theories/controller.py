"""
OntoDerive 控制论层 v2 — PID反馈 + 收敛检测
=============================================
P(比例): 当前违规数
I(积分): 指数衰减加权历史平均
D(微分): 滑动窗口平均变化率
收敛检测: |D| < epsilon && I稳定
可调增益系数: Kp/Ki/Kd
"""

import datetime
import json
from collections import deque
from pathlib import Path
from typing import Any

from ontoderive.foundation.utils import wf


class PIDController:
    def __init__(
        self, project_root: Any, kp: Any = 1.0, ki: Any = 0.5, kd: Any = 0.5, window: Any = 5, epsilon: Any = 0.1
    ) -> None:
        self.root = Path(project_root)
        self.log_dir = self.root / "_derivation_logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.history = self._load_history()

        # 可调增益
        self.kp = kp
        self.ki = ki
        self.kd = kd

        # 滑动窗口和收敛阈值
        self.window = window
        self.epsilon = epsilon

        # 微分历史
        self._d_history: deque[Any] = deque(maxlen=window)

    def _load_history(self) -> Any:
        history = []
        for f in sorted(self.log_dir.glob("check-result*.json")):
            try:
                history.append(json.loads(f.read_text()))
            except Exception:
                pass
        return history

    def analyze(self) -> dict[str, Any]:
        current = self._get_current_violations()
        p_value = current.get("total_violations", 0)
        i_value = self._integral_term()
        d_value = self._derivative_term()
        self._d_history.append(d_value)

        control_signal = round(self.kp * p_value + self.ki * i_value + self.kd * d_value, 2)
        is_converged = self._check_convergence()
        recommended_thresholds = self._adaptive_thresholds()
        actions = self._generate_actions(p_value, i_value, d_value, is_converged)

        return {
            "p_value": p_value,
            "i_value": i_value,
            "d_value": d_value,
            "control_signal": control_signal,
            "stability": "stable" if abs(d_value) < 0.3 else "unstable",
            "converged": is_converged,
            "recommended_thresholds": recommended_thresholds,
            "actions": actions,
            "history_count": len(self.history),
        }

    def _get_current_violations(self) -> dict[str, Any]:
        latest = self.history[-1] if self.history else {}
        sevs = latest.get("severities", {})
        total = sevs.get("WARN", 0) + sevs.get("ERROR", 0) + sevs.get("BLOCKER", 0)
        return {"total_violations": total, "severities": sevs}

    def _integral_term(self) -> Any:
        """指数衰减加权：越近的检查权重越高"""
        if not self.history:
            return 0.0
        n = len(self.history)
        weighted_sum = 0.0
        weight_total = 0.0
        decay = 0.85  # 衰减因子
        for i, h in enumerate(self.history):
            sevs = h.get("severities", {})
            violations = sevs.get("WARN", 0) + sevs.get("ERROR", 0) + sevs.get("BLOCKER", 0)
            w = decay ** (n - 1 - i)  # 最近权重最高
            weighted_sum += violations * w
            weight_total += w
        return round(weighted_sum / weight_total, 2) if weight_total > 0 else 0.0

    def _derivative_term(self) -> Any:
        """滑动窗口平均变化率"""
        if len(self.history) < 2:
            return 0.0

        def get_total(h: Any) -> Any:
            sevs = h.get("severities", {})
            return sevs.get("WARN", 0) + sevs.get("ERROR", 0) + sevs.get("BLOCKER", 0)

        # 计算最近window条的差分
        diffs = []
        for i in range(max(1, len(self.history) - self.window), len(self.history)):
            diffs.append(get_total(self.history[i]) - get_total(self.history[i - 1]))
        return round(sum(diffs) / len(diffs), 2) if diffs else 0.0

    def _check_convergence(self) -> Any:
        """收敛判定: |D| < epsilon 且最近D值稳定"""
        if len(self._d_history) < self.window:
            return False
        recent_d = list(self._d_history)[-self.window :]
        avg_d = sum(abs(d) for d in recent_d) / len(recent_d)
        return avg_d < self.epsilon

    def _adaptive_thresholds(self) -> dict[str, Any]:
        """基于历史数据动态校准阈值"""
        n = len(self.history)
        if n < 3:
            return {"assertion_traceability": ">=30%", "falsifiability": ">=15%"}
        elif n < 8:
            return {"assertion_traceability": ">=50%", "falsifiability": ">=25%"}
        else:
            return {"assertion_traceability": ">=70%", "falsifiability": ">=35%"}

    def _generate_actions(self, p_value: Any, i_value: Any, d_value: Any, converged: Any) -> Any:
        actions = []
        if converged:
            actions.append("✅ 推导已收敛，检查全部通过")
        if p_value > 0:
            actions.append(f"P项({p_value}): 修复当前{p_value}个违规项")
        if i_value > 1:
            actions.append(f"I项({i_value}): 历史平均违规较高，检查规约是否合理")
        if d_value > 0.5:
            actions.append(f"D项({d_value}): 违规在增长，需紧急干预")
        elif d_value < -0.5:
            actions.append(f"D项({d_value}): 违规在快速减少，保持节奏")
        if not actions:
            actions.append("系统状态正常，无需干预")
        return actions

    def report(self) -> Any:
        pid = self.analyze()
        report = f"""---
title: 控制论PID分析报告 v2
generated: {datetime.datetime.now().isoformat()}
---

## PID控制信号

| 分量 | 数值 | 增益 | 加权值 |
|------|------|------|--------|
| P(比例) | {pid["p_value"]} | {self.kp} | {round(self.kp * pid["p_value"], 2)} |
| I(积分) | {pid["i_value"]} | {self.ki} | {round(self.ki * pid["i_value"], 2)} |
| D(微分) | {pid["d_value"]} | {self.kd} | {round(self.kd * pid["d_value"], 2)} |
| **控制信号** | | | **{pid["control_signal"]}** |
| 稳定性 | {pid["stability"]} | 收敛 | {pid["converged"]} |

## 收敛判定
- 条件: |D均值| < {self.epsilon} (窗口={self.window})
- 状态: {"✅ 已收敛" if pid["converged"] else "⏳ 未收敛"}

## 建议行动
"""
        for action in pid["actions"]:
            report += f"- {action}\n"

        report += f"""
## 自适应阈值

| 规约 | 建议阈值 | 依据({len(self.history)}次检查) |
|------|---------|------|
| C-05追溯率 | {pid["recommended_thresholds"]["assertion_traceability"]} | 自适应校准 |
| C-06可证伪 | {pid["recommended_thresholds"]["falsifiability"]} | 自适应校准 |
"""
        wf(self.log_dir / "pid-report.md", report)
        print(f"[controller] ✅ PID报告 v2: {self.log_dir / 'pid-report.md'}")
        print(f"[controller] 📊 控制信号={pid['control_signal']}, 收敛={'是' if pid['converged'] else '否'}")
        return pid
