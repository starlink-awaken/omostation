"""DSL Lexer - tokenizes DSL source code into tokens."""

from __future__ import annotations

from dataclasses import dataclass, field

from runtime.executor.dsl_types import SourceLocation

KEYWORDS: dict[str, str] = {
    # Structure
    "agent": "KEYWORD",
    "input": "KEYWORD",
    "output": "KEYWORD",
    "tools": "KEYWORD",
    "capability": "KEYWORD",
    "body": "KEYWORD",
    "governance": "KEYWORD",
    "metadata": "KEYWORD",
    # Statements
    "step": "KEYWORD",
    "conditional_step": "KEYWORD",
    "condition": "KEYWORD",
    "loop": "KEYWORD",
    "parallel": "KEYWORD",
    "try_catch": "KEYWORD",
    # Control flow
    "test": "KEYWORD",
    "consequent": "KEYWORD",
    "alternate": "KEYWORD",
    "loop_type": "KEYWORD",
    "variable": "KEYWORD",
    "collection": "KEYWORD",
    "branches": "KEYWORD",
    "max_concurrency": "KEYWORD",
    "try_block": "KEYWORD",
    "catch_variable": "KEYWORD",
    "catch_block": "KEYWORD",
    "finally_block": "KEYWORD",
    # Call
    "call": "KEYWORD",
    "inputs": "KEYWORD",
    "outputs": "KEYWORD",
    "retry": "KEYWORD",
    # Properties
    "description": "KEYWORD",
    "type": "KEYWORD",
    "layer": "KEYWORD",
    "domain": "KEYWORD",
    "data_type": "KEYWORD",
    "required": "KEYWORD",
    "default": "KEYWORD",
    "validation": "KEYWORD",
    "name": "KEYWORD",
    "level": "KEYWORD",
    "alias": "KEYWORD",
    # Governance
    "first_principles_check": "KEYWORD",
    "red_team_threshold": "KEYWORD",
    "quality_gate_enabled": "KEYWORD",
    "max_retries": "KEYWORD",
    "token_budget": "KEYWORD",
    # Metadata
    "author": "KEYWORD",
    "version": "KEYWORD",
    "license": "KEYWORD",
    "tags": "KEYWORD",
    # Literals
    "true": "BOOLEAN",
    "false": "BOOLEAN",
    "null": "KEYWORD",
    # Data types
    "string": "KEYWORD",
    "number": "KEYWORD",
    "boolean": "KEYWORD",
    "any": "KEYWORD",
    "void": "KEYWORD",
    "object": "KEYWORD",
    "array": "KEYWORD",
    "union": "KEYWORD",
    "literal": "KEYWORD",
    "for": "KEYWORD",
    "while": "KEYWORD",
    "for_each": "KEYWORD",
    "structural": "KEYWORD",
    "worker": "KEYWORD",
    "L1": "KEYWORD",
    "L2": "KEYWORD",
    "L3": "KEYWORD",
    "L4": "KEYWORD",
    "very_low": "KEYWORD",
    "low": "KEYWORD",
    "medium": "KEYWORD",
    "high": "KEYWORD",
    "critical": "KEYWORD",
    "basic": "KEYWORD",
    "intermediate": "KEYWORD",
    "advanced": "KEYWORD",
    "expert": "KEYWORD",
}

TOKEN_TYPES = set(KEYWORDS.values()) | {
    "IDENTIFIER", "STRING", "NUMBER", "BOOLEAN",
    "LBRACE", "RBRACE", "LBRACKET", "RBRACKET",
    "LPAREN", "RPAREN", "COLON", "SEMICOLON",
    "COMMA", "DOT", "ARROW", "PIPE",
    "LT", "GT", "LTE", "GTE",
    "EQ", "NEQ", "AND", "OR", "NOT",
    "PLUS", "MINUS", "STAR", "SLASH", "PERCENT",
    "AT", "HASH", "QUERY", "EOF",
}


@dataclass
class Token:
    type: str = "EOF"
    value: str = ""
    loc: SourceLocation = field(default_factory=SourceLocation)


