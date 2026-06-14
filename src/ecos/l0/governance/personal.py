"""L0 个人知识原语 — 为个人数字大脑构建基础

支持个人数字大脑的核心组件：
- PersonalKnowledgeManager: 个人知识管理器
- KnowledgeGraphBuilder: 知识图谱构建
- PreferenceEngine: 偏好学习引擎
- RecommendationEngine: 推荐引擎
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


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
    relations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "knowledge_type": self.knowledge_type.value,
            "content": self.content,
            "relations": self.relations,
            "metadata": self.metadata,
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
    def get_recommendation(self, user_id: str, context: dict[str, Any]) -> list[KnowledgeNode]:
        pass
    
    @abstractmethod
    def get_knowledge_graph(self) -> dict[str, list[str]]:
        pass


class PersonalKnowledgeManager(PersonalKnowledgePrimitive):
    """个人知识管理器"""
    
    def __init__(self):
        self.knowledge: dict[str, KnowledgeNode] = {}
        self.preferences: dict[str, dict[str, UserPreference]] = {}
        self.relations: dict[str, list[str]] = {}
    
    def add_knowledge(self, node: KnowledgeNode) -> bool:
        self.knowledge[node.node_id] = node
        for relation in node.relations:
            if node.node_id not in self.relations:
                self.relations[node.node_id] = []
            self.relations[node.node_id].append(relation)
        return True
    
    def query_knowledge(self, query: str) -> list[KnowledgeNode]:
        results = []
        query_lower = query.lower()
        for node in self.knowledge.values():
            content_str = str(node.content).lower()
            if query_lower in content_str:
                results.append(node)
        return results
    
    def learn_preference(self, user_id: str, preference: UserPreference) -> bool:
        if user_id not in self.preferences:
            self.preferences[user_id] = {}
        self.preferences[user_id][preference.key] = preference
        return True
    
    def get_recommendation(self, user_id: str, context: dict[str, Any]) -> list[KnowledgeNode]:
        recent = sorted(self.knowledge.values(), key=lambda x: x.updated_at, reverse=True)
        return recent[:5]
    
    def get_knowledge_graph(self) -> dict[str, list[str]]:
        return self.relations


class KnowledgeGraphBuilder:
    """知识图谱构建器"""
    
    def __init__(self):
        self.edges: list[GraphEdge] = []
        self.nodes: dict[str, dict[str, Any]] = {}
    
    def add_node(self, node_id: str, metadata: dict[str, Any] | None = None) -> None:
        self.nodes[node_id] = metadata or {}
    
    def add_edge(self, source: str, target: str, relation: str, weight: float = 1.0) -> None:
        edge = GraphEdge(source=source, target=target, relation=relation, weight=weight)
        self.edges.append(edge)
    
    def get_neighbors(self, node_id: str) -> list[str]:
        neighbors = []
        for edge in self.edges:
            if edge.source == node_id:
                neighbors.append(edge.target)
            elif edge.target == node_id:
                neighbors.append(edge.source)
        return list(set(neighbors))
    
    def find_path(self, start: str, end: str, max_depth: int = 3) -> list[list[str]]:
        paths = []
        self._dfs(start, end, [], paths, max_depth)
        return paths
    
    def _dfs(self, current: str, target: str, path: list[str], paths: list[list[str]], max_depth: int):
        if current == target:
            paths.append(path + [current])
            return
        if len(path) >= max_depth:
            return
        for neighbor in self.get_neighbors(current):
            if neighbor not in path:
                self._dfs(neighbor, target, path + [current], paths, max_depth)
    
    def to_mermaid(self) -> str:
        lines = ["graph LR"]
        seen_edges = set()
        for edge in self.edges:
            edge_key = (edge.source, edge.target)
            if edge_key not in seen_edges:
                lines.append(f"    {edge.source} -->|{edge.relation}| {edge.target}")
                seen_edges.add(edge_key)
        return "\n".join(lines)


class PreferenceEngine:
    """偏好学习引擎"""
    
    def __init__(self):
        self.preferences: dict[str, dict[str, float]] = {}
    
    def learn(self, user_id: str, key: str, value: Any, weight: float = 1.0) -> None:
        if user_id not in self.preferences:
            self.preferences[user_id] = {}
        current = self.preferences[user_id].get(key, 0.0)
        self.preferences[user_id][key] = current + weight
    
    def get_preference(self, user_id: str, key: str) -> float:
        return self.preferences.get(user_id, {}).get(key, 0.0)
    
    def get_top_preferences(self, user_id: str, limit: int = 5) -> list[tuple[str, float]]:
        prefs = self.preferences.get(user_id, {})
        sorted_prefs = sorted(prefs.items(), key=lambda x: x[1], reverse=True)
        return sorted_prefs[:limit]


class RecommendationEngine:
    """推荐引擎"""
    
    def __init__(self, knowledge_manager: PersonalKnowledgeManager, preference_engine: PreferenceEngine):
        self.knowledge_manager = knowledge_manager
        self.preference_engine = preference_engine
    
    def recommend(self, user_id: str, context: dict[str, Any] | None = None) -> list[Recommendation]:
        recommendations = []
        
        # 基于知识相似度推荐
        for node in self.knowledge_manager.knowledge.values():
            score = self._calculate_relevance(user_id, node)
            if score > 0:
                recommendations.append(Recommendation(
                    node_id=node.node_id,
                    score=score,
                    reason="基于用户偏好匹配",
                ))
        
        recommendations.sort(key=lambda r: r.score, reverse=True)
        return recommendations[:5]
    
    def _calculate_relevance(self, user_id: str, node: KnowledgeNode) -> float:
        score = 0.5
        top_prefs = self.preference_engine.get_top_preferences(user_id, 3)
        for key, weight in top_prefs:
            if key in str(node.content):
                score += weight * 0.1
        return min(score, 1.0)
