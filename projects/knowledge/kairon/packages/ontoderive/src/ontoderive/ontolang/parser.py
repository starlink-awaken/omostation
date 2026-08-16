"""OntoLang 词法+语法解析器 — 手写递归下降"""

import re
from typing import Any

from .ast import (
    AST,
    EntityDef,
    FactDef,
    InferenceDef,
    ParseError,
    ProtocolDef,
    RelationDef,
    SourcePos,
)


class Token:
    def __init__(self, kind: Any, value: Any, line: Any, col: Any) -> None:
        self.kind = kind
        self.value = value
        self.line = line
        self.col = col


class Lexer:
    TOKENS = [
        ("ENTITY", r"entity\b"),
        ("FACT", r"fact\b"),
        ("INFERENCE", r"inference\b"),
        ("PROTOCOL", r"protocol\b"),
        ("RELATION", r"relation\b"),
        ("ID", r"[A-Za-z][A-Za-z0-9_-]*"),
        ("STRING", r'"[^"]*"'),
        ("NUMBER", r"\d+\.?\d*"),
        ("COLON", r":"),
        ("LBRACE", r"\{"),
        ("RBRACE", r"\}"),
        ("LBRACKET", r"\["),
        ("RBRACKET", r"\]"),
        ("COMMA", r","),
        ("NEWLINE", r"\n"),
        ("COMMENT", r"--[^\n]*"),
        ("WS", r"[ \t\r]+"),
    ]

    def __init__(self, source: Any, filename: Any = "") -> None:
        self.source = source
        self.pos = 0
        self.line = 1
        self.col = 1
        self.filename = filename

    def tokenize(self) -> Any:
        tokens = []
        while self.pos < len(self.source):
            matched = False
            for kind, pattern in self.TOKENS:
                m = re.match(pattern, self.source[self.pos :])
                if m:
                    val = m.group(0)
                    if kind not in ("WS", "COMMENT", "NEWLINE"):
                        tokens.append(Token(kind, val, self.line, self.col))
                    if kind == "NEWLINE":
                        self.line += 1
                        self.col = 1
                    else:
                        self.col += len(val)
                    self.pos += len(val)
                    matched = True
                    break
            if not matched:
                # 处理中文字符
                ch = self.source[self.pos]
                if re.match(r"[一-鿿　-〿＀-￯]", ch):
                    if not tokens or tokens[-1].kind != "CN_TEXT":
                        tokens.append(Token("CN_TEXT", ch, self.line, self.col))
                    else:
                        tokens[-1].value += ch
                    self.col += 1
                    self.pos += 1
                else:
                    tokens.append(Token("UNKNOWN", ch, self.line, self.col))
                    self.col += 1
                    self.pos += 1
        tokens.append(Token("EOF", "", self.line, self.col))
        return tokens


