"""
语义匹配中间层 — SemanticMatcher
==================================
填补正则匹配到LLM调用之间的能力断层。
使用TF-IDF + 余弦相似度做模糊匹配，适用于:
- 实体名模糊匹配 (A2风险传导)
- 共享资源语义关联 (A4激励不相容)
- 跨描述概念相似度 (A3代理问题上下文理解)

原则: 零LLM, 零外部依赖, 纯Python实现
"""

import math
import re
from collections import Counter


class SemanticMatcher:
    """TF-IDF + 余弦相似度 语义匹配器"""

    def __init__(self, corpus: list[str] | None = None) -> None:
        self.corpus = corpus or []
        self.idf: dict[str, float] = {}
        self.doc_vectors: list[dict[str, float]] = []
        if self.corpus:
            self.fit(self.corpus)

    def fit(self, documents: list[str]) -> None:
        """在语料上训练IDF"""
        self.corpus = documents
        n_docs = len(documents)
        df: Counter[str] = Counter()
        doc_term_counts: list[Counter[str]] = []

        for doc in documents:
            terms = self._tokenize(doc)
            doc_term_counts.append(Counter(terms))
            for term in set(terms):
                df[term] += 1

        # IDF
        self.idf = {term: math.log((n_docs + 1) / (count + 1)) + 1 for term, count in df.items()}

        # TF-IDF向量
        self.doc_vectors = []
        for term_counts in doc_term_counts:
            vec = {}
            total = sum(term_counts.values()) or 1
            for term, count in term_counts.items():
                vec[term] = (count / total) * self.idf.get(term, 1.0)
            self.doc_vectors.append(vec)

    def _tokenize(self, text: str) -> list[str]:
        """中文bigram + 英文/数字token化"""
        tokens: list[str] = []
        # 提取英文词+数字
        eng_tokens = re.findall(r"[a-zA-Z_]\w*|\d+\.?\d*", text)
        tokens.extend(t.lower() for t in eng_tokens if len(t) >= 2)
        # 中文bigram
        cjk_chars = re.findall(r"[一-鿿]", text)
        for i in range(len(cjk_chars) - 1):
            tokens.append(cjk_chars[i] + cjk_chars[i + 1])
        return tokens

    def _vectorize(self, text: str) -> dict[str, float]:
        """将文本转为TF-IDF向量"""
        terms = self._tokenize(text)
        term_counts = Counter(terms)
        total = sum(term_counts.values()) or 1
        vec = {}
        for term, count in term_counts.items():
            tf = count / total
            idf = self.idf.get(term, 1.0)  # 未知词用默认IDF
            vec[term] = tf * idf
        return vec

    def cosine_similarity(self, vec_a: dict[str, float], vec_b: dict[str, float]) -> float:
        """两个TF-IDF向量的余弦相似度"""
        all_terms = set(vec_a) | set(vec_b)
        dot = sum(vec_a.get(t, 0) * vec_b.get(t, 0) for t in all_terms)
        norm_a = math.sqrt(sum(v**2 for v in vec_a.values()))
        norm_b = math.sqrt(sum(v**2 for v in vec_b.values()))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def match(self, query: str, candidates: list[str], threshold: float = 0.15) -> list[tuple[str, float]]:
        """查询与候选集的相似度排序"""
        q_vec = self._vectorize(query)
        results = []
        for cand in candidates:
            c_vec = self._vectorize(cand)
            sim = self.cosine_similarity(q_vec, c_vec)
            if sim >= threshold:
                results.append((cand, sim))
        return sorted(results, key=lambda x: -x[1])

    def best_match(self, query: str, candidates: list[str], threshold: float = 0.15) -> tuple[str, float]:
        """最佳匹配"""
        matches = self.match(query, candidates, threshold)
        return matches[0] if matches else ("", 0.0)

    def is_semantically_related(self, text_a: str, text_b: str, threshold: float = 0.20) -> bool:
        """判断两个文本是否语义相关"""
        vec_a = self._vectorize(text_a)
        vec_b = self._vectorize(text_b)
        return self.cosine_similarity(vec_a, vec_b) >= threshold
