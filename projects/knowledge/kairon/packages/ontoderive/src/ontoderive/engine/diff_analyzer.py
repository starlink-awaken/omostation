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
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Sisyphus'
Layer: L3
Constraint: '[!!] AUTO_ADDED_METADATA'
Summary: 'Auto-generated metadata for diff_analyzer.py'
Tags:
- auto-metadata
Authority: organs/D-Logos/AGENTS.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Diff Analyzer ≡ Module
# 内涵 ≝ {Diff, Analyzer}
# 外延 ≝ {e | e ∈ D-Logos ∧ implements(e, DiffAnalyzer)}
# 功能 ⊢ {Diff_Analyzer, Init_Diff, Validate_Analyzer}
# =============================================================================

"""差异分析器 (DiffAnalyzer)

比对文档声明和代码实现:
- 匹配文档声明和代码实体
- 分类差异类型 (Type A/B/C/D)
- 生成差异报告
"""

_log = logging.getLogger(__name__)


class DiffType(Enum):
    """差异类型"""

    TYPE_A = "type_a"  # 文档过时，实现已变更
    TYPE_B = "type_b"  # 实现缺失，文档有定义
    TYPE_C = "type_c"  # 文档错误，需重新描述
    TYPE_D = "type_d"  # 实现偏差，需重构代码


class MatchConfidence(Enum):
    """匹配置信度"""

    EXACT = "exact"  # 完全匹配
    HIGH = "high"  # 高置信度
    MEDIUM = "medium"  # 中等置信度
    LOW = "low"  # 低置信度
    NO_MATCH = "no_match"  # 无匹配


@dataclass
class MatchResult:
    """匹配结果"""

    doc_declaration_id: str
    doc_declaration_type: str
    doc_source: str
    doc_line: int

    code_entity_id: str | None = None
    code_entity_type: str | None = None
    code_source: str | None = None
    code_line: int | None = None

    confidence: MatchConfidence = MatchConfidence.NO_MATCH
    match_reason: str = ""

    # 差异信息
    diff_type: DiffType | None = None
    diff_description: str = ""

    # 接口差异详情
    param_mismatch: list[str] = field(default_factory=list)
    return_type_mismatch: str | None = None
    missing_methods: list[str] = field(default_factory=list)
    extra_methods: list[str] = field(default_factory=list)


@dataclass
class DiffReport:
    """差异报告"""

    total_declarations: int
    total_entities: int
    matched_count: int
    unmatched_doc_count: int
    unmatched_code_count: int

    # 按类型统计
    diff_type_a: int
    diff_type_b: int
    diff_type_c: int
    diff_type_d: int

    # 详细匹配结果
    matches: list[MatchResult]

    # 修复建议
    recommendations: list[dict]


