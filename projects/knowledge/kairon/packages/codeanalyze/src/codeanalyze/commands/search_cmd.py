"""CLI commands: search"""

import json as _json
from collections import defaultdict

import click

from codeanalyze.analyzers import ripgrep  # type: ignore[import-not-found]
from codeanalyze.commands.common import console  # type: ignore[import-not-found]
from codeanalyze.core.registry import build_registry  # type: ignore[import-not-found]


@click.command()
@click.argument("pattern")
@click.argument("path", default=".")
@click.option("--regex", is_flag=True, default=True, help="正则表达式搜索（默认）")
@click.option("--fixed", "-F", is_flag=True, help="精确字符串搜索")
@click.option("--ignore-case", "-i", is_flag=True, help="忽略大小写")
@click.option("--glob", "-g", default=None, help="文件通配符过滤（如 '*.py'）")
@click.option("--type", "-t", "file_type", default=None, help="文件类型过滤（如 py, md, json）")
@click.option("--context", "-C", default=0, type=int, help="上下文行数")
@click.option("--max", "-m", default=50, type=int, help="最大匹配数")
@click.option("--json", "-j", "json_flag", is_flag=True, help="JSON 结构化输出")
def search(
    pattern: str,
    path: str,
    regex: bool,
    fixed: bool,
    ignore_case: bool,
    glob: str | None,
    file_type: str | None,
    context: int,
    max: int,
    json_flag: bool,
) -> None:
    """使用 ripgrep 在代码库中快速搜索。

    比 grep 快 10x，自动跳过 .gitignore 中的目录。
    支持正则、精确字符串、结构化 JSON 输出。
    """
    reg = build_registry()
    rg = reg.tools.get("ripgrep")

    if not rg or not rg.available:
        console.print("[red]❌ ripgrep 未安装. 安装: brew install ripgrep (macOS) 或 apt install ripgrep (Linux)[/]")
        return

    result = ripgrep.search(
        pattern=pattern,
        path=path,
        regex=regex and not fixed,
        fixed_strings=fixed,
        ignore_case=ignore_case,
        max_count=max,
        context_before=context,
        context_after=context,
        glob=glob,
        file_type=file_type,
        json_output=json_flag,
    )

    if result.error:
        console.print(f"[red]❌ 搜索失败: {result.error}[/]")
        return

    if json_flag:
        console.print(
            _json.dumps(
                {
                    "pattern": result.pattern,
                    "path": result.path,
                    "total": result.total,
                    "elapsed_ms": result.elapsed_ms,
                    "matches": [{"path": m.path, "line": m.line_number, "text": m.text} for m in result.matches],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    # 纯文本输出
    console.print(f'[bold cyan]▶ 搜索 "{pattern}" 在 {path}[/]')
    if result.total == 0:
        console.print("  [yellow]未找到匹配[/]")
        return

    console.print(f"  [green]找到 {result.total} 匹配 ({result.elapsed_ms}ms)[/]")

    # 按文件分组显示
    by_file = defaultdict(list)
    for m in result.matches:
        by_file[m.path].append(m)

    for filepath, matches in sorted(by_file.items()):
        display_path = filepath[len(result.path) :].lstrip("/") if filepath.startswith(result.path) else filepath
        console.print(f"\n  [underline]{display_path}[/] ({len(matches)} 匹配)")
        for m in matches[:10]:
            line = m.text.strip()[:120]
            console.print(f"    L{m.line_number:4d} │ {line}")
        if len(matches) > 10:
            console.print(f"    ... 还有 {len(matches) - 10} 匹配")
