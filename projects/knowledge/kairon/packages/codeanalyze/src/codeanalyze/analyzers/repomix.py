"""repomix 分析器 — 将代码库打包为 LLM 友好格式

repomix 把整个代码库压缩成单一文件（XML/Markdown/JSON），
让 LLM 一次性获得完整上下文，无需多次文件读取。

常用场景:
- 把 repo 喂给 Claude/GPT 做全局分析
- 生成代码审查用的快照文件
- 为 AI 编写文档/重构提供完整上下文
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RepomixResult:
    """repomix 打包结果"""

    output_path: str | None = None
    output_format: str = "xml"
    file_count: int = 0
    token_count: int = 0
    char_count: int = 0
    elapsed_ms: int = 0
    error: str | None = None
    summary: dict = field(default_factory=dict)


def is_available() -> bool:
    """检查 repomix 是否可用（npx 通用，不需要全局安装）。"""
    return shutil.which("repomix") is not None or shutil.which("npx") is not None


def get_version() -> str | None:
    """获取 repomix 版本。"""
    if shutil.which("repomix"):
        try:
            r = subprocess.run(["repomix", "--version"], capture_output=True, text=True, timeout=10)
            return r.stdout.strip() or None
        except Exception:
            pass
    # npx 方式
    if shutil.which("npx"):
        try:
            r = subprocess.run(
                ["npx", "-y", "repomix", "--version"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            return r.stdout.strip() or None
        except Exception:
            pass
    return None


def pack(
    path: str = ".",
    output: str | None = None,
    fmt: str = "xml",
    include: list[str] | None = None,
    ignore: list[str] | None = None,
    no_gitignore: bool = False,
    remove_comments: bool = False,
    remove_empty_lines: bool = False,
    top_files: int | None = None,
    token_count: bool = True,
) -> RepomixResult:
    """打包代码库为 LLM 友好格式。

    Args:
        path: 代码库根目录
        output: 输出文件路径（默认 repomix-output.xml/md/json）
        fmt: 输出格式，xml | markdown | plain
        include: 包含的文件 glob（如 ["src/**/*.py"]）
        ignore: 排除的文件 glob（如 ["tests/**", "*.lock"]）
        no_gitignore: 不使用 .gitignore 规则
        remove_comments: 移除注释以节省 token
        remove_empty_lines: 移除空行
        top_files: 只显示 token 数最多的 N 个文件
        token_count: 统计 token 数（稍慢）
    """
    root = Path(path).resolve()
    result = RepomixResult(output_format=fmt)

    if not is_available():
        result.error = "repomix/npx 未安装. 安装: npm install -g repomix 或 brew install node"
        return result

    # 决定输出路径
    ext_map = {"xml": "xml", "markdown": "md", "plain": "txt"}
    ext = ext_map.get(fmt, "xml")
    out_path = Path(output) if output else root / f"repomix-output.{ext}"
    result.output_path = str(out_path)

    # 构造命令
    cmd: list[str]
    if shutil.which("repomix"):
        cmd = ["repomix"]
    else:
        cmd = ["npx", "-y", "repomix"]

    cmd.extend(["--output", str(out_path)])
    cmd.extend(["--style", fmt])

    if include:
        cmd.extend(["--include", ",".join(include)])
    if ignore:
        cmd.extend(["--ignore", ",".join(ignore)])
    if no_gitignore:
        cmd.append("--no-gitignore")
    if remove_comments:
        cmd.append("--remove-comments")
    if remove_empty_lines:
        cmd.append("--remove-empty-lines")
    if top_files is not None:
        cmd.extend(["--top-files-len", str(top_files)])

    cmd.append(str(root))

    import time

    t0 = time.time()

    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(root),
        )
        result.elapsed_ms = int((time.time() - t0) * 1000)

        if r.returncode != 0:
            result.error = (r.stderr or r.stdout or "").strip()[:500]
            return result

        # 解析输出摘要
        _parse_stdout_summary(result, r.stdout + r.stderr)

        # 读取输出文件获取大小信息
        if out_path.exists():
            content = out_path.read_text("utf-8", errors="replace")
            result.char_count = len(content)

    except subprocess.TimeoutExpired:
        result.error = "打包超时（120s）"
    except FileNotFoundError:
        result.error = "repomix/npx 未找到"

    return result


def pack_to_string(
    path: str = ".",
    fmt: str = "xml",
    include: list[str] | None = None,
    ignore: list[str] | None = None,
    max_chars: int = 100_000,
) -> str:
    """打包代码库并直接返回字符串（适合直接嵌入 prompt）。

    注意：大型 repo 可能超过 max_chars 限制，会返回截断版本。
    """
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=f".{fmt}", delete=False) as f:
        tmp = f.name

    try:
        result = pack(path=path, output=tmp, fmt=fmt, include=include, ignore=ignore)
        if result.error:
            return f"<!-- repomix error: {result.error} -->"
        content = Path(tmp).read_text("utf-8", errors="replace")
        if len(content) > max_chars:
            content = content[:max_chars] + f"\n<!-- truncated at {max_chars} chars -->"
        return content
    finally:
        Path(tmp).unlink(missing_ok=True)


def get_stats(path: str = ".") -> dict:
    """快速统计代码库文件数和 token 估算（不写输出文件）。"""
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as f:
        tmp = f.name

    try:
        result = pack(path=path, output=tmp, fmt="xml", token_count=True)
        return {
            "file_count": result.file_count,
            "token_count": result.token_count,
            "char_count": result.char_count,
            "elapsed_ms": result.elapsed_ms,
            "error": result.error,
        }
    finally:
        Path(tmp).unlink(missing_ok=True)


def _parse_stdout_summary(result: RepomixResult, stdout: str) -> None:
    """从 repomix 输出中解析统计信息。"""
    lines = stdout.strip().split("\n")
    for line in lines:
        line_lower = line.lower()
        # repomix 输出格式: "Files: 42" / "Tokens: 12,345"
        if "files:" in line_lower or "file count:" in line_lower:
            try:
                num = "".join(c for c in line.split(":")[-1] if c.isdigit())
                if num:
                    result.file_count = int(num)
            except (ValueError, IndexError):
                pass
        elif "token" in line_lower:
            try:
                num = "".join(c for c in line.split(":")[-1] if c.isdigit())
                if num:
                    result.token_count = int(num)
            except (ValueError, IndexError):
                pass
