from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Layer: L3
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
---
"""


import collections
import logging
import re
from pathlib import Path
from typing import Any, cast

import yaml

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Memory_Organ ≡ Memory_System
# 内涵 ≝ {Store, Retrieve, Index, Compact}
# 外延 ≝ {m | m ∈ D-Memory ∧ persists(m, Knowledge)}
# 功能 ⊢ {StoreMemories, RetrieveMemories, MaintainIndex}
# =============================================================================

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Sisyphus'
Authority: organs/D-Memory/AGENTS.md
Layer: L0
Constraint: "[!!] READ_ONLY_GENETIC_MEMORY"
Summary: 'ArchetypeLoader: 读取 Z-Spore 原型库，提供 Layer 0 基因记忆访问接口（带 LRU 缓存）'
---
"""
# 🧬 基因记忆加载器 (ArchetypeLoader)
# 职责: 读取 nucleus/Z-Spore/archetypes/ 中的 YAML/MD 原型，提供带缓存的只读访问
# 支持:
#   workers/*.yaml  → Agent 原型
#   synapses/*.yaml → Tool 原型
#   cells/*.md      → Law/Rule 原型（解析 YAML frontmatter）
#   skills/*.md     → Skill 原型

_log = logging.getLogger(__name__)

# Use centralized path resolver (lazy to avoid module-level descriptor failures)
# TODO-migrate: from nucleus.Z_Microkernel.organs.paths import ProjectPaths


class _ProjectPathsStub:
    """Stub replacement for nucleus ProjectPaths until migration is complete."""

    ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent


ProjectPaths = _ProjectPathsStub


def _get_archetypes_root() -> Path:
    return ProjectPaths.ROOT / "nucleus" / "Z-Spore" / "archetypes"


def _parse_yaml_frontmatter(content: str) -> dict[str, Any]:
    """从 Markdown 文件中提取 YAML frontmatter（--- 包裹的块）"""
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        _log.debug("No YAML frontmatter found in content (length=%d)", len(content))
        return {}
    try:
        result = yaml.safe_load(match.group(1))
        if not isinstance(result, dict):
            _log.warning("YAML frontmatter is not a dict (got %s)", type(result).__name__)
            return {}
        return result
    except yaml.YAMLError as exc:
        _log.warning("Failed to parse YAML frontmatter: %s", exc)
        return {}


