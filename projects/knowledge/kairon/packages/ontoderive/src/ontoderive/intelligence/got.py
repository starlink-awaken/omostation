"""
GoT (Graph of Thoughts) — 基于蕴含图的图推理引擎
==================================================
利用OntoDerive已有的EntailmentGraph作为推理骨架,
LLM在图上游走, 在合并节点综合多路推理。
"""

import re
from typing import Any


class GraphOfThoughts:
    """图思维引擎 — 在蕴含图上做LLM推理"""

    def __init__(self, entailment_graph: Any, enhancer: Any) -> None:
        self.graph = entailment_graph  # logic.EntailmentGraph
        self.llm = enhancer
        self.thoughts: dict[Any, Any] = {}  # node_id → 推理结果

    def traverse_and_reason(self, merge_at_depth: Any = 2) -> Any:
        """
        图游走推理:
        1. 拓扑排序确定推理顺序
        2. 叶子节点(事实)直接读取, 不调LLM
        3. 中间节点(推论)调LLM分析
        4. 合并节点(多输入)综合多路推理
        """
        order = self._topological_order()
        results = {}

        for node in order:
            # 收集前提的推理结果
            parents = self.graph.reverse.get(node, [])
            parent_thoughts = {
                p: self.thoughts.get(p, {"type": "fact", "summary": self.graph.nodes.get(p, {}).get("label", "")})
                for p in parents
            }

            node_info = self.graph.nodes.get(node, {})
            if node_info.get("type") == "inference":
                # 推论节点: LLM分析
                thought = self._reason_on_node(node, parent_thoughts)
                self.thoughts[node] = thought
                results[node] = thought

        # 在合并节点综合
        merges = self._find_merge_nodes()
        for node, inputs in merges.items():
            if len(inputs) >= 2:
                self.thoughts[node] = self._merge_paths(node, inputs)

        return results

    def _reason_on_node(self, node: Any, parent_thoughts: Any) -> Any:
        """单节点推理"""
        parents_str = "\n".join(f"  {p}: {t.get('summary', '')[:100]}" for p, t in parent_thoughts.items())
        node_label = self.graph.nodes.get(node, {}).get("label", node)[:200]

        prompt = f"""分析这个推论的逻辑一致性。

前提节点:
{parents_str}

当前推论: {node_label}

请评估:
1. 逻辑连贯性: 结论是否从前提合理推出?
2. 证据充分性: 前提是否足够支撑结论?
3. 潜在问题: 是否有隐藏假设或逻辑跳跃?

输出JSON: {{"coherence": 1-5, "sufficiency": 1-5, "issues": ["..."], "summary": "..."}}"""
        result = self.llm._call(prompt, "你是逻辑分析专家。输出JSON。", 0.2)
        if not result:
            return {"summary": node_label[:100]}
        try:
            return __import__("json").loads(result)
        except Exception:
            m = re.search(r"\{[^}]+\}", result)
            if m:
                try:
                    return __import__("json").loads(m.group())
                except Exception:
                    pass
        return {"summary": node_label[:100]}

    def _merge_paths(self, node: Any, input_nodes: Any) -> Any:
        """合并多条推理路径"""
        thoughts = {n: self.thoughts.get(n, {}) for n in input_nodes}
        summaries = "\n".join(
            f"路径{i + 1}({n[:30]}): {t.get('summary', '')[:150]}" for i, (n, t) in enumerate(thoughts.items())
        )
        prompt = f"""综合以下{len(input_nodes)}条推理路径, 给出合并判断。

{summaries}

合并节点: {node[:100]}

如果有矛盾: 明确指出来源
如果互补: 说明如何综合
如果重叠: 指出冗余

输出JSON: {{"merged": "...", "contradictions": [...], "confidence": 0.0-1.0}}"""
        result = self.llm._call(prompt, "输出JSON。", 0.2)
        try:
            return __import__("json").loads(result)
        except Exception:
            return {"merged": f"{len(input_nodes)}条路径综合"}

    def _find_merge_nodes(self) -> Any:
        """找出有多个输入的合并节点"""
        merges = {}
        for node in self.graph.nodes:
            inputs = self.graph.reverse.get(node, [])
            if len(inputs) >= 2 and self.graph.nodes[node].get("type") == "inference":
                merges[node] = inputs
        return merges

    def _topological_order(self) -> Any:
        """拓扑排序 (Kahn)"""
        in_degree: dict[Any, Any] = {}
        for u in self.graph.nodes:
            for v in self.graph.edges.get(u, []):
                in_degree[v] = in_degree.get(v, 0) + 1
        queue = [n for n in self.graph.nodes if in_degree.get(n, 0) == 0]
        order = []
        while queue:
            u = queue.pop(0)
            order.append(u)
            for v in self.graph.edges.get(u, []):
                in_degree[v] -= 1
                if in_degree[v] == 0:
                    queue.append(v)
        return order
