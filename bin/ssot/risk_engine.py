#!/usr/bin/env python3
"""Risk Engine — 动态风险策略引擎.

5层决策 (L0-L4), 基于风险评估公式 + Trust积累 + LLM评估.
驱动所有 agent action 的安全策略.

Levels:
  L0 全自动 | L1 自动+通知 | L2 预览+确认 | L3 审阅+批准 | L4 禁止

Usage:
  from risk_engine import RiskEngine, Action
  engine = RiskEngine()
  decision = engine.evaluate(Action(type="send_email", target="leader"))
  if decision.can_execute():
      execute()
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from _shared import ROOT, utc_now

# ── 风险因子权重 ──────────────────────────────────────────

ACTION_BASE_RISK = {
    "read": 1, "classify": 1, "scan": 1,
    "write": 2, "generate": 2, "draft": 2, "create_doc": 2,
    "forward": 4, "send_email": 5, "submit": 6,
    "modify": 5, "archive": 3,
    "delete": 9, "publish": 8, "modify_permission": 10,
}

TARGET_MULTIPLIER = {
    "self": 0.5, "internal": 0.8, "subordinate": 1.5,
    "leader": 2.5, "external": 4.0, "public": 5.0,
}

REVERSIBILITY = {
    "undoable": 0.5, "replaceable": 1.0, "permanent": 2.0,
}

SENSITIVITY = {
    "routine": 1.0, "internal": 1.5, "confidential": 2.5, "secret": 4.0,
}

# ── 决策等级 ──────────────────────────────────────────────

LEVELS = {
    "L0": {"max_risk": 2, "label": "全自动", "requires_human": False},
    "L1": {"max_risk": 4, "label": "自动+通知", "requires_human": False},
    "L2": {"max_risk": 6, "label": "预览+确认", "requires_human": True, "confirm_type": "one_click"},
    "L3": {"max_risk": 8, "label": "审阅+批准", "requires_human": True, "confirm_type": "full_review"},
    "L4": {"max_risk": 99, "label": "禁止", "requires_human": True, "confirm_type": "never"},
}


@dataclass
class Action:
    """待评估的动作."""
    type: str = ""
    target: str = "self"
    content: str = ""
    reversibility: str = "replaceable"
    sensitivity: str = "routine"
    confidence: float = 0.8
    domain: str = "work"
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class Decision:
    """风险评估结果."""
    level: str = "L3"
    risk_score: float = 5.0
    strategy: str = "review"
    reasoning: str = ""
    trust_adjusted: bool = False

    def can_auto_execute(self) -> bool:
        return self.level in ("L0", "L1")

    def needs_confirmation(self) -> bool:
        return self.level in ("L2", "L3")

    def is_forbidden(self) -> bool:
        return self.level == "L4"


# ── Trust 积累存储 ────────────────────────────────────────

TRUST_FILE = ROOT / ".omo" / "state" / "risk-trust.json"


def _load_trust() -> dict[str, dict]:
    if not TRUST_FILE.exists():
        return {}
    try:
        return json.loads(TRUST_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_trust(data: dict) -> None:
    TRUST_FILE.parent.mkdir(parents=True, exist_ok=True)
    TRUST_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _trust_key(action: Action) -> str:
    return f"{action.type}:{action.target}"


# ── 域策略覆盖 ────────────────────────────────────────────

DOMAIN_OVERRIDES = {
    "work": {
        "send_email:subordinate": "L2",  # 预览+确认
        "send_email:leader": "L3",       # 审阅+批准
        "send_email:external": "L4",     # 禁止自动
        "submit:superior": "L3",         # 审阅+批准
        "forward:subordinate": "L2",     # 预览+确认
        "generate:self": "L0",           # 全自动
        "read:self": "L0",               # 全自动
    },
    "family": {"send_email:spouse": "L0", "send_email:child": "L1"},
    "health": {"generate:report": "L0", "send_email:doctor": "L2"},
    "personal": {"generate:note": "L0"},
}


class RiskEngine:
    """动态风险策略引擎 — 单例, 所有 agent 共享."""

    def evaluate(self, action: Action) -> Decision:
        """评估 action 风险, 返回决策."""
        # 1. 计算基础 risk score
        base = ACTION_BASE_RISK.get(action.type, 5)
        target_mult = TARGET_MULTIPLIER.get(action.target, 2.0)
        revers = REVERSIBILITY.get(action.reversibility, 1.0)
        sens = SENSITIVITY.get(action.sensitivity, 1.5)
        conf_factor = 0.8 if action.confidence > 0.9 else (1.0 if action.confidence > 0.6 else 1.5)

        risk_score = base * target_mult * revers * sens * conf_factor

        # 2. 映射到等级
        level = self._risk_to_level(risk_score)

        # 3. 域策略覆盖
        override_key = f"{action.type}:{action.target}"
        domain_overrides = DOMAIN_OVERRIDES.get(action.domain, {})
        if override_key in domain_overrides:
            level = domain_overrides[override_key]

        # 4. Trust 动态调整
        trust = _load_trust()
        key = _trust_key(action)
        trust_data = trust.get(key, {"score": 0.5, "success": 0, "fail": 0})

        trust_adjusted = False
        if trust_data["success"] >= 10 and trust_data["score"] > 0.8 and level != "L0":
            # 降一级 (L3→L2, L2→L1)
            levels_list = list(LEVELS.keys())
            idx = levels_list.index(level)
            if idx > 0:
                level = levels_list[idx - 1]
                trust_adjusted = True
        elif trust_data["fail"] > 0 and trust_data["score"] < 0.3:
            # 升一级
            levels_list = list(LEVELS.keys())
            idx = levels_list.index(level)
            if idx < len(levels_list) - 1:
                level = levels_list[idx + 1]
                trust_adjusted = True

        strategy = LEVELS[level]["label"]

        return Decision(
            level=level,
            risk_score=round(risk_score, 1),
            strategy=strategy,
            reasoning=f"base={base} target={target_mult}x revers={revers} sens={sens} conf={conf_factor} trust={trust_data['score']}",
            trust_adjusted=trust_adjusted,
        )

    def evaluate_unknown(self, action: Action) -> Decision:
        """LLM 评估未知 action 的风险 (通过 AetherForge 算力)."""
        try:
            from _llm_helper import llm_ask

            response = llm_ask(
                f"评估以下动作的风险 (0-10分) 并建议决策等级:\n"
                f"动作类型: {action.type}\n目标: {action.target}\n"
                f"内容: {action.content[:200]}\n域: {action.domain}\n"
                f"输出 JSON: {{\"risk_score\": N, \"level\": \"L0-L4\", \"reasoning\": \"...\"}}",
                timeout=20.0,
            )
            if response:
                import re
                m = re.search(r'\{[^{}]*"risk_score"[^{}]*\}', response)
                if m:
                    import json
                    parsed = json.loads(m.group())
                    return Decision(
                        level=parsed.get("level", "L3"),
                        risk_score=float(parsed.get("risk_score", 5)),
                        strategy=LEVELS.get(parsed.get("level", "L3"), {}).get("label", "审阅+批准"),
                        reasoning=f"LLM: {parsed.get('reasoning', '')[:100]}",
                    )
        except Exception:
            pass
        return Decision(level="L3", risk_score=7.0, strategy="审阅+批准", reasoning="LLM评估失败, 默认保守")

    def _risk_to_level(self, risk: float) -> str:
        for level_id, config in LEVELS.items():
            if risk <= config["max_risk"]:
                return level_id
        return "L4"

    def record_outcome(self, action: Action, success: bool) -> None:
        """记录 action 执行结果, 更新 trust."""
        trust = _load_trust()
        key = _trust_key(action)
        data = trust.get(key, {"score": 0.5, "success": 0, "fail": 0})

        if success:
            data["success"] += 1
            data["score"] = min(1.0, data["score"] + 0.1)
        else:
            data["fail"] += 1
            data["score"] = max(0.0, data["score"] - 0.5)

        data["last_updated"] = utc_now()
        trust[key] = data
        _save_trust(trust)


# ── CLI ──────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--type", required=True, help="action type")
    parser.add_argument("--target", default="self")
    parser.add_argument("--sensitivity", default="routine", choices=list(SENSITIVITY.keys()))
    parser.add_argument("--domain", default="work")
    parser.add_argument("--confidence", type=float, default=0.8)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    engine = RiskEngine()
    action = Action(
        type=args.type, target=args.target,
        sensitivity=args.sensitivity, domain=args.domain,
        confidence=args.confidence,
    )
    decision = engine.evaluate(action)

    if args.json:
        print(json.dumps({
            "action": args.type, "target": args.target,
            "level": decision.level, "risk_score": decision.risk_score,
            "strategy": decision.strategy, "reasoning": decision.reasoning,
            "trust_adjusted": decision.trust_adjusted,
        }, ensure_ascii=False, indent=2))
    else:
        print(f"动作: {args.type} → {args.target}")
        print(f"等级: {decision.level} ({decision.strategy})")
        print(f"风险: {decision.risk_score}")
        print(f"自动执行: {'✅' if decision.can_auto_execute() else '❌'}")
        if decision.trust_adjusted:
            print(f"⚠️ Trust调整: 等级已根据历史记录动态调整")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