class DiffAnalyzer:
    """差异分析器"""

    def __init__(self) -> None:
        self.metadata_path = "organs/D-Logos/organs/diff_analyzer.py"
        self.organ_name = "diff_analyzer"
        self.organ_id = f"eidos-{id(self):x}"
        self._status = "active"
        self._metabolic_budget = 1000.0
        self.matches: list[MatchResult] = []

    def analyze(self, doc_ast_path: Path, impl_manifest_path: Path) -> DiffReport:
        """分析文档和实现的差异"""
        _log.info("🔍 分析文档 - 实现差异...")

        # 加载数据
        with open(doc_ast_path, encoding="utf-8") as f:
            doc_data = json.load(f)

        with open(impl_manifest_path, encoding="utf-8") as f:
            impl_data = json.load(f)

        # 构建索引
        doc_declarations = self._build_doc_index(doc_data)
        code_entities = self._build_code_index(impl_data)

        # 执行匹配
        _log.info("  执行匹配...")
        for _doc_id, doc_decl in doc_declarations.items():
            match = self._find_match(doc_decl, code_entities)
            self.matches.append(match)

        # 统计结果
        matched = [m for m in self.matches if m.confidence != MatchConfidence.NO_MATCH]
        unmatched_doc = [m for m in self.matches if m.confidence == MatchConfidence.NO_MATCH]

        # 计算差异类型
        diff_type_a = sum(1 for m in self.matches if m.diff_type == DiffType.TYPE_A)
        diff_type_b = sum(1 for m in self.matches if m.diff_type == DiffType.TYPE_B)
        diff_type_c = sum(1 for m in self.matches if m.diff_type == DiffType.TYPE_C)
        diff_type_d = sum(1 for m in self.matches if m.diff_type == DiffType.TYPE_D)

        # 生成修复建议
        recommendations = self._generate_recommendations()

        report = DiffReport(
            total_declarations=len(doc_declarations),
            total_entities=len(code_entities),
            matched_count=len(matched),
            unmatched_doc_count=len(unmatched_doc),
            unmatched_code_count=0,  # 简化实现
            diff_type_a=diff_type_a,
            diff_type_b=diff_type_b,
            diff_type_c=diff_type_c,
            diff_type_d=diff_type_d,
            matches=self.matches,
            recommendations=recommendations,
        )

        _log.info("✅ 分析完成:")
        _log.info("  文档声明：{report.total_declarations}")
        _log.info("  代码实体：{report.total_entities}")
        _log.info("  已匹配：{report.matched_count}")
        _log.info("  未匹配文档：{report.unmatched_doc_count}")
        _log.info("  差异分布：A={diff_type_a}, B={diff_type_b}, C={diff_type_c}, D={diff_type_d}")

        return report

    def _build_doc_index(self, doc_data: dict) -> dict[str, dict]:
        """构建文档索引"""
        index = {}
        for doc in doc_data.get("documents", []):
            for decl in doc.get("declarations", []):
                key = f"{decl['id']}_{decl['type']}"
                index[key] = {
                    **decl,
                    "source_file": doc["source_file"],
                }
        return index

    def _build_code_index(self, impl_data: dict) -> dict[str, dict]:
        """构建代码索引"""
        index = {}
        for cls in impl_data.get("classes", []):
            index[cls["qualified_name"]] = cls
        for func in impl_data.get("functions_and_methods", []):
            index[func["qualified_name"]] = func
        return index

    def _find_match(self, doc_decl: dict, code_entities: dict) -> MatchResult:
        """为文档声明查找匹配的代码实体"""
        doc_name = doc_decl["name"]
        doc_type = doc_decl["type"]

        # 策略 1: 精确名称匹配
        for _entity_id, entity in code_entities.items():
            if entity["name"] == doc_name:
                # 检查接口差异
                param_mismatch = self._check_param_mismatch(doc_decl, entity)
                return_mismatch = self._check_return_mismatch(doc_decl, entity)

                diff_type = None
                if param_mismatch or return_mismatch:
                    diff_type = DiffType.TYPE_D  # 实现偏差

                return MatchResult(
                    doc_declaration_id=doc_decl["id"],
                    doc_declaration_type=doc_type,
                    doc_source=doc_decl["source_file"],
                    doc_line=doc_decl["line_number"],
                    code_entity_id=entity["id"],
                    code_entity_type=entity.get("entity_type", "unknown"),
                    code_source=entity["source_file"],
                    code_line=entity.get("line_number"),
                    confidence=MatchConfidence.EXACT,
                    match_reason="名称完全匹配",
                    diff_type=diff_type,
                    diff_description="实现与文档名称匹配" if not diff_type else "接口存在差异",
                    param_mismatch=param_mismatch,
                    return_type_mismatch=return_mismatch,
                )

        # 策略 2: 模糊匹配（包含关系）
        for _entity_id, entity in code_entities.items():
            if doc_name.lower() in entity["name"].lower() or entity["name"].lower() in doc_name.lower():
                # 检查接口差异
                param_mismatch = self._check_param_mismatch(doc_decl, entity)
                return_mismatch = self._check_return_mismatch(doc_decl, entity)

                diff_type = None
                if param_mismatch or return_mismatch:
                    diff_type = DiffType.TYPE_D  # 实现偏差
                else:
                    diff_type = DiffType.TYPE_A  # 可能是文档过时

                return MatchResult(
                    doc_declaration_id=doc_decl["id"],
                    doc_declaration_type=doc_type,
                    doc_source=doc_decl["source_file"],
                    doc_line=doc_decl["line_number"],
                    code_entity_id=entity["id"],
                    code_entity_type=entity.get("entity_type", "unknown"),
                    code_source=entity["source_file"],
                    code_line=entity.get("line_number"),
                    confidence=MatchConfidence.MEDIUM,
                    match_reason="名称模糊匹配",
                    diff_type=diff_type,
                    diff_description="名称相似但实现可能有差异",
                    param_mismatch=param_mismatch,
                    return_type_mismatch=return_mismatch,
                )

        # 策略 3: 检查是否是协议/约束类型（可能没有直接代码对应）
        if doc_type in ["protocol", "constraint", "config"]:
            # 对于这些类型，尝试在代码中查找相关关键词
            for _entity_id, entity in code_entities.items():
                entity_name = entity.get("name", "").lower()
                doc_name_lower = doc_name.lower()

                # 检查是否有语义关联
                if self._has_semantic_relation(doc_name_lower, entity_name):
                    return MatchResult(
                        doc_declaration_id=doc_decl["id"],
                        doc_declaration_type=doc_type,
                        doc_source=doc_decl["source_file"],
                        doc_line=doc_decl["line_number"],
                        code_entity_id=entity["id"],
                        code_entity_type=entity.get("entity_type", "unknown"),
                        code_source=entity["source_file"],
                        code_line=entity.get("line_number"),
                        confidence=MatchConfidence.LOW,
                        match_reason="语义关联匹配",
                        diff_type=DiffType.TYPE_C,  # 可能是文档错误
                        diff_description="协议/约束类型，需人工确认",
                    )

        # 未找到匹配
        # 判断是 Type B (实现缺失) 还是 Type C (文档错误)
        diff_type = DiffType.TYPE_B  # 默认假设实现缺失

        # 如果是协议/约束类型，可能是 Type C
        if doc_type in ["protocol", "constraint"]:
            diff_type = DiffType.TYPE_C

        return MatchResult(
            doc_declaration_id=doc_decl["id"],
            doc_declaration_type=doc_type,
            doc_source=doc_decl["source_file"],
            doc_line=doc_decl["line_number"],
            confidence=MatchConfidence.NO_MATCH,
            match_reason="未找到匹配的代码实体",
            diff_type=diff_type,
            diff_description="文档有定义但代码未实现" if diff_type == DiffType.TYPE_B else "文档描述可能错误",
        )

    def _has_semantic_relation(self, doc_name: str, entity_name: str) -> bool:
        """检查是否有语义关联"""
        # 简单的关键词匹配
        keywords = doc_name.split("_")
        for keyword in keywords:
            if len(keyword) > 3 and keyword in entity_name:
                return True
        return False

    def _check_param_mismatch(self, doc_decl: dict, code_entity: dict) -> list[str]:
        """检查参数不匹配"""
        mismatches = []

        doc_params = {p["name"]: p for p in doc_decl.get("parameters", [])}
        code_params = {p["name"]: p for p in code_entity.get("parameters", [])}

        # 文档有但代码没有的参数
        for param_name in doc_params:
            if param_name not in code_params:
                mismatches.append(f"文档有参数 '{param_name}' 但实现缺失")

        # 代码有但文档没有的参数
        for param_name in code_params:
            if param_name not in doc_params:
                mismatches.append(f"实现有参数 '{param_name}' 但文档未定义")

        # 类型不匹配
        for param_name, doc_param in doc_params.items():
            if param_name in code_params:
                doc_type = doc_param.get("type", "")
                code_type = code_params[param_name].get("type", "")
                if doc_type and code_type and doc_type != code_type:
                    mismatches.append(f"参数 '{param_name}' 类型不匹配：文档={doc_type}, 实现={code_type}")

        return mismatches

    def _check_return_mismatch(self, doc_decl: dict, code_entity: dict) -> str | None:
        """检查返回值类型不匹配"""
        doc_return = doc_decl.get("return_type", "")
        code_return = code_entity.get("return_type", "")

        if doc_return and code_return and doc_return != code_return:
            return f"返回值类型不匹配：文档={doc_return}, 实现={code_return}"
        return None

    def _generate_recommendations(self) -> list[dict]:
        """生成修复建议"""
        recommendations = []

        for match in self.matches:
            if match.diff_type:
                rec: dict[str, Any] = {
                    "declaration_id": match.doc_declaration_id,
                    "declaration_name": match.doc_declaration_id,
                    "diff_type": match.diff_type.value,
                    "source": match.doc_source,
                    "line": match.doc_line,
                }

                if match.diff_type == DiffType.TYPE_A:
                    rec["action"] = "更新文档"
                    rec["priority"] = "P1"
                    rec["description"] = f"文档已过时，实现已变更为 {match.code_entity_id}"

                elif match.diff_type == DiffType.TYPE_B:
                    rec["action"] = "补充实现或修正文档"
                    rec["priority"] = "P0"
                    rec["description"] = "文档有定义但代码未实现，需评估是否补充实现"

                elif match.diff_type == DiffType.TYPE_C:
                    rec["action"] = "修正文档"
                    rec["priority"] = "P1"
                    rec["description"] = "文档描述错误，需重新描述或删除"

                elif match.diff_type == DiffType.TYPE_D:
                    rec["action"] = "重构代码或更新文档"
                    rec["priority"] = "P1"
                    rec["description"] = "实现与文档定义不一致，需对齐"
                    if match.param_mismatch:
                        rec["details"] = match.param_mismatch
                    if match.return_type_mismatch:
                        rec["details"] = rec.get("details", []) + [match.return_type_mismatch]

                recommendations.append(rec)

        return recommendations

    def export_report(self, report: DiffReport, output_path: Path) -> None:
        """导出差异报告"""
        data = {
            "summary": {
                "total_declarations": report.total_declarations,
                "total_entities": report.total_entities,
                "matched": report.matched_count,
                "unmatched_doc": report.unmatched_doc_count,
                "diff_type_a": report.diff_type_a,
                "diff_type_b": report.diff_type_b,
                "diff_type_c": report.diff_type_c,
                "diff_type_d": report.diff_type_d,
                "alignment_rate": f"{(report.matched_count / max(1, report.total_declarations) * 100):.1f}%",
            },
            "recommendations": report.recommendations,
            "detailed_matches": [
                {
                    "doc_id": m.doc_declaration_id,
                    "doc_type": m.doc_declaration_type,
                    "doc_source": m.doc_source,
                    "doc_line": m.doc_line,
                    "code_id": m.code_entity_id,
                    "code_type": m.code_entity_type,
                    "code_source": m.code_source,
                    "code_line": m.code_line,
                    "confidence": m.confidence.value,
                    "diff_type": m.diff_type.value if m.diff_type else None,
                    "diff_description": m.diff_description,
                    "param_mismatch": m.param_mismatch,
                    "return_mismatch": m.return_type_mismatch,
                }
                for m in report.matches
            ],
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        _log.info("✅ 差异报告已导出：{output_path}")
