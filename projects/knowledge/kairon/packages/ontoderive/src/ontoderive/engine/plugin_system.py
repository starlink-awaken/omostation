from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Layer: L3
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
---
"""


import json
import logging
import re
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Sisyphus'
Layer: L3
Constraint: '[!!] AUTO_ADDED_METADATA'
Summary: 'Auto-generated metadata for plugin_system.py'
Tags:
- auto-metadata
Authority: organs/D-Logos/AGENTS.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Plugin System ≡ Module
# 内涵 ≝ {Plugin, System}
# 外延 ≝ {e | e ∈ D-Logos ∧ implements(e, PluginSystem)}
# 功能 ⊢ {Plugin_System, Init_Plugin, Validate_System}
# =============================================================================


"""插件系统 (Plugin System)

D-Logos 插件机制，支持多种文档格式处理。

功能:
- 插件注册与管理
- 内置文档处理器（Markdown, reStructuredText, YAML, JSON）
- 插件启用/禁用
- 插件组合（Pipeline）

Usage:
    from D_Logos.organs import (
        DocPlugin,
        PluginRegistry,
        PluginManager,
        PluginPipeline,
        MarkdownProcessor,
        ReStructuredTextProcessor,
        YamlProcessor,
        JsonProcessor,
    )

    # 使用插件管理器
    manager = PluginManager()
    manager.register(MarkdownProcessor())

    # 处理文档
    result = manager.process("path/to/file.md")

    # 使用 Pipeline 组合插件
    pipeline = PluginPipeline([MarkdownProcessor(), YamlProcessor()])
    result = pipeline.process(content)
