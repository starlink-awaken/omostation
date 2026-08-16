"""

# ruff: noqa: E501
OntoDerive 形式语言层 — OntoLang解析器（v1兼容接口）
=====================================================
委托到 ontolang/ 包的新解析器，保留原 api 兼容性。
"""

import re
from importlib import import_module
from typing import Any

_ontolang_v2 = import_module("ontoderive.ontolang")


class OntoLangParser:
    def __init__(self) -> None:
        self.v2 = _ontolang_v2.OntoLangParserV2()
        self.errors: list[Any] = []
        self.warnings: list[Any] = []

    def parse(self, source: Any) -> Any:
        ast = self.v2.parse(source)
        # 转换为v1兼容格式
        legacy = _ontolang_v2.to_legacy_ast(ast)
        legacy["errors"] = (
            [{"line": e.pos.line, "msg": e.msg} for e in self.v2.parser.errors]
            if hasattr(self.v2.parser, "errors")
            else []
        )
        return legacy

    def validate(self, ast: Any) -> Any:
        # ast是dict格式（v1兼容），需要转换
        if isinstance(ast, dict):
            return self._validate_dict(ast)
        return self.v2.validate(ast)

    def _validate_dict(self, ast: Any) -> Any:
        errors = []
        for e in ast.get("entities", []):
            prefix = e["id"].split("-")[0] if "-" in e["id"] else ""
            if prefix not in ("ORG", "ROL", "PRJ"):
                errors.append(f"E{e.get('line', 0)}: '{e['id']}' 前缀无效, 应为 ['ORG', 'ROL', 'PRJ']")
        for inf in ast.get("inferences", []):
            if "derives_from" not in inf.get("raw", ""):
                errors.append(f"E{inf.get('line', 0)}: '{inf['id']}' 缺少derives_from声明")
        for f in ast.get("facts", []):
            if not re.match(r"^(D-F|P-F)\d+", f["id"]):
                errors.append(f"E{f.get('line', 0)}: '{f['id']}' 事实ID格式无效")
        return errors

    def test_suite(self) -> Any:
        legacy_ast, errors, parse_errors = self.v2.test_suite()
        self.errors = ["parse_error"] * parse_errors
        return legacy_ast
