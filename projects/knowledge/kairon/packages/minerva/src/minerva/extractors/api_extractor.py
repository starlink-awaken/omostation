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
# Api Extractor ≡ API
# 内涵 ≝ {Api, Extractor}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, ApiExtractor)}
# 功能 ⊢ {Api_Extractor, Init_Api, Validate_Extractor}
# =============================================================================

# ---
# domain: D-Harvest
# layer: organ
# status: active
# ---

"""
API JSON Extractor - Extracts structured knowledge from API JSON responses
Supports JSONPath/JMESPath expressions for flexible field extraction
"""
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from minerva.extractors.base import IContentExtractor, StructuredKnowledge
from minerva.sources.connectors import RawContent


@dataclass
class ApiExtractionConfig:
    """API JSON提取配置"""

    # JSONPath表达式配置
    title_path: str = "$.title"
    body_path: str = "$.content"
    uri_path: str | None = None  # 例如: "$.url", "$.link"
    metadata_paths: dict[str, str] = field(default_factory=dict)  # 例如: {"author": "$.data.user.name"}

    # 内容验证
    min_body_length: int = 10
    max_body_length: int = 50000
    required_fields: list[str] = field(default_factory=list)  # 必需字段路径

    # 数组处理
    array_mode: bool = False  # 是否为数组模式
    array_item_path: str | None = None  # 数组项路径，例如: "$.data.items[*]"

    # 自定义处理器
    body_processor: Callable[[Any], str] | None = None


class JsonPathExtractor:
    """JSONPath表达式解析器 - 支持类似$.field.nested的路径语法"""

    def __init__(self, expression: str) -> None:
        """
        初始化JSONPath表达式

        Args:
            expression: JSONPath表达式，例如"$.data.title", "$.items[*].name"
        """
        self.expression = expression.strip()
        self.path_parts = self._parse_expression(expression)

    def _parse_expression(self, expression: str) -> list:
        """解析JSONPath表达式为路径部分"""
        if not expression.startswith("$."):
            raise ValueError(f"Invalid JSONPath expression: {expression}")

        # 移除$前缀
        path = expression[2:]

        # 分割路径
        parts = []
        current = ""

        for char in path:
            if char == "." and current:
                parts.append(current)
                current = ""
            elif char == "[":
                # 处理数组通配符 [*]
                if current:
                    parts.append(current)
                    current = ""
                # 查找匹配的 ]
                bracket_end = path.find("]", path.index(char))
                if bracket_end == -1:
                    raise ValueError(f"Unclosed bracket in: {expression}")

                array_spec = path[path.index(char) : bracket_end + 1]
                parts.append(array_spec)

                # 移动到]之后
                path = path[bracket_end + 1 :]
                break
            else:
                current += char

        if current:
            parts.append(current)

        return parts

    def extract(self, data: dict) -> Any | None:  # type: ignore[override]
        """
        从数据中提取指定路径的值

        Args:
            data: JSON数据字典

        Returns:
            提取的值，如果路径不存在则返回None
        """
        if not data:
            return None

        current = data

        for part in self.path_parts:
            if part == "[*]":
                # 数组通配符 - 返回所有元素
                if isinstance(current, list):
                    return current
                return None

            if isinstance(current, dict):
                if part in current:
                    current = current[part]
                else:
                    return None
            elif isinstance(current, list) and part.isdigit():
                # 数组索引访问
                index = int(part)
                if 0 <= index < len(current):
                    current = current[index]
                else:
                    return None
            else:
                return None

        return current

    def extract_all(self, data: dict) -> list:
        """
        提取所有匹配的值（用于数组通配符）

        Args:
            data: JSON数据字典

        Returns:
            匹配值的列表
        """
        result = self.extract(data)
        if result is None:
            return []
        elif isinstance(result, list):
            return result
        else:
            return [result]