class Lexer:
    def __init__(self, source: str = "", filename: str = "<unknown>") -> None:
        self.source = source
        self.filename = filename
        self._pos = 0
        self._line = 1
        self._col = 1

    def reset(self) -> None:
        self._pos = 0
        self._line = 1
        self._col = 1

    def set_source(self, source: str, filename: str = "<unknown>") -> None:
        self.source = source
        self.filename = filename
        self.reset()

    @property
    def _current(self) -> str:
        return self.source[self._pos] if self._pos < len(self.source) else "\0"

    def _peek(self, offset: int = 1) -> str:
        idx = self._pos + offset
        return self.source[idx] if idx < len(self.source) else "\0"

    def _advance(self) -> str:
        ch = self._current
        self._pos += 1
        if ch == "\n":
            self._line += 1
            self._col = 1
        else:
            self._col += 1
        return ch

    def _skip_whitespace(self) -> None:
        while self._current != "\0" and self._current in " \t\n\r":
            self._advance()

    def _skip_comment(self) -> None:
        if self._current == "#":
            while self._current not in ("\n", "\0"):
                self._advance()

    def _read_string(self) -> Token:
        start_line = self._line
        start_col = self._col
        quote = self._advance()
        value = ""
        while self._current != quote and self._current != "\0":
            if self._current == "\\":
                self._advance()
                value += self._advance()
            else:
                value += self._advance()
        if self._current == "\0":
            raise ValueError(f"Unterminated string at line {start_line}")
        self._advance()  # skip closing quote
        return Token(
            type="STRING", value=value,
            loc=SourceLocation(file=self.filename, line=start_line, column=start_col),
        )

    def _read_number(self) -> Token:
        start_line = self._line
        start_col = self._col
        value = ""
        while self._current in "0123456789.":
            value += self._advance()
        return Token(
            type="NUMBER", value=value,
            loc=SourceLocation(file=self.filename, line=start_line, column=start_col),
        )

    def _read_identifier(self) -> Token:
        start_line = self._line
        start_col = self._col
        value = ""
        while self._current.isalnum() or self._current in ("_", "-"):
            value += self._advance()
        token_type = KEYWORDS.get(value, "IDENTIFIER")
        return Token(
            type=token_type, value=value,
            loc=SourceLocation(file=self.filename, line=start_line, column=start_col),
        )

    def tokenize(self) -> list[Token]:
        tokens: list[Token] = []
        while self._pos < len(self.source):
            self._skip_whitespace()
            if self._current == "#":
                self._skip_comment()
                continue
            if self._current == "\0":
                break
            ch = self._current
            start_line = self._line
            start_col = self._col

            if ch in ('"', "'"):
                tokens.append(self._read_string())
                continue
            if ch in "0123456789":
                tokens.append(self._read_number())
                continue
            if ch.isalpha() or ch == "_":
                tokens.append(self._read_identifier())
                continue

            # Operators and delimiters
            self._advance()

            if ch == "{" and self._current == "|":
                self._advance()
                tok_type = "PIPE"
                tok_val = "{|"
            elif ch == "|" and self._current == "}":
                self._advance()
                tok_type = "PIPE"
                tok_val = "|}"
            elif ch == "-" and self._current == ">":
                self._advance()
                tok_type = "ARROW"
                tok_val = "->"
            elif ch == "<" and self._current == "=":
                self._advance()
                tok_type = "LTE"
                tok_val = "<="
            elif ch == ">" and self._current == "=":
                self._advance()
                tok_type = "GTE"
                tok_val = ">="
            elif ch == "=" and self._current == "=":
                self._advance()
                tok_type = "EQ"
                tok_val = "=="
            elif ch == "!" and self._current == "=":
                self._advance()
                tok_type = "NEQ"
                tok_val = "!="
            elif ch == "&" and self._current == "&":
                self._advance()
                tok_type = "AND"
                tok_val = "&&"
            elif ch == "|" and self._current == "|":
                self._advance()
                tok_type = "OR"
                tok_val = "||"
            else:
                single_map: dict[str, str] = {
                    "{": "LBRACE", "}": "RBRACE",
                    "[": "LBRACKET", "]": "RBRACKET",
                    "(": "LPAREN", ")": "RPAREN",
                    ":": "COLON", ";": "SEMICOLON",
                    ",": "COMMA", ".": "DOT",
                    "|": "PIPE", "<": "LT", ">": "GT",
                    "!": "NOT", "+": "PLUS", "-": "MINUS",
                    "*": "STAR", "/": "SLASH", "%": "PERCENT",
                    "@": "AT", "?": "QUERY",
                }
                tok_type = single_map.get(ch, "EOF")
                tok_val = ch

            tokens.append(
                Token(
                    type=tok_type, value=tok_val,
                    loc=SourceLocation(file=self.filename, line=start_line, column=start_col),
                )
            )

        tokens.append(
            Token(
                type="EOF", value="",
                loc=SourceLocation(file=self.filename, line=self._line, column=self._col),
            )
        )
        return tokens
