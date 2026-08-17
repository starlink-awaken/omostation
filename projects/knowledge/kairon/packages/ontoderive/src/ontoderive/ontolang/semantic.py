"""OntoLang 语义分析器"""

import re

from .ast import AST, SemanticError


class SemanticAnalyzer:
    VALID_ENTITY_PREFIXES = {"ORG", "ROL", "PRJ", "POL", "DAT"}
    VALID_FACT_PATTERN = re.compile(r"^(D-F|P-F)\d+")

    def analyze(self, ast: AST) -> list[SemanticError]:
        errors = []
        ids_seen = set()

        for e in ast.entities:
            prefix = e.id.split("-")[0] if "-" in e.id else e.id
            if prefix not in self.VALID_ENTITY_PREFIXES:
                errors.append(
                    SemanticError(
                        f"实体 '{e.id}' 前缀无效，应为 {sorted(self.VALID_ENTITY_PREFIXES)}",
                        e.id,
                        e.pos,
                        f"如: ORG-{e.id}",
                    )
                )
            if e.id in ids_seen:
                errors.append(SemanticError(f"实体ID '{e.id}' 重复声明", e.id, e.pos))
            ids_seen.add(e.id)

        for f in ast.facts:
            if not self.VALID_FACT_PATTERN.match(f.id):
                errors.append(
                    SemanticError(f"事实 '{f.id}' ID格式无效，应为 D-F数字 或 P-F数字", f.id, f.pos, "如: D-F1, P-F9")
                )
            if f.id in ids_seen:
                errors.append(SemanticError(f"事实ID '{f.id}' 重复声明", f.id, f.pos))
            ids_seen.add(f.id)

        for inf in ast.inferences:
            if not re.match(r"^INF-", inf.id):
                errors.append(SemanticError(f"推论 '{inf.id}' ID应以 INF- 开头", inf.id, inf.pos, f"如: INF-{inf.id}"))
            if not inf.derives_from:
                errors.append(
                    SemanticError(
                        f"推论 '{inf.id}' 缺少 derives_from 声明", inf.id, inf.pos, "添加 derives_from: [D-F1, ...]"
                    )
                )
            # 检查引用是否有效
            for ref in inf.derives_from:
                if ref not in ids_seen and not self.VALID_FACT_PATTERN.match(ref):
                    errors.append(
                        SemanticError(
                            f"推论 '{inf.id}' 引用未声明的 '{ref}'", inf.id, inf.pos, "确保被引用的事实/推论已声明"
                        )
                    )
            ids_seen.add(inf.id)

        for p in ast.protocols:
            if not p.constraint:
                errors.append(SemanticError(f"规约 '{p.id}' 缺少约束表达式", p.id, p.pos, '添加 constraint: "..."'))
            ids_seen.add(p.id)

        return errors
