"""L0 个人知识原语 — 为个人数字大脑构建基础"""

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
    FACT = "fact"                   # 事实
    CONCEPT = "concept"             # 概念
    PROCEDURE = "procedure"         # 程序
    METACOGNITION = "metacognition"  # 元认知


class PreferenceType(Enum):
    """偏好类型"""
    TOPIC = "topic"         # 主题偏好
    FORMAT = "format"       # 格式偏好
    STYLE = "style"         # 风格偏好
    TIME = "time"           # 时间偏好


@dataclass
class KnowledgeNode:
    """知识节点
    
    L0 原语: 个人知识的基本单元
    """
    node_id: str
    knowledge_type: KnowledgeType
    content: dict[str, Any]
    relations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
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


class PersonalKnowledgePrimitive(ABC):
    """个人知识原语基类
    
    L0 原语: 所有个人知识操作必须继承此基类
    """
    
    @abstractmethod
    def add_knowledge(self, node: KnowledgeNode) -> bool:
        """添加知识"""
        pass
    
    @abstractmethod
    def query_knowledge(self, query: str) -> list[KnowledgeNode]:
        """查询知识"""
        pass
    
    @abstractmethod
    def learn_preference(self, user_id: str, preference: UserPreference) -> bool:
        """学习偏好"""
        pass
    
    @abstractmethod
    def get_recommendation(self, user_id: str, context: dict[str, Any]) -> list[KnowledgeNode]:
        """获取推荐"""
        pass
    
    @abstractmethod
    def get_knowledge_graph(self) -> dict[str, list[str]]:
        """获取知识图谱"""
        pass


class PersonalKnowledgeManager(PersonalKnowledgePrimitive):
    """个人知识管理器实现"""
    
    def __init__(self):
        self.knowledge: dict[str, KnowledgeNode] = {}
        self.preferences: dict[str, dict[str, UserPreference]] = {}
        self.relations: dict[str, list[str]] = {}
    
    def add_knowledge(self, node: KnowledgeNode) -> bool:
        """添加知识"""
        self.knowledge[node.node_id] = node
        
        # 更新关系图
        for relation in node.relations:
            if node.node_id not in self.relations:
                self.relations[node.node_id] = []
            self.relations[node.node_id].append(relation)
        
        return True
    
    def query_knowledge(self, query: str) -> list[KnowledgeNode]:
        """查询知识"""
        # 简化实现：关键词匹配
        results = []
        query_lower = query.lower()
        
        for node in self.knowledge.values():
            content_str = str(node.content).lower()
            if query_lower in content_str:
                results.append(node)
        
        return results
    
    def learn_preference(self, user_id: str, preference: UserPreference) -> bool:
        """学习偏好"""
        if user_id not in self.preferences:
            self.preferences[user_id] = {}
        
        self.preferences[user_id][preference.key] = preference
        return True
    
    def get_recommendation(self, user_id: str, context: dict[str, Any]) -> list[KnowledgeNode]:
        """获取推荐"""
        # 简化实现：返回最近添加的知识
        recent = sorted(
            self.knowledge.values(),
            key=lambda x: x.updated_at,
            reverse=True
        )
        return recent[:5]
    
    def get_knowledge_graph(self) -> dict[str, list[str]]:
        """获取知识图谱"""
        return self.relations
