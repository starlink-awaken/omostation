"""ISC lexer and parser -- migrated from agentmesh engine/isc/parser.ts."""

from __future__ import annotations

from typing import Any

from .isc_errors import (
    ISCEmptyExpressionError,
    ISCInvalidCharacterError,
    ISCUnexpectedTokenError,
    ISCUnterminatedStringError,
)

# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------

PRECEDENCE: dict[str, int] = {
    "||": 1, "&&": 2,
    "==": 3, "!=": 3, ">": 3, ">=": 3, "<": 3, "<=": 3,
    "!": 4, ".": 5, "[": 5,
}


def _make_token(ttype: str, value: Any, pos: int, line: int, col: int, length: int = 0) -> dict:
    return {"type": ttype, "value": value, "position": pos, "line": line, "column": col, "length": length}


# ---------------------------------------------------------------------------
# Lexer
# ---------------------------------------------------------------------------

class ISCLexer:
    """Tokenizes an ISC expression string into a token stream."""

    def __init__(self) -> None:
        self._input = ""
        self._pos = 0
        self._line = 1
        self._col = 1

    def tokenize(self, source: str) -> list[dict]:
        self._input = source
        self._pos = 0
        self._line = 1
        self._col = 1
        tokens: list[dict] = []
        while not self._at_end():
            tok = self._scan()
            if tok["type"] != "UNKNOWN":
                tokens.append(tok)
        tokens.append(_make_token("EOF", None, self._pos, self._line, self._col))
        return tokens

    def _scan(self) -> dict:
        ch = self._advance()
        start_pos = self._pos - 1
        start_line, start_col = self._line, self._col - 1

        if ch.isspace():
            return self._scan()

        # Single-char tokens
        mapping: dict[str, str] = {
            "(": "LPAREN", ")": "RPAREN",
            "[": "LBRACKET", "]": "RBRACKET",
            ".": "DOT", "%": "PERCENT",
        }
        if ch in mapping:
            return _make_token(mapping[ch], ch, start_pos, start_line, start_col, 1)

        if ch == "!":
            if self._match("="):
                return _make_token("NEQ", "!=", start_pos, start_line, start_col, 2)
            return _make_token("NOT", "!", start_pos, start_line, start_col, 1)
        if ch == "=":
            if self._match("="):
                return _make_token("EQ", "==", start_pos, start_line, start_col, 2)
            raise ISCInvalidCharacterError("=", start_pos)
        if ch == "<":
            if self._match("="):
                return _make_token("LTE", "<=", start_pos, start_line, start_col, 2)
            return _make_token("LT", "<", start_pos, start_line, start_col, 1)
        if ch == ">":
            if self._match("="):
                return _make_token("GTE", ">=", start_pos, start_line, start_col, 2)
            return _make_token("GT", ">", start_pos, start_line, start_col, 1)
        if ch == "&":
            if self._match("&"):
                return _make_token("AND", "&&", start_pos, start_line, start_col, 2)
            raise ISCInvalidCharacterError("&", start_pos)
        if ch == "|":
            if self._match("|"):
                return _make_token("OR", "||", start_pos, start_line, start_col, 2)
            raise ISCInvalidCharacterError("|", start_pos)
        if ch in ('"', "'"):
            return self._scan_string(ch, start_pos, start_line, start_col)
        if ch.isdigit():
            return self._scan_number(ch, start_pos, start_line, start_col)
        if ch.isalpha() or ch == "_":
            return self._scan_ident(ch, start_pos, start_line, start_col)

        raise ISCInvalidCharacterError(ch, start_pos)

    def _scan_string(self, quote: str, start_pos: int, start_line: int, start_col: int) -> dict:
        value = ""
        while not self._at_end() and self._peek() != quote:
            ch = self._advance()
            if ch == "\\" and not self._at_end():
                nxt = self._advance()
                escape_map = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", quote: quote}
                value += escape_map.get(nxt, nxt)
            else:
                value += ch
        if self._at_end():
            raise ISCUnterminatedStringError(start_pos, quote)
        self._advance()
        return _make_token("STRING", value, start_pos, start_line, start_col)

    def _scan_number(self, first: str, start_pos: int, start_line: int, start_col: int) -> dict:
        value = first
        has_dot = False
        while not self._at_end() and (self._peek().isdigit() or (self._peek() == "." and not has_dot)):
            if self._peek() == ".":
                has_dot = True
            elif has_dot:
                break
            value += self._advance()
        num = float(value) if has_dot else int(value)
        return _make_token("NUMBER", num, start_pos, start_line, start_col, len(value))

    def _scan_ident(self, first: str, start_pos: int, start_line: int, start_col: int) -> dict:
        value = first
        while not self._at_end() and (self._peek().isalnum() or self._peek() in ("_", "-")):
            value += self._advance()
        up = value.upper()
        kw_map = {"AND": "AND", "OR": "OR", "NOT": "NOT", "TRUE": "BOOLEAN", "FALSE": "BOOLEAN"}
        kw_val = {"AND": "&&", "OR": "||", "NOT": "!", "TRUE": True, "FALSE": False}
        if up in kw_map:
            return _make_token(kw_map[up], kw_val[up], start_pos, start_line, start_col, len(value))
        return _make_token("IDENTIFIER", value, start_pos, start_line, start_col, len(value))

    def _advance(self) -> str:
        ch = self._input[self._pos]
        self._pos += 1
        if ch == "\n":
            self._line += 1
            self._col = 1
        else:
            self._col += 1
        return ch

    def _peek(self) -> str:
        return self._input[self._pos] if self._pos < len(self._input) else ""

    def _match(self, expected: str) -> bool:
        if self._at_end() or self._peek() != expected:
            return False
        self._advance()
        return True

    def _at_end(self) -> bool:
        return self._pos >= len(self._input)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class ISCParser:
    """Parses ISC expression tokens into an AST."""

    def __init__(self) -> None:
        self._lexer = ISCLexer()
        self._tokens: list[dict] = []
        self._current = 0
        self._source = ""

    def parse(self, source: str) -> dict:
        self._source = source
        self._tokens = self._lexer.tokenize(source)
        self._current = 0
        if len(self._tokens) <= 1:
            raise ISCEmptyExpressionError()
        expr = self._parse_or()
        if not self._at_end() and self._peek()["type"] != "EOF":
            t = self._peek()
            raise ISCUnexpectedTokenError("end of expression", str(t["value"]), t["position"])
        return expr

    def _parse_or(self) -> dict:
        left = self._parse_and()
        while self._match("OR"):
            right = self._parse_and()
            left = {"type": "Logical", "operator": "||", "left": left, "right": right}
        return left

    def _parse_and(self) -> dict:
        left = self._parse_comparison()
        while self._match("AND"):
            right = self._parse_comparison()
            left = {"type": "Logical", "operator": "&&", "left": left, "right": right}
        return left

    def _parse_comparison(self) -> dict:
        left = self._parse_unary()
        while self._match("EQ", "NEQ", "GT", "GTE", "LT", "LTE"):
            op_map = {
                "EQ": "==", "NEQ": "!=", "GT": ">",
                "GTE": ">=", "LT": "<", "LTE": "<=",
            }
            op = op_map[self._prev()["type"]]
            right = self._parse_unary()
            left = {"type": "Comparison", "operator": op, "left": left, "right": right}
        return left

    def _parse_unary(self) -> dict:
        if self._match("NOT"):
            arg = self._parse_unary()
            return {"type": "Unary", "operator": "!", "argument": arg}
        return self._parse_primary()

    def _parse_primary(self) -> dict:
        if self._match("LPAREN"):
            expr = self._parse_or()
            self._consume("RPAREN", "Expected ')' after expression")
            return self._parse_post(expr)
        if self._match("BOOLEAN"):
            lit = {"type": "Literal", "value": self._prev()["value"]}
            return self._parse_post(lit)
        if self._match("IDENTIFIER"):
            ident = {"type": "Identifier", "name": self._prev()["value"]}
            if self._check("PERCENT"):
                self._advance()
            return self._parse_post(ident)
        if self._check("NUMBER"):
            tok = self._consume("NUMBER", "Expected number")
            val = tok["value"]
            if self._match("PERCENT"):
                val = val / 100.0
            lit = {"type": "Literal", "value": val}
            return self._parse_post(lit)
        if self._match("STRING"):
            return self._parse_post({"type": "Literal", "value": self._prev()["value"]})
        t = self._peek()
        raise ISCUnexpectedTokenError("expression", str(t["value"]), t["position"])

    def _parse_post(self, expr: dict) -> dict:
        while True:
            if self._match("DOT"):
                if not self._match("IDENTIFIER"):
                    t = self._peek()
                    raise ISCUnexpectedTokenError("property name", str(t["value"]), t["position"])
                prop = self._prev()["value"]
                expr = self._parse_post({"type": "Member", "object": expr, "property": prop, "computed": False})
            elif self._match("LBRACKET"):
                pt = self._consume("STRING", "Expected string property name")
                self._consume("RBRACKET", "Expected ']' after property name")
                expr = self._parse_post({"type": "Member", "object": expr, "property": pt["value"], "computed": True})
            else:
                break
        return expr

    def _check(self, *types: str) -> bool:
        return not self._at_end() and self._peek()["type"] in types

    def _match(self, *types: str) -> bool:
        for t in types:
            if self._check(t):
                self._advance()
                return True
        return False

    def _consume(self, ttype: str, msg: str) -> dict:
        if self._check(ttype):
            return self._advance()
        t = self._peek()
        raise ISCUnexpectedTokenError(ttype, str(t["value"]), t["position"])

    def _peek(self) -> dict:
        return self._tokens[self._current]

    def _prev(self) -> dict:
        return self._tokens[self._current - 1]

    def _advance(self) -> dict:
        if not self._at_end():
            self._current += 1
        return self._prev()

    def _at_end(self) -> bool:
        return self._peek()["type"] == "EOF"
