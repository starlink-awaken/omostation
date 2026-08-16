"""
ReAct (Reasoning + Acting) — 推理+行动交替引擎
=================================================
LLM在OntoDerive的工具系统上交替推理和行动。
已有7个Action原语, 只需定义ReAct循环。
"""

import re
from pathlib import Path
from typing import Any


class ReActEngine:
    """ReAct引擎 — Thought→Action→Observation循环"""

    ACTION_SCHEMA = {
        "read_fact": {"args": ["fact_id"], "desc": "读取事实的值和来源"},
        "read_inference": {"args": ["inf_id"], "desc": "读取推论全文和引用链"},
        "check_reference": {"args": ["inf_id"], "desc": "验证推论的所有引用是否存在"},
        "get_confidence": {"args": ["inf_id"], "desc": "获取贝叶斯传播后的置信度"},
        "trace_chain": {"args": ["inf_id"], "desc": "追溯完整推导链(D-F→INF→...) "},
        "find_contradictions": {"args": [], "desc": "运行矛盾检测, 返回矛盾对列表"},
        "compute_kqi": {"args": [], "desc": "计算KQI知识质量指数"},
    }

    def __init__(self, project_root: Any, enhancer: Any) -> None:
        self.root = Path(project_root)
        self.llm = enhancer
        self.history: list[Any] = []  # [(thought, action, observation), ...]

    def _build_action_prompt(self) -> Any:
        tools = "\n".join(
            f"- {name}({', '.join(info['args'])}): {info['desc']}" for name, info in self.ACTION_SCHEMA.items()
        )
        return f"""你是知识工程分析专家。你可以使用以下工具来验证你的推理。

{tools}

每次响应格式(严格):
Thought: [你的推理步骤]
Action: [工具名](参数)

示例:
Thought: 需要验证INF-L1引用的D-F1是否正确
Action: read_fact(D-F1)

分析完成时:
Thought: [最终结论, 基于观察证据]
Action: FINISH

当前任务: 分析项目的知识工程质量。从check_reference开始。"""

    def run(self, max_steps: Any = 5) -> dict[str, Any]:
        """ReAct主循环"""
        system = self._build_action_prompt()

        for step in range(max_steps):
            history_str = (
                "\n".join(
                    f"Step {i}: Thought: {t} → Action: {a} → Obs: {o[:150]}" for i, (t, a, o) in enumerate(self.history)
                )
                if self.history
                else "(首次行动, 请从check_reference开始)"
            )

            prompt = f"历史:\n{history_str}\n\n请给出下一步的Thought和Action:"
            result = self.llm._call(prompt, system, 0.2)
            if not result:
                break

            thought, action_name, action_arg = self._parse_result(result)
            if action_name == "FINISH" or action_name is None:
                return {"verdict": thought, "steps": step + 1, "history": self.history}

            observation = self._execute(action_name, action_arg)
            self.history.append((thought, f"{action_name}({action_arg})", str(observation)[:300]))

        return {"verdict": f"ReAct分析完成({len(self.history)}步)", "steps": len(self.history), "history": self.history}

    def _parse_result(self, text: Any) -> tuple[Any, ...]:
        """解析LLM的Thought/Action"""
        thought = ""
        action_name = None
        action_arg = ""

        tm = re.search(r"Thought:\s*(.+?)(?=\nAction:|\Z)", text, re.DOTALL)
        if tm:
            thought = tm.group(1).strip()[:300]

        am = re.search(r"Action:\s*(\w+)\(?([^)]*)\)?", text)
        if am:
            action_name = am.group(1).strip()
            action_arg = am.group(2).strip().strip("'\"")
            if action_name == "FINISH":
                return thought, "FINISH", ""

        return thought, action_name, action_arg

    def _execute(self, name: Any, arg: Any) -> dict[str, Any]:
        """执行Action"""
        try:
            if name == "read_fact":
                for f in (self.root / "facts").rglob("*.md"):
                    t = f.read_text()
                    if arg in t:
                        m = re.search(rf"\| {re.escape(arg)}\s*\|([^|]+)\|([^|]+)\|", t)
                        if m:
                            return {"fact": arg, "desc": m.group(1).strip(), "value": m.group(2).strip()}
                return {"error": f"事实{arg}不存在"}

            if name == "read_inference":
                for f in (self.root / "inferences").rglob("*.md"):
                    t = f.read_text()
                    if arg in t:
                        blocks = re.split(r"^##\s+", t, re.MULTILINE)
                        for b in blocks[1:]:
                            if arg in b:
                                df = re.findall(r"(D-F\d+|P-F\d+|INF-[\w\d]+)", b)
                                return {"inference": arg, "derives_from": list(set(df)), "text": b[:300]}
                return {"error": f"推论{arg}不存在"}

            if name == "check_reference":
                for f in (self.root / "inferences").rglob("*.md"):
                    t = f.read_text()
                    if arg in t:
                        blocks = re.split(r"^##\s+", t, re.MULTILINE)
                        for b in blocks[1:]:
                            if arg in b:
                                refs = re.findall(r"(D-F\d+|P-F\d+|INF-[\w\d]+)", b)
                                valid = [r for r in refs if self._exists(r)]
                                missing = [r for r in refs if not self._exists(r)]
                                return {"valid_refs": valid, "missing_refs": missing, "all_valid": len(missing) == 0}
                return {"error": f"推论{arg}不存在"}

            if name == "get_confidence":
                try:
                    from ontoderive.theories.bayesian import BayesianLayer

                    bl = BayesianLayer(self.root)
                    _, infs = bl.propagate_all()
                    for k, v in infs.items():
                        if arg in k:
                            return {"inference": arg, "confidence": v.get("propagated_confidence", "N/A")}
                except Exception:
                    pass
                return {"error": f"无法计算{arg}的置信度"}

            if name == "trace_chain":
                chain = [arg]
                try:
                    for f in (self.root / "inferences").rglob("*.md"):
                        t = f.read_text()
                        blocks = re.split(r"^##\s+", t, re.MULTILINE)
                        for b in blocks[1:]:
                            if arg in b:
                                df = re.findall(r"(D-F\d+|P-F\d+)", b)
                                chain.extend(df)
                except Exception:
                    pass
                return {"chain": chain, "depth": len(chain) - 1}

            if name == "find_contradictions":
                try:
                    from ontoderive.theories.logic import build_from_project

                    g = build_from_project(self.root)
                    return {"contradictions": g.find_contradictions()}
                except Exception:
                    return {"error": "矛盾检测失败"}

            if name == "compute_kqi":
                try:
                    from ontoderive.theories.metrics import MetricsLayer

                    ml = MetricsLayer(self.root)
                    kqi = ml.compute_kqi()
                    return {"kqi": kqi["kqi"], "coverage": f"{kqi['coverage'] * 100:.0f}%"}
                except Exception:
                    return {"error": "KQI计算失败"}

        except Exception as e:
            return {"error": str(e)}
        return {"error": f"未知Action: {name}"}

    def _exists(self, ref_id: Any) -> bool:
        """检查ID是否存在"""
        for d in ["facts", "inferences", "entities"]:
            for f in (self.root / d).rglob("*.md"):
                if ref_id in f.read_text():
                    return True
        return False
