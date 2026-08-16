"""
OntoDerive 贝叶斯层 v2 — DAG信念传播
=====================================
基于有向无环图的信念传播：
- 节点 = Facts + Inferences，边 = derives_from
- sum-product message passing
- 循环引用检测
- Graphviz DOT可视化
"""

import datetime
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from ontoderive.foundation.utils import all_md, detect_cycles, rf, wf

CONFIDENCE_MAP = {
    "fact": 0.95,
    "high": 0.92,
    "inference": 0.85,
    "medium": 0.70,
    "hypothesis": 0.50,
    "low": 0.30,
    "estimated": 0.25,
    "assumption": 0.10,
}

DIRECT_FACTOR = 0.90
INDIRECT_FACTOR = 0.80
MAX_ITERATIONS = 20
CONVERGENCE_EPSILON = 0.001


class BayesianNetwork:
    """有向无环图：节点=事实+推论，边=derives_from"""

    def __init__(self) -> None:
        self.nodes: dict[Any, Any] = {}  # id -> {confidence, type(fact|inference), label}
        self.edges: dict[Any, Any] = {}  # from_id -> [to_id]
        self.reverse: defaultdict[str, list[Any]] = defaultdict(list)  # to_id -> [from_id]
        self.fact_ids: set[Any] = set()
        self.inf_ids: set[Any] = set()

    def add_fact(self, fid: Any, confidence: Any = 0.95, label: Any = "") -> None:
        self.nodes[fid] = {"confidence": confidence, "type": "fact", "label": label}
        self.fact_ids.add(fid)
        self.edges.setdefault(fid, [])

    def add_inference(self, iid: Any, derives_from: Any, base_conf: Any = 0.85, label: Any = "") -> None:
        self.nodes[iid] = {"confidence": base_conf, "type": "inference", "label": label, "base_confidence": base_conf}
        self.inf_ids.add(iid)
        self.edges.setdefault(iid, [])
        for src in derives_from:
            self.reverse[iid].append(src)
            if src in self.nodes:
                self.edges.setdefault(src, []).append(iid)

    def finalize(self) -> None:
        """解析所有前向引用，确保边完整"""
        for iid in list(self.inf_ids):
            for src in list(self.reverse.get(iid, [])):
                if src in self.nodes and iid not in self.edges.get(src, []):
                    self.edges.setdefault(src, []).append(iid)
                # 为不在nodes中的引用创建占位（事实ID可能不在scan结果中）
                if src not in self.nodes and not self._is_fact_id(src):
                    pass  # 忽略无效引用

    def _is_fact_id(self, fid: Any) -> Any:
        return bool(re.match(r"^(D-F|P-F)\d+", fid))

    def detect_cycles(self) -> Any:
        return detect_cycles(self.nodes, self.edges)

    def propagate(self) -> dict[str, Any]:
        """Sum-product信念传播 — 多轮迭代直至收敛"""
        cycles = self.detect_cycles()
        if cycles:
            return {"error": f"检测到{len(cycles)}个循环引用", "cycles": cycles, "nodes": self.nodes}

        # 拓扑排序（Kahn算法）
        in_degree: defaultdict[str, int] = defaultdict(int)
        for u in self.nodes:
            for v in self.edges.get(u, []):
                in_degree[v] += 1

        queue = [n for n in self.nodes if in_degree.get(n, 0) == 0]
        topo_order = []
        while queue:
            u = queue.pop(0)
            topo_order.append(u)
            for v in self.edges.get(u, []):
                in_degree[v] -= 1
                if in_degree[v] == 0:
                    queue.append(v)

        # 传播：按拓扑序更新每个推论节点的置信度
        changed = True
        iteration = 0
        while changed and iteration < MAX_ITERATIONS:
            changed = False
            iteration += 1
            for iid in self.inf_ids:
                parents = self.reverse.get(iid, [])
                if not parents:
                    continue
                parent_confs = []
                weights = []
                for p in parents:
                    if p in self.nodes:
                        parent_confs.append(self.nodes[p]["confidence"])
                        # 事实前提权重更高
                        weights.append(1.0 if p in self.fact_ids else 0.8)

                if not parent_confs:
                    continue

                avg_conf = sum(pc * w for pc, w in zip(parent_confs, weights)) / sum(weights)
                # 直接推导用DIRECT_FACTOR，间接用INDIRECT_FACTOR
                has_direct = any(p in self.fact_ids for p in parents)
                factor = DIRECT_FACTOR if has_direct else INDIRECT_FACTOR
                new_conf = avg_conf * factor

                old_conf = self.nodes[iid]["confidence"]
                if abs(new_conf - old_conf) > CONVERGENCE_EPSILON:
                    self.nodes[iid]["confidence"] = round(max(0.01, min(0.99, new_conf)), 4)
                    changed = True

        return {"nodes": self.nodes, "iterations": iteration, "converged": not changed}

    def to_dot(self) -> Any:
        """生成Graphviz DOT格式"""
        lines = ["digraph BayesianNetwork {", "  rankdir=LR;", "  node [shape=box];"]
        for nid, info in self.nodes.items():
            color = "green" if info["type"] == "fact" else "blue"
            conf = info["confidence"]
            label = f"{nid}\\n{info.get('label', '')[:20]}\\nP={conf:.2f}"
            lines.append(f'  "{nid}" [label="{label}", fillcolor={color}, style=filled];')
        for u in self.nodes:
            for v in self.edges.get(u, []):
                lines.append(f'  "{u}" -> "{v}";')
        lines.append("}")
        return "\n".join(lines)