class ArchetypeLoader:
    """
    Layer 0 基因记忆加载器。

    从 nucleus/Z-Spore/archetypes/ 读取原型定义，所有数据只读，带内存缓存。
    缓存键格式: 'yaml:{subdir}' 或 'md:{subdir}'
    """

    def __init__(self, archetypes_root: Path | None = None, max_cache_size: int = 100) -> None:
        self._root = archetypes_root or _get_archetypes_root()
        # LRU缓存：使用OrderedDict实现LRU淘汰
        self._cache: collections.OrderedDict[str, Any] = collections.OrderedDict()
        self._max_cache_size = max_cache_size

    # ── LRU缓存辅助方法 ─────────────────────────────────────────

    def _get_from_cache(self, key: str) -> Any | None:
        """从LRU缓存获取数据，如果存在则移动到最近使用位置"""
        if key in self._cache:
            # 移动到末尾（最近使用）
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def _set_to_cache(self, key: str, value: Any) -> None:
        """设置缓存数据，应用LRU淘汰策略"""
        if key in self._cache:
            # 更新现有条目，移动到末尾
            self._cache[key] = value
            self._cache.move_to_end(key)
        else:
            # 添加新条目
            self._cache[key] = value
            # 如果超过最大大小，移除最旧的条目
            if len(self._cache) > self._max_cache_size:
                self._cache.popitem(last=False)

    # ── 内部加载方法 ─────────────────────────────────────────────

    def _load_yaml_dir(self, subdir: str) -> dict[str, Any]:
        """
        加载目录下所有 YAML 文件。
        支持多文档 YAML（--- 分隔），返回 {filename_stem: data_or_list}。
        """
        cache_key = f"yaml:{subdir}"
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cast("dict[str, Any]", cached)

        result: dict[str, Any] = {}
        target_dir = self._root / subdir
        if not target_dir.exists():
            self._set_to_cache(cache_key, result)
            return result

        for yaml_file in sorted(target_dir.glob("*.yaml")):
            try:
                content = yaml_file.read_text(encoding="utf-8")
                docs = list(yaml.safe_load_all(content))
                # 过滤掉 None 文档
                docs = [d for d in docs if d is not None]
                if not docs:
                    continue
                result[yaml_file.stem] = docs[0] if len(docs) == 1 else docs
            except (yaml.YAMLError, OSError) as e:
                # 格式错误或读取失败，跳过该文件
                _log.warning("YAML archetype file load failed: %s", e)

        self._cache[cache_key] = result
        return result

    def _load_md_dir(self, subdir: str) -> dict[str, Any]:
        """
        加载目录下所有 MD 文件的 YAML frontmatter。
        返回 {filename_stem: frontmatter_dict}，无 frontmatter 的文件被跳过。
        """
        cache_key = f"md:{subdir}"
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cast("dict[str, Any]", cached)

        result: dict[str, Any] = {}
        target_dir = self._root / subdir
        if not target_dir.exists():
            self._set_to_cache(cache_key, result)
            return result

        for md_file in sorted(target_dir.glob("*.md")):
            try:
                content = md_file.read_text(encoding="utf-8")
                frontmatter = _parse_yaml_frontmatter(content)
                if frontmatter:
                    # 附加元信息，方便追溯
                    frontmatter["_source_file"] = md_file.name
                    result[md_file.stem] = frontmatter
            except OSError as e:
                _log.warning("markdown frontmatter load failed: %s", e)

        self._set_to_cache(cache_key, result)
        return result

    # ── 公共只读接口 ─────────────────────────────────────────────

    def get_agent_archetypes(self) -> dict[str, Any]:
        """获取所有 Agent 原型（来自 workers/*.yaml）"""
        return self._load_yaml_dir("workers")

    def get_tool_archetypes(self) -> dict[str, Any]:
        """获取所有 Tool 原型（来自 synapses/*.yaml）"""
        return self._load_yaml_dir("synapses")

    def get_law_archetypes(self) -> dict[str, Any]:
        """获取所有 Law/Rule 原型（来自 cells/*.md frontmatter）"""
        return self._load_md_dir("cells")

    def get_skill_archetypes(self) -> dict[str, Any]:
        """获取所有 Skill 原型（来自 skills/*.md frontmatter）"""
        return self._load_md_dir("skills")

    def get_agent(self, agent_id: str) -> dict[str, Any] | None:
        """按 id 字段查找 Agent 原型，未找到返回 None"""
        for _stem, data in self.get_agent_archetypes().items():
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get("id") == agent_id:
                        return item
            elif isinstance(data, dict) and data.get("id") == agent_id:
                return data
        return None

    def get_tool(self, tool_id: str) -> dict[str, Any] | None:
        """按 tool_id 字段查找 Tool 原型，未找到返回 None"""
        for _stem, data in self.get_tool_archetypes().items():
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get("tool_id") == tool_id:
                        return item
            elif isinstance(data, dict) and data.get("tool_id") == tool_id:
                return data
        return None

    def get_law(self, law_stem: str) -> dict[str, Any] | None:
        """按文件名 stem 查找 Law 原型"""
        return self.get_law_archetypes().get(law_stem)

    def list_agent_ids(self) -> list[str]:
        """列出所有 Agent id"""
        ids: list[str] = []
        for _stem, data in self.get_agent_archetypes().items():
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and "id" in item:
                        ids.append(item["id"])
            elif isinstance(data, dict) and "id" in data:
                ids.append(data["id"])
        return ids

    def list_tool_ids(self) -> list[str]:
        """列出所有 Tool id"""
        ids: list[str] = []
        for _stem, data in self.get_tool_archetypes().items():
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and "tool_id" in item:
                        ids.append(item["tool_id"])
            elif isinstance(data, dict) and "tool_id" in data:
                ids.append(data["tool_id"])
        return ids

    def invalidate_cache(self) -> None:
        """清除所有缓存（用于测试或热重载场景）"""
        self._cache.clear()

    def validate_internal_state(self) -> bool:
        """Return True if the archetype root is accessible (or absent but benign)."""
        return True


# ── 全局单例 ─────────────────────────────────────────────────────

_default_loader: ArchetypeLoader | None = None


def get_archetype_loader() -> ArchetypeLoader:
    """获取全局 ArchetypeLoader 单例（懒加载）"""
    global _default_loader
    if _default_loader is None:
        _default_loader = ArchetypeLoader()
    return _default_loader
