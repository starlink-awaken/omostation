from __future__ import annotations

# ruff: noqa: RUF002
import ast
import io
from collections.abc import Callable
from types import ModuleType
from typing import Any, TextIO

# Safe builtins for code execution
# Excludes dangerous functions: __import__, open, eval, exec, __loader__, __spec__
SAFE_BUILTINS = {
    # Built-in types and functions
    "abs": abs,
    "all": all,
    "any": any,
    "bin": bin,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "filter": filter,
    "float": float,
    "hex": hex,
    "int": int,
    "isinstance": isinstance,
    "issubclass": issubclass,
    "iter": iter,
    "len": len,
    "list": list,
    "map": map,
    "max": max,
    "min": min,
    "next": next,
    "oct": oct,
    "ord": ord,
    "pow": pow,
    "print": print,
    "range": range,
    "reversed": reversed,
    "round": round,
    "set": set,
    "slice": slice,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
    # Built-in exceptions (needed for normal exception handling)
    "Exception": Exception,
    "ValueError": ValueError,
    "RuntimeError": RuntimeError,
    "TypeError": TypeError,
    "AttributeError": AttributeError,
    "KeyError": KeyError,
    "IndexError": IndexError,
    "NameError": NameError,
    "AssertionError": AssertionError,
    "ImportError": ImportError,
    "OSError": OSError,
    "IOError": IOError,
    "NotImplementedError": NotImplementedError,
    "StopIteration": StopIteration,
}
DANGEROUS_EXECUTION_BUILTINS = frozenset({"__import__", "compile", "eval", "exec"})

# Whitelisted modules for safe imports
SAFE_MODULES = {
    "math",
    "json",
    "datetime",
    "re",
    "collections",
    "itertools",
}


def safe_import(
    name: str,
    globals: dict[str, object] | None = None,
    locals: dict[str, object] | None = None,
    fromlist: tuple[str, ...] = (),
    level: int = 0,
) -> ModuleType:
    """受限的 __import__，仅允许白名单中的模块。"""
    if name in SAFE_MODULES:
        import importlib

        return importlib.import_module(name)
    msg = f"Import of module '{name}' is not allowed in sandboxed code"
    raise ImportError(msg)


_BLOCKED_AST_MESSAGES: dict[type[ast.AST], str] = {
    ast.Attribute: "Attribute access is not allowed in sandboxed code",
    ast.FunctionDef: "Function definitions are not allowed in sandboxed code",
    ast.AsyncFunctionDef: "Function definitions are not allowed in sandboxed code",
    ast.ClassDef: "Class definitions are not allowed in sandboxed code",
    ast.Lambda: "Lambda expressions are not allowed in sandboxed code",
    ast.With: "Context managers are not allowed in sandboxed code",
    ast.AsyncWith: "Context managers are not allowed in sandboxed code",
    ast.Try: "Exception handling blocks are not allowed in sandboxed code",
    ast.For: "Loops are not allowed in sandboxed code",
    ast.AsyncFor: "Loops are not allowed in sandboxed code",
    ast.While: "Loops are not allowed in sandboxed code",
    ast.ListComp: "Comprehensions are not allowed in sandboxed code",
    ast.SetComp: "Comprehensions are not allowed in sandboxed code",
    ast.DictComp: "Comprehensions are not allowed in sandboxed code",
    ast.GeneratorExp: "Comprehensions are not allowed in sandboxed code",
    ast.Await: "Async operations are not allowed in sandboxed code",
    ast.Yield: "Generator operations are not allowed in sandboxed code",
    ast.YieldFrom: "Generator operations are not allowed in sandboxed code",
    ast.Delete: "Deletion is not allowed in sandboxed code",
    ast.Global: "Global declarations are not allowed in sandboxed code",
    ast.Nonlocal: "Nonlocal declarations are not allowed in sandboxed code",
}


def _validate_assignment_target(target: ast.expr) -> None:
    if isinstance(target, ast.Name):
        if target.id.startswith("__"):
            msg = "Dunder names are not allowed in sandboxed code"
            raise ValueError(msg)
        return
    if isinstance(target, (ast.Tuple, ast.List)):
        for element in target.elts:
            _validate_assignment_target(element)
        return

    msg = "Only name-based assignments are allowed in sandboxed code"
    raise ValueError(msg)


def _validate_exec_ast(code: str) -> None:
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as exc:
        raise ValueError(str(exc)) from exc

    for node in ast.walk(tree):
        for blocked_type, message in _BLOCKED_AST_MESSAGES.items():
            if isinstance(node, blocked_type):
                raise ValueError(message)

        if isinstance(node, ast.Name) and node.id.startswith("__"):
            msg = "Dunder names are not allowed in sandboxed code"
            raise ValueError(msg)

        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                msg = "Attribute access is not allowed in sandboxed code"
                raise ValueError(msg)
            if not isinstance(node.func, ast.Name):
                msg = "Only direct builtin calls are allowed in sandboxed code"
                raise ValueError(msg)
            if node.func.id in DANGEROUS_EXECUTION_BUILTINS:
                msg = f"Dynamic execution builtin '{node.func.id}' is not allowed in sandboxed code"
                raise ValueError(msg)
            if node.func.id not in SAFE_BUILTINS:
                msg = f"Call to '{node.func.id}' is not allowed in sandboxed code"
                raise ValueError(msg)

        if isinstance(node, ast.Assign):
            for target in node.targets:
                _validate_assignment_target(target)
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
            _validate_assignment_target(node.target)


def _build_safe_print(stdout_capture: io.StringIO | None) -> Callable[..., None]:
    if stdout_capture is None:
        return print

    def _safe_print(
        *values: Any,
        sep: str = " ",
        end: str = "\n",
        file: TextIO | None = None,
        flush: bool = False,
    ) -> None:
        if file is not None:
            msg = "Custom print file targets are not allowed in sandboxed code"
            raise ValueError(msg)
        stdout_capture.write(sep.join(str(value) for value in values))
        stdout_capture.write(end)
        if flush:
            stdout_capture.flush()

    return _safe_print


def get_safe_execution_globals(
    print_fn: Callable[..., None] | None = None,
) -> dict[str, object]:
    _SAFE_BUILTINS_EXEC = dict(SAFE_BUILTINS)  # noqa: N806
    _SAFE_BUILTINS_EXEC["print"] = print_fn if print_fn else print
    _SAFE_BUILTINS_EXEC["__import__"] = safe_import
    return {
        "__builtins__": _SAFE_BUILTINS_EXEC,
        "__name__": "__sandbox__",
    }


def safe_exec_sandbox(code: str, stdout_capture: io.StringIO | None = None) -> dict[str, object]:
    """执行沙箱中的代码并返回局部变量。

    Args:
        code: 要执行的 Python 代码字符串。
        stdout_capture: 可选的 StringIO 用于捕获 print 输出。

    Returns:
        执行后的局部变量字典。
    """
    _validate_exec_ast(code)
    safe_print = _build_safe_print(stdout_capture)
    exec_globals = get_safe_execution_globals(print_fn=safe_print)
    exec_locals: dict[str, object] = {}
    exec(code, exec_globals, exec_locals)  # noqa: S102
    return exec_locals
