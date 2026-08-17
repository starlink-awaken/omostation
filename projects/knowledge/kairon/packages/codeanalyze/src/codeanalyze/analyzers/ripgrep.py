"""ripgrep 分析器 — 超快代码搜索

基于 ripgrep (rg) 的结构化代码搜索工具。
输出与 get_entities/get_relations 兼容的搜索格式。
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class RgMatch:
    """单个 ripgrep 匹配结果"""

    path: str
    line_number: int
    column: int
    text: str
    lines_before: list[str] = field(default_factory=list)
    lines_after: list[str] = field(default_factory=list)

    @property
    def context(self) -> str:
        lines = []
        if self.lines_before:
            lines.extend(self.lines_before)
        lines.append(self.text)
        if self.lines_after:
            lines.extend(self.lines_after)
        return "\n".join(lines)


@dataclass
class RgResult:
    """搜索匹配集合"""

    pattern: str
    path: str
    matches: list[RgMatch] = field(default_factory=list)
    total: int = 0
    elapsed_ms: int = 0
    error: str | None = None


def is_available() -> bool:
    """检查 ripgrep 是否已安装。"""
    return shutil.which("rg") is not None


def get_version() -> str | None:
    """获取 ripgrep 版本。"""
    try:
        r = subprocess.run(["rg", "--version"], capture_output=True, text=True, timeout=5)
        first_line = r.stdout.strip().split("\n")[0] if r.stdout else None
        if first_line:
            return first_line.split(" ", 1)[-1] if " " in first_line else first_line
        return None
    except Exception:
        return None


def search(
    pattern: str,
    path: str = ".",
    regex: bool = True,
    fixed_strings: bool = False,
    ignore_case: bool = False,
    max_count: int = 200,
    context_before: int = 0,
    context_after: int = 0,
    glob: str | None = None,
    file_type: str | None = None,
    json_output: bool = True,
) -> RgResult:
    """使用 ripgrep 搜索代码。

    Args:
        pattern: 搜索模式
        path: 搜索路径
        regex: 是否作为正则表达式（默认 True）
        fixed_strings: 是否精确字符串匹配（覆盖 regex）
        ignore_case: 忽略大小写
        max_count: 最大匹配数
        context_before: 匹配前显示行数
        context_after: 匹配后显示行数
        glob: 文件通配符过滤（如 "*.py"）
        file_type: 按 rg 文件类型过滤（如 "py", "md"）
        json_output: 是否使用 JSON 结构化输出
    """
    result = RgResult(
        pattern=pattern,
        path=str(Path(path).resolve()),
    )

    cmd = ["rg"]

    # 匹配模式
    if fixed_strings:
        cmd.append("--fixed-strings")
    elif not regex:
        cmd.append("--fixed-strings")
    if ignore_case:
        cmd.append("-i")

    # 输出格式
    if json_output:
        cmd.append("--json")
    else:
        cmd.append("--with-filename")
        cmd.append("--line-number")

    # 上下文
    ctx = context_before or context_after
    if context_before and context_after:
        cmd.extend(["-C", str(context_before)])  # -C 同时控制前后
    elif context_before:
        cmd.extend(["-B", str(context_before)])
    elif context_after:
        cmd.extend(["-A", str(context_after)])
    elif ctx:
        cmd.extend(["-C", str(ctx)])

    # 文件过滤
    if glob:
        cmd.extend(["-g", glob])
    if file_type:
        cmd.extend(["-t", file_type])

    # 数量限制
    if max_count:
        cmd.extend(["-m", str(max_count)])

    cmd.append("--")
    cmd.append(pattern)
    cmd.append(path)

    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if r.returncode not in (0, 1):
            # 1 = no matches, still valid
            result.error = r.stderr.strip()[:500]
            return result

        if json_output:
            _parse_json_output(result, r.stdout)
        else:
            _parse_text_output(result, r.stdout)

    except subprocess.TimeoutExpired:
        result.error = "搜索超时（60s）"
    except FileNotFoundError:
        result.error = "rg 未安装"

    return result


def _parse_json_output(result: RgResult, stdout: str) -> None:
    """解析 ripgrep JSON 输出。"""
    current = None
    lines_before: list[str] = []
    after_remaining = 0

    for line in stdout.strip().split("\n"):
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue

        obj_type = obj.get("type")

        if obj_type == "begin":
            current = obj.get("data", {}).get("path", {}).get("text", "?")
            lines_before = []
            after_remaining = 0

        elif obj_type == "match":
            data = obj.get("data", {})
            path_text = data.get("path", {}).get("text", current or "?")
            line_num = data.get("line_number", 0)
            col = data.get("absolute_column", 0) or data.get("column", 0)
            raw = data.get("lines", {}).get("text", "").rstrip("\n")

            match = RgMatch(
                path=path_text,
                line_number=line_num,
                column=col,
                text=raw,
            )

            match.lines_before = list(lines_before)
            if after_remaining > 0 and result.matches:
                result.matches[-1].lines_after.extend(lines_before[:after_remaining])
                after_remaining = 0

            result.matches.append(match)
            result.total += 1
            lines_before = []

        elif obj_type == "context":
            data = obj.get("data", {})
            lines_before.append(data.get("lines", {}).get("text", "").rstrip("\n"))
            after_remaining = 0

        elif obj_type == "summary":
            stats = obj.get("data", {}).get("stats", {})
            result.elapsed_ms = stats.get("elapsed_millis", 0)


def _parse_text_output(result: RgResult, stdout: str) -> None:
    """解析 ripgrep 纯文本输出。"""
    for line in stdout.strip().split("\n"):
        if not line:
            continue
        # 格式: path:line_num:text
        parts = line.split(":", 2)
        if len(parts) >= 3:
            result.matches.append(
                RgMatch(
                    path=parts[0],
                    line_number=int(parts[1]),
                    column=0,
                    text=parts[2],
                )
            )
            result.total += 1


def search_files(
    pattern: str,
    path: str = ".",
    **kwargs: Any,
) -> list[dict]:
    """搜索并返回结构化结果列表（兼容实体格式）。"""
    result = search(pattern, path, **kwargs)
    if result.error:
        return [{"error": result.error}]

    entities = []
    for m in result.matches:
        entities.append(
            {
                "id": f"rg-{hash(m.path + str(m.line_number)) % 1000000:06d}",
                "name": m.text.strip()[:80],
                "type": "SearchMatch",
                "source": "ripgrep",
                "source_path": m.path,
                "source_line": m.line_number,
                "confidence": 1.0,
                "properties": {
                    "pattern": pattern,
                    "context": m.context[:200] if m.context else "",
                    "column": m.column,
                },
            }
        )
    return entities
