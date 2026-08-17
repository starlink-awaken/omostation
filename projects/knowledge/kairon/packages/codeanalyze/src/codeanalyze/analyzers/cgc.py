"""CodeGraphContext (CGC) 分析器 — 语义属性图构建与查询

CodeGraphContext 基于 tree-sitter 和 SCIP 构建代码库的语义属性图。
支持 KuzuDB 等后端，提供符号级的关系查询（调用链、继承等）。
比 CRG (Code-Review-Graph) 更现代、支持更多语言。
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CgcResult:
    """CGC 操作结果"""

    success: bool = False
    data: dict | list | str | None = None
    error: str | None = None
    elapsed_ms: int = 0


def is_available() -> bool:
    """检查 codegraphcontext (cgc) 是否已安装。"""
    return shutil.which("cgc") is not None


def get_version() -> str | None:
    """获取 codegraphcontext 版本。"""
    if not is_available():
        return None
    try:
        r = subprocess.run(
            ["cgc", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return r.stdout.strip() or r.stderr.strip() or None
    except Exception:
        return None


def init_graph(path: str = ".") -> CgcResult:
    """初始化/更新 CGC 图数据库。"""
    root = Path(path).resolve()
    result = CgcResult()

    if not is_available():
        result.error = "codegraphcontext 未安装. 安装: pip install codegraphcontext"
        return result

    try:
        r = subprocess.run(
            ["cgc", "index", str(root)],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(root),
        )
        if r.returncode != 0:
            result.error = (r.stderr or r.stdout or "").strip()[:500]
            return result

        result.success = True
        result.data = r.stdout.strip()
    except subprocess.TimeoutExpired:
        result.error = "CGC 索引超时（300s）"
    except Exception as e:
        result.error = str(e)

    return result


def query(query_str: str, path: str = ".") -> CgcResult:
    """对 CGC 图数据库执行 Cypher/Kuzu 查询。"""
    root = Path(path).resolve()
    result = CgcResult()

    if not is_available():
        result.error = "codegraphcontext 未安装"
        return result

    try:
        r = subprocess.run(
            ["cgc", "query", query_str, "--json"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(root),
        )
        if r.returncode != 0:
            result.error = (r.stderr or r.stdout or "").strip()[:500]
            return result

        result.success = True
        try:
            result.data = json.loads(r.stdout.strip())
        except json.JSONDecodeError:
            result.data = r.stdout.strip()

    except subprocess.TimeoutExpired:
        result.error = "CGC 查询超时（60s）"
    except Exception as e:
        result.error = str(e)

    return result