class ApiContentExtractor(IContentExtractor):
    """从API JSON响应中提取结构化知识 - 支持JSONPath表达式"""

    def __init__(self, config: ApiExtractionConfig | None = None) -> None:
        self.config = config or ApiExtractionConfig()

    async def extract(self, raw: RawContent) -> list[StructuredKnowledge]:  # type: ignore[override]
        """从JSON内容中提取结构化知识"""
        # 解析JSON数据
        json_data = self._parse_json(raw)

        # 判断是否需要提取数组
        if self.config.array_mode:
            return self._extract_array(json_data, raw)

        # 单个对象提取
        result = self._extract_single(json_data, raw)
        if result:
            return [result]
        return []

    def _parse_json(self, raw: RawContent) -> dict:
        """解析JSON数据"""
        if isinstance(raw.data, bytes):
            try:
                json_str = raw.data.decode("utf-8")
            except UnicodeDecodeError:
                json_str = raw.data.decode("latin-1", errors="replace")
        else:
            json_str = raw.data

        try:
            data = json.loads(json_str)
            if not isinstance(data, dict):
                raise ValueError(f"Expected JSON object, got {type(data).__name__}")
            return data
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON data: {e}") from e

    def _extract_array(self, json_data: dict, raw: RawContent) -> list[StructuredKnowledge]:
        """从数组中提取多个知识对象"""
        items = []

        # 如果配置了数组项路径，先提取路径指定的数组
        if self.config.array_item_path:
            extractor = JsonPathExtractor(self.config.array_item_path)
            items = extractor.extract_all(json_data)
        else:
            # 尝试从根对象提取数组
            for value in json_data.values():
                if isinstance(value, list):
                    items = value
                    break

        if not items:
            return []

        results = []
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                continue

            try:
                knowledge = self._extract_single(item, raw, item_index=idx)
                if knowledge:
                    results.append(knowledge)
            except (ValueError, KeyError, TypeError):
                # 跳过无法处理的项目
                continue

        return results

    def _extract_single(
        self, json_data: dict, raw: RawContent, item_index: int | None = None
    ) -> StructuredKnowledge | None:
        """从单个JSON对象中提取知识"""
        try:
            # 验证必需字段
            if self.config.required_fields:
                for field_path in self.config.required_fields:
                    extractor = JsonPathExtractor(field_path)
                    if extractor.extract(json_data) is None:
                        raise ValueError(f"Required field missing: {field_path}")

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

        except (ValueError, KeyError, TypeError):
            # 记录错误但继续处理
            return None

    def _extract_title(self, json_data: dict, raw: RawContent, item_index: int | None = None) -> str:
        """使用JSONPath提取标题"""
        extractor = JsonPathExtractor(self.config.title_path)
        title = extractor.extract(json_data)

        if title:
            return str(title)

        # 如果是数组项，使用索引生成标题
        if item_index is not None:
            return f"Item {item_index + 1}"

        # 从URI生成标题
        return self._title_from_uri(raw.uri)

    def _extract_body(self, json_data: dict, raw: RawContent) -> str:
        """使用JSONPath提取正文内容"""
        extractor = JsonPathExtractor(self.config.body_path)
        body = extractor.extract(json_data)

        if body is None:
            # 尝试备用字段
            for fld in ["content", "description", "text", "summary"]:
                try:
                    extractor = JsonPathExtractor(f"$.{fld}")
                    body = extractor.extract(json_data)
                    if body:
                        break
                except (ValueError, KeyError):
                    continue

        if body is None:
            # 最后的回退：将整个对象转为字符串
            return self._json_to_text(json_data)

        return self._process_body_value(body)

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
        """使用JSONPath提取URI"""
        if self.config.uri_path:
            extractor = JsonPathExtractor(self.config.uri_path)
            uri = extractor.extract(json_data)
            if uri:
                return str(uri)

        # 尝试常见字段
        for fld in ["url", "link", "permalink", "canonical_url"]:
            try:
                extractor = JsonPathExtractor(f"$.{fld}")
                uri = extractor.extract(json_data)
                if uri:
                    return str(uri)
            except (ValueError, KeyError):
                continue

        # 使用原始URI
        return raw.uri

    def _extract_metadata(self, json_data: dict, raw: RawContent, item_index: int | None = None) -> dict:
        """使用JSONPath提取元数据"""
        metadata = {
            "content_type": raw.content_type,
            "extraction_method": "api_json_extractor",
            "original_uri": raw.uri,
        }

        # 添加索引（如果是数组项）
        if item_index is not None:
            metadata["array_index"] = str(item_index)

        # 提取配置的元数据字段
        for meta_key, json_path in self.config.metadata_paths.items():
            try:
                extractor = JsonPathExtractor(json_path)
                value = extractor.extract(json_data)
                if value is not None:
                    metadata[meta_key] = value
            except (ValueError, KeyError):
                continue

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
            if fld not in metadata:
                try:
                    extractor = JsonPathExtractor(f"$.{fld}")
                    value = extractor.extract(json_data)
                    if value is not None:
                        metadata[fld] = value
                except (ValueError, KeyError):
                    continue

        return metadata

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
