"""OntoLang AST → Markdown/JSON 代码生成"""

from .ast import AST


def to_markdown(ast: AST) -> str:
    lines = []
    if ast.entities:
        lines.append("## 实体定义\n")
        for e in ast.entities:
            lines.append(f"### {e.id} : {e.entity_type}")
            for k, v in e.properties.items():
                if isinstance(v, list):
                    lines.append(f"- {k}: [{', '.join(str(x) for x in v)}]")
                else:
                    lines.append(f"- {k}: {v}")
            lines.append("")

    if ast.facts:
        lines.append("## 事实声明\n")
        lines.append("| 编号 | 类型 | 属性 |")
        lines.append("|------|------|------|")
        for f in ast.facts:
            props = "; ".join(f"{k}={v}" for k, v in f.properties.items())
            lines.append(f"| {f.id} | {f.fact_type} | {props} |")
        lines.append("")

    if ast.inferences:
        lines.append("## 推论体系\n")
        for inf in ast.inferences:
            lines.append(f"### {inf.id} : {inf.inference_type}")
            if inf.derives_from:
                lines.append(f"- derives_from: [{', '.join(inf.derives_from)}]")
            if inf.conclusion:
                lines.append(f"- conclusion: {inf.conclusion}")
            for k, v in inf.properties.items():
                lines.append(f"- {k}: {v}")
            lines.append("")

    if ast.protocols:
        lines.append("## 规约约束\n")
        for p in ast.protocols:
            lines.append(f"### {p.id} : {p.constraint_type}")
            if p.constraint:
                lines.append(f"- constraint: {p.constraint}")
            for k, v in p.properties.items():
                lines.append(f"- {k}: {v}")
            lines.append("")
    return "\n".join(lines)


def to_json(ast: AST) -> dict:
    return {
        "entities": [{"id": e.id, "type": e.entity_type, "properties": e.properties} for e in ast.entities],
        "facts": [{"id": f.id, "type": f.fact_type, "properties": f.properties} for f in ast.facts],
        "inferences": [
            {
                "id": inf.id,
                "type": inf.inference_type,
                "derives_from": inf.derives_from,
                "conclusion": inf.conclusion,
                "properties": inf.properties,
            }
            for inf in ast.inferences
        ],
        "protocols": [
            {"id": p.id, "type": p.constraint_type, "constraint": p.constraint, "properties": p.properties}
            for p in ast.protocols
        ],
    }


def to_legacy_ast(ast: AST) -> dict:
    """转换为兼容原 ontolang.py 的 dict 格式"""
    return {
        "entities": [
            {"id": e.id, "type": e.entity_type, "line": e.pos.line if e.pos else 0, "raw": ""} for e in ast.entities
        ],
        "facts": [{"id": f.id, "type": f.fact_type, "line": f.pos.line if f.pos else 0, "raw": ""} for f in ast.facts],
        "inferences": [
            {
                "id": inf.id,
                "type": inf.inference_type,
                "line": inf.pos.line if inf.pos else 0,
                "raw": (
                    f"inference {inf.id} : {inf.inference_type} {{ derives_from: {inf.derives_from} }}"
                    if inf.derives_from
                    else ""
                ),
            }
            for inf in ast.inferences
        ],
        "protocols": [
            {"id": p.id, "type": p.constraint_type, "line": p.pos.line if p.pos else 0, "raw": ""}
            for p in ast.protocols
        ],
    }
