"""
ToolForge v2 — 思维工具匹配（原 MindForge，已并入 OntoDerive）
=============================================================
支持 TF-IDF 语义匹配 + 关键词 fallback。
输出: 匹配的方法论/策略/模式/原则/理论/技能 + 使用建议 + 匹配原因
"""
# pyright: reportGeneralTypeIssues=false

import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

CATALOG_PATH = Path(__file__).parent / "catalog.json"


def _tokenize(text: Any) -> Any:
    """中英文混合分词：英文按词，中文生成bigram+unigram提高召回"""
    tokens = []
    text_lower = text.lower()
    # 英文词
    tokens.extend(re.findall(r"[a-zA-Z]+", text_lower))
    # 中文：bigram (相邻2字) + unigram (单字)
    cn_chars = re.findall(r"[一-鿿]", text_lower)
    for i in range(len(cn_chars) - 1):
        tokens.append(cn_chars[i] + cn_chars[i + 1])
    tokens.extend(cn_chars)
    return tokens


def _build_vocab(docs: Any) -> Any:
    vocab: dict[Any, Any] = {}
    for tokens in docs:
        for t in set(tokens):
            vocab[t] = vocab.get(t, 0) + 1
    return {term: idx for idx, term in enumerate(sorted(vocab))}


def _compute_tf(tokens: Any, vocab_size: Any) -> Any:
    tf: defaultdict[str, float] = defaultdict(float)
    total = len(tokens) or 1
    for t in tokens:
        tf[t] += 1.0 / total
    return tf


def _compute_idf(docs: Any, vocab: Any) -> Any:
    n = len(docs)
    idf = {}
    for term, idx in vocab.items():
        df = sum(1 for d in docs if term in d)
        idf[term] = math.log((n + 1) / (df + 1)) + 1
    return idf


try:
    from ..protocols import ToolForgeInterface  # type: ignore[reportMissingImports]
except ImportError:
    from ontoderive.foundation.protocols import ToolForgeInterface  # type: ignore[import-not-found,assignment,no-redef]


