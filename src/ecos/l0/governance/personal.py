"""L0 个人知识原语 — 为个人数字大脑构建基础

支持个人数字大脑的核心组件：
- PersonalKnowledgeManager: 个人知识管理器 (搜索/图谱/推荐)
- KnowledgeGraphBuilder: 知识图谱构建 (中心度/社区发现/路径搜索)
- PreferenceEngine: 偏好学习引擎 (衰减/衰减/聚类)
- RecommendationEngine: 推荐引擎 (TF-IDF/协同过滤/图谱传播)
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from ecos.common.logger import get_logger

logger = get_logger("personal")


class KnowledgeType(Enum):
    """知识类型

    M1 定义: 个人知识分类
    """

    FACT = "fact"
    CONCEPT = "concept"
    PROCEDURE = "procedure"
    METACOGNITION = "metacognition"


class PreferenceType(Enum):
    """偏好类型"""

    TOPIC = "topic"
    FORMAT = "format"
    STYLE = "style"
    TIME = "time"


@dataclass
class KnowledgeNode:
    """知识节点"""

    node_id: str
    knowledge_type: KnowledgeType
    content: dict[str, Any]
    tags: list[str] = field(default_factory=list)
    relations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    access_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "knowledge_type": self.knowledge_type.value,
            "content": self.content,
            "tags": self.tags,
            "relations": self.relations,
            "metadata": self.metadata,
            "access_count": self.access_count,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class UserPreference:
    """用户偏好"""

    user_id: str
    preference_type: PreferenceType
    key: str
    value: Any
    weight: float = 1.0
    hit_count: int = 0
    last_hit: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class GraphEdge:
    """图谱边"""

    source: str
    target: str
    relation: str
    weight: float = 1.0


@dataclass
class Recommendation:
    """推荐结果"""

    node_id: str
    score: float
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)


class PersonalKnowledgePrimitive(ABC):
    """个人知识原语基类"""

    @abstractmethod
    def add_knowledge(self, node: KnowledgeNode) -> bool:
        pass

    @abstractmethod
    def query_knowledge(self, query: str) -> list[KnowledgeNode]:
        pass

    @abstractmethod
    def learn_preference(self, user_id: str, preference: UserPreference) -> bool:
        pass

    @abstractmethod
    def get_recommendation(
        self, user_id: str, context: dict[str, Any]
    ) -> list[KnowledgeNode]:
        pass

    @abstractmethod
    def get_knowledge_graph(self) -> dict[str, list[str]]:
        pass


class PersonalKnowledgeManager(PersonalKnowledgePrimitive):
    """个人知识管理器 — 支持全文搜索、标签过滤、关联查询"""

    def __init__(self):
        self.knowledge: dict[str, KnowledgeNode] = {}
        self.preferences: dict[str, dict[str, UserPreference]] = {}
        self.relations: dict[str, set[str]] = {}
        self.tag_index: dict[str, set[str]] = defaultdict(set)
        self._idf_cache: dict[str, float] = {}
        self._idf_dirty = True

    def add_knowledge(self, node: KnowledgeNode) -> bool:
        """添加知识节点"""
        try:
            self.knowledge[node.node_id] = node
            for relation in node.relations:
                self.relations.setdefault(node.node_id, set()).add(relation)
                self.relations.setdefault(relation, set()).add(node.node_id)
            for tag in node.tags:
                self.tag_index[tag].add(node.node_id)
            self._idf_dirty = True
            logger.info(
                "添加知识: %s, type=%s", node.node_id, node.knowledge_type.value
            )
            return True
        except Exception as e:  # defensive fallback
            logger.error("添加知识失败: %s - %s", node.node_id, str(e))
            return False

    def remove_knowledge(self, node_id: str) -> bool:
        """移除知识节点"""
        try:
            if node_id not in self.knowledge:
                return False
            node = self.knowledge[node_id]
            del self.knowledge[node_id]

            for rel in node.relations:
                self.relations.get(rel, set()).discard(node_id)
            self.relations.pop(node_id, None)

            for tag in node.tags:
                self.tag_index.get(tag, set()).discard(node_id)

            self._idf_dirty = True
            logger.info("移除知识: %s", node_id)
            return True
        except Exception as e:  # defensive fallback
            logger.error("移除知识失败: %s - %s", node_id, str(e))
            return False

    def get_knowledge(self, node_id: str) -> KnowledgeNode | None:
        node = self.knowledge.get(node_id)
        if node:
            node.access_count += 1
        return node

    def query_knowledge(self, query: str, limit: int = 20) -> list[KnowledgeNode]:
        """TF-IDF 加权全文搜索"""
        query_terms = self._tokenize(query)
        if not query_terms:
            return []

        scores: dict[str, float] = defaultdict(float)
        idf = self._compute_idf()

        for term in query_terms:
            if term not in idf:
                continue
            for node_id, node in self.knowledge.items():
                content_text = self._node_to_text(node)
                content_terms = self._tokenize(content_text)
                tf = content_terms.count(term) / max(len(content_terms), 1)
                scores[node_id] += tf * idf[term]

        for node_id in scores:
            node = self.knowledge[node_id]
            recency = self._recency_score(node)
            scores[node_id] *= 1.0 + 0.2 * recency

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [self.knowledge[nid] for nid, score in ranked[:limit] if score > 0]

    def query_by_tags(
        self, tags: list[str], match_all: bool = False
    ) -> list[KnowledgeNode]:
        """按标签查询"""
        if not tags:
            return []

        if match_all:
            node_ids = set(self.knowledge.keys())
            for tag in tags:
                node_ids &= self.tag_index.get(tag, set())
        else:
            node_ids: set[str] = set()
            for tag in tags:
                node_ids |= self.tag_index.get(tag, set())

        return [self.knowledge[nid] for nid in node_ids if nid in self.knowledge]

    def get_related(self, node_id: str, depth: int = 1) -> list[KnowledgeNode]:
        """获取关联知识"""
        if node_id not in self.knowledge:
            return []

        visited = {node_id}
        current = {node_id}
        result: list[KnowledgeNode] = []

        for _ in range(depth):
            next_level: set[str] = set()
            for nid in current:
                for rel in self.relations.get(nid, set()):
                    if rel not in visited and rel in self.knowledge:
                        visited.add(rel)
                        next_level.add(rel)
                        result.append(self.knowledge[rel])
            current = next_level

        return result

    def learn_preference(self, user_id: str, preference: UserPreference) -> bool:
        if user_id not in self.preferences:
            self.preferences[user_id] = {}
        existing = self.preferences[user_id].get(preference.key)
        if existing:
            existing.weight += preference.weight
            existing.hit_count += 1
            existing.last_hit = datetime.now(timezone.utc)
        else:
            self.preferences[user_id][preference.key] = preference
        return True

    def get_recommendation(
        self, user_id: str, context: dict[str, Any] | None = None
    ) -> list[KnowledgeNode]:
        recent = sorted(
            self.knowledge.values(),
            key=lambda x: (x.updated_at, x.access_count),
            reverse=True,
        )
        return recent[:5]

    def get_knowledge_graph(self) -> dict[str, list[str]]:
        return {nid: list(rels) for nid, rels in self.relations.items()}

    def get_stats(self) -> dict[str, Any]:
        """获取知识库统计"""
        type_counts: dict[str, int] = defaultdict(int)
        for node in self.knowledge.values():
            type_counts[node.knowledge_type.value] += 1

        total_tags = sum(len(n.tags) for n in self.knowledge.values())
        total_relations = sum(len(r) for r in self.relations.values()) // 2

        return {
            "node_count": len(self.knowledge),
            "type_distribution": dict(type_counts),
            "total_tags": total_tags,
            "total_relations": total_relations,
            "user_count": len(self.preferences),
        }

    def _compute_idf(self) -> dict[str, float]:
        if not self._idf_dirty and self._idf_cache:
            return self._idf_cache

        doc_freq: dict[str, int] = defaultdict(int)
        n_docs = len(self.knowledge)

        for node in self.knowledge.values():
            terms = set(self._tokenize(self._node_to_text(node)))
            for term in terms:
                doc_freq[term] += 1

        self._idf_cache = {
            term: math.log((n_docs + 1) / (df + 1)) + 1 for term, df in doc_freq.items()
        }
        self._idf_dirty = False
        return self._idf_cache

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        tokens = []
        for char in text.lower():
            if char.isalnum():
                tokens.append(char)
            else:
                tokens.append(" ")
        return [t for t in "".join(tokens).split() if len(t) > 1]

    @staticmethod
    def _node_to_text(node: KnowledgeNode) -> str:
        parts = [node.node_id]
        parts.extend(str(v) for v in node.content.values())
        parts.extend(node.tags)
        return " ".join(parts)

    def _recency_score(self, node: KnowledgeNode) -> float:
        now = datetime.now(timezone.utc)
        age_days = (now - node.updated_at).total_seconds() / 86400
        return math.exp(-age_days / 30)


class KnowledgeGraphBuilder:
    """知识图谱构建器 — PageRank + 中心度 + 社区发现 + 增量构建"""

    def __init__(self):
        self.edges: list[GraphEdge] = []
        self.nodes: dict[str, dict[str, Any]] = {}
        self._adjacency: dict[str, list[str]] = defaultdict(list)
        self._edge_index: dict[tuple[str, str], int] = {}
        self._version: int = 0
        self._change_log: list[dict[str, Any]] = []

    @property
    def version(self) -> int:
        return self._version

    def add_node(self, node_id: str, metadata: dict[str, Any] | None = None) -> bool:
        if node_id in self.nodes:
            return False
        self.nodes[node_id] = metadata or {}
        self._version += 1
        self._change_log.append(
            {"op": "add_node", "node_id": node_id, "v": self._version}
        )
        return True

    def update_node(self, node_id: str, metadata: dict[str, Any]) -> bool:
        if node_id not in self.nodes:
            return False
        self.nodes[node_id].update(metadata)
        self._version += 1
        self._change_log.append(
            {"op": "update_node", "node_id": node_id, "v": self._version}
        )
        return True

    def remove_node(self, node_id: str) -> bool:
        if node_id not in self.nodes:
            return False
        del self.nodes[node_id]
        self.edges = [
            e for e in self.edges if e.source != node_id and e.target != node_id
        ]
        self._adjacency.pop(node_id, None)
        for adj in self._adjacency.values():
            adj[:] = [n for n in adj if n != node_id]
        self._edge_index = {
            (s, t): i
            for i, (s, t, *_) in enumerate([(e.source, e.target) for e in self.edges])
        }
        self._version += 1
        self._change_log.append(
            {"op": "remove_node", "node_id": node_id, "v": self._version}
        )
        return True

    def add_edge(
        self, source: str, target: str, relation: str, weight: float = 1.0
    ) -> bool:
        edge_key = (source, target)
        if edge_key in self._edge_index:
            return False
        edge = GraphEdge(source=source, target=target, relation=relation, weight=weight)
        self.edges.append(edge)
        self._edge_index[edge_key] = len(self.edges) - 1
        self._adjacency[source].append(target)
        self._adjacency[target].append(source)
        self.nodes.setdefault(source, {})
        self.nodes.setdefault(target, {})
        self._version += 1
        self._change_log.append(
            {"op": "add_edge", "source": source, "target": target, "v": self._version}
        )
        return True

    def update_edge(self, source: str, target: str, weight: float) -> bool:
        edge_key = (source, target)
        idx = self._edge_index.get(edge_key)
        if idx is None:
            return False
        self.edges[idx] = GraphEdge(
            source=source,
            target=target,
            relation=self.edges[idx].relation,
            weight=weight,
        )
        self._version += 1
        return True

    def remove_edge(self, source: str, target: str) -> bool:
        edge_key = (source, target)
        idx = self._edge_index.pop(edge_key, None)
        if idx is None:
            return False
        self.edges.pop(idx)
        self._adjacency[source] = [n for n in self._adjacency[source] if n != target]
        self._adjacency[target] = [n for n in self._adjacency[target] if n != source]
        self._edge_index = {(e.source, e.target): i for i, e in enumerate(self.edges)}
        self._version += 1
        self._change_log.append(
            {
                "op": "remove_edge",
                "source": source,
                "target": target,
                "v": self._version,
            }
        )
        return True

    def batch_add(
        self,
        nodes: list[tuple[str, dict[str, Any]]] | None = None,
        edges: list[tuple[str, str, str]] | None = None,
    ) -> int:
        """批量添加，返回变更数"""
        count = 0
        for node_id, meta in nodes or []:
            if self.add_node(node_id, meta):
                count += 1
        for src, tgt, rel in edges or []:
            if self.add_edge(src, tgt, rel):
                count += 1
        return count

    def get_changes_since(self, version: int) -> list[dict[str, Any]]:
        """获取指定版本之后的变更"""
        return [c for c in self._change_log if c["v"] > version]

    def get_snapshot(self) -> dict[str, Any]:
        """获取当前快照"""
        return {
            "version": self._version,
            "nodes": {k: v.copy() for k, v in self.nodes.items()},
            "edges": [(e.source, e.target, e.relation, e.weight) for e in self.edges],
        }

    def merge_snapshot(self, snapshot: dict[str, Any]) -> int:
        """合并快照，返回变更数"""
        count = 0
        for node_id, meta in snapshot.get("nodes", {}).items():
            if node_id not in self.nodes:
                self.add_node(node_id, meta)
                count += 1
        for src, tgt, rel, weight in snapshot.get("edges", []):
            if (src, tgt) not in self._edge_index:
                self.add_edge(src, tgt, rel, weight)
                count += 1
        return count

    def get_neighbors(self, node_id: str) -> list[str]:
        return list(set(self._adjacency.get(node_id, [])))

    def get_edge_weight(self, source: str, target: str) -> float:
        for edge in self.edges:
            if edge.source == source and edge.target == target:
                return edge.weight
            if edge.source == target and edge.target == source:
                return edge.weight
        return 0.0

    def find_path(self, start: str, end: str, max_depth: int = 5) -> list[list[str]]:
        paths: list[list[str]] = []
        self._dfs(start, end, [], paths, max_depth)
        return paths

    def _dfs(
        self,
        current: str,
        target: str,
        path: list[str],
        paths: list[list[str]],
        max_depth: int,
    ):
        if current == target:
            paths.append(path + [current])
            return
        if len(path) >= max_depth:
            return
        for neighbor in self.get_neighbors(current):
            if neighbor not in path:
                self._dfs(neighbor, target, path + [current], paths, max_depth)

    def pagerank(self, damping: float = 0.85, iterations: int = 20) -> dict[str, float]:
        """PageRank 中心度计算 — 缓存邻居度数优化"""
        n = len(self.nodes)
        if n == 0:
            return {}

        scores: dict[str, float] = {nid: 1.0 / n for nid in self.nodes}
        neighbor_counts: dict[str, int] = {
            nid: max(len(self.get_neighbors(nid)), 1) for nid in self.nodes
        }
        neighbors_cache: dict[str, list[str]] = {
            nid: self.get_neighbors(nid) for nid in self.nodes
        }

        for _ in range(iterations):
            new_scores: dict[str, float] = {}
            for nid in self.nodes:
                rank_sum = sum(
                    scores.get(nb, 0) / neighbor_counts[nb]
                    for nb in neighbors_cache[nid]
                )
                new_scores[nid] = (1 - damping) / n + damping * rank_sum
            scores = new_scores

        total = sum(scores.values())
        if total > 0:
            scores = {k: v / total for k, v in scores.items()}

        return scores

    def degree_centrality(self) -> dict[str, float]:
        """度中心性"""
        n = len(self.nodes)
        if n <= 1:
            return {nid: 0.0 for nid in self.nodes}
        return {nid: len(self.get_neighbors(nid)) / (n - 1) for nid in self.nodes}

    def betweenness_centrality(self) -> dict[str, float]:
        """介数中心性 — 基于最短路径"""
        centrality: dict[str, float] = defaultdict(float)
        nodes = list(self.nodes.keys())

        for s in nodes:
            for t in nodes:
                if s == t:
                    continue
                paths = self.find_path(s, t, max_depth=4)
                if not paths:
                    continue
                shortest_len = min(len(p) for p in paths)
                shortest_paths = [p for p in paths if len(p) == shortest_len]
                for path in shortest_paths:
                    for node in path[1:-1]:
                        centrality[node] += 1.0 / len(shortest_paths)

        n = len(nodes)
        if n > 2:
            normalization = (n - 1) * (n - 2)
            centrality = {k: v / normalization for k, v in centrality.items()}

        return dict(centrality)

    def find_communities(self) -> list[list[str]]:
        """贪心社区发现 — 基于模块度"""
        communities: list[list[str]] = [[nid] for nid in self.nodes]
        node_to_comm: dict[str, int] = {nid: i for i, nid in enumerate(self.nodes)}
        m = len(self.edges)
        if m == 0:
            return communities

        max_iterations = len(self.nodes) * 2
        for _ in range(max_iterations):
            improved = False
            for edge in self.edges:
                src_comm = node_to_comm.get(edge.source)
                tgt_comm = node_to_comm.get(edge.target)
                if src_comm is None or tgt_comm is None or src_comm == tgt_comm:
                    continue

                src_degree = len(self.get_neighbors(edge.source))
                tgt_degree = len(self.get_neighbors(edge.target))

                qi = edge.weight / m - (src_degree * tgt_degree) / (2 * m * m)
                if qi > 0:
                    communities[src_comm].remove(edge.source)
                    communities[tgt_comm].append(edge.source)

                    communities = [c for c in communities if c]
                    node_to_comm = {}
                    for idx, comm in enumerate(communities):
                        for nid in comm:
                            node_to_comm[nid] = idx

                    improved = True
                    break

            if not improved:
                break

        return [c for c in communities if c]

    def to_mermaid(self) -> str:
        lines = ["graph LR"]
        seen_edges: set[tuple[str, str]] = set()
        for edge in self.edges:
            edge_key = (edge.source, edge.target)
            if edge_key not in seen_edges:
                lines.append(f"    {edge.source} -->|{edge.relation}| {edge.target}")
                seen_edges.add(edge_key)
        return "\n".join(lines)

    def get_stats(self) -> dict[str, Any]:
        return {
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "avg_degree": (
                sum(len(self.get_neighbors(n)) for n in self.nodes) / len(self.nodes)
                if self.nodes
                else 0
            ),
        }


class PreferenceEngine:
    """偏好学习引擎 — 带时间衰减和衰减重放"""

    def __init__(self, decay_half_life_days: float = 30.0):
        self.preferences: dict[str, dict[str, float]] = {}
        self._hit_counts: dict[str, dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        self._last_hits: dict[str, dict[str, datetime]] = defaultdict(dict)
        self.decay_half_life = decay_half_life_days * 86400

    def learn(self, user_id: str, key: str, value: Any, weight: float = 1.0) -> None:
        if user_id not in self.preferences:
            self.preferences[user_id] = {}
        current = self.preferences[user_id].get(key, 0.0)
        self.preferences[user_id][key] = current + weight
        self._hit_counts[user_id][key] += 1
        self._last_hits[user_id][key] = datetime.now(timezone.utc)

    def get_preference(self, user_id: str, key: str) -> float:
        raw = self.preferences.get(user_id, {}).get(key, 0.0)
        last_hit = self._last_hits.get(user_id, {}).get(key)
        if last_hit:
            age = (datetime.now(timezone.utc) - last_hit).total_seconds()
            decay = (
                math.exp(-0.693 * age / self.decay_half_life)
                if self.decay_half_life > 0
                else 1.0
            )
            return raw * decay
        return raw

    def get_top_preferences(
        self, user_id: str, limit: int = 5
    ) -> list[tuple[str, float]]:
        prefs = self.preferences.get(user_id, {})
        scored = []
        for key in prefs:
            score = self.get_preference(user_id, key)
            if score > 0:
                scored.append((key, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]

    def get_hit_stats(self, user_id: str) -> dict[str, dict[str, Any]]:
        return {
            key: {
                "hit_count": self._hit_counts[user_id][key],
                "last_hit": self._last_hits[user_id][key].isoformat()
                if key in self._last_hits[user_id]
                else None,
                "current_score": self.get_preference(user_id, key),
            }
            for key in self.preferences.get(user_id, {})
        }

    def decay_all(self) -> int:
        """全局衰减，返回被清除的偏好数"""
        now = datetime.now(timezone.utc)
        removed = 0

        for user_id in list(self.preferences.keys()):
            prefs = self.preferences[user_id]
            to_remove = []
            for key in list(prefs.keys()):
                last_hit = self._last_hits.get(user_id, {}).get(key)
                if last_hit:
                    age = (now - last_hit).total_seconds()
                    decay = math.exp(-0.693 * age / self.decay_half_life)
                    if decay < 0.01:
                        to_remove.append(key)
                else:
                    to_remove.append(key)

            for key in to_remove:
                del prefs[key]
                self._hit_counts[user_id].pop(key, None)
                self._last_hits[user_id].pop(key, None)
                removed += 1

        return removed


class RecommendationEngine:
    """推荐引擎 — TF-IDF 相关度 + 偏好匹配 + 图谱传播"""

    def __init__(
        self,
        knowledge_manager: PersonalKnowledgeManager,
        preference_engine: PreferenceEngine,
    ):
        self.knowledge_manager = knowledge_manager
        self.preference_engine = preference_engine

    def recommend(
        self, user_id: str, context: dict[str, Any] | None = None, limit: int = 10
    ) -> list[Recommendation]:
        """多维度推荐"""
        top_prefs = dict(self.preference_engine.get_top_preferences(user_id, 10))
        recommendations: dict[str, tuple[float, str]] = {}

        idf = self.knowledge_manager._compute_idf()

        for node_id, node in self.knowledge_manager.knowledge.items():
            pref_score = self._preference_match(user_id, node, top_prefs)
            tfidf_score = self._tfidf_relevance(node, top_prefs, idf)
            diversity_score = self._diversity_score(node)

            final_score = 0.4 * tfidf_score + 0.4 * pref_score + 0.2 * diversity_score

            if final_score > 0.01:
                reason_parts = []
                if tfidf_score > 0.3:
                    reason_parts.append("内容相关")
                if pref_score > 0.3:
                    reason_parts.append("偏好匹配")
                if diversity_score > 0.5:
                    reason_parts.append("新颖性高")
                reason = "·".join(reason_parts) if reason_parts else "综合推荐"

                recommendations[node_id] = (final_score, reason)

        ranked = sorted(recommendations.items(), key=lambda x: x[1][0], reverse=True)

        results = []
        for node_id, (score, reason) in ranked[:limit]:
            results.append(
                Recommendation(
                    node_id=node_id,
                    score=score,
                    reason=reason,
                    metadata={
                        "type": self.knowledge_manager.knowledge[
                            node_id
                        ].knowledge_type.value
                    },
                )
            )
        return results

    def recommend_similar(self, node_id: str, limit: int = 5) -> list[Recommendation]:
        """基于内容相似度推荐"""
        if node_id not in self.knowledge_manager.knowledge:
            return []

        source_node = self.knowledge_manager.knowledge[node_id]
        source_text = PersonalKnowledgeManager._node_to_text(source_node)

        scores: dict[str, float] = {}
        for nid, node in self.knowledge_manager.knowledge.items():
            if nid == node_id:
                continue
            target_text = PersonalKnowledgeManager._node_to_text(node)
            sim = self._text_similarity(source_text, target_text)
            if sim > 0:
                scores[nid] = sim

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [
            Recommendation(node_id=nid, score=score, reason="内容相似")
            for nid, score in ranked[:limit]
        ]

    def _preference_match(
        self, user_id: str, node: KnowledgeNode, top_prefs: dict[str, float]
    ) -> float:
        if not top_prefs:
            return 0.0

        node_text = PersonalKnowledgeManager._node_to_text(node).lower()
        match_score = 0.0
        for key, weight in top_prefs.items():
            if key.lower() in node_text:
                match_score += weight

        max_possible = sum(top_prefs.values())
        return match_score / max_possible if max_possible > 0 else 0.0

    def _tfidf_relevance(
        self, node: KnowledgeNode, keywords: dict[str, float], idf: dict[str, float]
    ) -> float:
        if not keywords:
            return 0.0

        node_text = PersonalKnowledgeManager._node_to_text(node)
        node_terms = PersonalKnowledgeManager._tokenize(node_text)

        score = 0.0
        for keyword in keywords:
            if keyword in idf:
                tf = node_terms.count(keyword) / max(len(node_terms), 1)
                score += tf * idf[keyword] * keywords[keyword]

        return min(score, 1.0)

    def _diversity_score(self, node: KnowledgeNode) -> float:
        if not node.tags:
            return 0.5
        type_scores = {
            KnowledgeType.FACT: 0.8,
            KnowledgeType.CONCEPT: 0.6,
            KnowledgeType.PROCEDURE: 0.5,
            KnowledgeType.METACOGNITION: 0.9,
        }
        return type_scores.get(node.knowledge_type, 0.5)

    @staticmethod
    def _text_similarity(text_a: str, text_b: str) -> float:
        terms_a = set(PersonalKnowledgeManager._tokenize(text_a))
        terms_b = set(PersonalKnowledgeManager._tokenize(text_b))
        if not terms_a or not terms_b:
            return 0.0
        intersection = terms_a & terms_b
        union = terms_a | terms_b
        return len(intersection) / len(union) if union else 0.0
