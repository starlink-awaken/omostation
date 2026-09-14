"""code-review-graph 适配器 — Tree-sitter 持久化知识图谱"""

from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class CrgStats:
    """code-review-graph 图谱统计"""

    total_files: int = 0
    total_nodes: int = 0
    total_edges: int = 0
    source_lines: int = 0
    file_coverage: float = 0.0
    db_size_kb: float = 0.0
    error: str | None = None


_CRG_CMD: list[str] | None = None


def _get_crg_cmd() -> list[str]:
    """获取 code-review-graph 命令（优先用 CLI，降级用 python -m）。"""
    global _CRG_CMD
    if _CRG_CMD is not None:
        return _CRG_CMD
    if shutil.which("code-review-graph"):
        _CRG_CMD = ["code-review-graph"]
    else:
        import sys

        _CRG_CMD = [sys.executable, "-m", "code_review_graph"]
    return _CRG_CMD


def is_available() -> bool:
    """检查 code-review-graph 是否已安装。"""
    if shutil.which("code-review-graph"):
        return True
    try:
        r = subprocess.run(
            [*_get_crg_cmd(), "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return r.returncode == 0
    except Exception as e:
        logger.warning("CRG not available: %s", e)
        return False


def get_version() -> str | None:
    """获取版本。"""
    try:
        r = subprocess.run(
            [*_get_crg_cmd(), "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return (r.stdout.strip() or r.stderr.strip()) or None
    except Exception as e:
        logger.warning("CRG version check failed: %s", e)
        return None


def build(path: str = ".", force: bool = False) -> CrgStats:
    """构建/重建 Tree-sitter 知识图谱。

    Args:
        path: 项目根目录路径
        force: 是否强制重建
    """
    stats = CrgStats()

    if not is_available():
        stats.error = "code-review-graph 未安装"
        return stats

    cmd = [*_get_crg_cmd(), "build"]

    try:
        args = [*cmd, "--repo", path]
        if force:
            args.append("--force")
        r = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=300,  # 5 min
        )
        if r.returncode != 0:
            stats.error = r.stderr.strip()[:500]
            return stats

        _parse_status(stats, r.stdout)
    except subprocess.TimeoutExpired:
        stats.error = "构建超时（5min）"
    except Exception as e:
        stats.error = str(e)[:200]

    return stats


def update(path: str = ".") -> CrgStats:
    """增量更新图谱（仅重新分析变化文件）。"""
    stats = CrgStats()

    if not is_available():
        stats.error = "code-review-graph 未安装"
        return stats

    try:
        r = subprocess.run(
            [*_get_crg_cmd(), "update", "--repo", path],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if r.returncode != 0:
            stats.error = r.stderr.strip()[:500]
            return stats

        _parse_status(stats, r.stdout)
    except subprocess.TimeoutExpired:
        stats.error = "更新超时（2min）"
    except Exception as e:
        stats.error = str(e)[:200]

    return stats


def status(path: str = ".") -> CrgStats:
    """查看图谱状态和统计信息。"""
    stats = CrgStats()

    if not is_available():
        stats.error = "code-review-graph 未安装"
        return stats

    try:
        r = subprocess.run(
            [*_get_crg_cmd(), "status", "--repo", path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.returncode != 0:
            stats.error = r.stderr.strip()[:500]
            return stats

        _parse_status(stats, r.stdout)
    except Exception as e:
        stats.error = str(e)[:200]

    return stats


def _parse_status(stats: CrgStats, output: str) -> None:
    """解析 code-review-graph 的文本输出到结构化数据。"""
    for line in output.split("\n"):
        line = line.strip().lower()
        if "files" in line and ":" in line:
            try:
                stats.total_files = int(line.split(":")[-1].strip())
            except ValueError:
                pass
        elif "nodes" in line and ":" in line:
            try:
                stats.total_nodes = int(line.split(":")[-1].strip())
            except ValueError:
                pass
        elif "edges" in line and ":" in line:
            try:
                stats.total_edges = int(line.split(":")[-1].strip())
            except ValueError:
                pass
        elif "loc" in line and ":" in line:
            try:
                stats.source_lines = int(line.split(":")[-1].strip().split()[0])
            except ValueError:
                pass


def get_graph_path(path: str = ".") -> str | None:
    """获取 SQLite 数据库路径。"""
    crg_dir = Path(path) / ".code-review-graph"
    db = crg_dir / "graph.db"
    if db.exists():
        return str(db)
    # 也检查上级目录
    for p in [Path(path).resolve(), Path(path).resolve().parent]:
        db = p / ".code-review-graph" / "graph.db"
        if db.exists():
            return str(db)
    return None


def visualise(path: str = ".", output: str | None = None) -> str | None:
    """生成交互式 HTML 图谱可视化。"""
    target = output or str(Path(path).resolve() / "codeanalyze-crg-viz.html")

    try:
        r = subprocess.run(
            [*_get_crg_cmd(), "visualize", "--repo", path, "--output", target],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if r.returncode == 0 and Path(target).exists():
            return target
        return None
    except Exception as e:
        logger.warning("CRG visualize failed: %s", e)
        return None
