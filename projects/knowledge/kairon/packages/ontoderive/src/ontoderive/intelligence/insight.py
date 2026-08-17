"""
OntoDerive Insight — 统一洞察引擎
===================================
所有模块通过InsightEngine调用LLM，而非各自直接调用llm.py。
标准Insight数据结构，支持外部工具消费（Dashboard、API、Notebook）。
"""

import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Insight:
    """标准洞察数据结构 — 外部工具可消费的原子单位"""

    type: str  # derivation | contradiction | quality | recommendation
    content: str  # 洞察内容
    confidence: float  # 0-1
    cites: list[str] = field(default_factory=list)  # [D-F1, INF-L2, ...]
    method: str = "llm"  # llm | rule
    model: str = ""  # 使用的模型名
    timestamp: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Any:
        return asdict(self)

    def to_markdown(self) -> Any:
        cites_str = ", ".join(self.cites) if self.cites else "无"
        return f"**[{self.type}]** {self.content} (置信度:{self.confidence:.0%}, 引用:{cites_str})"


class InsightCache:
    """洞察缓存 — 项目内容不变时不重复调用LLM"""

    def __init__(self, cache_dir: Any = None) -> None:
        self.cache_dir = Path(cache_dir) if cache_dir else Path("_derivation_logs")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[Any, Any] = {}

    def _key(self, project_root: Any, category: Any) -> Any:
        import hashlib

        root = Path(project_root)
        hashes = []
        for d in ["facts", "inferences", "scheme"]:
            dp = root / d
            if dp.exists():
                for f in sorted(dp.rglob("*.md")):
                    hashes.append(hashlib.md5(f.read_bytes()).hexdigest()[:8])  # noqa: S324
        return f"{category}-{hashlib.md5(''.join(hashes).encode()).hexdigest()[:12]}"  # noqa: S324

    def get(self, project_root: Any, category: Any) -> Any:
        key = self._key(project_root, category)
        cache_file = self.cache_dir / f"insight-{key}.json"
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text())
                return [Insight(**i) for i in data.get("insights", [])]
            except Exception:
                pass
        return None

    def set(self, project_root: Any, category: Any, insights: Any) -> None:
        key = self._key(project_root, category)
        cache_file = self.cache_dir / f"insight-{key}.json"
        cache_file.write_text(
            json.dumps(
                {
                    "insights": [i.to_dict() for i in insights],
                    "cached_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                },
                ensure_ascii=False,
                indent=2,
            )
        )


class InsightEngine:
    """统一洞察引擎 — 所有需要LLM的模块通过此引擎调用"""

    def __init__(self, enhancer: Any = None, cache_dir: Any = None) -> None:
        self.enhancer = enhancer
        if enhancer is None:
            try:
                from .llm import get_enhancer

                self.enhancer = get_enhancer()
            except Exception:
                self.enhancer = None
        self.cache = InsightCache(cache_dir)
        self._history: list[Insight] = []  # 本次会话的所有洞察

    @property
    def available(self) -> Any:
        return self.enhancer and self.enhancer.available

    def _call(self, prompt: Any, system: Any = "", temperature: Any = 0.3) -> Any:
        if not self.available or self.enhancer is None:
            return None
        return self.enhancer._call(prompt, system, temperature)

    # ── 四种标准洞察类型 ──

    def derive_insights(self, project_root: Any, facts_summary: Any, inferences_text: Any) -> Any:
        """类型1: 推导洞察 — 基于事实/推论发现新连接"""
        cached = self.cache.get(project_root, "derive")
        if cached:
            self._history.extend(cached)
            return cached

        if not self.available:
            return []

        prompt = f"""分析以下事实和推论，找出人可能忽略的新洞察。每条引用具体编号。

事实: {facts_summary}
推论: {inferences_text[:2000]}

给出2-3条洞察。每条一行，格式:
[置信度:high/medium/low] 洞察内容 | 引用: D-F1, INF-L2"""
        result = self._call(prompt, "你是严谨的知识工程分析专家。", 0.3)
        if not result:
            return []

        insights = []
        for line in result.split("\n"):
            if not line.strip() or "洞察" not in line:
                continue
            conf = 0.85 if "high" in line.lower() else (0.65 if "medium" in line.lower() else 0.45)
            cites = re.findall(r"(D-F\d+|P-F\d+|INF-[\w\d]+)", line)
            content = re.sub(r"\[置信度:\w+\]\s*", "", line).strip()[:200]
            insight = Insight(
                type="derivation",
                content=content,
                confidence=conf,
                cites=cites,
                method="llm",
                model=self.enhancer.model if self.enhancer else "",
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            )
            insights.append(insight)

        self._history.extend(insights)
        self.cache.set(project_root, "derive", insights)
        return insights

    def judge_quality(self, project_root: Any, context: Any) -> Any:
        """类型2: 质量评估洞察 — LLM对项目整体质量评分"""
        if not self.available:
            return {"verdict": "llm_unavailable", "score": None}

        prompt = f"""你是知识工程质量评审专家。评估以下项目的质量。

项目概况: {json.dumps(context, ensure_ascii=False)[:2000]}

给出整体评分(1-10)和三条建议。输出JSON: {{"score":7,"verdict":"...","recommendations":[...]}}"""
        result = self._call(prompt, "只输出JSON。", 0.2)
        if not result:
            return {"verdict": "eval_failed", "score": None}

        try:
            return json.loads(result)
        except json.JSONDecodeError:
            m = re.search(r"\{[\s\S]*\}", result)
            if m:
                try:
                    parsed = json.loads(m.group())
                    insight = Insight(
                        type="quality",
                        content=parsed.get("verdict", ""),
                        confidence=0.80,
                        method="llm",
                        model=self.enhancer.model if self.enhancer else "",
                        timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
                        metadata=parsed,
                    )
                    self._history.append(insight)
                    return parsed
                except Exception:
                    pass
        return {"verdict": "eval_failed", "raw": result[:500]}

    def check_contradiction(
        self, inf_a_title: Any, inf_a_text: Any, inf_b_title: Any, inf_b_text: Any, shared_facts: Any
    ) -> Any:
        """类型3: 矛盾检测洞察 — 语义级别判断两个推论是否矛盾"""
        if not self.available:
            return None

        prompt = f"""判断以下两个推论是否存在实质性矛盾。仅回答YES或NO。

推论A({inf_a_title}): {inf_a_text[:300]}
推论B({inf_b_title}): {inf_b_text[:300]}
共享事实: {shared_facts}

是否存在矛盾？(YES/NO):"""
        result = self._call(prompt, "仅回答YES或NO。", 0.1)
        is_contradiction = result and "YES" in result.upper()

        insight = Insight(
            type="contradiction",
            content=f"{inf_a_title} vs {inf_b_title}: {'存在矛盾' if is_contradiction else '无矛盾'}",
            confidence=0.90 if is_contradiction else 0.75,
            cites=shared_facts,
            method="llm",
            model=self.enhancer.model if self.enhancer else "",
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            metadata={"inference_a": inf_a_title, "inference_b": inf_b_title, "is_contradiction": is_contradiction},
        )
        self._history.append(insight)
        return insight

    def recommend_tools(self, goal: Any, context: Any, tools: Any) -> Any:
        """类型4: 推荐洞察 — LLM语义匹配最合适的思维工具"""
        if not self.available:
            return None

        tools_text = "\n".join(f"{t['id']}: {t['name']} — {t.get('description', '')[:60]}" for t in tools[:30])
        prompt = f"""从工具列表选出最适合目标的3个工具ID。

目标: {goal} | 上下文: {context}
工具: {tools_text}

只输出3个ID，逗号分隔:"""
        result = self._call(prompt, "只输出工具ID。", 0.1)
        if result:
            ids = [x.strip() for x in result.split(",")[:3]]
            insight = Insight(
                type="recommendation",
                content=f"推荐工具: {', '.join(ids)}",
                confidence=0.80,
                cites=ids,
                method="llm",
                model=self.enhancer.model if self.enhancer else "",
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            )
            self._history.append(insight)
            return ids
        return None

    # ── 导出接口 ──

    def export_insights(self, format: Any = "json") -> Any:
        """导出本次会话的所有洞察"""
        data = [i.to_dict() for i in self._history]
        if format == "json":
            return json.dumps(data, ensure_ascii=False, indent=2)
        elif format == "markdown":
            return "\n\n".join(i.to_markdown() for i in self._history)
        return data

    def save_insights(self, output_dir: Any) -> None:
        """保存洞察到文件，供外部工具消费"""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "insights.json").write_text(self.export_insights("json"))
        (out / "insights.md").write_text(self.export_insights("markdown"))
        print(f"[insight] ✅ {len(self._history)}条洞察 → {out}/insights.{{json,md}}")

    def clear_cache(self) -> None:
        """清除LLM结果缓存（项目内容变更后调用）"""
        for f in self.cache.cache_dir.glob("insight-*.json"):
            f.unlink()

    # ═══ LLM推理增强: Self-Consistency ═══

    def judge_with_consensus(self, project_root: Any, context: Any, n_samples: Any = 3) -> dict[str, Any]:
        """多次采样取中位数, 减少单次随机性"""
        scores, verdicts = [], []
        for i in range(n_samples):
            result = self.judge_quality(project_root, context)
            if result.get("score"):
                scores.append(result["score"])
                verdicts.append(result.get("verdict", ""))
        if not scores:
            return {"verdict": "eval_failed", "score": None}
        return {
            "score": sorted(scores)[len(scores) // 2],
            "min": min(scores),
            "max": max(scores),
            "consensus": len(set(verdicts)) == 1,
            "samples": n_samples,
        }

    # ═══ LLM推理增强: Reflexion ═══

    def reflect_and_refine(self, project_root: Any, context: Any, max_refinements: Any = 2) -> Any:
        """自我反思修正: 生成→评估→发现问题→修正"""
        import re

        initial = self.judge_quality(project_root, context)
        if not initial.get("score"):
            return initial
        for i in range(max_refinements):
            prompt = (
                f"反思你的评审(评分{initial.get('score')}): "
                f"{initial.get('verdict', '')[:200]}。是否有遗漏？修正评分(1-10):"
            )
            reflection = self._call(prompt, "你是善于自我反思的评审专家。", 0.3)
            if not reflection:
                break
            m = re.search(r"(\d+)\s*分", reflection)
            if m:
                refined = int(m.group(1))
                if 1 <= refined <= 10 and refined != initial["score"]:
                    initial["refined_score"] = refined
                    initial["reflection"] = reflection[:200]
                    break
        return initial
