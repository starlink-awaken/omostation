"""
ssot-kernel — extractor/template.py
=====================================
模板式提取器：用正则模式从固定格式文档中提取知识。

不依赖 LLM。适合的场景：
- 政策文件库（固定编号格式，如 P-F15、京科发〔2026〕XX号）
- 定期报告（每期结构一致，字段位置固定）
- Excel/CSV 导出的结构化文本
- 标准化的会议纪要模板

工作原理：
1. 对每类源定义一个 TemplatePattern（正则表达式集）
2. 逐个匹配提取文本
3. 输出统一的 ExtractionResult
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .base import ExtractionCandidate, ExtractionResult, Extractor, TextSource


@dataclass
class TemplatePattern:
    """一个模板模式：用正则从文本中提取一段知识"""

    name: str  # 模式名称
    category: str  # entity / fact / inference / relation / rule
    id_prefix: str  # 提取的 ID 前缀（如 "DAT-"）
    title_pattern: str = ""  # 标题匹配正则（如 r"^##\s+(.+)）"
    field_patterns: dict[str, str] = field(default_factory=dict)  # 字段提取正则：{字段名: 正则}
    confidence: float = 0.7
    post_process: str = ""  # 后处理函数名（可选）
    # AST 增强字段：当设置时，优先使用 AST 树提取而不是全文 regex
    scope_heading: str = ""  # 可选：限定在哪个 h2 章节内匹配（如"一、人"）
    node_type: str = ""  # AST 节点类型（如 "heading"），设置在 AST 节点上提取
    node_level: int = 0  # AST 节点级别（如 3 表示 h3）
    field_keys: list[str] = field(
        default_factory=list
    )  # AST：从列表项中按 key 提取字段（如 ["**名称**:", "**角色**:"]）

    @property
    def uses_ast(self) -> bool:
        """是否使用 AST 提取（比全文 regex 更精确）"""
        return bool(self.scope_heading and self.node_type)


# ── 内置模板模式──

POLICY_PATTERNS = [
    TemplatePattern(
        name="policy_level1",
        category="fact",
        id_prefix="POL-",
        title_pattern=r"^\|.*P-F(\d+).*\|.*$",
        field_patterns={
            "id": r"^\|\s*(P-F[\d-]+)",
            "level": r"^\|.*Level\s*(\d)",
            "title": r"\|([^|]+)\|",
            "authority": r"\|([^|]+)\|",
        },
        confidence=0.6,
    ),
]


# 通用表格提取模式：Markdown 表格 → 事实
TABLE_PATTERN = TemplatePattern(
    name="markdown_table",
    category="fact",
    id_prefix="DAT-",
    title_pattern=r"^\|.*\|$",
    field_patterns={
        "id": r"^\|\s*(\*\*)?(DAT-[\w-]+)",
        "value": r"\|([^|]+)\|",
    },
    confidence=0.5,
)

# 标题式实体提取："## ORG-xxx" → 组织实体
HEADING_ENTITY_PATTERN = TemplatePattern(
    name="heading_entity_org",
    category="entity",
    id_prefix="ORG-",
    title_pattern=r"^##\s+(ORG-[\w一-鿿-]+)",
    field_patterns={
        "id": r"^##\s+(ORG-[\w一-鿿-]+)",
        "name": r"##\s+\w+[\s（(](.+?)[)）]",
    },
    confidence=0.6,
)

# 角色实体: "## ROL-xxx"
HEADING_ROL_PATTERN = TemplatePattern(
    name="heading_entity_rol",
    category="entity",
    id_prefix="ROL-",
    title_pattern=r"^##\s+(ROL-[\w一-鿿-]+)",
    field_patterns={
        "id": r"^##\s+(ROL-[\w一-鿿-]+)",
    },
    confidence=0.6,
)

# 人物实体: "## person-xxx"
HEADING_PERSON_PATTERN = TemplatePattern(
    name="heading_entity_person",
    category="entity",
    id_prefix="person-",
    title_pattern=r"^##\s+(person-[\w一-鿿-]+)",
    field_patterns={
        "id": r"^##\s+(person-[\w一-鿿-]+)",
    },
    confidence=0.6,
)

# 项目实体: "## project-xxx"
HEADING_PROJECT_PATTERN = TemplatePattern(
    name="heading_entity_project",
    category="entity",
    id_prefix="project-",
    title_pattern=r"^##\s+(project-[\w一-鿿-]+)",
    field_patterns={
        "id": r"^##\s+(project-[\w一-鿿-]+)",
    },
    confidence=0.6,
)

# 内联政策引用: "P-F15 xxx 来源: xxx"
INLINE_POLICY_PATTERN = TemplatePattern(
    name="inline_policy",
    category="fact",
    id_prefix="POL-",
    title_pattern=r"(P-F[\d-]+)\s+([^\n]{2,60})",
    field_patterns={
        "id": r"(P-F[\d-]+)",
        "title": r"P-F[\d-]+\s+([^\n]{2,60})",
        "source": r"来源[：:]\s*([^\n]{2,30})",
    },
    confidence=0.5,
)

# 中文数据事实: "优质成果数: 470 项"
CN_DATA_FACT_PATTERN = TemplatePattern(
    name="cn_data_fact",
    category="fact",
    id_prefix="DAT-",
    title_pattern=r"^([\w一-鿿]{2,30}(?:数|额|量|率|值|规模))[：:]\s*([\d.]+)\s*([^\d\n，。、]{0,30})",
    field_patterns={
        "title": r"^([\w一-鿿]{2,30}(?:数|额|量|率|值|规模))[：:]",
        "value": r"[：:]\s*([\d.]+)",
        "unit": r"[\d.]+\s*([^\d\n，。、]{1,30})",
    },
    confidence=0.4,
)

# 矛盾诊断提取："## LX ... 推导过程：... 推论结论："
INFERENCE_PATTERN = TemplatePattern(
    name="contradiction_inference",
    category="inference",
    id_prefix="INF-",
    title_pattern=r"^##\s+L(\d+)\s",
    field_patterns={
        "id": r"^\|.*(INF-[\w-]+)",
        "title": r"^##\s+(.+)$",
    },
    confidence=0.6,
)


# ENTITIES.md 格式提取：### person-name + 列表项
ENTITIES_PERSON_PATTERN = TemplatePattern(
    name="entities_md_person",
    category="entity",
    id_prefix="person-",
    title_pattern=r"^###\s+(person-[\w一-鿿-]+)",
    field_patterns={
        "name": r"\*\*名称\*\*:\s*(.+)",
        "role": r"\*\*角色\*\*:\s*(.+)",
        "org": r"\*\*关联组织\*\*:\s*\[(.+?)\]",
        "trust": r"\*\*可信度\*\*:\s*(.+)",
    },
    confidence=0.7,
    # AST 增强：只在"一、人"章节内，按 h3 节点提取
    scope_heading="一、人",
    node_type="heading",
    node_level=3,
    field_keys=[
        "**名称**:",
        "**角色**:",
        "**关联组织**:",
        "**可信度**:",
        "**接触深度**:",
        "**当前状态**:",
        "**标签**:",
        "**详见**:",
        "**关联**:",
        "**来源**:",
    ],
)

ENTITIES_ORG_PATTERN = TemplatePattern(
    name="entities_md_org",
    category="entity",
    id_prefix="org-",
    title_pattern=r"^###\s+(org-[\w一-鿿-]+)",
    field_patterns={
        "name": r"\*\*名称\*\*:\s*(.+)",
        "type": r"\*\*类型\*\*:\s*(.+)",
        "parent": r"\*\*上级\*\*:\s*(.+)",
    },
    confidence=0.7,
    # AST 增强：只在"二、组织"章节内
    scope_heading="二、组织",
    node_type="heading",
    node_level=3,
    field_keys=[
        "**名称**:",
        "**类型**:",
        "**上级**:",
        "**来源**:",
        "**标签**:",
        "**关联**:",
        "**当前状态**:",
        "**详见**:",
    ],
)

ENTITIES_PROJECT_PATTERN = TemplatePattern(
    name="entities_md_project",
    category="entity",
    id_prefix="project-",
    title_pattern=r"^###\s+(project-[\w一-鿿-]+)",
    field_patterns={
        "name": r"\*\*名称\*\*:\s*(.+)",
        "status": r"\*\*状态\*\*:\s*(.+)",
        "owner": r"\*\*主导方\*\*:\s*(.+)",
    },
    confidence=0.7,
    # AST 增强：只在"三、项目/任务"章节内
    scope_heading="三、项目",
    node_type="heading",
    node_level=3,
    field_keys=["**名称**:", "**状态**:", "**主导方**:", "**来源**:", "**标签**:", "**关联**:", "**当前状态**:"],
)


class TemplateExtractor(Extractor):
    """模板式提取器：用正则模式批量提取"""

    def __init__(self, patterns: list[TemplatePattern] | None = None):
        self.patterns = patterns or self._default_patterns()

    @property
    def extractor_name(self) -> str:
        return "template"

    def can_handle(self, source: TextSource) -> bool:
        """检查文本是否匹配已知模板"""
        if source.source_type in ("structured", "file"):
            return True
        # 启发式检测（source_type 为 document 或 free_text 时也尝试）
        text = source.raw_text
        if re.search(r"(?:P-F|DAT-|POL-)\d+", text):
            return True
        if re.search(r"^\|.*\|.*\|", text, re.MULTILINE):
            return True
        if re.search(r"^##\s+(ORG-|ROL-|person-|project-)", text, re.MULTILINE):
            return True
        if re.search(r"^###\s+(person-|org-|project-)", text, re.MULTILINE):
            return True
        if re.search(r"^\w+数[：:]\s*\d+", text, re.MULTILINE):
            return True
        return False

    def extract(self, source: TextSource) -> ExtractionResult:
        candidates = []
        source.raw_text.split("\n")

        for pattern in self.patterns:
            try:
                # AST 模式优先：scope_heading + node_type 时使用 AST 树提取
                if pattern.uses_ast:
                    extracted = self._ast_extract(source.raw_text, pattern)
                else:
                    extracted = self._apply_pattern(source.raw_text, pattern)
                candidates.extend(extracted)
            except Exception as e:
                import sys

                print(f"  ⚠️ 模板[{pattern.name}]异常: {e}", file=sys.stderr)
                continue

        # 去重（按 ID）+ 规范化 ID 前缀 + 字符串确权
        seen = set()
        verified = []
        raw_text = source.raw_text
        for c in candidates:
            cid = c.id or c.content.get("id", "")
            # P2 fix: 规范化 ID 前缀
            cid = self._normalize_id(cid, c.category)
            if cid:
                c.id = cid
                if "id" in c.content:
                    c.content["id"] = cid
            if not cid or cid in seen:
                continue
            seen.add(cid)
            # 字符串确权：候选 ID 必须在原文中出现过
            # （去假阳性：如果候选 ID 在原文中找不到对应行，丢弃）
            if self._confirm_in_text(cid, raw_text) or not raw_text.strip():
                verified.append(c)

        return ExtractionResult(
            candidates=verified,
            summary=f"模板提取完成: {len(verified)} 个候选 (来自 {len(self.patterns)} 个模板)",
            confidence=0.65 if verified else 0.0,
        )

    def _confirm_in_text(self, cid: str, text: str) -> bool:
        """字符串确权：检查候选 ID 是否在原文中出现"""
        if not cid or not text:
            return True
        # 精确搜索（如 person-yangbo、ORG-测试中心）
        if cid in text:
            return True
        # 尝试前缀剥离搜索：POL-P-F15 → P-F15
        parts = cid.split("-", 1)
        if len(parts) > 1 and parts[1] in text:
            return True
        # 再剥一层：POL-P-F15 → F15
        sub = parts[1].split("-", 1)
        if len(sub) > 1 and sub[1] in text:
            return True
        return False

    def _ast_extract(self, text: str, pattern: TemplatePattern) -> list[ExtractionCandidate]:
        """AST 实体级提取：在 AST 树上按节点精确提取字段。

        流程：
        1. 将全文解析为 AST 树
        2. 找到 scope_heading 指定的 h2 章节
        3. 在章节内找到所有指定级别的节点（如 h3 标题）
        4. 从每个节点的子节点（列表项）中按 field_keys 提取字段值
        5. 用正则提取 ID
        """
        from .markdown_ast import MarkdownParser

        candidates: list[ExtractionCandidate] = []
        doc = MarkdownParser().parse(text)
        if not doc:
            return candidates

        # 1. 找到 scope_heading 指定的章节
        scope_nodes = []
        for root_node in doc:
            scope_nodes.extend(root_node.find_all("heading", level=2))
        target_section = None
        for sn in scope_nodes:
            if pattern.scope_heading in sn.title:
                target_section = sn
                break
        if not target_section:
            return candidates

        # 2. 在章节内找所有指定级别的节点
        entities = target_section.find_all(pattern.node_type, pattern.node_level)
        if not entities:
            return candidates

        # 3. 对每个实体节点提取字段
        for entity_node in entities:
            # 从标题提取 ID
            eid = entity_node.title.strip()
            # AST 模式：标题已经是纯净文本（如 "person-yangbo"），直接使用
            # 如果 title_pattern 带标题标记（如 ^###\s+），只在非 AST 模式使用
            if not pattern.uses_ast and pattern.title_pattern:
                id_m = re.search(pattern.title_pattern, entity_node.title or entity_node.content)
                if id_m:
                    eid = id_m.group(1).strip() if id_m.lastindex else eid

            if not eid:
                continue

            # 4. 从子节点的列表项中按 field_keys 提取字段
            content = {"id": eid}
            for child in entity_node.children:
                if child.type != "list_item":
                    continue
                item_text = child.title or child.content
                # 按 field_keys 匹配
                if pattern.field_keys:
                    for key in pattern.field_keys:
                        if item_text.startswith(key):
                            value = item_text[len(key) :].strip()
                            # 从 key 推断字段名
                            field_name = key.strip("*: ").lower().replace(" ", "_")
                            content[field_name] = value
                            break
                # 如果没有 field_keys，用 field_patterns 尝试匹配
                elif pattern.field_patterns:
                    for field_name, field_re in pattern.field_patterns.items():
                        fm = re.search(field_re, item_text)
                        if fm:
                            val = fm.group(fm.lastindex or 1).strip()
                            val = re.sub(r"\*\*", "", val)
                            if val:
                                content[field_name] = val

            candidates.append(
                ExtractionCandidate(
                    category=pattern.category,
                    id=eid,
                    content=content,
                    source_snippet=entity_node.title[:50],
                    confidence=pattern.confidence,
                )
            )

        return candidates

    _NON_ID_WORDS = frozenset(
        {
            "日期",
            "来源",
            "单位",
            "备注",
            "说明",
            "备注",
            "名称",
            "描述",
            "摘要",
            "标题",
            "作者",
            "时间",
            "投资",
            "金额",
        }
    )

    def _normalize_id(self, cid: str, category: str) -> str:
        """P2 fix: 规范化 ID 前缀，如 P-F15 → POL-P-F15"""
        if not cid:
            return cid
        # 过滤非 ID 的中文词
        if cid in self._NON_ID_WORDS or (
            cid.replace("-", "").isalpha()
            and not cid.startswith(("ORG-", "ROL-", "PRJ-", "DAT-", "POL-", "INF-", "person-", "org-", "project-"))
        ):
            return ""
        # 事实：P-F → POL-P-F, D-F → DAT-D-F
        if category == "fact":
            if re.match(r"^P-F\d", cid) and not cid.startswith("POL-"):
                return f"POL-{cid}"
            if re.match(r"^D-F\d", cid) and not cid.startswith("DAT-"):
                return f"DAT-{cid}"
            if cid.startswith("POL-P-F") or cid.startswith("DAT-D-F"):
                return cid  # 已规范化
        # 推论：L → INF-L
        if category == "inference" and cid.startswith("L") and not cid.startswith("INF-"):
            return f"INF-{cid}"
        # 实体：保留原始前缀
        return cid

    def _apply_pattern(self, text: str, pattern: TemplatePattern) -> list[ExtractionCandidate]:
        """对文本应用一个模板模式"""
        candidates = []
        matches = list(re.finditer(pattern.title_pattern, text, re.MULTILINE))
        for m in matches:
            content = {}
            # 从标题正则捕获 ID（group 1）
            matched_id = m.group(1).strip() if m.lastindex and m.lastindex >= 1 else ""

            for fname, field_re in pattern.field_patterns.items():
                fm = re.search(field_re, text[max(0, m.start() - 50) : m.end() + 200], re.MULTILINE)
                if fm:
                    # 取最后一个捕获组或第一个
                    val = fm.group(fm.lastindex or 1).strip()
                    # 去掉 markdown 标记
                    val = re.sub(r"\*\*", "", val)
                    if val:
                        content[fname] = val

            # 只要有内容就保留下
            if content or matched_id:
                candidate = ExtractionCandidate(
                    category=pattern.category,
                    id=matched_id or content.get("id", ""),
                    content=content,
                    source_snippet=text[m.start() : m.end()][:100],
                    confidence=pattern.confidence,
                )
                candidates.append(candidate)

        return candidates

    def _default_patterns(self) -> list[TemplatePattern]:
        """返回内置的默认模板集"""
        return [
            POLICY_PATTERNS[0],
            TABLE_PATTERN,
            HEADING_ENTITY_PATTERN,
            HEADING_ROL_PATTERN,
            HEADING_PERSON_PATTERN,
            HEADING_PROJECT_PATTERN,
            INLINE_POLICY_PATTERN,
            CN_DATA_FACT_PATTERN,
            INFERENCE_PATTERN,
            ENTITIES_PERSON_PATTERN,
            ENTITIES_ORG_PATTERN,
            ENTITIES_PROJECT_PATTERN,
        ]

    def register_pattern(self, pattern: TemplatePattern):
        """注册自定义模板"""
        self.patterns.append(pattern)
