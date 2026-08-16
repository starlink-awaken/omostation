"""
OntoDerive 信息论层 v2 — 知识质量指数(KQI)与历史追踪
========================================================
使用贝叶斯网络真实置信度分布计算KQI。
新增：KQI历史追踪、趋势分析、信息增益引导。
"""

import datetime
import math
import re
from pathlib import Path
from typing import Any

from ontoderive.foundation.utils import all_md, load_json, rf, save_json, wf  # type: ignore[import-not-found,no-redef]


class MetricsLayer:
    def __init__(self, project_root: Any) -> None:
        self.root = Path(project_root)
        self.facts_dir = self.root / "facts"
        self.entities_dir = self.root / "entities"
        self.inferences_dir = self.root / "inferences"
        self.scheme_dir = self.root / "scheme"
        self.log_dir = self.root / "_derivation_logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._history_path = self.log_dir / "kqi_history.json"

    def entropy(self, probabilities: Any) -> Any:
        h = 0
        for p in probabilities:
            if 0 < p < 1:
                h += -p * math.log2(p) - (1 - p) * math.log2(1 - p)
        return round(h, 4)

    def get_real_confidences(self) -> tuple[Any, ...]:
        """尝试从贝叶斯网络获取真实置信度分布"""
        try:
            from .bayesian import BayesianLayer
        except ImportError:
            from bayesian import BayesianLayer  # type: ignore[import-not-found,no-redef]

        bl = BayesianLayer(self.root)
        facts, inferences = bl.propagate_all()
        fact_confs = [f["confidence"] for f in facts.values()]
        inf_confs = [i["propagated_confidence"] for i in inferences.values() if i["propagated_confidence"]]
        if not inf_confs:
            inf_confs = [i["base_confidence"] for i in inferences.values()]
        return fact_confs, inf_confs, len(facts), len(inferences)

    def compute_kqi(self, use_bayesian: Any = True, precomputed_confs: Any = None) -> Any:
        """
        KQI知识质量指数。公式: 0.25*熵 + 0.25*覆盖 + 0.20*密度 + 0.15*实体 + 0.15*方案。
        ⚠️ 权重未经经验校准，仅供参考。基准值: 空项目KQI≈0.5, z-park KQI≈0.44。
        """
        facts_text = ""
        for f in all_md(self.facts_dir):
            facts_text += rf(f)
        fact_ids = set(re.findall(r"(D-F\d+|P-F\d+)", facts_text))
        n_facts = len(fact_ids)

        infs_text = ""
        for f in all_md(self.inferences_dir):
            infs_text += rf(f)
        inf_blocks = len(re.findall(r"^##\s+", infs_text, re.MULTILINE))
        n_inferences = max(0, inf_blocks - 1)

        entities_text = ""
        for f in all_md(self.entities_dir):
            entities_text += rf(f)
        n_entities = len(set(re.findall(r"\*\*(ORG-[\w-]+|ROL-[\w-]+|PRJ-[\w-]+)\*\*", entities_text)))

        scheme_text = ""
        for f in all_md(self.scheme_dir):
            scheme_text += rf(f)
        n_scheme_files = len(all_md(self.scheme_dir))

        traced = sum(1 for fid in fact_ids if fid in scheme_text)
        coverage = traced / n_facts if n_facts > 0 else 1.0

        # 置信度分布：优先使用预计算结果（Pipeline传递），否则自己算
        if precomputed_confs:
            all_confs = precomputed_confs.get("facts", []) + precomputed_confs.get("inferences", [])
        elif use_bayesian and n_facts > 0:
            try:
                fact_confs, inf_confs, _, _ = self.get_real_confidences()
                all_confs = fact_confs + inf_confs
            except Exception:
                all_confs = [0.95] * n_facts + [0.85] * n_inferences
        else:
            all_confs = [0.95] * n_facts + [0.85] * n_inferences

        h_total = self.entropy(all_confs)
        mean_conf = sum(all_confs) / len(all_confs) if all_confs else 0
        density = n_inferences / n_facts if n_facts > 0 else 0

        # 推导链深度（最长/平均）
        max_depth = self._estimate_chain_depth(n_facts, n_inferences)

        kqi = round(
            (
                0.25 * (1 - h_total / max(n_facts + n_inferences, 1))
                + 0.25 * coverage
                + 0.20 * min(density / 0.5, 1.0)
                + 0.15 * min(n_entities / max(n_facts, 1), 1.0)
                + 0.15 * min(n_scheme_files / 3, 1.0)
            ),
            4,
        )

        result = {
            "kqi": kqi,
            "entropy": h_total,
            "mean_confidence": round(mean_conf, 4),
            "n_facts": n_facts,
            "n_inferences": n_inferences,
            "n_entities": n_entities,
            "n_scheme_files": n_scheme_files,
            "coverage": round(coverage, 4),
            "density": round(density, 4),
            "max_chain_depth": max_depth,
        }

        # 保存KQI历史
        self._save_history(result)
        return result

    def _estimate_chain_depth(self, n_facts: Any, n_inferences: Any) -> Any:
        if n_facts == 0 or n_inferences == 0:
            return 0
        try:
            from .logic import build_from_project
        except ImportError:
            from logic import build_from_project  # type: ignore[import-not-found,no-redef]
        g = build_from_project(self.root)
        return g.chain_depths()["max"]

    def _save_history(self, kqi_data: Any) -> None:
        history = load_json(self._history_path) or {"entries": []}
        entry = {"timestamp": datetime.datetime.now().isoformat(), **kqi_data}
        history["entries"].append(entry)
        # 保留最近100条
        if len(history["entries"]) > 100:
            history["entries"] = history["entries"][-100:]
        save_json(self._history_path, history)

    def get_kqi_trend(self, window: Any = 5) -> dict[str, Any]:
        """分析最近N条KQI记录的趋势"""
        history = load_json(self._history_path) or {"entries": []}
        entries = history["entries"]
        if len(entries) < 2:
            return {"trend": "insufficient_data", "slope": 0, "entries": len(entries)}

        recent = entries[-window:]
        values = [e["kqi"] for e in recent]
        n = len(values)
        if n < 2:
            return {"trend": "insufficient_data", "slope": 0, "entries": len(entries)}

        # 简单线性回归斜率
        x_mean = (n - 1) / 2
        y_mean = sum(values) / n
        slope = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        slope /= sum((i - x_mean) ** 2 for i in range(n)) or 1

        if abs(slope) < 0.005:
            trend = "stable"
        elif slope > 0:
            trend = "improving"
        else:
            trend = "declining"

        return {
            "trend": trend,
            "slope": round(slope, 4),
            "entries": len(entries),
            "latest_kqi": values[-1],
            "first_kqi": values[0],
            "window": n,
        }

    def information_gain(self, before_kqi: Any, after_kqi: Any) -> Any:
        return round(before_kqi["entropy"] - after_kqi["entropy"], 4)

    def suggest_next_fact(self) -> Any:
        """基于信息增益，建议下一个最有价值的事实方向"""
        kqi = self.compute_kqi()
        suggestions = []
        if kqi["coverage"] < 0.5:
            suggestions.append("方案中事实引用覆盖率不足，建议补充方案中的事实编号引用")
        if kqi["density"] < 0.3:
            suggestions.append("推导密度偏低，建议增加推论数以达到0.5 inf/fact")
        if kqi["n_entities"] == 0:
            suggestions.append("缺少实体定义，建议创建entities/目录")
        if kqi["n_scheme_files"] == 0:
            suggestions.append("缺少方案产出，建议创建scheme/目录")

        trend = self.get_kqi_trend()
        if trend["trend"] == "declining":
            suggestions.append(f"KQI趋势下降 (斜率={trend['slope']})，建议检查推导链是否退化")

        return suggestions

    def full_report(self) -> Any:
        kqi = self.compute_kqi()
        trend = self.get_kqi_trend()

        report = f"""---
title: 知识质量指数(KQI)报告 v2
generated: {datetime.datetime.now().isoformat()}
---

## KQI综合指数: {kqi["kqi"]} | 趋势: {trend["trend"]}

| 维度 | 数值 | 权重 |
|------|------|------|
| 知识熵 | {kqi["entropy"]} bits | 25% |
| 追溯覆盖率 | {kqi["coverage"] * 100:.0f}% | 25% |
| 推导密度 | {kqi["density"]:.2f} inf/fact | 20% |
| 实体覆盖 | {kqi["n_entities"]} | 15% |
| 方案文件 | {kqi["n_scheme_files"]} | 15% |
| 平均置信度 | {kqi["mean_confidence"]} | — |
| 推导链深度 | {kqi["max_chain_depth"]} | — |

## KQI趋势分析

- 记录数: {trend["entries"]}
- 最新KQI: {trend.get("latest_kqi", kqi["kqi"])}
- 斜率: {trend["slope"]}

## 改善建议
"""
        for s in self.suggest_next_fact():
            report += f"- {s}\n"

        wf(self.log_dir / "kqi-report.md", report)
        print(f"[metrics] ✅ KQI报告 v2: {self.log_dir / 'kqi-report.md'}")
        print(f"[metrics] 📊 KQI={kqi['kqi']}, 趋势={trend['trend']}, 置信度均值={kqi['mean_confidence']}")
        return kqi