class ToolForge(ToolForgeInterface):
    """思维工具匹配引擎 v2 — TF-IDF + 关键词双模式"""

    def __init__(self, catalog_path: Any = None) -> None:
        path = Path(catalog_path) if catalog_path else CATALOG_PATH
        self.catalog = json.loads(path.read_text()) if path.exists() else {"tools": []}
        self._tools = self.catalog.get("tools", [])
        self._tool_by_id = {t["id"]: t for t in self._tools}
        self._build_tfidf_index()

    def _build_tfidf_index(self) -> None:
        self._tool_docs = []
        for t in self._tools:
            doc = " ".join(t.get("keywords", [])) + " " + t["name"] + " " + t.get("description", "")
            self._tool_docs.append(_tokenize(doc))
        self._vocab = _build_vocab(self._tool_docs)
        self._idf = _compute_idf(self._tool_docs, self._vocab)
        # 为每个工具预计算TF-IDF向量（稠密列表）
        vocab_size = len(self._vocab)
        self._tool_vecs = []
        for tokens in self._tool_docs:
            tf = _compute_tf(tokens, vocab_size)
            vec = [0.0] * vocab_size
            for term, freq in tf.items():
                if term in self._vocab:
                    vec[self._vocab[term]] = freq * self._idf.get(term, 1.0)
            self._tool_vecs.append(vec)

    def _tfidf_vector(self, tokens: Any) -> Any:
        tf = _compute_tf(tokens, len(self._vocab))
        vec = [0.0] * len(self._vocab)
        for term, freq in tf.items():
            if term in self._vocab:
                vec[self._vocab[term]] = freq * self._idf.get(term, 1.0)
        return vec

    def _cosine(self, a: Any, b: Any) -> Any:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a)) or 1
        norm_b = math.sqrt(sum(x * x for x in b)) or 1
        return dot / (norm_a * norm_b)

    def _tfidf_match(self, goal: Any, context: Any = "") -> Any:
        query_tokens = _tokenize(f"{goal} {context}")
        if not query_tokens:
            return []
        query_vec = self._tfidf_vector(query_tokens)
        results = []
        for i, t in enumerate(self._tools):
            score = self._cosine(query_vec, self._tool_vecs[i])
            if score > 0:
                results.append((t, score))
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def _keyword_match(self, goal: Any, context: Any = "") -> Any:
        search_text = f"{goal} {context}".lower()
        results = []
        for tool in self._tools:
            score = 0.0
            matched = []
            for kw in tool.get("keywords", []):
                if kw.lower() in search_text:
                    score += 1
                    matched.append(kw)
            name_chars = [c for c in tool["name"] if c in search_text]
            if len(name_chars) >= 2:
                score += 0.5
            if score > 0:
                results.append((tool, round(score, 1), matched))
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def match(self, goal: Any, context: Any = "", limit: Any = 3, mode: Any = "keyword") -> Any:
        """匹配工具，按类别分组，返回含 why_matched 的结果"""
        if mode == "tfidf" or mode == "hybrid":
            tfidf_results = self._tfidf_match(goal, context)
        else:
            tfidf_results = []

        if mode == "keyword" or mode == "hybrid":
            kw_results = self._keyword_match(goal, context)
        else:
            kw_results = []

        # 混合模式：合并两种结果
        if mode == "hybrid":
            scored = {}
            for t, s in tfidf_results:
                scored[t["id"]] = {"tool": t, "score": s * 0.7, "why": f"TF-IDF语义匹配 (cos={s:.2f})"}
            for t, s, matched in kw_results:
                bonus = s * 0.3
                if t["id"] in scored:
                    scored[t["id"]]["score"] += bonus
                    scored[t["id"]]["why"] += f" + 关键词({','.join(matched[:3])})"
                else:
                    scored[t["id"]] = {"tool": t, "score": bonus, "why": f"关键词匹配: {','.join(matched[:5])}"}
            combined = sorted(scored.values(), key=lambda x: x["score"], reverse=True)
        elif mode == "tfidf":
            combined = [
                {"tool": t, "score": round(s, 2), "why": f"TF-IDF语义匹配 (cos={s:.2f})"} for t, s in tfidf_results
            ]
        else:
            combined = [{"tool": t, "score": s, "why": f"关键词匹配: {','.join(m[:5])}"} for t, s, m in kw_results]

        results: dict[str, Any] = {
            "methodologies": [],
            "strategies": [],
            "patterns": [],
            "principles": [],
            "theories": [],
            "skills": [],
        }
        for item in combined:
            t = item["tool"]
            category = t.get("category", "")
            if category in results and len(results[category]) < limit:
                results[category].append(
                    {
                        "id": t["id"],
                        "name": t["name"],
                        "score": item["score"],
                        "matched": item["why"],
                        "description": t.get("description", ""),
                        "applies_to": t.get("applies_to", ""),
                        "source": t.get("source", ""),
                    }
                )
        return results

    def select(self, goal: Any, context: Any = "", top_n: Any = 5, mode: Any = "keyword") -> Any:
        """跨类别 Top-N 扁平列表"""
        matched = self.match(goal, context, limit=top_n, mode=mode)
        all_tools = []
        for cat_tools in matched.values():
            all_tools.extend(cat_tools)
        all_tools.sort(key=lambda x: x["score"], reverse=True)
        return all_tools[:top_n]

    def to_inference_guide(self, goal: Any, context: Any = "", mode: Any = "tfidf") -> Any:
        """生成推导指导 — framework_map 从 catalog 动态构建"""
        matched = self.match(goal, context, limit=5, mode=mode)
        lines = [
            "# ToolForge → OntoDerive 推导指导",
            f"## 目标: {goal}",
            f"## 上下文: {context or '未指定'}",
            f"## 匹配模式: {mode}",
            "",
            "## 推荐推导框架",
        ]

        framework_map = {}
        for t in self._tools:
            tid = t["id"]
            guide = t.get("derivation_guide", "")
            if guide:
                framework_map[tid] = f"使用{t['name']}框架：{guide}"
            else:
                cat_map = {
                    "methodologies": f"在 inferences/ 中运用{t['name']}方法建立推导结构",
                    "strategies": f"在 inferences/ 中推导{t['name']}路径",
                    "patterns": f"在 scheme/ 中设计{t['name']}模式",
                    "principles": f"在推导中遵循{t['name']}原则，标注来源引用",
                    "theories": f"在 inferences/ 中以{t['name']}为理论基础进行推导",
                    "skills": f"在 scheme/ 中输出{t['name']}相关方案",
                }
                framework_map[tid] = cat_map.get(t.get("category", ""), f"参考{t['name']}进行推导")

        for category, tools in matched.items():
            for t in tools:
                tid = t["id"]
                line = f"- **{t['name']}** ({tid}): {framework_map.get(tid, '')}"
                lines.append(line)

        return "\n".join(lines)

    def report(self, goal: Any, context: Any = "", mode: Any = "tfidf") -> Any:
        """终端输出匹配报告"""
        matched = self.match(goal, context, mode=mode)
        print(f"\n{'═' * 50}")
        print(f"  ToolForge v2 思维工具匹配 (mode={mode})")
        print(f"  目标: {goal}")
        if context:
            print(f"  上下文: {context}")
        print(f"{'═' * 50}\n")

        total = 0
        for category, tools in matched.items():
            if not tools:
                continue
            cat_name = self.catalog.get("categories", {}).get(category, category)  # type: ignore[reportAttributeAccessIssue]
            print(f"  📂 {category} — {cat_name}")
            for t in tools:
                desc = t["description"][:50]
                print(f"    {t['id']} {t['name']} (匹配度:{t['score']:.2f}) — {desc}")
                print(f"      原因: {t['matched']}")
                total += 1

        print(f"\n  共匹配 {total} 个工具")
        return matched


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ToolForge v2 思维工具匹配引擎")
    parser.add_argument("goal", nargs="?", default="", help="目标描述")
    parser.add_argument("--goal", dest="goal2", help="目标描述（命名参数）")
    parser.add_argument("--context", help="上下文/领域描述")
    parser.add_argument("--mode", choices=["tfidf", "keyword", "hybrid"], default="tfidf")
    parser.add_argument("--inference-guide", action="store_true", help="输出推导指导")
    parser.add_argument("--top", type=int, default=5, help="Top-N 工具数")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    tf = ToolForge()
    goal = args.goal or args.goal2 or "分析"
    context = args.context or ""

    if args.inference_guide:
        print(tf.to_inference_guide(goal, context, mode=args.mode))
    elif args.json:
        print(json.dumps(tf.select(goal, context, args.top, mode=args.mode), ensure_ascii=False, indent=2))
    else:
        matched = tf.report(goal, context, mode=args.mode)
        if matched:
            print("\n💡 使用建议: 将以上工具作为分析框架，在 OntoDerive 的 inferences/ 中建立对应的推导结构")
