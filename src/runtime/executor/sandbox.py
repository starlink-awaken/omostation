# ruff: noqa: S102
"""Sandbox executor for safe code execution."""

import ast
import signal
import time
from dataclasses import dataclass
from typing import Any

SAFE_BUILTINS = {
    "abs": abs, "all": all, "any": any, "bool": bool, "dict": dict,
    "enumerate": enumerate, "filter": filter, "float": float, "int": int,
    "len": len, "list": list, "map": map, "max": max, "min": min,
    "range": range, "round": round, "set": set, "sorted": sorted,
    "str": str, "sum": sum, "tuple": tuple, "zip": zip,
    "print": print, "True": True, "False": False, "None": None,
}

@dataclass
class SandboxResult:
    success: bool
    output: Any = None
    error: str = ""
    duration_ms: float = 0.0
    stdout: str = ""

class TimeoutError(Exception):
    """Raised on sandbox timeout."""
    pass

class Sandbox:
    """Safely execute Python code with resource limits."""

    @staticmethod
    def validate_code(code):
        """Check for forbidden patterns."""
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    return False, "No imports allowed"
            return True, ""
        except SyntaxError as exc:
            return False, str(exc)

    @staticmethod
    def execute(code, timeout_sec=5.0, max_output_len=10000):
        """Execute code with timeout and output limits."""
        valid, err = Sandbox.validate_code(code)
        if not valid:
            return SandboxResult(success=False, error=err)
        t0 = time.time()
        g = {"__builtins__": SAFE_BUILTINS}
        captured = []
        g["print"] = lambda *a: captured.append(" ".join(str(x) for x in a))

        def timeout_handler(signum, frame):
            raise TimeoutError()

        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(int(timeout_sec))
        try:
            exec(compile(code, "<sandbox>", "exec"), g, {})
            signal.alarm(0)
            stdout_text = chr(10).join(captured)
            if len(stdout_text) > max_output_len:
                stdout_text = stdout_text[:max_output_len] + "..."
            result_val = g.get("result", None)
            elapsed = (time.time() - t0) * 1000
            return SandboxResult(success=True, output=result_val, stdout=stdout_text, duration_ms=elapsed)
        except TimeoutError:
            elapsed = (time.time() - t0) * 1000
            return SandboxResult(success=False, error="Timeout", duration_ms=elapsed)
        except Exception as exc:
            elapsed = (time.time() - t0) * 1000
            return SandboxResult(success=False, error=str(exc), duration_ms=elapsed)
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