class Parser:
    VALID_ENTITY_PREFIXES = {"ORG", "ROL", "PRJ", "POL", "DAT"}
    VALID_FACT_PREFIXES = {"D-F", "P-F"}

    def __init__(self, filename: Any = "") -> None:
        self.tokens: list[Token] = []
        self.idx = 0
        self.filename = filename
        self.errors: list[ParseError] = []

    def peek(self) -> Any:
        return self.tokens[self.idx] if self.idx < len(self.tokens) else Token("EOF", "", 0, 0)

    def consume(self, kind: Any = None) -> Any:
        t = self.peek()
        if kind and t.kind != kind:
            self.errors.append(
                ParseError(
                    f"期望 {kind}，得到 {t.kind}('{t.value}')",
                    SourcePos(t.line, t.col, self.filename),
                    f"在{t.value}前插入 {kind}",
                )
            )
        self.idx += 1
        return t

    def skip_newlines(self) -> None:
        while self.peek().kind == "NEWLINE":
            self.idx += 1

    def parse(self, source: Any) -> Any:
        self.tokens = Lexer(source, self.filename).tokenize()
        self.idx = 0
        self.errors = []
        ast = AST()

        while self.peek().kind != "EOF":
            self.skip_newlines()
            t = self.peek()
            if t.kind == "EOF":
                break
            try:
                if t.kind == "ENTITY":
                    node = self._parse_entity()
                    if node:
                        ast.entities.append(node)
                elif t.kind == "FACT":
                    node = self._parse_fact()
                    if node:
                        ast.facts.append(node)
                elif t.kind == "INFERENCE":
                    node = self._parse_inference()
                    if node:
                        ast.inferences.append(node)
                elif t.kind == "PROTOCOL":
                    node = self._parse_protocol()
                    if node:
                        ast.protocols.append(node)
                elif t.kind == "RELATION":
                    node = self._parse_relation()
                    if node:
                        ast.relations.append(node)
                elif t.kind in ("CN_TEXT", "ID"):
                    # 跳过非声明行
                    self.idx += 1
                else:
                    self.errors.append(
                        ParseError(
                            f"意外的token: {t.kind}('{t.value}')",
                            SourcePos(t.line, t.col, self.filename),
                            "期望 entity/fact/inference/protocol/relation 声明",
                        )
                    )
                    self.idx += 1
            except Exception as e:
                self.errors.append(ParseError(f"解析错误: {e}", SourcePos(t.line, t.col, self.filename)))
                self.idx += 1

        return ast

    def _parse_properties(self) -> Any:
        props = {}
        self.consume("LBRACE")
        while self.peek().kind not in ("RBRACE", "EOF"):
            self.skip_newlines()
            if self.peek().kind == "RBRACE":
                break
            key = self.peek()
            if key.kind in ("ID", "CN_TEXT"):
                self.idx += 1
                self.consume("COLON")
                val = self.peek()
                if val.kind == "STRING":
                    props[key.value] = val.value.strip('"')
                    self.idx += 1
                elif val.kind == "NUMBER":
                    props[key.value] = float(val.value) if "." in val.value else int(val.value)
                    self.idx += 1
                elif val.kind == "LBRACKET":
                    items = self._parse_list()
                    props[key.value] = items
                else:
                    self.idx += 1
            else:
                self.idx += 1
        self.consume("RBRACE")
        return props

    def _parse_list(self) -> Any:
        items = []
        self.consume("LBRACKET")
        while self.peek().kind not in ("RBRACKET", "EOF"):
            t = self.peek()
            if t.kind in ("ID", "STRING"):
                items.append(t.value.strip('"'))
                self.idx += 1
                if self.peek().kind == "COMMA":
                    self.idx += 1
            elif t.kind == "COMMA":
                self.idx += 1
            else:
                self.idx += 1
        self.consume("RBRACKET")
        return items

    def _parse_common(self, keyword: Any, default_type: Any) -> Any:
        """通用声明解析：返回 (decl_id, decl_type, props, pos)"""
        pos = SourcePos(self.peek().line, self.peek().col, self.filename)
        self.consume(keyword.upper())
        id_tok = self.peek()
        if not (id_tok.kind in ("ID", "CN_TEXT") or id_tok.value):
            self.errors.append(ParseError(f"{keyword}声明缺少ID", pos))
            return None
        self.idx += 1
        decl_id = id_tok.value
        self.consume("COLON")
        type_tok = self.peek()
        decl_type = type_tok.value if type_tok.kind in ("ID", "CN_TEXT") else default_type
        self.idx += 1
        props = self._parse_properties() if self.peek().kind == "LBRACE" else {}
        return (decl_id, decl_type, props, pos)

    def _parse_entity(self) -> Any:
        r = self._parse_common("ENTITY", "Entity")
        if not r:
            return None
        decl_id, decl_type, props, pos = r
        return EntityDef(id=decl_id, entity_type=decl_type, properties=props, pos=pos)

    def _parse_fact(self) -> Any:
        r = self._parse_common("FACT", "DataPoint")
        if not r:
            return None
        decl_id, decl_type, props, pos = r
        return FactDef(id=decl_id, fact_type=decl_type, properties=props, pos=pos)

    def _parse_inference(self) -> Any:
        r = self._parse_common("INFERENCE", "Inference")
        if not r:
            return None
        decl_id, decl_type, props, pos = r
        df = props.pop("derives_from", [])
        if isinstance(df, str):
            df = [df]
        conclusion = str(props.pop("conclusion", ""))
        return InferenceDef(
            id=decl_id, inference_type=decl_type, derives_from=df, conclusion=conclusion, properties=props, pos=pos
        )

    def _parse_protocol(self) -> Any:
        r = self._parse_common("PROTOCOL", "Constraint")
        if not r:
            return None
        decl_id, decl_type, props, pos = r
        constraint = str(props.pop("constraint", ""))
        return ProtocolDef(id=decl_id, constraint_type=decl_type, constraint=constraint, properties=props, pos=pos)

    # 关系词汇表: 关系名 → (domain, range)
    RELATION_VOCAB = {
        "cooperates_with": ("DOMAIN", "DOMAIN"),
        "competes_with": ("DOMAIN", "DOMAIN"),
        "part_of": ("DOMAIN", "DOMAIN"),
        "contains": ("DOMAIN", "DOMAIN"),
        "employs": ("ORG", "ROL"),
        "belongs_to": ("DOMAIN", "DOMAIN"),
        "depends_on": ("DOMAIN", "DOMAIN"),
        "causes": ("FACT", "FACT"),
        "influences": ("DOMAIN", "DOMAIN"),
        "precedes": ("DOMAIN", "DOMAIN"),
        "authored_by": ("DOCUMENT", "DOMAIN"),
        "references": ("DOMAIN", "DOMAIN"),
        "derives_from": ("INFERENCE", "FACT"),
        "maps_to": ("DOMAIN", "DOMAIN"),
    }

    def _parse_relation(self) -> Any:
        pos = SourcePos(self.peek().line, self.peek().col, self.filename)
        self.consume("RELATION")
        # 支持的语法: relation ORG-A cooperates_with ORG-B
        # 关系词汇表验证
        subj = self._read_until_comma_or_id_end()
        rel = self.peek().value
        self.idx += 1
        obj = self._read_until_comma_or_id_end()
        if rel not in self.RELATION_VOCAB:
            sorted(self.RELATION_VOCAB.keys())
            # 不阻塞, 仅记录 — 允许用户自定义关系类型
            pass
        return RelationDef(subject=subj, relation_type=rel, object=obj, pos=pos)

    def _read_until_comma_or_id_end(self) -> Any:
        """读取一个完整的ID值, 遇到已知关系名则停止"""
        parts = []
        while self.peek().kind not in ("EOF", "NEWLINE", "COMMA", "LBRACE", "RBRACE"):
            t = self.peek()
            # 遇到已知关系名 → 停止, 这是下一个token
            if t.value in self.RELATION_VOCAB:
                break
            if t.kind in ("ID", "CN_TEXT", "NUMBER"):
                parts.append(t.value)
                self.idx += 1
            elif t.kind == "UNKNOWN" and t.value in ("-", "_"):
                parts.append(t.value)
                self.idx += 1
            else:
                break
        if not parts:
            t = self.peek()
            self.idx += 1
            return t.value
        return "".join(parts)
