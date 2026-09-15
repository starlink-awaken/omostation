"""policydoc: export"""

import json as _json
from pathlib import Path

import click
from codeanalyze.documents.official import analyze_policy_directory  # type: ignore[import-not-found]
from codeanalyze.reports.export import policy_graph_to_kg  # type: ignore[import-not-found]
from rich.panel import Panel

from policydoc.cli import _validate_path, console  # type: ignore[import-not-found]


def _md_summary(kg, project_name):
    return f"# 政策知识图谱导出 — {project_name}\n- 实体: {kg.entity_count} 个\n- 关系: {kg.relation_count} 条"


@click.command()
@click.argument("path", default=".")
@click.option("--format", "-f", "output_format", default="json", type=click.Choice(["json", "json-ld", "cypher", "md"]))
@click.option("--output", "-o", default=None)
@click.option("--eidos", is_flag=True, default=False)
@click.option("--pipeline", is_flag=True, default=False)
def export(path, output_format, output, eidos, pipeline):
    """导出政策文档知识图谱。"""
    root = Path(_validate_path(path)).resolve()
    console.print(Panel.fit(f"[bold cyan]📦 导出知识图谱: {root.name}[/]", border_style="cyan"))

    pg = analyze_policy_directory(str(root))
    kg = policy_graph_to_kg(pg)

    suffix_map = {"json": ".json", "json-ld": ".jsonld", "cypher": ".cypher", "md": ".md"}
    serializers = {
        "json": lambda: kg.to_json(),
        "json-ld": lambda: _json.dumps(kg.to_json_ld(), ensure_ascii=False, indent=2),
        "cypher": lambda: kg.to_cypher(),
        "md": lambda: _md_summary(kg, root.name),
    }

    target = output or str(root / f"policydoc-export{suffix_map[output_format]}")
    Path(target).write_text(serializers[output_format](), encoding="utf-8")
    console.print(f"\n  ✅ {output_format.upper()} 导出完成: {target}")
    console.print(f"  📊 {kg.entity_count} 实体 / {kg.relation_count} 关系")

    if eidos:
        from codeanalyze.integrations.eidos_adapter import convert_kg  # type: ignore[import-not-found]

        data = convert_kg(kg)
        etarget = output or str(root / "policydoc-eidos.json")
        Path(etarget).write_text(_json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        console.print(f"  📄 Eidos: {etarget}")

    if pipeline:
        console.print("[green]✅ 导出完成: codeanalyze → Eidos (单向导出，KOS/OntoDerive 需手动执行)[/]")
