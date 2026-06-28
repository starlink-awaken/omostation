"""SQLite 持久化存储 — 研究结果、用户状态、系统历史。

IDataAccess Protocol 接口层支持 SQLite 和未来 MCP/HTTP 后端切换。
"""

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

DB_PATH = Path.home() / ".workspace" / "data.db"

# P110-F (TASK-F7114ABA 治本): SQLiteDataAccess 拆分
from .storage_sqlite import SQLiteDataAccess

# ──────────────────────────────────────────────────────────────────────
# W011: IDataAccess Protocol
# ──────────────────────────────────────────────────────────────────────


@runtime_checkable
class IDataAccess(Protocol):
    """数据访问层接口 — 支持 SQLite 和未来 MCP/HTTP 后端。"""

    def save_research(
        self,
        topic: str,
        summary: str,
        full_text: str = "",
        source_count: int = 0,
        agent: str = "",
    ) -> int: ...

    def add_follow_up(self, research_id: int, question: str, answer: str) -> None: ...

    def list_research(
        self,
        limit: int = 10,
        include_quarantined: bool = False,
        include_archived: bool = False,
    ) -> list[dict[str, Any]]: ...

    def search_research(self, keyword: str, limit: int = 10) -> list[dict[str, Any]]: ...

    def get_research(self, research_id: int) -> dict[str, Any] | None: ...

    def set_research_tags(self, research_id: int, tags: list[str]) -> list[str]: ...

    def rename_research(self, research_id: int, new_topic: str) -> bool: ...

    def quarantine_research(
        self,
        research_ids: list[int],
        reason: str = "manual quarantine",
    ) -> tuple[list[int], list[int]]: ...

    def restore_research(self, research_ids: list[int]) -> tuple[list[int], list[int]]: ...

    def archive_research(
        self,
        research_ids: list[int],
        reason: str = "manual archive",
    ) -> tuple[list[int], list[int]]: ...

    def restore_archived_research(self, research_ids: list[int]) -> tuple[list[int], list[int]]: ...

    def add_research_relations(
        self,
        parent_ids: list[int],
        child_id: int,
        relation_type: str,
    ) -> None: ...

    def save_published_report(self, research_id: int, style: str, output_path: str) -> int: ...

    def get_research_timeline(self, research_id: int) -> list[dict[str, Any]]: ...

    def get_research_dossier(self, research_id: int) -> dict[str, Any] | None: ...

    def set_research_agent(self, research_id: int, agent_name: str) -> bool: ...

    def compute_half_life(self, research_id: int) -> dict[str, Any]: ...

    def export_backup(self) -> dict[str, Any]: ...

    def import_backup(self, data: dict[str, Any]) -> dict[str, int]: ...


# ──────────────────────────────────────────────────────────────────────
# W012: SQLiteDataAccess 实现
# ──────────────────────────────────────────────────────────────────────


# W013: 全局 accessor
# ──────────────────────────────────────────────────────────────────────

_DATA_ACCESS: IDataAccess | None = None


def get_data_access() -> IDataAccess:
    global _DATA_ACCESS
    if _DATA_ACCESS is None:
        _DATA_ACCESS = SQLiteDataAccess()
    return _DATA_ACCESS


def set_data_access(accessor: IDataAccess) -> None:
    """测试用：注入 mock 实现。"""
    global _DATA_ACCESS
    _DATA_ACCESS = accessor


# ──────────────────────────────────────────────────────────────────────
# 向后兼容 shim：模块级函数委托到全局 accessor
# ──────────────────────────────────────────────────────────────────────


def save_research(topic: str, summary: str, full_text: str = "", source_count: int = 0, agent: str = "") -> int:
    return get_data_access().save_research(topic, summary, full_text, source_count, agent)


def add_follow_up(research_id: int, question: str, answer: str) -> None:
    return get_data_access().add_follow_up(research_id, question, answer)


def list_research(
    limit: int = 10, include_quarantined: bool = False, include_archived: bool = False
) -> list[dict[str, Any]]:
    return get_data_access().list_research(limit, include_quarantined, include_archived)


def search_research(keyword: str, limit: int = 10) -> list[dict[str, Any]]:
    return get_data_access().search_research(keyword, limit)


def get_research(research_id: int) -> dict[str, Any] | None:
    return get_data_access().get_research(research_id)


def _normalize_tags(tags: list[str]) -> list[str]:
    return SQLiteDataAccess._normalize_tags(tags)


def set_research_tags(research_id: int, tags: list[str]) -> list[str]:
    return get_data_access().set_research_tags(research_id, tags)


def rename_research(research_id: int, new_topic: str) -> bool:
    return get_data_access().rename_research(research_id, new_topic)


def quarantine_research(research_ids: list[int], reason: str = "manual quarantine") -> tuple[list[int], list[int]]:
    return get_data_access().quarantine_research(research_ids, reason)


def restore_research(research_ids: list[int]) -> tuple[list[int], list[int]]:
    return get_data_access().restore_research(research_ids)


def archive_research(research_ids: list[int], reason: str = "manual archive") -> tuple[list[int], list[int]]:
    return get_data_access().archive_research(research_ids, reason)


def restore_archived_research(research_ids: list[int]) -> tuple[list[int], list[int]]:
    return get_data_access().restore_archived_research(research_ids)


def add_research_relations(parent_ids: list[int], child_id: int, relation_type: str) -> None:
    return get_data_access().add_research_relations(parent_ids, child_id, relation_type)


def save_published_report(research_id: int, style: str, output_path: str) -> int:
    return get_data_access().save_published_report(research_id, style, output_path)


def get_research_timeline(research_id: int) -> list[dict[str, Any]]:
    return get_data_access().get_research_timeline(research_id)


def get_research_dossier(research_id: int) -> dict[str, Any] | None:
    return get_data_access().get_research_dossier(research_id)


def set_research_agent(research_id: int, agent_name: str) -> bool:
    return get_data_access().set_research_agent(research_id, agent_name)


def compute_half_life(research_id: int) -> dict[str, Any]:
    return get_data_access().compute_half_life(research_id)


def export_backup() -> dict[str, Any]:
    return get_data_access().export_backup()


def import_backup(data: dict[str, Any]) -> dict[str, int]:
    return get_data_access().import_backup(data)
