"""
OntoDerive 共享工具函数 v2.3
=============================
消除各模块重复的 rf/wf/all_md/load_json/save_json 拷贝。
v2.3: 添加 CachedReader 消除单次 run_check 中的重复文件 I/O。
"""

import json
import re
from pathlib import Path
from typing import Any


class CachedReader:
    """单次检查生命周期内的文件读缓存 — 每个文件只从磁盘读一次"""

    def __init__(self) -> None:
        self._files: dict[Any, Any] = {}  # path_str → text
        self._listings: dict[Any, Any] = {}  # dir_str → [Path]

    def rf(self, path: Any) -> Any:
        key = str(path)
        if key not in self._files:
            p = Path(path)
            self._files[key] = p.read_text("utf-8", errors="ignore") if p.exists() else ""
        return self._files[key]

    def all_md(self, directory: Any) -> Any:
        key = str(directory)
        if key not in self._listings:
            dp = Path(directory)
            self._listings[key] = sorted(dp.rglob("*.md")) if dp.exists() else []
        return self._listings[key]


# 全局无状态工具（向后兼容）
def rf(path: Any) -> Any:
    """读文件，文件不存在返回空串"""
    p = Path(path) if isinstance(path, str) else path
    return p.read_text("utf-8", errors="ignore") if p.exists() else ""


def wf(path: Any, text: Any) -> None:
    """写文件，自动创建父目录"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def all_md(directory: Any) -> Any:
    """列出目录下所有 .md 文件，按路径排序"""
    dp = Path(directory)
    return sorted(dp.rglob("*.md")) if dp.exists() else []


def load_json(path: Any) -> Any:
    """加载JSON文件，失败返回None"""
    p = Path(path)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            return None
    return None


def save_json(path: Any, data: Any) -> None:
    """保存JSON文件，自动创建父目录"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def scan_facts_from_md(text: str) -> dict:
    """从Markdown表格中扫描事实数据 (D-F / P-F)"""
    facts: dict[str, dict] = {"data": {}, "policy": {}}
    for m in re.finditer(r"\| (D-F\d+)\s*\|([^|]+)\|([^|]+)\|", text):
        facts["data"][m.group(1)] = {"desc": m.group(2).strip(), "value": m.group(3).strip()}
    for m in re.finditer(r"\| (P-F\d+)\s*\|([^|]+)\|", text):
        facts["policy"][m.group(1)] = {"desc": m.group(2).strip()}
    return facts


def scan_inferences_from_md(text: str) -> dict:
    """从Markdown中扫描推论块 (INF-)"""
    inferences = {}
    for block in re.split(r"^##\s+", text, flags=re.MULTILINE)[1:]:
        title = block.strip().split("\n")[0].strip()
        df_line = re.search(r"derives_from:\s*\[([^\]]+)\]", block)
        df = re.findall(r"(D-F\d+|P-F\d+|INF-[\w\d]+)", df_line.group(1)) if df_line else []
        inferences[title] = {"derives_from": list(set(df)), "text": block[:300]}
    return inferences


def detect_cycles(nodes: Any, edges: Any) -> Any:
    """
    共享的三色DFS环检测算法。
    nodes: dict {id: info} 或 set of ids
    edges: dict {from_id: [to_id]} 或 defaultdict(list)
    返回检测到的环列表。
    """
    node_ids = set(nodes.keys()) if isinstance(nodes, dict) else set(nodes)
    white, gray, black = 0, 1, 2
    color = {n: white for n in node_ids}
    cycles = []

    def dfs(u: Any, path: Any) -> None:
        color[u] = gray
        path.append(u)
        for v in edges.get(u, []):
            if v not in color:
                continue
            if color[v] == gray:
                cycle_start = path.index(v)
                cycles.append(path[cycle_start:] + [v])
            elif color[v] == white:
                dfs(v, path)
        path.pop()
        color[u] = black

    for n in node_ids:
        if color.get(n) == white:
            dfs(n, [])
    return cycles
