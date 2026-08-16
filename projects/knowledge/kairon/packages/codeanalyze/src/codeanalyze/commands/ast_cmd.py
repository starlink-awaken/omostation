"""CLI commands: ast (ast-grep)"""

import json as _json

import click

from codeanalyze.analyzers import ast_grep  # type: ignore[import-not-found]
from codeanalyze.commands.common import console  # type: ignore[import-not-found]
from codeanalyze.core.registry import build_registry  # type: ignore[import-not-found]


@click.command()
@click.argument("pattern")
@click.argument("path", default=".")
@click.option("--lang", "-l", help="指定语言 (如 py, js, ts, rs, go)")
@click.option("--strict", is_flag=True, help="严格模式匹配")
@click.option("--max", "-m", default=50, type=int, help="最大匹配数")
@click.option("--json", "-j", "json_flag", is_flag=True, help="JSON 结构化输出")
def ast(
    pattern: str,
    path: str,
    lang: str | None,
    strict: bool,
    max: int,
    json_flag: bool,
) -> None:
    """使用 ast-grep (sg) 进行 AST 结构化搜索。

    比纯文本 ripgrep 更精确，能匹配 "$FUNC($___)" 等语法结构。
    """
    reg = build_registry()
    ag = reg.tools.get("ast-grep")

    if not ag or not ag.available:
        console.print("[red]❌ ast-grep 未安装. 安装: brew install ast-grep[/]")
        return

    result = ast_grep.search(
        pattern=pattern,
        path=path,
        language=lang,
        strict=strict,
        max_count=max,
    )

    if result.error:
        console.print(f"[red]❌ AST 搜索失败: {result.error}[/]")
        return

    if json_flag:
        console.print(
            _json.dumps(
                {
                    "pattern": result.pattern,
                    "path": result.path,
                    "language": result.language,
                    "total": result.total,
                    "matches": [
                        {
                            "path": m.path,
                            "line": m.line_start,
                            "col": m.col_start,
                            "text": m.text,
                        }
                        for m in result.matches
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    console.print(f'[bold cyan]▶ AST 搜索 "{pattern}" 在 {path}[/]')
    if result.total == 0:
        console.print("  [yellow]未找到匹配[/]")
        return

    console.print(f"  [green]找到 {result.total} 个匹配[/]")
    for m in result.matches:
        display_path = m.path[len(result.path) :].lstrip("/") if m.path.startswith(result.path) else m.path
        console.print(f"  [underline]{display_path}[/]:{m.line_start}:{m.col_start}")
        for i, line in enumerate(m.text.strip().split("\n")):
            if i > 5:
                console.print("    ...")
                break
            console.print(f"    {line}")
