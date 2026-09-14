"""CLI commands: export"""

import json as _json
from pathlib import Path

import click
from rich.panel import Panel

from codeanalyze.commands.common import _validate_path, console  # type: ignore[import-not-found]
from codeanalyze.core.results import KnowledgeGraph  # type: ignore[import-not-found]
from codeanalyze.documents.official import analyze_policy_directory  # type: ignore[import-not-found]
from codeanalyze.integrations.forge import guardrail  # type: ignore[import-not-found]
from codeanalyze.reports.export import merge_code_kg, policy_graph_to_kg  # type: ignore[import-not-found]


def _md_summary(kg: KnowledgeGraph) -> str:
    lines = [
        "# 知识图谱导出报告",
        "## 概览",
        f"- 实体: {kg.entity_count} 个",
        f"- 关系: {kg.relation_count} 条",
        f"- 来源文件: {len(kg.source_files)} 个",
        "",
        "## 实体列表",
    ]
    for e in kg.entities.values():
        prov = f" [来源: {e.provenance.source_file.split('/')[-1] if e.provenance else '-'}]"
        lines.append(f"- [{e.type}] **{e.name}** (域: {e.domain}, 置信: {e.confidence}){prov}")
    lines.extend(["", "## 关系列表"])
    for i, r in enumerate(kg.relations):
        if i >= 60:
            lines.append(f"  ... 还有 {len(kg.relations) - 60} 条")
            break
        src = kg.entities.get(r.source_id)
        tgt = kg.entities.get(r.target_id)
        sn = src.name if src else r.source_id[:30]
        tn = tgt.name if tgt else r.target_id[:30]
        lines.append(f"- {sn} --[{r.type}]--> {tn}")
    lines.extend(["", "## 来源文件"])
    for sf_path, info in kg.source_files.items():
        name = sf_path.split("/")[-1]
        lines.append(f"- {name} (分析器: {info['analyzer']})")
    return "\n".join(lines)


