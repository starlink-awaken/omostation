"""cockpit.chain.context — 模板渲染与条件求值 (轻量独立实现, 语义参考 journey-runner).

模板语法: {{params.x}} {{env.X}} {{steps.<n>.stdout|stderr|exit_code|json.<path>}} {{prev.output}}
json.<path> 仅当该步 stdout 可 json.loads 时可寻址, 否则抛 ChainTemplateError.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any


class ChainTemplateError(Exception):
    """模板渲染失败 (引用缺失 / json 不可寻址)."""


class ChainConditionError(Exception):
    """条件表达式非法."""


_TEMPLATE_RE = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")


def _resolve_steps(steps: dict[str, Any], ref: str) -> str:
    parts = ref.split(".")
    if len(parts) < 3:
        raise ChainTemplateError(f"steps 引用须含字段名: steps.{ref}")
    name, attr = parts[1], parts[2]
    if name not in steps:
        raise ChainTemplateError(f"引用未执行的步骤: steps.{name}")
    step = steps[name]
    if attr == "exit_code":
        return str(step.get("exit_code", -1))
    if attr in ("stdout", "stderr"):
        value = str(step.get(attr, "")).strip()
        return value.replace("\n", "\\n")
    if attr == "json":
        stdout = step.get("stdout", "")
        try:
            data = json.loads(stdout)
        except (json.JSONDecodeError, TypeError) as e:
            raise ChainTemplateError(f"steps.{name}.stdout 不是合法 JSON: {e}") from e
        path = parts[3:]
        for p in path:
            m = re.fullmatch(r"(\w+)\[(\d+)\]", p)
            if m and isinstance(data, dict):
                key, idx = m.group(1), int(m.group(2))
                if key not in data or not isinstance(data[key], list) or idx >= len(data[key]):
                    raise ChainTemplateError(f"steps.{name}.json 路径不存在: {'.'.join(path)}")
                data = data[key][idx]
            elif isinstance(data, dict):
                if p not in data:
                    raise ChainTemplateError(f"steps.{name}.json 路径不存在: {'.'.join(path)}")
                data = data[p]
            elif isinstance(data, list):
                try:
                    data = data[int(p)]
                except (ValueError, IndexError) as e:
                    raise ChainTemplateError(f"steps.{name}.json 索引非法: {p}") from e
            else:
                raise ChainTemplateError(f"steps.{name}.json 路径中途不可再寻址: {p}")
        if isinstance(data, (dict, list)):
            return json.dumps(data, ensure_ascii=False)
        return str(data)
    raise ChainTemplateError(f"steps.{name} 不支持的字段: {attr}")


def render_template(text: str, ctx: dict[str, Any]) -> str:
    """把 {{...}} 占位符展开为字符串. 未执行的步骤引用抛 ChainTemplateError."""

    def _sub(m: re.Match) -> str:
        ref = m.group(1).strip()
        if ref.startswith("params."):
            key = ref[len("params."):]
            params = ctx.get("params", {})
            if key not in params:
                raise ChainTemplateError(f"params.{key} 未提供")
            return str(params[key])
        if ref.startswith("env."):
            key = ref[len("env."):]
            val = os.environ.get(key)
            if val is None:
                raise ChainTemplateError(f"env.{key} 未设置")
            return val
        if ref.startswith("steps."):
            return _resolve_steps(ctx.get("steps", {}), ref)
        if ref == "prev.output":
            prev = ctx.get("prev")
            if not prev:
                raise ChainTemplateError("prev.output: 无前序步骤输出")
            return str(prev.get("stdout", "")).strip().replace("\n", "\\n")
        raise ChainTemplateError(f"未知模板引用: {ref}")

    return _TEMPLATE_RE.sub(_sub, text)


# ── 条件求值: ==/!=/contains/and/or/not/数字比较 ──────────────────────────────

_TOKEN_RE = re.compile(
    r"""\s*(?:
        (==|!=|>=|<=|>|<)
      | (contains)
      | (and|or|not)
      | ("[^"]*"|'[^']*')
      | (-?\d+(?:\.\d+)?)
      | ([A-Za-z_][\w.\[\]]*)
      | (\()
      | (\))
    )""",
    re.VERBOSE,
)


def _tokenize(expr: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    pos = 0
    while pos < len(expr):
        if expr[pos].isspace():
            pos += 1
            continue
        m = _TOKEN_RE.match(expr, pos)
        if not m or m.end() == pos:
            raise ChainConditionError(f"非法 token 位置 {pos}: '{expr[pos:]}'")
        op, contains, kw, string, number, ident, lp, rp = m.groups()
        if op:
            tokens.append(("OP", op))
        elif contains:
            tokens.append(("OP", "contains"))
        elif kw:
            tokens.append(("KW", kw))
        elif string is not None:
            tokens.append(("STR", string[1:-1]))
        elif number:
            tokens.append(("NUM", number))
        elif ident:
            tokens.append(("IDENT", ident))
        elif lp:
            tokens.append(("LP", "("))
        elif rp:
            tokens.append(("RP", ")"))
        pos = m.end()
    return tokens


class _CondParser:
    """递归下降: or_expr → and_expr → not_expr → atom → comparison."""

    def __init__(self, tokens: list[tuple[str, str]], ctx: dict[str, Any]):
        self.tokens = tokens
        self.pos = 0
        self.ctx = ctx

    def peek(self) -> tuple[str, str] | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def next(self) -> tuple[str, str]:
        tok = self.peek()
        if tok is None:
            raise ChainConditionError("表达式意外结束")
        self.pos += 1
        return tok

    def parse(self) -> bool:
        if not self.tokens:
            raise ChainConditionError("空表达式")
        val = self.or_expr()
        if self.pos != len(self.tokens):
            raise ChainConditionError(f"多余 token: {self.tokens[self.pos]}")
        return val

    def or_expr(self) -> bool:
        left = self.and_expr()
        while (t := self.peek()) and t == ("KW", "or"):
            self.next()
            right = self.and_expr()
            left = left or right
        return left

    def and_expr(self) -> bool:
        left = self.not_expr()
        while (t := self.peek()) and t == ("KW", "and"):
            self.next()
            right = self.not_expr()
            left = left and right
        return left

    def not_expr(self) -> bool:
        if (t := self.peek()) and t == ("KW", "not"):
            self.next()
            return not self.not_expr()
        return self.atom()

    def _resolve_ident(self, name: str) -> Any:
        parts = name.split(".")
        node: Any = self.ctx
        for p in parts:
            key: Any = p
            m = re.fullmatch(r"(\w+)\[(\d+)\]", p)
            if m:
                key, idx = m.group(1), int(m.group(2))
                if not isinstance(node, dict) or key not in node:
                    raise ChainConditionError(f"引用无法解析: {name}")
                node = node[key]
                if not isinstance(node, list) or idx >= len(node):
                    raise ChainConditionError(f"索引越界: {name}")
                node = node[idx]
                continue
            if isinstance(node, dict) and key in node:
                node = node[key]
            else:
                raise ChainConditionError(f"引用无法解析: {name}")
        return node

    def atom(self) -> Any:
        tok = self.next()
        kind, value = tok
        if kind == "LP":
            val = self.or_expr()
            closing = self.next()
            if closing != ("RP", ")"):
                raise ChainConditionError("缺右括号")
            return val
        if kind in ("STR", "NUM"):
            return value
        if kind == "IDENT" and value in ("true", "false"):
            return value == "true"
        if kind == "IDENT" and value == "null":
            return None
        if kind == "IDENT":
            resolved = self._resolve_ident(value)
            # 后续是 comparison 则解析右值
            if (t := self.peek()) and t[0] == "OP":
                op = self.next()[1]
                right = self.atom()
                return _compare(op, resolved, right)
            return resolved
        raise ChainConditionError(f"非法 token: {tok}")


def _to_num(v: Any) -> float:
    try:
        return float(str(v).strip())
    except ValueError as e:
        raise ChainConditionError(f"数字比较需数字: {v!r}") from e


def _compare(op: str, left: Any, right: Any) -> bool:
    if op == "contains":
        return str(right) in str(left)
    if op in (">", "<", ">=", "<="):
        return _numeric_compare(op, _to_num(left), _to_num(right))
    if op == "==":
        return _loose_eq(left, right)
    if op == "!=":
        return not _loose_eq(left, right)
    raise ChainConditionError(f"未知操作符: {op}")


def _numeric_compare(op: str, a: float, b: float) -> bool:
    return {"<": a < b, ">": a > b, "<=": a <= b, ">=": a >= b}[op]


def _loose_eq(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return str(left).lower() == str(right).lower()
    try:
        return float(str(left).strip()) == float(str(right).strip())
    except ValueError:
        return str(left) == str(right)


def evaluate_condition(expr: str, ctx: dict[str, Any]) -> bool:
    """条件求值. 非法表达式抛 ChainConditionError."""
    if not expr.strip():
        return True
    tokens = _tokenize(expr)
    return bool(_CondParser(tokens, ctx).parse())
