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
# Markdown File Adapter ≡ Module
# 内涵 ≝ {Markdown, File, Adapter}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, MarkdownFileAdapter)}
# 功能 ⊢ {Markdown_File, File_Adapter, Adapter_Init}
# =============================================================================

# ---
# domain: D-Harvest
# layer: organ
# status: active
"""
Markdown 文件存储适配器
将收割的知识以 Markdown 格式存储到 docs/docs/knowledge/ 目录
"""

import asyncio
import hashlib
import logging
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

_log = logging.getLogger(__name__)


class MarkdownFileStorageAdapter:
    """Markdown 文件存储适配器 - 将知识存储为Markdown文件"""

    # 12个主题分类目录映射
    CATEGORIES = {
        "agent": "01-agent",
        "skills": "02-skills",
        "harness": "03-harness",
        "memory": "04-memory",
        "context": "05-context",
        "models": "06-models",
        "tools": "07-tools",
        "evaluation": "08-evaluation",
        "evolution": "09-evolution",
        "production": "10-production",
        "research": "11-research",
        "trends": "12-trends",
    }

    # 文件名安全字符模式
    _SAFE_FILENAME_PATTERN = re.compile(r"[^\w\s-]")
    _WHITESPACE_PATTERN = re.compile(r"[-\s]+")

    def _load_hash_index(self) -> None:
        """加载现有内容哈希到内存用于快速去重"""
        hash_pattern = re.compile(r"^hash:\s*([a-f0-9]+)$", re.MULTILINE)
        for md_file in self.knowledge_root.rglob("*.md"):
            try:
                with open(md_file, encoding="utf-8") as f:
                    # 只读取前20行(frontmatter部分)
                    first_lines = "".join([f.readline() for _ in range(20)])
                    match = hash_pattern.search(first_lines)
                    if match:
                        self._hash_index.add(match.group(1))
            except (OSError, UnicodeDecodeError):
                continue
        _log.info(f"Loaded {len(self._hash_index)} existing hashes into index")

    def __init__(
        self,
        knowledge_root: Path,
        downstream_callback: Callable[[Path], Any] | None = None,
    ) -> None:
        """
        初始化Markdown存储适配器

        Args:
            knowledge_root: knowledge目录根路径
            downstream_callback: 存储成功后的回调函数(用于触发下游处理)
        """
        self.knowledge_root = Path(knowledge_root)
        self.knowledge_root.mkdir(parents=True, exist_ok=True)
        self.downstream_callback = downstream_callback
        self._hash_index: set[str] = set()
        self._load_hash_index()
        _log.info(f"MarkdownFileStorageAdapter initialized with root: {self.knowledge_root}")

    def _get_category_dir(self, category: str, subcategory: str) -> Path:
        """
        获取分类目录路径(带路径遍历保护)

        Args:
            category: 主分类 (agent/skills/harness/...)
            subcategory: 子分类 (theory/practice/...)

        Returns:
            完整目录路径
        """
        category_dir = self.CATEGORIES.get(category, "12-trends")
        # 清洗 subcategory 防止路径遍历攻击
        safe_subcategory = self._SAFE_FILENAME_PATTERN.sub("", subcategory)
        safe_subcategory = safe_subcategory.strip("-").lower()
        if not safe_subcategory or safe_subcategory in (".", ".."):
            safe_subcategory = "general"

        target_dir = self.knowledge_root / category_dir / safe_subcategory
        # 确保最终路径在 knowledge_root 内
        try:
            target_dir.resolve().relative_to(self.knowledge_root.resolve())
        except ValueError:
            _log.warning("Path traversal attempt detected, using 'general' subcategory")
            target_dir = self.knowledge_root / category_dir / "general"

        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir

    @staticmethod
    def _compute_hash(title: str, body: str) -> str:
        """
        计算内容哈希用于去重

        Args:
            title: 标题
            body: 正文内容

        Returns:
            SHA256哈希值(前16位)
        """
        content = f"{title}{body}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    async def _exists(self, content_hash: str) -> bool:
        """
        检查内容是否已存在(通过内存哈希索引，O(1)查询)

        Args:
            content_hash: 内容哈希

        Returns:
            是否已存在
        """
        return content_hash in self._hash_index

    def _generate_filename(self, title: str, uri: str) -> str:
        """
        生成安全的文件名

        Args:
            title: 标题
            uri: 来源URL

        Returns:
            安全的文件名(小写、连字符分隔、.md后缀)
        """
        # 从标题生成基础文件名
        base = title.strip()[:50]  # 限制长度
        base = self._SAFE_FILENAME_PATTERN.sub("", base)
        base = self._WHITESPACE_PATTERN.sub("-", base)
        base = base.strip("-").lower()

        # 如果标题为空或处理后为空，使用URL
        if not base:
            base = Path(uri).stem[:30]

        # 添加时间戳避免冲突（包含微秒精度）
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
        return f"{timestamp}-{base}.md"

    @staticmethod
    def _extract_domain(uri: str) -> str:
        """
        从URL提取域名

        Args:
            uri: URL地址

        Returns:
            域名
        """
        parsed = urlparse(uri)
        return parsed.netloc or "local"

    async def store_knowledge(
        self,
        uri: str,
        title: str,
        body: str,
        metadata: dict[str, Any] | None = None,
        category: str = "research",
        subcategory: str = "general",
    ) -> Path | None:
        """
        存储知识为 Markdown 文件

        Args:
            uri: 来源 URL
            title: 标题
            body: 正文内容
            metadata: 额外元数据
            category: 主分类 (agent/skills/harness/...)
            subcategory: 子分类 (theory/practice/...)

        Returns:
            文件路径，如果已存在则返回 None
        """
        # 1. 检查去重
        content_hash = self._compute_hash(title, body)
        if await self._exists(content_hash):
            _log.info(f"Content already exists (hash: {content_hash}), skipping")
            return None

        # 更新哈希索引
        self._hash_index.add(content_hash)

        # 2. 构建文件路径
        target_dir = self._get_category_dir(category, subcategory)

        # 3. 生成文件名
        filename = self._generate_filename(title, uri)
        file_path = target_dir / filename

        # 4. 构建 frontmatter
        post_metadata = {
            "来源": self._extract_domain(uri),
            "tags": metadata.get("tags", [category]) if metadata else [category],
            "date": datetime.now(UTC).strftime("%Y-%m-%d"),
            "url": uri,
            "hash": content_hash,
        }

        # 添加额外元数据
        if metadata:
            for key, value in metadata.items():
                if key not in ("tags",):
                    post_metadata[key] = value

        # 5. 写入文件
        try:
            # 构建完整的Markdown内容
            content = self._build_markdown(post_metadata, title, body)

            # 原子写入：先写临时文件，再重命名
            temp_path = file_path.with_suffix(".tmp")
            temp_path.write_text(content, encoding="utf-8")
            temp_path.replace(file_path)

            _log.info(f"Stored knowledge to markdown: {file_path}")

            # 6. 触发下游处理
            if self.downstream_callback:
                try:
                    await self.downstream_callback(file_path)
                except (OSError, ValueError, RuntimeError, asyncio.CancelledError) as exc:
                    _log.warning(f"Downstream callback failed: {exc}", exc_info=True)

            return file_path

        except (OSError, ValueError, RuntimeError) as exc:
            _log.error(f"Failed to store markdown file: {exc}")
            return None

    @staticmethod
    def _build_markdown(metadata: dict[str, Any], title: str, body: str) -> str:
        """
        构建完整的Markdown内容

        Args:
            metadata: frontmatter元数据
            title: 标题
            body: 正文内容

        Returns:
            完整Markdown文本
        """
        lines = ["---"]
        for key, value in metadata.items():
            if isinstance(value, list):
                value_str = str(value).replace("'", '"')
            else:
                value_str = str(value)
            lines.append(f"{key}: {value_str}")
        lines.append("---")
        lines.append("")
        lines.append(f"# {title}")
        lines.append("")
        lines.append(body)
        return "\n".join(lines)


def get_markdown_storage_adapter(
    knowledge_root: Path,
    downstream_callback: Callable[[Path], Any] | None = None,
) -> MarkdownFileStorageAdapter:
    """
    工厂函数：获取Markdown存储适配器实例

    Args:
        knowledge_root: knowledge目录根路径
        downstream_callback: 存储成功后的回调函数

    Returns:
        MarkdownFileStorageAdapter实例
    """
    return MarkdownFileStorageAdapter(knowledge_root, downstream_callback)
