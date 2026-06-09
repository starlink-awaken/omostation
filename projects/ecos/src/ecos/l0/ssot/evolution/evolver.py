"""
ssot-kernel — evolution/evolver.py
====================================
进化引擎：串联 checkpoint → mine → suggest → apply → verify 闭环。

不自动执行任何修改。每一步都要人工确认。
"""

from __future__ import annotations

from pathlib import Path

from ..config_loader import load_domain
from ..engine import RuleEngine
from ..reporter import Reporter
from .checkpoint import CheckpointManager
from .rule_miner import EvolutionReport, RuleMiner, RuleSuggestion


class Evolver:
    """进化引擎——引导规则迭代的闭环流程"""

    def __init__(self, domain_dir: str):
        self.domain_dir = domain_dir
        self.cp = CheckpointManager(domain_dir)
        self.engine = RuleEngine()

    def analyze(self) -> EvolutionReport:
        """执行一轮进化分析：创建检查点 → 跑推导 → 挖规则 → 出建议

        不修改任何文件。只输出建议。
        """
        # 1. 创建检查点
        cp_name = self.cp.create("pre-evolve")

        # 2. 加载领域
        config = load_domain(self.domain_dir)

        # 3. 跑一次全量推导
        report = self.engine.execute(config)

        # 4. 挖掘规则建议
        miner = RuleMiner(config, report)
        suggestions = miner.mine_all()

        # 5. 排序（按置信度）
        suggestions.sort(key=lambda s: s.confidence, reverse=True)

        return EvolutionReport(
            suggestions=suggestions,
            checkpoint=cp_name,
            summary=f"发现 {len(suggestions)} 条潜在规则建议 (已自动创建检查点: {cp_name})",
        )

    def apply_suggestion(
        self, suggestion: RuleSuggestion, auto_confirm: bool = False
    ) -> bool:
        """应用一条规则建议到 rules.yaml

        Args:
            suggestion: 规则建议
            auto_confirm: 自动确认（跳过人工程序）

        Returns:
            是否成功应用
        """
        import yaml

        from ..config_loader import ConfigLoader

        rules_path = Path(self.domain_dir) / "rules.yaml"
        if not rules_path.exists():
            return False

        # 读取当前规则
        loader = ConfigLoader(self.domain_dir)
        existing = loader._load_yaml("rules") or {"rules": []}

        # 从 suggestion 构建规则条目
        new_rule = {
            "id": suggestion.id,
            "pattern": suggestion.pattern,
            "name": suggestion.name,
            "premises": [{"condition": c} for c in suggestion.conditions],
            "logic": suggestion.logic,
        }

        # 检查重复
        for rule in existing.get("rules", []):
            if rule.get("id") == new_rule["id"]:
                return False

        # 追加
        if "rules" not in existing:
            existing["rules"] = []
        existing["rules"].append(new_rule)

        # 写回
        rules_path.write_text(
            yaml.dump(
                existing, allow_unicode=True, default_flow_style=False, sort_keys=False
            ),
            encoding="utf-8",
        )
        return True

    def verify_evolution(self) -> str:
        """应用建议后，重新推导并对比前后结果"""
        config = load_domain(self.domain_dir)
        report = self.engine.execute(config)
        return Reporter.summary_line(report)
