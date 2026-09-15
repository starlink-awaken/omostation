from __future__ import annotations

"""
API JSON Extractor - Extracts structured knowledge from API JSON responses

Extracted from SharedBrain D_Harvest → minerva.
"""
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from minerva.extractors.base import IContentExtractor, StructuredKnowledge
from minerva.sources.connectors import RawContent


@dataclass
class JsonPathConfig:
    """JSON路径配置，支持嵌套字段提取"""

    title_path: str | None = None  # 例如: "data.title", "meta.name"
    body_path: str | None = None  # 例如: "content", "data.description"
    uri_path: str | None = None  # 例如: "url", "link"
    metadata_paths: dict[str, str] = field(
        default_factory=dict
    )  # 例如: {"author": "data.author", "date": "created_at"}


@dataclass
class JsonExtractionConfig:
    """JSON提取配置"""

    # 默认字段映射
    default_title_field: str = "title"
    default_body_field: str = "content"
    default_uri_field: str = "url"

    # 数组处理配置
    treat_as_array: bool = False  # 是否将根对象视为数组处理
    array_item_path: str | None = None  # 例如: "data.items" 指定数组路径

    # 自定义字段映射
    field_mapping: JsonPathConfig = field(default_factory=JsonPathConfig)

    # 内容验证
    min_body_length: int = 10
    max_body_length: int = 50000

    # 自定义内容处理器
    body_processor: Callable[[object], str] | None = None