@click.command()
@click.argument("path", default=".")
@click.option(
    "--format",
    "-f",
    "output_format",
    default="json",
    type=click.Choice(["json", "json-ld", "cypher", "md"]),
    help="输出格式: json(Agent), json-ld(本体), cypher(Neo4j), md(摘要)",
)
@click.option("--output", "-o", default=None, help="输出文件路径")
@click.option("--code", is_flag=True, default=False, help="包含代码分析引擎数据(Graphify)")
@click.option("--eidos", is_flag=True, default=False, help="转换为 Eidos 兼容格式 + 校验")
@click.option("--pretty", is_flag=True, default=True, help="格式化输出")
@click.option(
    "--mode",
    default="summary",
    type=click.Choice(["summary", "condensed", "full"]),
    help="summary=摘要(类型分布), condensed=精简(-SourceFile), full=全量",
)
@guardrail(required_steps=["analyze", "export"], max_retries=2)
def export(path: str, output_format: str, output: str | None, code: bool, eidos: bool, pretty: bool, mode: str) -> None:
    """导出结构化知识图谱（JSON/JSON-LD/Cypher/Markdown）。

    将所有分析结果转为统一的 Entity-Relation 模型，
    每个实体带溯源信息（来源文件、提取方法、置信度），
    支持图数据库导入和 Agent 直接消费。

    溯源示例：实体从哪个文件来、用什么方法提取的、置信度多少，
    都在 provenance 字段中可追踪。
    """
    root = _validate_path(path)
    console.print(
        Panel.fit(
            f"[bold cyan]📦 导出知识图谱: {root.name}[/]",
            border_style="cyan",
        )
    )

    # 文档引擎
    console.print("  [cyan]▶ 文档分析引擎...[/]")
    pg = analyze_policy_directory(str(root))
    kg = policy_graph_to_kg(pg)
    console.print(f"    ✅ {kg.entity_count} 实体 / {kg.relation_count} 关系 / {len(kg.source_files)} 追溯源文件")

    # 代码引擎（可选）
    if code:
        console.print("  [cyan]▶ 代码分析引擎 (Graphify)...[/]")
        old_count = kg.entity_count
        kg = merge_code_kg(kg, str(root))
        added = kg.entity_count - old_count
        err = kg.metadata.get("code_engine_error")
        if err:
            console.print(f"    [yellow]⚠️ {err}[/]")
            console.print("    [dim]跳过代码实体[/]")
        else:
            console.print(f"    ✅ 新增 {added} 个代码实体")

    # 序列化器（提前定义，供 mode 分支使用）
    suffix_map = {"json": ".json", "json-ld": ".jsonld", "cypher": ".cypher", "md": ".md"}
    serializers = {
        "json": lambda: kg.to_json(),
        "json-ld": lambda: _json.dumps(kg.to_json_ld(), ensure_ascii=False, indent=2 if pretty else None),
        "cypher": lambda: kg.to_cypher(),
        "md": lambda: _md_summary(kg),
    }

    # 模式过滤
    if mode == "summary":
        type_counts: dict[str, int] = {}
        for e in kg.entities.values():
            type_counts[e.type] = type_counts.get(e.type, 0) + 1
        summary_data = {
            "meta": {
                "project": root.name,
                "mode": "summary",
                "total_entities": kg.entity_count,
                "total_relations": kg.relation_count,
                "source_files": len(kg.source_files),
            },
            "entity_types": dict(sorted(type_counts.items(), key=lambda x: -x[1])),
            "relation_count": kg.relation_count,
        }
        content = _json.dumps(summary_data, ensure_ascii=False, indent=2)
        console.print(f"  [dim]摘要模式: {len(type_counts)} 种实体类型[/]")

    elif mode == "condensed":
        source_ids = {eid for eid, e in kg.entities.items() if e.type == "SourceFile"}
        for sid in source_ids:
            del kg.entities[sid]
        kg.relations = [r for r in kg.relations if r.source_id not in source_ids and r.target_id not in source_ids]
        content = serializers[output_format]()
        console.print(f"  [dim]精简模式: 移除 {len(source_ids)} 个 SourceFile 实体[/]")

    else:  # full
        content = serializers[output_format]()

    # Cypher 特殊警告
    if output_format == "cypher":
        console.print("  [yellow]⚠️ Cypher 导出为纯文本脚本，需要 Neo4j 环境执行。[/]")
        console.print("  [yellow]   建议先用 JSON 格式导出供 Agent 消费。[/]")

    suffix = suffix_map[output_format]

    format_labels = {
        "json": "JSON 知识图谱（Agent 消费）",
        "json-ld": "JSON-LD 语义图谱（本体建模）",
        "cypher": "Cypher 导入脚本（Neo4j）",
        "md": "图谱摘要报告（人工阅读）",
    }

    target = output or str(root / f"codeanalyze-export{suffix}")
    Path(target).write_text(content, encoding="utf-8")

    console.print(f"\n  ✅ {format_labels[output_format]}")
    console.print(f"  📄 {target}")
    console.print(f"  📊 {kg.entity_count} 实体 / {kg.relation_count} 关系 / {len(kg.source_files)} 来源文件")

    # Eidos 集成（可选）
    if eidos:
        console.print("\n  [cyan]▶ Eidos 格式转换 + Schema 校验...[/]")
        from codeanalyze.integrations.eidos_adapter import (  # type: ignore[import-not-found]
            convert_kg,
            try_eidos_validate,
        )

        eidos_data = convert_kg(kg)
        eidos_target = output or str(root / "codeanalyze-eidos.json")
        Path(eidos_target).write_text(
            _json.dumps(eidos_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        console.print(f"  📄 Eidos 输出: {eidos_target}")
        console.print(f"     OntologyNode: {len(eidos_data['ontology_nodes'])}")
        console.print(f"     Relation:     {len(eidos_data['relations'])}")
        console.print(f"     Fact:         {len(eidos_data['facts'])}")
        console.print(f"     KnowledgeCard: {len(eidos_data['cards'])}")

        validation = try_eidos_validate(eidos_data)
        if validation.get("available"):
            console.print("  ✅ Eidos 校验: Schema 可用")
        else:
            console.print(f"  ⏭️  Eidos 校验跳过({validation.get('note', validation.get('error', 'unknown'))})")

        console.print(
            Panel.fit(
                "[bold green]✅ Eidos 集成完成[/]\n"
                "  集成路径: codeanalyze → Eidos (单向导出，KOS/OntoDerive 需手动执行)\n"
                "  执行: eidos validate codeanalyze-eidos.json --type node",
                border_style="green",
            )
        )

    # 溯源统计
    with_prov = sum(1 for e in kg.entities.values() if e.provenance)
    console.print(f"  📋 带溯源实体: {with_prov}/{kg.entity_count}")

    console.print(
        Panel.fit(
            "[bold green]✅ 导出完成[/]\n"
            "  Agent: JSON 格式直接注入 context\n"
            "  本体建模: JSON-LD 兼容语义网工具\n"
            "  图数据库: Cypher 直接导入 Neo4j\n"
            "  溯源追踪: 每个实体标注来源文件和提取方法",
            border_style="green",
        )
    )