"""

_log = logging.getLogger(__name__)


@dataclass
class PluginMetadata:
    """插件元数据"""

    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    supported_extensions: list[str] = field(default_factory=list)


class DocPlugin(ABC):
    """文档处理器插件基类

    所有文档处理器必须继承此类并实现 process 方法。
    """

    def __init__(self) -> None:
        self._enabled = True
        self._metadata = self._create_metadata()

    @abstractmethod
    def _create_metadata(self) -> PluginMetadata:
        """创建插件元数据"""
        pass

    @property
    def name(self) -> str:
        """插件名称"""
        return self._metadata.name

    @property
    def version(self) -> str:
        """插件版本"""
        return self._metadata.version

    @property
    def description(self) -> str:
        """插件描述"""
        return self._metadata.description

    @property
    def supported_extensions(self) -> list[str]:
        """支持的文件扩展名"""
        return self._metadata.supported_extensions

    @property
    def enabled(self) -> bool:
        """插件是否启用"""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        """设置插件启用状态"""
        self._enabled = value

    def process(self, content: str) -> dict[str, Any]:
        """处理文档内容

        Args:
            content: 文档内容

        Returns:
            处理结果字典
        """
        if not self._enabled:
            return {"error": f"Plugin '{self.name}' is disabled", "success": False}

        try:
            return self._process(content)
        except (TypeError, ValueError, AttributeError, RuntimeError) as e:
            return {"error": str(e), "success": False}

    @abstractmethod
    def _process(self, content: str) -> dict[str, Any]:
        """实际处理逻辑（由子类实现）

        Args:
            content: 文档内容

        Returns:
            处理结果字典
        """
        pass


class MarkdownProcessor(DocPlugin):
    """Markdown 文档处理器"""

    def _create_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="markdown",
            version="1.0.0",
            description="Markdown 文档处理器",
            supported_extensions=[".md", ".markdown"],
        )

    def _process(self, content: str) -> dict[str, Any]:
        """处理 Markdown 文档

        提取:
        - 标题（h1-h6）
        - 代码块
        - 链接
        - 列表
        - 表格
        - 强调文本
        """
        result: dict[str, Any] = {
            "type": "markdown",
            "success": True,
            "content": content,
            "headings": [],
            "code_blocks": [],
            "links": [],
            "lists": [],
            "tables": [],
            "emphasis": [],
        }

        # 提取标题
        heading_pattern = r"^(#{1,6})\s+(.+)$"
        for line in content.split("\n"):
            m = re.match(heading_pattern, line)
            if m:
                level = len(m.group(1))
                text = m.group(2).strip()
                result["headings"].append({"level": level, "text": text})

        # 提取代码块
        code_block_pattern = r"```(\w*)\n([\s\S]*?)```"
        for match in re.finditer(code_block_pattern, content):
            language = match.group(1) or "text"
            code = match.group(2).strip()
            result["code_blocks"].append({"language": language, "code": code})

        # 提取链接
        link_pattern = r"\[([^\]]+)\]\(([^\)]+)\)"
        for match in re.finditer(link_pattern, content):
            text = match.group(1)
            url = match.group(2)
            result["links"].append({"text": text, "url": url})

        # 提取列表
        list_pattern = r"^[\s]*[-*+]\s+(.+)$|^[\s]*\d+\.\s+(.+)$"
        for line in content.split("\n"):
            m = re.match(list_pattern, line)
            if m:
                item = m.group(1) or m.group(2)
                result["lists"].append(item.strip())

        # 提取表格
        table_pattern = r"\|(.+)\|"
        tables = []
        in_table = False
        for line in content.split("\n"):
            if re.match(table_pattern, line):
                if not in_table:
                    in_table = True
                cells = [c.strip() for c in line.split("|")[1:-1]]
                # 跳过分隔行
                if all(c in ["---", ":--", "--:", ":-:"] for c in cells):
                    continue
                tables.append(cells)
            else:
                if in_table and tables:
                    result["tables"].append(tables)
                    tables = []
                in_table = False
        if tables:
            result["tables"].append(tables)

        # 提取强调文本
        emphasis_pattern = r"(\*\*|__)(.+?)\1|(\*|_)(.+?)\3"
        for match in re.finditer(emphasis_pattern, content):
            if match.group(1):  # bold
                result["emphasis"].append({"type": "bold", "text": match.group(2)})
            else:  # italic
                result["emphasis"].append({"type": "italic", "text": match.group(4)})

        return result


class ReStructuredTextProcessor(DocPlugin):
    """reStructuredText 文档处理器"""

    def _create_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="restructuredtext",
            version="1.0.0",
            description="reStructuredText 文档处理器",
            supported_extensions=[".rst"],
        )

    def _process(self, content: str) -> dict[str, Any]:
        """处理 reStructuredText 文档

        提取:
        - 标题
        - 代码块
        - 链接
        - 列表
        - 表格
        - 域（docinfo）
        """
        result: dict[str, Any] = {
            "type": "restructuredtext",
            "success": True,
            "content": content,
            "sections": [],
            "code_blocks": [],
            "links": [],
            "lists": [],
            "directives": [],
        }

        # 提取标题（Title 和 Subtitle）
        title_pattern = r"^([^\n]+)\n[=-~]{3,}\n"
        for match in re.finditer(title_pattern, content):
            title = match.group(1).strip()
            underline = match.group(0).split("\n")[1]
            level = "title" if underline[0] == "=" else "subtitle"
            result["sections"].append({"level": level, "title": title})

        # 提取章节标题
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                if re.match(r"^[=-~]{3,}$", next_line):
                    result["sections"].append({"level": "section", "title": line.strip(), "underline": next_line[0]})

        # 提取代码块 (literal block :: 格式)
        code_block_pattern = r"::\n\n(\s+)(.+?)(?:\n\n|\n[^ ])"
        for match in re.finditer(code_block_pattern, content):
            code = match.group(2).strip()
            result["code_blocks"].append({"type": "literal_block", "code": code})

        # 提取代码块 (code-block 指令格式)
        code_directive_pattern = r"\.\. code-block:: (\w*)\n\n((?:    .*\n?)+)"
        for match in re.finditer(code_directive_pattern, content):
            language = match.group(1) or "text"
            code = match.group(2).strip()
            result["code_blocks"].append({"type": "code-block", "language": language, "code": code})

        # 提取内联代码
        inline_code_pattern = r"``([^`]+)``"
        for match in re.finditer(inline_code_pattern, content):
            result["code_blocks"].append({"type": "inline", "code": match.group(1)})

        # 提取链接
        link_pattern = r"`([^<]+)<([^>]+)>`_"
        for match in re.finditer(link_pattern, content):
            result["links"].append({"text": match.group(1), "url": match.group(2)})

        # 提取匿名链接
        anon_link_pattern = r"`([^`]+)`__"
        for match in re.finditer(anon_link_pattern, content):
            result["links"].append({"text": match.group(1), "url": "anonymous"})

        # 提取列表
        bullet_pattern = r"^[\s]*[-*+]\s+(.+)$"
        for line in content.split("\n"):
            m = re.match(bullet_pattern, line)
            if m:
                result["lists"].append({"type": "bullet", "item": m.group(1).strip()})

        # 提取编号列表
        numbered_pattern = r"^[\s]*\d+\.\s+(.+)$"
        for line in content.split("\n"):
            m = re.match(numbered_pattern, line)
            if m:
                result["lists"].append({"type": "numbered", "item": m.group(1).strip()})

        # 提取指令（directives）
        directive_pattern = r"\.\. (\w+)::"
        for match in re.finditer(directive_pattern, content):
            result["directives"].append(match.group(1))

        return result


class YamlProcessor(DocPlugin):
    """YAML 文档处理器"""

    def _create_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="yaml",
            version="1.0.0",
            description="YAML 文档处理器",
            supported_extensions=[".yaml", ".yml"],
        )

    def _process(self, content: str) -> dict[str, Any]:
        """处理 YAML 文档"""
        try:
            data = yaml.safe_load(content)
            return {
                "type": "yaml",
                "success": True,
                "data": data,
                "keys": list(data.keys()) if isinstance(data, dict) else [],
            }
        except yaml.YAMLError as e:
            return {
                "type": "yaml",
                "success": False,
                "error": str(e),
            }


class JsonProcessor(DocPlugin):
    """JSON 文档处理器"""

    def _create_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="json",
            version="1.0.0",
            description="JSON 文档处理器",
            supported_extensions=[".json"],
        )

    def _process(self, content: str) -> dict[str, Any]:
        """处理 JSON 文档"""
        try:
            data = json.loads(content)
            return {
                "type": "json",
                "success": True,
                "data": data,
                "keys": list(data.keys()) if isinstance(data, dict) else [],
            }
        except json.JSONDecodeError as e:
            return {
                "type": "json",
                "success": False,
                "error": str(e),
            }


class PluginRegistry:
    """插件注册表

    负责插件的注册、注销、获取和列表操作。
    """

    def __init__(self) -> None:
        self._plugins: dict[str, DocPlugin] = {}

    def register(self, plugin: DocPlugin) -> None:
        """注册插件

        Args:
            plugin: 要注册的插件实例

        Raises:
            ValueError: 如果插件名称已存在
        """
        if plugin.name in self._plugins:
            raise ValueError(f"Plugin '{plugin.name}' is already registered")
        self._plugins[plugin.name] = plugin

    def unregister(self, name: str) -> None:
        """注销插件

        Args:
            name: 插件名称

        Raises:
            KeyError: 如果插件不存在
        """
        if name not in self._plugins:
            raise KeyError(f"Plugin '{name}' is not registered")
        del self._plugins[name]

    def get_plugin(self, name: str) -> DocPlugin | None:
        """获取插件

        Args:
            name: 插件名称

        Returns:
            插件实例，如果不存在返回 None
        """
        return self._plugins.get(name)

    def list_plugins(self, enabled_only: bool = False) -> list[str]:
        """列出所有插件

        Args:
            enabled_only: 是否只返回已启用的插件

        Returns:
            插件名称列表
        """
        if enabled_only:
            return [name for name, plugin in self._plugins.items() if plugin.enabled]
        return list(self._plugins.keys())

    def __len__(self) -> int:
        """返回注册表中的插件数量"""
        return len(self._plugins)

    def __contains__(self, name: str) -> bool:
        """检查插件是否已注册"""
        return name in self._plugins


class PluginPipeline:
    """插件管道

    按顺序执行多个插件。
    """

    def __init__(self, plugins: list[DocPlugin] | None = None) -> None:
        self._plugins: list[DocPlugin] = plugins or []

    def add(self, plugin: DocPlugin) -> PluginPipeline:
        """添加插件到管道

        Args:
            plugin: 要添加的插件

        Returns:
            自身（用于链式调用）
        """
        self._plugins.append(plugin)
        return self

    def remove(self, name: str) -> bool:
        """从管道中移除插件

        Args:
            name: 插件名称

        Returns:
            是否成功移除
        """
        for i, plugin in enumerate(self._plugins):
            if plugin.name == name:
                self._plugins.pop(i)
                return True
        return False

    def process(self, content: str) -> list[dict[str, Any]]:
        """按顺序处理内容

        Args:
            content: 要处理的内容

        Returns:
            所有插件的处理结果列表
        """
        results = []
        current_content = content

        for plugin in self._plugins:
            if plugin.enabled:
                result = plugin.process(current_content)
                results.append(result)

                # 如果处理成功，将结果传往下个插件
                if result.get("success", False):
                    # 将结果转换为字符串供下个插件使用
                    if isinstance(result.get("data"), (dict, list)):
                        current_content = json.dumps(result["data"])
                    elif result.get("content"):
                        current_content = result["content"]

        return results

    def __len__(self) -> int:
        """返回管道中的插件数量"""
        return len(self._plugins)

    def __iter__(self) -> Iterator[DocPlugin]:
        """迭代管道中的插件"""
        return iter(self._plugins)


class PluginManager:
    """插件管理器

    统一管理所有插件，提供便捷的接口。
    """

    def __init__(self) -> None:
        self.registry = PluginRegistry()
        self._init_builtin_plugins()

    def _init_builtin_plugins(self) -> None:
        """初始化内置插件"""
        self.register(MarkdownProcessor())
        self.register(ReStructuredTextProcessor())
        self.register(YamlProcessor())
        self.register(JsonProcessor())

    def register(self, plugin: DocPlugin) -> None:
        """注册插件

        Args:
            plugin: 要注册的插件
        """
        self.registry.register(plugin)

    def unregister(self, name: str) -> None:
        """注销插件

        Args:
            name: 插件名称
        """
        self.registry.unregister(name)

    def enable(self, name: str) -> bool:
        """启用插件

        Args:
            name: 插件名称

        Returns:
            是否成功启用
        """
        plugin = self.registry.get_plugin(name)
        if plugin:
            plugin.enabled = True
            return True
        return False

    def disable(self, name: str) -> bool:
        """禁用插件

        Args:
            name: 插件名称

        Returns:
            是否成功禁用
        """
        plugin = self.registry.get_plugin(name)
        if plugin:
            plugin.enabled = False
            return True
        return False

    def get_plugin(self, name: str) -> DocPlugin | None:
        """获取插件

        Args:
            name: 插件名称

        Returns:
            插件实例
        """
        return self.registry.get_plugin(name)

    def list_plugins(self, enabled_only: bool = False) -> list[str]:
        """列出插件

        Args:
            enabled_only: 是否只返回已启用的插件

        Returns:
            插件名称列表
        """
        return self.registry.list_plugins(enabled_only)

    def process(self, file_path: str | Path) -> dict[str, Any]:
        """处理文档文件

        根据文件扩展名自动选择合适的插件。

        Args:
            file_path: 文件路径

        Returns:
            处理结果
        """
        file_path = Path(file_path)
        extension = file_path.suffix.lower()

        # 查找支持该扩展名的插件
        for plugin in self.registry.list_plugins():
            plugin_obj = self.registry.get_plugin(plugin)
            if plugin_obj and extension in plugin_obj.supported_extensions:
                if plugin_obj.enabled:
                    content = file_path.read_text(encoding="utf-8")
                    return plugin_obj.process(content)
                else:
                    return {"error": f"Plugin '{plugin}' is disabled", "success": False}

        return {"error": f"No plugin found for extension '{extension}'", "success": False}

    def process_content(self, content: str, plugin_name: str | None = None) -> dict[str, Any]:
        """处理文档内容

        Args:
            content: 文档内容
            plugin_name: 可选的插件名称

        Returns:
            处理结果
        """
        if plugin_name:
            plugin = self.registry.get_plugin(plugin_name)
            if plugin:
                return plugin.process(content)
            return {"error": f"Plugin '{plugin_name}' not found", "success": False}

        # 自动检测类型
        # 尝试 JSON
        try:
            json.loads(content)
            plugin = self.registry.get_plugin("json")
            if plugin:
                return plugin.process(content)
        except (json.JSONDecodeError, ValueError):
            pass

        # 尝试 YAML
        try:
            yaml.safe_load(content)
            plugin = self.registry.get_plugin("yaml")
            if plugin:
                return plugin.process(content)
        except yaml.YAMLError:
            pass

        # 默认使用 Markdown
        plugin = self.registry.get_plugin("markdown")
        if plugin:
            return plugin.process(content)

        return {"error": "No suitable plugin found", "success": False}

    def create_pipeline(self, plugin_names: list[str]) -> PluginPipeline | None:
        """创建插件管道

        Args:
            plugin_names: 插件名称列表

        Returns:
            PluginPipeline 实例，如果所有插件都存在
        """
        plugins = []
        for name in plugin_names:
            plugin = self.registry.get_plugin(name)
            if plugin:
                plugins.append(plugin)
            else:
                return None

        return PluginPipeline(plugins)


# 默认插件管理器实例
_default_manager: PluginManager | None = None


def get_plugin_manager() -> PluginManager:
    """获取默认插件管理器实例"""
    global _default_manager
    if _default_manager is None:
        _default_manager = PluginManager()
    return _default_manager


def process_document(file_path: str | Path) -> dict[str, Any]:
    """便捷函数：处理文档文件

    Args:
        file_path: 文件路径

    Returns:
        处理结果
    """
    return get_plugin_manager().process(file_path)


def process_content(content: str, plugin_name: str | None = None) -> dict[str, Any]:
    """便捷函数：处理文档内容

    Args:
        content: 文档内容
        plugin_name: 可选的插件名称

    Returns:
        处理结果
    """
    return get_plugin_manager().process_content(content, plugin_name)