class JsonContentExtractor(IContentExtractor):
    """从API JSON响应中提取结构化知识"""

    def __init__(self, config: JsonExtractionConfig | None = None) -> None:
        self.config = config or JsonExtractionConfig()

    async def extract(self, raw: RawContent) -> list[StructuredKnowledge]:  # type: ignore[override]
        """从JSON内容中提取结构化知识"""
        # 解析JSON数据
        json_data = self._parse_json(raw)

        # 判断是否需要提取数组
        if self._should_extract_array(json_data):
            return self._extract_array(json_data, raw)

        # 单个对象提取
        return [self._extract_single(json_data, raw)]

    def _parse_json(self, raw: RawContent) -> Any:
        """解析JSON数据"""
        if isinstance(raw.data, bytes):
            try:
                json_str = raw.data.decode("utf-8")
            except UnicodeDecodeError:
                json_str = raw.data.decode("latin-1", errors="replace")
        else:
            json_str = raw.data

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON data: {e}") from e

    def _should_extract_array(self, json_data: Any) -> bool:
        """判断是否需要提取数组"""
        # 检查是否配置了数组路径
        if self.config.array_item_path:
            return True

        # 检查根对象是否为数组
        if self.config.treat_as_array and isinstance(json_data, list):
            return True

        return False

    def _extract_array(self, json_data: Any, raw: RawContent) -> list[StructuredKnowledge]:
        """从数组中提取多个知识对象"""
        items = json_data

        # 如果配置了数组路径，先提取路径指定的数组
        if self.config.array_item_path:
            items = self._get_nested_value(json_data, self.config.array_item_path)
            if not isinstance(items, list):
                raise ValueError(f"Array path '{self.config.array_item_path}' does not point to a list")

        results = []
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                continue

            try:
                knowledge = self._extract_single(item, raw, item_index=idx)
                results.append(knowledge)
            except (ValueError, KeyError, TypeError):
                # 跳过无法处理的项目，继续处理其他项目
                continue

        return results

    def _extract_single(self, json_data: dict, raw: RawContent, item_index: int | None = None) -> StructuredKnowledge:
        """从单个JSON对象中提取知识"""
        # 提取标题
        title = self._extract_title(json_data, raw, item_index)

        # 提取正文
        body = self._extract_body(json_data, raw)

        # 验证内容长度
        if len(body) < self.config.min_body_length:
            raise ValueError(f"Body content too short: {len(body)} < {self.config.min_body_length}")

        if len(body) > self.config.max_body_length:
            body = body[: self.config.max_body_length]

        # 提取URI
        uri = self._extract_uri(json_data, raw)

        # 提取元数据
        metadata = self._extract_metadata(json_data, raw, item_index)

        return StructuredKnowledge(title=title, body=body, uri=uri, metadata=metadata, visibility="private")

    def _extract_title(self, json_data: dict, raw: RawContent, item_index: int | None = None) -> str:
        """提取标题"""
        # 优先使用配置的路径
        if self.config.field_mapping.title_path:
            title = self._get_nested_value(json_data, self.config.field_mapping.title_path)
            if title:
                return str(title)

        # 尝试默认字段
        for field_name in [self.config.default_title_field, "name", "headline", "subject"]:
            if field_name in json_data:
                value = json_data[field_name]
                if value:
                    return str(value)

        # 如果是数组项，使用索引生成标题
        if item_index is not None:
            return f"Item {item_index + 1}"

        # 从URI生成标题
        return self._title_from_uri(raw.uri)

    def _extract_body(self, json_data: dict, raw: RawContent) -> str:
        """提取正文内容"""
        # 优先使用配置的路径
        if self.config.field_mapping.body_path:
            body = self._get_nested_value(json_data, self.config.field_mapping.body_path)
            if body:
                return self._process_body_value(body)

        # 尝试默认字段
        for field_name in [self.config.default_body_field, "description", "text", "summary"]:
            if field_name in json_data:
                value = json_data[field_name]
                if value:
                    return self._process_body_value(value)

        # 如果没有找到特定字段，尝试将整个对象转为字符串
        return self._json_to_text(json_data)

    def _process_body_value(self, value: Any) -> str:
        """处理正文值"""
        if self.config.body_processor:
            return self.config.body_processor(value)

        if isinstance(value, str):
            return value.strip()
        elif isinstance(value, (int, float, bool)):
            return str(value)
        elif isinstance(value, list):
            # 处理数组，转换为段落
            items = []
            for item in value:
                if isinstance(item, str):
                    items.append(item)
                elif isinstance(item, dict):
                    items.append(self._json_to_text(item))
                else:
                    items.append(str(item))
            return "\n\n".join(items)
        elif isinstance(value, dict):
            return self._json_to_text(value)
        else:
            return str(value)

    def _json_to_text(self, data: Any) -> str:
        """将JSON对象转换为文本"""
        if isinstance(data, dict):
            # 按键值对格式化
            lines = []
            for key, value in data.items():
                if isinstance(value, (str, int, float, bool)):
                    lines.append(f"{key}: {value}")
                elif isinstance(value, list):
                    lines.append(f"{key}: {len(value)} items")
                # 跳过嵌套对象避免过于复杂
            return "\n".join(lines) if lines else json.dumps(data, ensure_ascii=False)
        elif isinstance(data, list):
            return "\n".join(str(item) for item in data)
        else:
            return str(data)

    def _extract_uri(self, json_data: dict, raw: RawContent) -> str:
        """提取URI"""
        # 优先使用配置的路径
        if self.config.field_mapping.uri_path:
            uri = self._get_nested_value(json_data, self.config.field_mapping.uri_path)
            if uri:
                return str(uri)

        # 尝试默认字段
        for field_name in [self.config.default_uri_field, "link", "permalink", "canonical_url"]:
            if field_name in json_data:
                value = json_data[field_name]
                if value:
                    return str(value)

        # 使用原始URI
        return raw.uri

    def _extract_metadata(self, json_data: dict, raw: RawContent, item_index: int | None = None) -> dict:
        """提取元数据"""
        metadata: dict[str, Any] = {
            "content_type": raw.content_type,
            "extraction_method": "json_extractor",
            "original_uri": raw.uri,
        }

        # 添加索引（如果是数组项）
        if item_index is not None:
            metadata["array_index"] = item_index

        # 提取配置的元数据字段
        for meta_key, json_path in self.config.field_mapping.metadata_paths.items():
            value = self._get_nested_value(json_data, json_path)
            if value is not None:
                metadata[meta_key] = value

        # 提取常见元数据字段
        common_meta_fields = [
            "author",
            "created_at",
            "updated_at",
            "published_at",
            "id",
            "uuid",
            "tags",
            "category",
            "source",
        ]
        for fld in common_meta_fields:
            if fld in json_data and fld not in metadata:
                metadata[fld] = json_data[fld]

        return metadata

    def _get_nested_value(self, data: dict, path: str) -> Any | None:
        """获取嵌套字段的值"""
        keys = path.split(".")
        value: Any = data

        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
                if value is None:
                    return None
            else:
                return None

        return value

    def _title_from_uri(self, uri: str) -> str:
        """从URI生成标题"""
        # 移除协议和路径
        parts = uri.split("/")
        if len(parts) > 1:
            last_part = parts[-1]
            # 移除文件扩展名和查询参数
            last_part = last_part.split(".")[0].split("?")[0]
            if last_part:
                # 转换连字符和下划线为空格
                title = last_part.replace("-", " ").replace("_", " ")
                import re

                title = re.sub(r"\s+", " ", title).strip().title()
                if title:
                    return title

        # 最终回退：使用域名
        from urllib.parse import urlparse

        parsed = urlparse(uri)
        return parsed.netloc or "Untitled Content"
