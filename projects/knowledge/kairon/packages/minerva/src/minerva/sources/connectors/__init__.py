from __future__ import annotations

"""
数据源连接器接口

Extracted from SharedBrain D_Harvest → minerva.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class RawContent:
    """原始内容"""

    uri: str
    data: str | bytes
    content_type: str
    metadata: dict = field(default_factory=dict)


class ISourceConnector(ABC):
    """数据源连接器接口"""

    @abstractmethod
    async def fetch(self) -> RawContent:
        """获取原始内容"""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """健康检查"""
        pass

    @property
    @abstractmethod
    def source_id(self) -> str:
        """数据源ID"""
        pass