class BayesianLayer:
    def __init__(self, project_root: Any) -> None:
        self.root = Path(project_root)
        self.facts_dir = self.root / "facts"
        self.inferences_dir = self.root / "inferences"
        self.log_dir = self.root / "_derivation_logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def scan_facts(self) -> Any:
        facts = {}
        for f in all_md(self.facts_dir):
            text = rf(f)
            for m in re.finditer(r"\| (D-F\d+|P-F\d+)\s*\|([^|]+)\|([^|]+)\|", text):
                fid = m.group(1)
                source = m.group(3).strip() if m.lastindex and m.lastindex >= 3 else ""
                # 基于来源可靠性差异化置信度
                conf = 0.95
                source_lower = source.lower()
                if any(kw in source_lower for kw in ["gartner", "aws", "linkedin", "行业报告"]):
                    conf = 0.92  # 外部来源，有一定偏差
                elif any(kw in source_lower for kw in ["hr", "财务", "cmdb", "soc", "apm"]):
                    conf = 0.97  # 内部系统数据，较可靠
                elif any(kw in source_lower for kw in ["调研", "供应商", "预估"]):
                    conf = 0.88  # 调研/供应商数据，需验证
                facts[fid] = {"desc": m.group(2).strip(), "value": source, "confidence": conf, "type": "fact"}
        return facts

    def scan_inferences(self) -> Any:
        inferences = {}
        for f in all_md(self.inferences_dir):
            text = rf(f)
            blocks = re.split(r"^##\s+", text, flags=re.MULTILINE)
            for block in blocks[1:]:
                lines = block.strip().split("\n")
                title = lines[0].strip() if lines else "unknown"
                full_text = block
                df_facts = re.findall(r"(D-F\d+|P-F\d+)", full_text)
                df_infs = re.findall(r"(INF-[\w\d]+|INF-V2-[\w\d]+)", full_text)
                conf_match = re.search(r"confidence:\s*(\w+)", full_text)
                raw_conf = conf_match.group(1) if conf_match else "inference"
                base_conf = CONFIDENCE_MAP.get(raw_conf, 0.85)
                inferences[title] = {
                    "derives_from": list(set(df_facts + df_infs)),
                    "raw_confidence": raw_conf,
                    "base_confidence": base_conf,
                    "propagated_confidence": None,
                    "text": full_text[:200],
                }
        return inferences

    def build_network(self, facts: Any, inferences: Any) -> Any:
        """构建贝叶斯网络DAG"""
        bn = BayesianNetwork()
        for fid, info in facts.items():
            bn.add_fact(fid, info["confidence"], info.get("desc", fid))
        for name, info in inferences.items():
            bn.add_inference(name, info["derives_from"], info["base_confidence"], name[:60])
        bn.finalize()  # 解析前向引用
        return bn

    def propagate_all(self) -> tuple[Any, ...]:
        facts = self.scan_facts()
        inferences = self.scan_inferences()
        bn = self.build_network(facts, inferences)
        result = bn.propagate()

        if "error" in result:
            print(f"[bayesian] ⚠️ {result['error']}")
            print("[bayesian]   回落至简化传播模式")
            # 回落：加权平均传播
            inferences = self._fallback_propagate(facts, inferences)
            return facts, inferences

        # 将传播结果写回inferences
        nodes = result["nodes"]
        for name, info in inferences.items():
            if name in nodes:
                info["propagated_confidence"] = nodes[name]["confidence"]
            else:
                info["propagated_confidence"] = info["base_confidence"]

        # 生成DOT文件
        dot = bn.to_dot()
        wf(self.log_dir / "bayesian-network.dot", dot)
        print(
            f"[bayesian] ✅ DAG: {len(bn.nodes)}节点, {sum(len(v) for v in bn.edges.values())}边, "
            f"{result.get('iterations', 0)}轮收敛"
        )
        print(f"[bayesian]    DOT: {self.log_dir / 'bayesian-network.dot'}")

        return facts, inferences

    def get_distribution(self) -> dict[str, Any]:
        """公开方法：返回置信度分布供Pipeline/Metrics消费"""
        facts, inferences = self.propagate_all()
        fact_confs = [f["confidence"] for f in facts.values()]
        inf_confs = [
            i.get("propagated_confidence", i.get("base_confidence", 0.85))
            for i in inferences.values()
            if i.get("propagated_confidence")
        ]
        return {
            "facts": fact_confs,
            "inferences": inf_confs,
            "n_facts": len(fact_confs),
            "n_inferences": len(inf_confs),
        }

    def _fallback_propagate(self, facts: Any, inferences: Any) -> Any:
        """原加权平均传播（兼容循环引用场景）"""
        for name, inf in inferences.items():
            premises = [f for f in inf["derives_from"] if f in facts]
            if premises:
                avg = sum(facts[p]["confidence"] for p in premises) / len(premises)
                inf["propagated_confidence"] = round(avg * DIRECT_FACTOR, 4)
            else:
                inf["propagated_confidence"] = inf["base_confidence"]
        for inf in inferences.values():
            inf["propagated_confidence"] = max(0.01, min(0.99, inf["propagated_confidence"]))
        return inferences

    def recompute_if_changed(self, fact_id: str, new_value: float) -> dict[str, Any]:
        """v3.6: What-if分析 — 修改一个事实值后重算下游置信度变化"""
        if not hasattr(self, "_cached_facts"):
            self._cached_facts, self._cached_inferences = self.propagate_all()
        facts = dict(self._cached_facts)  # 浅拷贝避免修改缓存
        inferences = dict(self._cached_inferences)
        if fact_id not in facts:
            return {"error": f"事实{fact_id}不存在"}
        old_conf = facts[fact_id].get("confidence", 0.95)
        facts[fact_id]["confidence"] = min(0.99, max(0.01, new_value))
        _, new_inferences = self._fallback_propagate(facts, inferences)
        deltas = {}
        for name, inf in new_inferences.items():
            new_conf = inf.get("propagated_confidence", 0)
            old = self._cached_inferences.get(name, {}).get("propagated_confidence", 0)
            if abs(new_conf - old) > 0.001:
                deltas[name] = {"old": old, "new": new_conf, "delta": round(new_conf - old, 4)}
        return {
            "fact_id": fact_id,
            "old_confidence": old_conf,
            "new_confidence": new_value,
            "affected_inferences": len(deltas),
            "deltas": deltas,
        }

    def confidence_report(self) -> Any:
        facts, inferences = self.propagate_all()
        report = f"""---
title: 贝叶斯信念传播报告 v2
generated: {datetime.datetime.now().isoformat()}
---

## 事实基座置信度

| 编号 | 简介 | 置信度 |
|------|------|--------|
"""
        for fid, info in sorted(facts.items()):
            report += f"| {fid} | {info['desc'][:30]} | {info['confidence']:.2f} |\n"

        report += "\n## 推论置信度(传播后)\n\n"
        report += "| 推论 | 原始标签 | 传播后置信度 | derives_from |\n"
        report += "|------|---------|-------------|-------------|\n"
        for name, info in sorted(inferences.items()):
            report += (
                f"| {name[:40]} | {info['raw_confidence']} | {info['propagated_confidence']:.2f} | "
                f"{', '.join(info['derives_from'][:5])} |\n"
            )

        all_confs = [i["propagated_confidence"] for i in inferences.values()] + [
            f["confidence"] for f in facts.values()
        ]
        entropy = 0
        for c in all_confs:
            if 0 < c < 1:
                entropy += -c * math.log2(c) - (1 - c) * math.log2(1 - c)

        report += f"\n## 熵\n\n知识库总熵: {entropy:.4f} bits\n"
        report += f"平均置信度: {sum(all_confs) / len(all_confs):.4f}\n"
        report += f"推论数: {len(inferences)}\n事实数: {len(facts)}\n"

        wf(self.log_dir / "bayesian-report.md", report)
        print(f"[bayesian] ✅ 报告: {self.log_dir / 'bayesian-report.md'}")
        return report
