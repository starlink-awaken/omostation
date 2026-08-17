"""
[DEPRECATED] OntoLang v2 解析器包 — 保留供外部兼容引用
==========================================================
此模块保留自 v3.5，当前 engine/ 内部无任何模块引用它。
保留原因是它是一个完整的递归下降解析器+AST+代码生成管线，
作为项目声明过的架构组件，删除会导致外部调用者静默断裂。

新代码不应依赖此模块。如需形式语言支持，使用 engine.theories.ontolang.OntoLangParser
"""

__all__ = []

import re
from typing import Any

from .ast import AST, EntityDef, FactDef, InferenceDef, ParseError, ProtocolDef, RelationDef, SemanticError, SourcePos
from .codegen import to_json, to_legacy_ast, to_markdown
from .parser import Lexer, Parser
from .semantic import SemanticAnalyzer

__all__ = [
    "AST",
    "EntityDef",
    "FactDef",
    "InferenceDef",
    "ParseError",
    "ProtocolDef",
    "RelationDef",
    "SemanticError",
    "SourcePos",
    "to_json",
    "to_legacy_ast",
    "to_markdown",
    "Lexer",
    "Parser",
    "SemanticAnalyzer",
    "OntoLangParserV2",
    "OntoLangParser",
]


class OntoLangParserV2:
    def __init__(self, filename: Any = "") -> None:
        self.filename = filename
        self.parser = Parser(filename)
        self.semantic = SemanticAnalyzer()

    def parse(self, source: Any) -> Any:
        return self.parser.parse(source)

    def validate(self, ast: Any) -> Any:
        return self.semantic.analyze(ast)

    def test_suite(self) -> tuple[Any, ...]:
        test_source = """-- 实体定义
entity ORG-国转中心 : Organization { governance: "双轨制" }
entity ROL-技术经理人 : Role { count: 133 }

-- 事实声明
fact D-F1 : DataPoint { value: 470, source: "中心介绍PDF" }
fact P-F9 : Policy { authority: "北京市" }

-- 推论
inference INF-L1 : Contradiction { derives_from: [D-F1], conclusion: "需要双轨分离" }

-- 规约
protocol P-CROSS-001 : Constraint { constraint: "mapping_coverage >= 90%" }
"""
        ast = self.parse(test_source)
        errors = self.validate(ast)
        return to_legacy_ast(ast), errors, len(self.parser.errors)


# v1兼容接口 — 与旧 ontolang.OntoLangParser 保持相同api
class OntoLangParser:
    def __init__(self) -> None:
        self.v2 = OntoLangParserV2()
        self.errors: list[Any] = []
        self.warnings: list[Any] = []

    def parse(self, source: Any) -> Any:
        ast = self.v2.parse(source)
        legacy = to_legacy_ast(ast)
        legacy["errors"] = [{"line": e.pos.line, "msg": e.msg} for e in self.v2.parser.errors]
        return legacy

    def validate(self, ast: Any) -> Any:
        if isinstance(ast, dict):
            return self._validate_dict(ast)
        return self.v2.validate(ast)

    def _validate_dict(self, ast: Any) -> Any:
        errors = []
        for e in ast.get("entities", []):
            prefix = e["id"].split("-")[0] if "-" in e["id"] else ""
            if prefix not in ("ORG", "ROL", "PRJ"):
                errors.append(f"E{e.get('line', 0)}: '{e['id']}' 前缀无效")
        for inf in ast.get("inferences", []):
            # 兼容 raw 字段和初始 dict 格式
            check_text = inf.get("raw", "") or str(inf.get("derives_from", "")) or ""
            if "derives_from" not in check_text and not inf.get("derives_from"):
                errors.append(f"E{inf.get('line', 0)}: '{inf['id']}' 缺少derives_from声明")
        for f in ast.get("facts", []):
            if not re.match(r"^(D-F|P-F)\d+", f["id"]):
                errors.append(f"E{f.get('line', 0)}: '{f['id']}' 事实ID格式无效")
        return errors

    def test_suite(self) -> Any:
        legacy_ast, errors, parse_errors = self.v2.test_suite()
        self.errors = ["parse_error"] * parse_errors
        return legacy_ast
