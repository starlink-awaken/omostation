"""
OntoDerive Judge — LLM驱动的真实推导与评估
=============================================
从"lint工具"升级到"judge工具"的核心模块。
每个判断必须可追溯：引用具体事实/推论编号。
"""

import json
import re
from pathlib import Path
from typing import Any


class JudgeResult:
    def __init__(self, category: Any, passed: Any, confidence: Any, reasoning: Any, cites: Any) -> None:
        self.category = category
        self.passed = passed
        self.confidence = confidence  # 0-1
        self.reasoning = reasoning
        self.cites = cites  # [D-F1, INF-L2, ...]


class OntoDeriveJudge:
    """LLM驱动的知识质量评估器"""

    def __init__(self, project_root: Any, enhancer: Any = None) -> None:
        self.root = Path(project_root)
        self.enhancer = enhancer
        if enhancer is None:
            try:
                from .llm import get_enhancer

                self.enhancer = get_enhancer()
            except Exception:
                self.enhancer = None

    def _rf(self, path: Any) -> Any:
        p = Path(path) if isinstance(path, str) else path
        return p.read_text("utf-8", errors="ignore") if p.exists() else ""

    def _all_md(self, directory: Any) -> Any:
        dp = Path(directory)
        return sorted(dp.rglob("*.md")) if dp.exists() else []

    def _collect_project_context(self) -> Any:
        """收集项目上下文"""
        ctx: dict[str, Any] = {"facts": {}, "inferences": {}, "schemes": {}}

        for f in self._all_md(self.root / "facts"):
            text = self._rf(f)
            for m in re.finditer(r"\| (D-F\d+|P-F\d+)\s*\|([^|]+)\|([^|]+)\|", text):
                ctx["facts"][m.group(1)] = {"desc": m.group(2).strip(), "value": m.group(3).strip()}

        for f in self._all_md(self.root / "inferences"):
            text = self._rf(f)
            blocks = re.split(r"^##\s+", text, flags=re.MULTILINE)
            for block in blocks[1:]:
                title = block.strip().split("\n")[0].strip()
                df = re.findall(r"(D-F\d+|P-F\d+|INF-[\w\d]+)", block)
                ctx["inferences"][title] = {"text": block[:500], "derives_from": list(set(df))}

        for f in self._all_md(self.root / "scheme"):
            text = self._rf(f)
            ctx["schemes"][f.name] = {"text": text[:500]}

        return ctx

    # ── 真实推导：从已知事实/推论生成新结论 ──

    def derive_new_insights(self) -> Any:
        """LLM基于现有事实和推论，生成人可能忽略的新洞察"""
        ctx = self._collect_project_context()
        if not self.enhancer or not self.enhancer.available:
            return []

        facts_summary = "\n".join(
            f"{fid}: {info['desc']} = {info['value']}" for fid, info in list(ctx["facts"].items())[:20]
        )
        infs_summary = "\n".join(
            f"{title}: {info['text'][:200]}" for title, info in list(ctx["inferences"].items())[:10]
        )

        prompt = f"""分析以下事实和推论，找出人可能忽略的**新洞察**。每条洞察必须引用具体的编号。

事实:
{facts_summary}

推论:
{infs_summary}

请给出2-3条新洞察。每条格式:
洞察: [内容] | 引用: [D-F1, INF-L2] | 置信度: [high/medium/low]"""
        result = self.enhancer._call(prompt, "你是严谨的知识工程分析专家。只输出基于事实的洞察，不编造。", 0.3)
        if not result:
            return []
        insights = []
        for line in result.split("\n"):
            if not line.strip() or not line.startswith("洞察"):
                continue
            cites = re.findall(r"(D-F\d+|P-F\d+|INF-[\w\d]+)", line)
            conf = "high" if "high" in line.lower() else ("medium" if "medium" in line.lower() else "low")
            conf_map = {"high": 0.85, "medium": 0.65, "low": 0.45}
            insights.append({"insight": line.strip()[:200], "cites": cites, "confidence": conf_map.get(conf, 0.5)})
        return insights

    # ── 真实评估：判断推论质量 ──

    def evaluate_inference_quality(self, inference_title: Any, inference_text: Any, derives_from: Any) -> Any:
        """评估单条推论的质量：逻辑连贯性、证据充分性、可证伪性"""
        if not self.enhancer or not self.enhancer.available:
            return None

        prompt = f"""评估以下推论的逻辑质量。严格基于事实，不编造。

推论: {inference_title}
内容: {inference_text[:500]}
引用的事实: {derives_from}

评估三个维度，每个1-5分:
1. 逻辑连贯性: 结论是否从前提合理推出？
2. 证据充分性: 引用的事实是否足够支撑结论？
3. 可证伪性: 是否存在可以推翻该推论的明确条件？

输出格式（只输出JSON）:
{{"logic_score": 4, "evidence_score": 3, "falsifiability_score": 5, "overall": 4, "reasoning": "..."}}"""
        result = self.enhancer._call(prompt, "你只输出JSON。不添加任何其他文字。", 0.1)
        if not result:
            return None
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            # try to extract JSON from the response
            m = re.search(r"\{[^}]+\}", result)
            if m:
                try:
                    return json.loads(m.group())
                except Exception:
                    pass
        return None

    def evaluate_all_inferences(self) -> Any:
        """评估所有推论，返回质量报告"""
        ctx = self._collect_project_context()
        results = {}
        for title, info in ctx["inferences"].items():
            score = self.evaluate_inference_quality(title, info["text"], info.get("derives_from", []))
            if score:
                results[title] = score
        return results

    # ── 真实判断：项目整体质量评估 ──

    def judge_project(self) -> Any:
        """
        综合评估项目质量。
        不是"13/13通过"的格式检查，而是基于LLM的内容质量判断。
        """
        ctx = self._collect_project_context()
        if not self.enhancer or not self.enhancer.available:
            return {
                "verdict": "insufficient_data",
                "reason": "LLM不可用，无法进行深度质量评估。回退到规则引擎的格式检查。",
                "rule_engine_only": True,
            }

        facts_sample = json.dumps({k: v["desc"][:40] for k, v in list(ctx["facts"].items())[:10]}, ensure_ascii=False)
        inferences_sample = json.dumps(
            {k: {"derives_from": v.get("derives_from", [])} for k, v in list(ctx["inferences"].items())[:8]},
            ensure_ascii=False,
        )

        prompt = f"""你是知识工程质量评审专家。评估以下项目的知识工程质量。

项目概况:
- 事实数: {len(ctx["facts"])}
- 推偶数: {len(ctx["inferences"])}
- 方案数: {len(ctx["schemes"])}

事实:
{facts_sample}

推论摘要:
{inferences_sample}

请给出项目整体质量评分(1-10)和三条最关键改善建议。
输出JSON: {{"score": 7, "strengths": [...], "weaknesses": [...], "recommendations": [...], "verdict": "..."}}"""
        result = self.enhancer._call(prompt, "你只输出JSON。", 0.2)
        if not result:
            return {"verdict": "eval_failed", "reason": "LLM返回空"}
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            m = re.search(r"\{[\s\S]*\}", result)
            if m:
                try:
                    return json.loads(m.group())
                except Exception:
                    pass
        return {"verdict": "eval_failed", "raw": result[:500]}
