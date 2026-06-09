"""
ssot-kernel — extractor/base.py
================================
提取层的核心接口定义。

三路提取器共享此接口：
1. 交互式 (Interactive) — 人机对话引导提取，Claude 提问，用户回答
2. 模板式 (Template)   — 固定格式文档的正则解析
3. LLM API (LLM)       — 可选，调用外部模型批量提取

所有提取器的输出都是统一的 ExtractionResult，经 Validator 校验后才写入 YAML。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

# ── 输入 ────────────────────────────────────────────


@dataclass
class TextSource:
    """提取器的输入——原始文本及其元信息"""

    raw_text: str  # 原始内容
    source_type: str = "free_text"  # conversation / document / structured / file
    source_name: str = ""  # 来源标识（如"5/8座谈会纪要"）
    metadata: dict[str, Any] = field(default_factory=dict)


# ── 输出 ────────────────────────────────────────────


@dataclass
class ExtractionCandidate:
    """单个提取候选——从文本中提取的一段信息，尚未校验"""

    category: str  # entity / fact / inference / relation / rule
    id: str = ""  # 建议 ID（可为空，由系统或用户填写）
    content: dict[str, Any] = field(default_factory=dict)
    source_snippet: str = ""  # 原文片段（用于追溯和校验）
    confidence: float = 0.5  # 0~1，提取置信度


@dataclass
class ExtractionResult:
    """一次提取的完整产出"""

    candidates: list[ExtractionCandidate] = field(default_factory=list)
    summary: str = ""  # 提取摘要（供人阅读）
    confidence: float = 0.0  # 整体置信度
    errors: list[str] = field(default_factory=list)

    @property
    def entity_candidates(self) -> list[ExtractionCandidate]:
        return [c for c in self.candidates if c.category == "entity"]

    @property
    def fact_candidates(self) -> list[ExtractionCandidate]:
        return [c for c in self.candidates if c.category == "fact"]

    @property
    def inference_candidates(self) -> list[ExtractionCandidate]:
        return [c for c in self.candidates if c.category == "inference"]

    @property
    def relation_candidates(self) -> list[ExtractionCandidate]:
        return [c for c in self.candidates if c.category == "relation"]

    @property
    def rule_candidates(self) -> list[ExtractionCandidate]:
        return [c for c in self.candidates if c.category == "rule"]


# ── 校验 ────────────────────────────────────────────


@dataclass
class Conflict:
    """提取候选与现有数据之间的冲突"""

    field: str
    existing_value: Any
    extracted_value: Any
    severity: str = "WARN"  # BLOCKER / ERROR / WARN
    suggestion: str = ""


@dataclass
class ValidationResult:
    """校验结果"""

    passed: bool = True
    conflicts: list[Conflict] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


# ── 提取器基类 ──────────────────────────────────────


class Extractor(ABC):
    """提取器基类。所有提取器（交互式/模板式/LLM）继承此接口。"""

    @property
    @abstractmethod
    def extractor_name(self) -> str:
        """提取器标识"""
        ...

    @abstractmethod
    def extract(self, source: TextSource) -> ExtractionResult:
        """从原始文本提取知识结构。"""
        ...

    def can_handle(self, source: TextSource) -> bool:
        """判断此提取器能否处理该输入。子类可覆盖。"""
        return True


# ── 校验器 ──────────────────────────────────────────


class CandidateValidator:
    """提取候选校验器。

    在写入 YAML 之前检查候选与现有领域配置的一致性：
    - ID 冲突（同一 ID 不同内容）
    - 事实值冲突（同编号不同数值）
    - ID 前缀规范（ORG-/ROL-/DAT-/POL- 等）
    """

    def __init__(self, existing_domain_dir: str = ""):
        from pathlib import Path

        self._domain_dir = Path(existing_domain_dir) if existing_domain_dir else None
        self._existing: dict[str, Any] = {}  # 缓存已加载的数据

    def validate(self, result: ExtractionResult) -> ValidationResult:
        """对提取结果执行校验"""
        v = ValidationResult()

        seen_ids: dict[str, Any] = {}
        for c in result.candidates:
            cid = c.id or c.content.get("id", "")
            if not cid:
                continue

            # 检查 ID 前缀规范
            prefix_ok = self._check_id_prefix(cid, c.category)
            if not prefix_ok:
                v.conflicts.append(
                    Conflict(
                        field="id",
                        existing_value="标准前缀",
                        extracted_value=cid,
                        severity="WARN",
                        suggestion=f"ID '{cid}' 不符合 {c.category} 的标准前缀规范",
                    )
                )

            # 检查 ID 重复
            if cid in seen_ids:
                v.conflicts.append(
                    Conflict(
                        field="id",
                        existing_value=seen_ids[cid],
                        extracted_value=cid,
                        severity="ERROR",
                        suggestion=f"ID '{cid}' 重复",
                    )
                )
            seen_ids[cid] = c.content.get("name", cid)

        # 对事实类型，检查数值冲突
        for c in result.fact_candidates:
            cid = c.id or c.content.get("id", "")
            existing_val = self._get_existing_value(cid)
            if existing_val is not None:
                new_val = c.content.get("value")
                if new_val is not None and str(new_val) != str(existing_val):
                    v.passed = False
                    v.conflicts.append(
                        Conflict(
                            field=f"{cid}.value",
                            existing_value=existing_val,
                            extracted_value=new_val,
                            severity="ERROR",
                            suggestion="确认数据来源是否更新，或是否是不同口径",
                        )
                    )

        v.passed = len([c for c in v.conflicts if c.severity == "ERROR"]) == 0
        return v

    def _check_id_prefix(self, cid: str, category: str) -> bool:
        prefix_map = {
            "entity": [
                "ORG-",
                "ROL-",
                "PRJ-",
                "RES-",
                "PERSON-",
                "person-",
                "org-",
                "project-",
                "ROL-person-",
            ],
            "fact": ["DAT-", "POL-", "P-"],
            "inference": ["INF-"],
            "relation": [],  # 关系没有 ID 前缀要求
            "rule": ["R-INF-"],
        }
        allowed = prefix_map.get(category, [])
        if not allowed:
            return True
        return any(cid.startswith(p) for p in allowed)

    def _get_existing_value(self, fact_id: str):
        """检查已有事实的值"""
        if self._domain_dir is None:
            return None
        try:
            from ..config_loader import load_domain

            config = load_domain(str(self._domain_dir))
            fact = config.find_fact(fact_id)
            if fact:
                return fact.value
        except Exception:
            pass
        return None


# ── 写入器 ──────────────────────────────────────────


class YamlWriter:
    """将校验后的提取结果写入领域 YAML 文件。"""

    def __init__(self, domain_dir: str):
        self.domain_dir = domain_dir

    def apply(self, result: ExtractionResult, auto_confirm: bool = False) -> list[str]:
        """将提取结果写入领域 YAML。

        Args:
            result: 校验后的提取结果
            auto_confirm: 自动确认（跳过人工确认步骤）

        Returns:
            applied: 实际写入的文件列表
        """
        from pathlib import Path

        import yaml

        applied = []
        dd = Path(self.domain_dir)

        # 确保目标目录存在
        dd.mkdir(parents=True, exist_ok=True)

        # 按类别分组写入
        writers = {
            "entity": ("entities.yaml", "entities"),
            "fact": ("facts.yaml", None),  # facts 分 policy/data
            "inference": ("inferences.yaml", "inferences"),
            "relation": ("relations.yaml", "relations"),
            "rule": ("rules.yaml", "rules"),
        }

        for cat, (filename, root_key) in writers.items():
            candidates = [c for c in result.candidates if c.category == cat]
            if not candidates:
                continue

            filepath = dd / filename
            if filepath.exists():
                existing: dict[str, Any] = (
                    yaml.safe_load(filepath.read_text("utf-8")) or {}
                )
            else:
                existing = {}

            # 将候选转 dict 并追加
            if cat == "fact":
                # facts 要分 policy 和 data
                for c in candidates:
                    cid = c.id or c.content.get("id", "")
                    target = "policy" if cid.startswith("POL-") else "data"
                    if target not in existing:
                        existing[target] = []
                    existing[target].append(c.content)
            else:
                key = root_key or f"{cat}s"
                if key not in existing:
                    existing[key] = []
                for c in candidates:
                    existing[key].append(c.content)

            filepath.write_text(
                yaml.dump(
                    existing,
                    allow_unicode=True,
                    default_flow_style=False,
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            applied.append(str(filepath))

        return applied
