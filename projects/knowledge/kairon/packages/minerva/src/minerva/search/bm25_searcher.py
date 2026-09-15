from __future__ import annotations

"""
Extracted from SharedBrain D_Harvest → minerva.

---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# Bm25 Searcher ≡ Module
# 内涵 ≝ {Bm25, Searcher}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, Bm25Searcher)}
# 功能 ⊢ {Bm25_Searcher, Init_Bm25, Validate_Searcher}
# =============================================================================

# ---
# domain: D-Harvest
# layer: organ
# status: active
# ---

"""
BM25 搜索实现

基于 BM25 算法的全文搜索引擎，支持中英文混合分词。
参考 D-Excretion/organs/archive_index.py 的实现模式。

算法参数：
- k1: 1.5 (词频饱和参数)
- b: 0.75 (长度归一化参数)
- 支持实时索引更新
"""

import logging
import pickle
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import numpy as np

_log = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """搜索结果条目"""

    id: int
    title: str
    body: str
    uri: str
    quality_score: float
    harvested_at: str
    metadata: dict = field(default_factory=dict)
    bm25_score: float = 0.0
    matched_terms: list[str] = field(default_factory=list)


class Tokenizer:
    """
    中英双语分词器

    - 英文：按单词分割，转为小写，去除标点
    - 中文：按字分割，支持连续汉字识别
    """

    # 中文 Unicode 范围
    CHINESE_PATTERN = re.compile(r"[\u4e00-\u9fff]")
    # 英文单词
    ENGLISH_PATTERN = re.compile(r"[a-zA-Z]+")
    # 数字
    NUMBER_PATTERN = re.compile(r"\d+")

    # 停用词（简化版）
    STOP_WORDS = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "must",
        "can",
        "this",
        "that",
        "these",
        "those",
        "i",
        "you",
        "he",
        "she",
        "it",
        "we",
        "they",
        "me",
        "him",
        "her",
        "us",
        "them",
        "my",
        "your",
        "his",
        "its",
        "our",
        "their",
        # 中文停用词
        "的",
        "了",
        "在",
        "是",
        "我",
        "有",
        "和",
        "就",
        "不",
        "人",
        "都",
        "一",
        "一个",
        "上",
        "也",
        "很",
        "到",
        "说",
        "要",
        "去",
        "你",
        "会",
        "着",
        "没有",
        "看",
        "好",
        "自己",
        "这",
    }

    def tokenize(self, text: str) -> list[str]:
        """
        对文本进行分词

        支持中英混合文本，对英文进行更细粒度的分割处理。

        Args:
            text: 输入文本

        Returns:
            分词结果列表
        """
        if not text:
            return []

        tokens = []
        i = 0
        text_len = len(text)

        while i < text_len:
            char = text[i]

            # 跳过空白字符和标点
            if char.isspace() or char in '.,!?;:\'"()[]{}《》【】、，。！？；："（）「」':
                i += 1
                continue

            # 中文：按字分割
            if self.CHINESE_PATTERN.match(char):
                token = char
                # 尝试收集连续的汉字（最长匹配）
                j = i + 1
                while j < text_len and self.CHINESE_PATTERN.match(text[j]):
                    token += text[j]
                    j += 1

                # 对于短词（1-2字）直接加入，长词拆分为字
                if len(token) <= 2:
                    if token not in self.STOP_WORDS:
                        tokens.append(token)
                else:
                    # 长词同时加入整词和单字
                    if token not in self.STOP_WORDS:
                        tokens.append(token)
                    # 同时加入前几个字作为特征
                    for k in range(min(4, len(token))):
                        if token[k] not in self.STOP_WORDS:
                            tokens.append(token[k])

                i = j
                continue

            # 英文单词
            if char.isalpha():
                j = i
                while j < text_len and text[j].isalpha():
                    j += 1
                word = text[i:j].lower()

                # 处理英文单词：添加完整单词和子词
                if word not in self.STOP_WORDS and len(word) > 1:
                    tokens.append(word)

                    # 对于较长的单词，也添加前3个字符（前缀匹配）
                    if len(word) >= 5:
                        tokens.append(word[:3])
                        tokens.append(word[:4])
                i = j
                continue

            # 数字
            if char.isdigit():
                j = i
                while j < text_len and text[j].isdigit():
                    j += 1
                tokens.append(text[i:j])
                i = j
                continue

            i += 1

        return tokens

    def tokenize_for_index(self, text: str) -> list[str]:
        """分词用于索引（去重）"""
        tokens = self.tokenize(text)
        return list(dict.fromkeys(tokens))  # 保持顺序去重


class BM25Index:
    """
    BM25 倒排索引

    存储倒排索引和文档统计信息，支持增量更新。
    """

    # BM25 参数
    K1 = 1.5  # 词频饱和参数
    B = 0.75  # 长度归一化参数
    EPSILON = 0.25  # IDF 平滑参数

    def __init__(self) -> None:
        # 倒排索引: {token: {doc_id: tf}}
        self._index: dict[str, dict[int, int]] = {}
        # 文档长度: {doc_id: length}
        self._doc_lengths: dict[int, int] = {}
        # 文档总数
        self._total_docs = 0
        # 平均文档长度
        self._avg_doc_length = 0.0
        # 文档内容缓存（用于计算相关性）
        self._doc_cache: dict[int, dict[str, Any]] = {}
        # 最后更新时间
        self._last_updated = datetime.now(UTC).isoformat()

    def add_document(self, doc_id: int, tokens: list[str], content: dict[str, Any]) -> None:
        """
        添加文档到索引

        Args:
            doc_id: 文档ID
            tokens: 分词后的词列表
            content: 文档原始内容
        """
        # 如果文档已存在，先移除
        if doc_id in self._doc_lengths:
            self.remove_document(doc_id)

        # 统计词频
        token_counts: dict[str, int] = {}
        for token in tokens:
            token_counts[token] = token_counts.get(token, 0) + 1

        # 更新倒排索引
        for token, count in token_counts.items():
            if token not in self._index:
                self._index[token] = {}
            self._index[token][doc_id] = count

        # 更新文档统计
        self._doc_lengths[doc_id] = len(tokens)
        self._doc_cache[doc_id] = content
        self._total_docs += 1

        # 更新平均长度
        if self._total_docs > 0:
            total_len = sum(self._doc_lengths.values())
            self._avg_doc_length = total_len / self._total_docs

        self._last_updated = datetime.now(UTC).isoformat()

    def remove_document(self, doc_id: int) -> None:
        """从索引中移除文档"""
        if doc_id not in self._doc_lengths:
            return

        # 从倒排索引中移除
        tokens_to_remove = []
        for token, postings in self._index.items():
            if doc_id in postings:
                del postings[doc_id]
                if not postings:
                    tokens_to_remove.append(token)

        for token in tokens_to_remove:
            del self._index[token]

        # 更新统计
        del self._doc_lengths[doc_id]
        del self._doc_cache[doc_id]
        self._total_docs -= 1

        # 更新平均长度
        if self._total_docs > 0:
            total_len = sum(self._doc_lengths.values())
            self._avg_doc_length = total_len / self._total_docs
        else:
            self._avg_doc_length = 0.0

        self._last_updated = datetime.now(UTC).isoformat()

    def calculate_idf(self, token: str) -> float:
        """
        计算逆文档频率（IDF）

        使用 BM25 的标准 IDF 公式：
        IDF = log((N - df + 0.5) / (df + 0.5))

        Args:
            token: 查询词

        Returns:
            IDF 值
        """
        if token not in self._index:
            return 0.0

        df = len(self._index[token])  # 文档频率
        n = self._total_docs

        # 标准 BM25 IDF
        idf = np.log((n - df + 0.5) / (df + 0.5) + self.EPSILON)
        return cast("float", max(0.0, idf))

    def search(self, query_tokens: list[str], top_k: int = 10) -> list[tuple[int, float, list[str]]]:
        """
        执行 BM25 搜索

        Args:
            query_tokens: 查询词列表
            top_k: 返回结果数量

        Returns:
            结果列表: [(doc_id, score, matched_terms), ...]
        """
        if not query_tokens or self._total_docs == 0:
            return []

        scores: dict[int, float] = {}
        matched_terms: dict[int, set[str]] = {}

        for token in query_tokens:
            if token not in self._index:
                continue

            idf = self.calculate_idf(token)

            # 遍历包含该词的文档
            for doc_id, tf in self._index[token].items():
                doc_length = self._doc_lengths.get(doc_id, 0)

                # BM25 公式
                # score = IDF * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (dl / avgdl)))
                dl_ratio = doc_length / (self._avg_doc_length or 1.0)
                denominator = tf + self.K1 * (1 - self.B + self.B * dl_ratio)

                if denominator > 0:
                    score = idf * (tf * (self.K1 + 1)) / denominator
                    scores[doc_id] = scores.get(doc_id, 0.0) + score

                    if doc_id not in matched_terms:
                        matched_terms[doc_id] = set()
                    matched_terms[doc_id].add(token)

        # 按分数排序并返回
        sorted_results = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

        return [(doc_id, score, list(matched_terms.get(doc_id, []))) for doc_id, score in sorted_results]

    def get_stats(self) -> dict[str, Any]:
        """获取索引统计信息"""
        return {
            "total_docs": self._total_docs,
            "total_tokens": len(self._index),
            "avg_doc_length": round(self._avg_doc_length, 2),
            "last_updated": self._last_updated,
        }

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        return {
            "index": self._index,
            "doc_lengths": self._doc_lengths,
            "total_docs": self._total_docs,
            "avg_doc_length": self._avg_doc_length,
            "doc_cache": self._doc_cache,
            "last_updated": self._last_updated,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BM25Index:
        """从字典反序列化"""
        index = cls()
        index._index = data.get("index", {})
        index._doc_lengths = data.get("doc_lengths", {})
        index._total_docs = data.get("total_docs", 0)
        index._avg_doc_length = data.get("avg_doc_length", 0.0)
        index._doc_cache = data.get("doc_cache", {})
        index._last_updated = data.get("last_updated", datetime.now(UTC).isoformat())
        return index


class BM25Searcher:
    """
    BM25 搜索器

    为 KnowledgeStore 提供 BM25 全文搜索能力。
    支持索引持久化和自动刷新。

    使用示例：
        searcher = BM25Searcher()
        await searcher.build_index(knowledge_store)
        results = await searcher.search("深度学习", top_k=10)
    """

    def __init__(self, cache_dir: Path | None = None) -> None:
        """
        初始化 BM25 搜索器

        Args:
            cache_dir: 索引缓存目录（默认: .omc/cache/bm25）
        """
        self.cache_dir = cache_dir or Path(".omc/cache/bm25")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.index = BM25Index()
        self.tokenizer = Tokenizer()
        self._index_built = False
        self._cache_file = self.cache_dir / "bm25_index.pkl"

        # 尝试加载缓存的索引
        self._load_cached_index()

    def _load_cached_index(self) -> None:
        """从缓存加载索引"""
        if self._cache_file.exists():
            try:
                with open(self._cache_file, "rb") as f:
                    data = pickle.load(f)  # noqa: S301
                    self.index = BM25Index.from_dict(data)
                    self._index_built = True
                    _log.info(f"[BM25Searcher] Loaded cached index: {self.index.get_stats()}")
            except (OSError, pickle.UnpicklingError, KeyError, ValueError) as e:
                _log.warning(f"[BM25Searcher] Failed to load cached index: {e}")
                self.index = BM25Index()
                self._index_built = False

    def _save_cached_index(self) -> None:
        """保存索引到缓存"""
        try:
            with open(self._cache_file, "wb") as f:
                pickle.dump(self.index.to_dict(), f)
            _log.info("[BM25Searcher] Index cached successfully")
        except OSError as e:
            _log.warning(f"[BM25Searcher] Failed to cache index: {e}")

    async def build_index(
        self, knowledge_store: Any, min_quality: float = 0.0, force_rebuild: bool = False
    ) -> dict[str, Any]:
        """
        构建 BM25 索引

        Args:
            knowledge_store: KnowledgeStore 实例
            min_quality: 最低质量分数
            force_rebuild: 强制重建索引

        Returns:
            索引统计信息
        """
        if self._index_built and not force_rebuild:
            _log.info("[BM25Searcher] Using existing index")
            return self.index.get_stats()

        _log.info("[BM25Searcher] Building BM25 index...")

        # 获取所有知识条目
        items = await knowledge_store.list_knowledge(
            limit=100000,  # 大量条目
            min_quality=min_quality,
        )

        # 清空现有索引
        self.index = BM25Index()

        for item in items:
            doc_id = item.get("id", 0)
            title = item.get("title", "")
            body = item.get("body", "")

            # 组合标题和正文进行索引（标题权重更高）
            index_text = f"{title} {title} {body}"  # 标题重复一次增加权重
            tokens = self.tokenizer.tokenize_for_index(index_text)

            self.index.add_document(doc_id, tokens, item)

        self._index_built = True

        # 保存缓存
        self._save_cached_index()

        stats = self.index.get_stats()
        _log.info(f"[BM25Searcher] Index built: {stats}")
        return stats

    async def add_document(self, doc_id: int, title: str, body: str, metadata: dict) -> None:
        """
        添加单个文档到索引（增量更新）

        Args:
            doc_id: 文档ID
            title: 标题
            body: 正文
            metadata: 元数据
        """
        index_text = f"{title} {title} {body}"
        tokens = self.tokenizer.tokenize_for_index(index_text)

        content = {
            "id": doc_id,
            "title": title,
            "body": body,
            "metadata": metadata,
        }

        self.index.add_document(doc_id, tokens, content)

        # 定期保存缓存（每 10 个文档）
        if doc_id % 10 == 0:
            self._save_cached_index()

    async def search(self, query: str, top_k: int = 20, min_quality: float = 0.0) -> list[SearchResult]:
        """
        执行 BM25 搜索

        Args:
            query: 搜索查询
            top_k: 返回结果数量
            min_quality: 最低质量分数过滤

        Returns:
            搜索结果列表
        """
        if not self._index_built:
            _log.warning("[BM25Searcher] Index not built, returning empty results")
            return []

        # 分词
        query_tokens = self.tokenizer.tokenize(query)
        if not query_tokens:
            return []

        _log.debug(f"[BM25Searcher] Searching with tokens: {query_tokens}")

        # 执行搜索
        raw_results = self.index.search(query_tokens, top_k=top_k * 2)  # 获取更多用于过滤

        results = []
        for doc_id, score, matched in raw_results:
            # 获取完整文档内容
            content = self.index._doc_cache.get(doc_id, {})

            # 质量过滤
            quality = content.get("quality_score", 0.0)
            if quality < min_quality:
                continue

            results.append(
                SearchResult(
                    id=doc_id,
                    title=content.get("title", ""),
                    body=content.get("body", ""),
                    uri=content.get("uri", ""),
                    quality_score=quality,
                    harvested_at=content.get("harvested_at", ""),
                    metadata=content.get("metadata", {}),
                    bm25_score=score,
                    matched_terms=matched,
                )
            )

            if len(results) >= top_k:
                break

        _log.info(f"[BM25Searcher] Query '{query}' returned {len(results)} results")
        return results

    async def search_with_fallback(
        self, query: str, knowledge_store: Any, top_k: int = 20, min_quality: float = 0.0
    ) -> list[SearchResult]:
        """
        带后备的搜索（如果索引未构建，使用简单的 LIKE 查询）

        Args:
            query: 搜索查询
            knowledge_store: KnowledgeStore 实例（用于后备查询）
            top_k: 返回结果数量
            min_quality: 最低质量分数

        Returns:
            搜索结果列表
        """
        if self._index_built:
            return await self.search(query, top_k, min_quality)

        # 后备：使用知识存储的简单搜索
        _log.warning("[BM25Searcher] Using fallback search (index not built)")
        items = await knowledge_store.search_knowledge(query, top_k, min_quality)

        return [
            SearchResult(
                id=item.get("id", 0),
                title=item.get("title", ""),
                body=item.get("body", ""),
                uri=item.get("uri", ""),
                quality_score=item.get("quality_score", 0.0),
                harvested_at=item.get("harvested_at", ""),
                metadata=item.get("metadata", {}),
                bm25_score=0.0,
                matched_terms=[],
            )
            for item in items
        ]

    def get_stats(self) -> dict[str, Any]:
        """获取搜索器统计信息"""
        return {
            "index_built": self._index_built,
            "cache_file": str(self._cache_file),
            **self.index.get_stats(),
        }

    def clear_cache(self) -> None:
        """清除索引缓存"""
        if self._cache_file.exists():
            self._cache_file.unlink()
            _log.info("[BM25Searcher] Cache cleared")
        self.index = BM25Index()
        self._index_built = False
