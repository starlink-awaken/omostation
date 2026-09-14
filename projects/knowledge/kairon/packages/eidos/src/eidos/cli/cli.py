from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import fields as dataclass_fields
from dataclasses import is_dataclass
from pathlib import Path
from typing import Any, cast

from eidos.core.schema import FieldType, Schema, SchemaField, SchemaRegistry
from eidos.core.validator import ValidationError, ValidationResult, Validator
from eidos.types import Fact, KnowledgeCard, OntologyNode

TYPE_MAP = {"KnowledgeCard": KnowledgeCard, "Fact": Fact, "OntologyNode": OntologyNode}
OUTPUT_JSON = {"tool": "eidos", "version": "0.1.0"}


def _build_registry() -> SchemaRegistry:
    registry = SchemaRegistry()
    registry.register(
        Schema(
            name="card",
            version="1.0.0",
            description="Card schema",
            fields={
                "id": SchemaField(name="id", field_type=FieldType.STRING, required=True),
                "title": SchemaField(name="title", field_type=FieldType.STRING, required=True),
                "count": SchemaField(name="count", field_type=FieldType.INTEGER, required=False),
            },
        )
    )
    registry.register(
        Schema(
            name="fact",
            version="1.0.0",
            description="Fact schema",
            fields={
                "subject": SchemaField(name="subject", field_type=FieldType.STRING, required=True),
                "value": SchemaField(name="value", field_type=FieldType.NUMBER, required=True),
            },
        )
    )
    registry.register(
        Schema(
            name="node",
            version="1.0.0",
            description="Node schema",
            fields={
                "id": SchemaField(name="id", field_type=FieldType.STRING, required=True),
                "type": SchemaField(name="type", field_type=FieldType.STRING, required=True),
            },
        )
    )
    return registry


def _print_validation_result(result: Any) -> None:
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


def _out(args: Any, data: dict) -> Any:
    """Output in JSON or human format based on --json flag."""
    if getattr(args, "json", False) or os.environ.get("PIPELINE_MODE"):
        output = {**OUTPUT_JSON, "command": args.command if hasattr(args, "command") else "", "data": data}
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        return data  # caller handles human output


def meta_command(args: Any) -> None:
    """Show SSOT meta-model: 8 MetaType × 4 MetaRelationType"""
    import json

    from eidos.meta import MetaRelationType, MetaType, list_types

    types = list_types()
    output = {
        "meta_types": [mt.value for mt in MetaType],
        "meta_relations": [mr.value for mr in MetaRelationType],
        "type_mapping": types,
    }

    if getattr(args, "pipeline_output", None):
        Path(args.pipeline_output).write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Output → {args.pipeline_output}")
        return

    if args.export or args.json or os.environ.get("PIPELINE_MODE"):
        _out(args, output)
        return

    print("SSOT Meta-Model (8 × 4)")
    print("=" * 40)
    print("\nMetaTypes:")
    for mt in MetaType:
        print(f"  {mt.value:12s} — {mt.display_name()}")
    print("\nMetaRelationTypes:")
    for mr in MetaRelationType:
        print(f"  {mr.value:12s}")
    types = list_types()
    print(f"\nType Mapping ({len(types)} types):")
    for t in types:
        print(f"  {t['meta_type']:12s} → {t['type_name']}")


def pipeline_command(args: Any) -> None:
    from eidos.pipeline import Pipeline, run_pipeline
    from eidos.pipeline.webui import generate_html

    if getattr(args, "web", None) == "web":
        html = generate_html(args.name)
        if args.output:
            Path(args.output).write_text(html, encoding="utf-8")
            print(f"Pipeline UI → {args.output}")
        else:
            print(html)
        return

    if args.file:
        pipeline = Pipeline.load(args.file)
    elif args.name:
        try:
            from eidos.pipeline.presets import PRESETS

            pipeline = PRESETS[args.name]
        except (ImportError, KeyError):
            print(f"Unknown preset: {args.name}")
            print("Available: knowledge-base, reasoning")
            return
    else:
        print("Use --file <path> or --name <preset>")
        return
    print(f"Pipeline: {pipeline.name} ({len(pipeline.steps)} steps)")
    exit_code = run_pipeline(pipeline, verbose=args.verbose)
    if exit_code == 0:
        print(f"✅ Done: {pipeline.name}")
    else:
        print(f"❌ FAILED: {pipeline.name}")


def viz_schema_command(args: Any) -> None:
    from eidos.viz import render

    sr = _build_registry()
    schema = sr.get(args.name) if hasattr(sr, "get") else None
    fields = []
    if schema:
        fields = [
            {"name": f.name, "type": f.field_type.value, "description": f.description}
            for f in getattr(schema, "fields", {}).values()
        ]
    else:
        type_cls = TYPE_MAP.get(args.name)
        if type_cls is None:
            print(f"Schema '{args.name}' not found")
            return
        if is_dataclass(type_cls):
            for f in dataclass_fields(type_cls):
                fields.append({"name": f.name, "type": getattr(f.type, "__name__", str(f.type)), "description": ""})
        else:
            annotations = getattr(type_cls, "__annotations__", {})
            fields = [
                {"name": name, "type": getattr(tp, "__name__", str(tp)), "description": ""}
                for name, tp in annotations.items()
            ]
    output = {
        "type": "schema",
        "name": args.name,
        "fields": fields,
        "mermaid": render("class", class_name=args.name, fields=fields),
    }
    if args.json or os.environ.get("PIPELINE_MODE"):
        _out(args, output)
        return
    print(output["mermaid"])


def viz_graph_command(args: Any) -> None:
    from eidos.viz import render

    # Try to load real data from KOS
    try:
        import subprocess

        kos_cmd = [
            "kos",
            "search",
            args.meta_type,
            "--limit",
            "10",
        ]
        result = subprocess.run(kos_cmd, capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and result.stdout.strip():
            if args.json or os.environ.get("PIPELINE_MODE"):
                _out(args, {"source": "kos", "output": result.stdout})
                return
            print(result.stdout)
            return
    except Exception:
        pass

    # Fallback to meta-model
    try:
        from eidos.meta import list_types

        types = list_types()
        nodes = [{"id": t["type_name"], "label": t["type_name"], "type": t["meta_type"]} for t in types]
        edges: list[dict[str, str]] = []
        mermaid = render("graph", nodes=nodes, edges=edges, title=args.meta_type)
        if args.json or os.environ.get("PIPELINE_MODE"):
            _out(args, {"nodes": nodes, "edges": edges, "mermaid": mermaid})
            return
        print(mermaid)
    except ImportError:
        print("Eidos meta not available")


def viz_explore_command(args: Any) -> None:
    """Interactive ontology exploration."""
    try:
        from eidos.viz_interactive import explore
    except ImportError:
        from eidos.meta import list_types
        from eidos.viz import render

        types = list_types()
        nodes = [
            {"id": t["type_name"], "label": t["type_name"], "type": t["meta_type"]}
            for t in types
            if not args.meta_type or t["meta_type"] == args.meta_type
        ]
        mermaid = render("graph", nodes=nodes, edges=[], title=args.meta_type)
        if args.json or os.environ.get("PIPELINE_MODE"):
            _out(args, {"nodes": nodes, "edges": [], "mermaid": mermaid})
            return
        print(mermaid)
        return
    explore(args.meta_type)


def viz_state_command(args: Any) -> None:
    from eidos.viz import render

    states = [mt.value for mt in __import__("eidos.meta", fromlist=["MetaType"]).MetaType]
    transitions: list[dict[str, str]] = []
    mermaid = render("state", states=states, transitions=transitions, initial=states[0])
    if args.json or os.environ.get("PIPELINE_MODE"):
        _out(args, {"states": states, "transitions": transitions, "initial": states[0], "mermaid": mermaid})
        return
    print(mermaid)


def viz_pipeline_command(args: Any) -> None:
    from eidos.viz import render

    steps = [
        {"name": "model", "description": "模型定义"},
        {"name": "extract", "description": "知识抽取"},
        {"name": "store", "description": "知识存储"},
        {"name": "reason", "description": "知识推导"},
        {"name": "viz", "description": "可视化"},
    ]
    mermaid = render("pipeline", steps=steps)
    if args.json or os.environ.get("PIPELINE_MODE"):
        _out(args, {"steps": steps, "mermaid": mermaid})
        return
    print(mermaid)


def viz_web_command(args: Any) -> None:
    """Generate interactive knowledge graph explorer."""
    from pathlib import Path

    from eidos.meta import list_constraints, list_types

    types = list_types()
    try:
        constraints = list_constraints()
    except Exception:
        constraints = []

    nodes = []
    edges = []

    for t in types:
        nodes.append(
            {
                "data": {"id": t["type_name"], "label": t["type_name"], "type": t["meta_type"]},
                "classes": t["meta_type"],
            }
        )

    for c in constraints:
        source = c.get("source", "")
        target = c.get("target", "")
        if not source or not target:
            continue
        edges.append(
            {
                "data": {
                    "id": f"{source}__{target}__{c.get('type', 'relates')}",
                    "source": source,
                    "target": target,
                    "label": c.get("type", "relates"),
                }
            }
        )

    elements_json = json.dumps(nodes + edges, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>Eidos Knowledge Graph Explorer</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.28.0/cytoscape.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/cytoscape-dagre/2.5.0/cytoscape-dagre.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/dagre/0.8.5/dagre.min.js"></script>
<style>
body {{ font-family: -apple-system, sans-serif; margin: 0; }}
#cy {{ width: 100%; height: 90vh; }}
.toolbar {{ padding: 8px 16px; background: #f5f5f5; border-bottom: 1px solid #ddd; }}
input {{ padding: 6px 12px; border: 1px solid #ccc; border-radius: 4px; width: 250px; }}
.info {{ padding: 8px 16px; background: #fff; border-bottom: 1px solid #eee; font-size: 0.85em; color: #555; }}
button {{ padding: 6px 12px; margin-left: 8px; border: 1px solid #ccc; border-radius: 4px; background: #fff; cursor: pointer; }}
button:hover {{ background: #f0f0f0; }}
</style>
</head>
<body>
<div class="toolbar">
<input type="text" id="search" placeholder="搜索节点..." oninput="filterGraph(this.value)">
<button onclick="resetGraph()">重置</button>
<button onclick="exportGraph()">导出</button>
</div>
<div class="info">
<span id="stats">0 nodes, 0 edges</span> | 点击节点查看详情
</div>
<div id="cy"></div>

<script>
 if (window.cytoscape && window.cytoscapeDagre) {{
   cytoscape.use(window.cytoscapeDagre);
 }}

var cy = cytoscape({{
  container: document.getElementById('cy'),
  elements: {elements_json},
  style: [
    {{selector: 'node', style: {{'label': 'data(label)', 'padding': '10px', 'background-color': '#6677cc', 'color': '#fff', 'font-size': '12px', 'text-valign': 'center', 'width': 'label', 'height': 'label', 'shape': 'roundrectangle'}}}},
    {{selector: 'edge', style: {{'width': 2, 'line-color': '#999', 'target-arrow-color': '#999', 'target-arrow-shape': 'triangle', 'curve-style': 'bezier', 'label': 'data(label)', 'font-size': '10px', 'color': '#666', 'text-background-color': '#fff', 'text-background-opacity': 1, 'text-background-padding': '2px'}}}},
    {{selector: '.domain', style: {{'background-color': '#4a90d9'}}}},
    {{selector: '.fact', style: {{'background-color': '#7b68ee'}}}},
    {{selector: '.document', style: {{'background-color': '#2ecc71'}}}},
    {{selector: ':selected', style: {{'border-color': '#ff6b6b', 'border-width': 3}}}},
    {{selector: '.highlighted', style: {{'background-color': '#ffb347', 'line-color': '#ffb347', 'target-arrow-color': '#ffb347'}}}},
    {{selector: '.dimmed', style: {{'opacity': 0.15}}}}
  ],
  layout: {{name: 'dagre', rankDir: 'LR', nodeSep: 28, rankSep: 48, edgeSep: 10}}
}});

document.getElementById('stats').textContent = cy.nodes().length + ' nodes, ' + cy.edges().length + ' edges';

cy.on('tap', 'node', function(evt) {{
  var n = evt.target;
  alert('Node: ' + n.data('label') + '\\nType: ' + n.data('type'));
}});

function filterGraph(query) {{
  cy.elements().removeClass('highlighted dimmed');
  if (!query) {{
    cy.elements().removeClass('dimmed');
    return;
  }}
  var q = query.toLowerCase();
  var matches = cy.nodes().filter(function(n) {{ return n.data('label').toLowerCase().includes(q); }});
  cy.elements().addClass('dimmed');
  matches.removeClass('dimmed');
  matches.connectedEdges().removeClass('dimmed');
  matches.connectedEdges().addClass('highlighted');
  matches.addClass('highlighted');
}}

function resetGraph() {{
  document.getElementById('search').value = '';
  cy.elements().removeClass('highlighted dimmed');
}}

function exportGraph() {{
  var png = cy.png({{full: true, scale: 2}});
  var link = document.createElement('a');
  link.download = 'ontology-graph.png';
  link.href = png;
  link.click();
}}
</script>
</body></html>"""

    Path(args.output).write_text(html)
    print(f"Interactive knowledge graph → {args.output} ({len(html)} chars)")


def define_command(args: Any) -> None:
    """Define a schema — from file, from args, or interactive."""
    import json
    from pathlib import Path

    from eidos.registry import SchemaRegistry

    name = args.name
    meta_type = args.meta_type
    fields = []

    interactive = getattr(args, "interactive", False)

    if args.file and not interactive:
        try:
            if getattr(args, "pipeline_input", None):
                pipeline_data = json.loads(Path(args.pipeline_input).read_text(encoding="utf-8"))
                data = pipeline_data.get("data", pipeline_data)
            else:
                data = json.loads(Path(args.file).read_text(encoding="utf-8"))
            fields = data.get("fields", [])
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error loading {args.file}: {e}")
            return
    else:
        print(f"Defining schema '{name}' (MetaType: {meta_type})")
        print("Enter field definitions. Empty name to finish.")
        i = 1
        while True:
            fname = input(f"  Field {i} name: ").strip()
            if not fname:
                break
            ftype = input(f"  Field {i} type (str/int/float/bool/list/ref) [str]: ").strip() or "str"
            freq = input(f"  Field {i} required? (y/n) [y]: ").strip().lower()
            required = freq != "n"
            desc = input(f"  Field {i} description: ").strip()
            type_map = {
                "str": "string",
                "int": "integer",
                "float": "number",
                "bool": "boolean",
                "list": "list",
                "ref": "ref",
            }
            fields.append(
                {"name": fname, "type": type_map.get(ftype, "string"), "required": required, "description": desc}
            )
            i += 1

    schema_fields = {}
    valid_field_types = {e.value: e for e in FieldType}
    for f in fields:
        field_type_value = f.get("type", "string")
        try:
            ft = valid_field_types.get(field_type_value, FieldType.STRING)
        except (ValueError, TypeError):
            ft = FieldType.STRING
        sf = SchemaField(
            name=f["name"],
            field_type=ft,
            required=f.get("required", True),
            description=f.get("description", ""),
        )
        schema_fields[sf.name] = sf

    schema = Schema(name=name, version="1.0.0", description=f"{meta_type} schema defined via CLI", fields=schema_fields)

    sr = SchemaRegistry()
    sr.register(schema)

    output = schema.to_json()
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Schema '{name}' written to {args.output}")
    else:
        print(output)
    print(f"\nSchema '{name}' defined successfully ({len(schema_fields)} fields)")


def store_command(args: Any) -> None:
    from eidos.storage import JSONFileBackend

    store = JSONFileBackend()
    if args.store_command == "save":
        try:
            data = json.loads(args.value)
        except json.JSONDecodeError:
            data = {"value": args.value}
        store.save(args.key, data)
        print(f"Saved: {args.key}")
    elif args.store_command == "load":
        data = store.load(args.key)
        if data:
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(f"Not found: {args.key}")
    elif args.store_command == "list":
        keys = store.list_keys(args.prefix)
        for k in keys:
            print(f"  {k}")


def main(argv: list[str] | None = None) -> int:
    print("⚠️ Eidos 独立 CLI 已弃用，请使用 cockpit 替代", file=sys.stderr)
    parser = argparse.ArgumentParser(
        prog="eidos",
        epilog="""使用示例:
  eidos list                          列出所有 Schema
  eidos validate data.json --type KnowledgeCard  校验知识卡片
  eidos validate --all                批量校验所有 Schema
  eidos meta                          显示元模型 (8 MetaType)
  eidos define MySchema               交互式定义 Schema
  eidos viz web                       生成 Dashboard HTML
  eidos pipeline --name knowledge-base 一键运行知识库管线""",
    )
    json_parent = argparse.ArgumentParser(add_help=False)
    json_parent.add_argument("--json", action="store_true", help="JSON 格式输出")
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细日志输出")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List all registered schemas", parents=[json_parent])

    validate_parser = subparsers.add_parser("validate", help="Validate a JSON file", parents=[json_parent])
    validate_parser.add_argument("file", nargs="?", help="Path to JSON file")
    validate_parser.add_argument("--type", dest="schema_type", help="Schema type to validate against")
    validate_parser.add_argument("--all", action="store_true", help="校验所有已注册 Schema")
    validate_parser.add_argument("--dir", help="校验目录中所有 JSON 文件")
    validate_parser.add_argument("--pipeline-input", help="Input file (pipeline:json mode)")
    validate_parser.add_argument("--pipeline-output", help="Output file (pipeline:json mode)")

    meta_parser = subparsers.add_parser("meta", help="显示元模型定义", parents=[json_parent])
    meta_parser.add_argument("--export", action="store_true", help="导出为 JSON")
    meta_parser.add_argument("--pipeline-input", help="Input file (pipeline mode)")
    meta_parser.add_argument("--pipeline-output", help="Output file (pipeline mode)")
    meta_parser.set_defaults(func=meta_command)

    # Pipeline command
    pipeline_parser = subparsers.add_parser("pipeline", help="管线编排", parents=[json_parent])
    pipeline_parser.add_argument("web", nargs="?", help=argparse.SUPPRESS)
    pipeline_parser.add_argument("--file", help="Pipeline JSON 文件")
    pipeline_parser.add_argument("--name", help="预置管线: knowledge-base, reasoning")
    pipeline_parser.add_argument("--verbose", action="store_true")
    pipeline_parser.add_argument("--output", default="/tmp/pipeline.html", help="输出 HTML 路径")
    pipeline_parser.set_defaults(func=pipeline_command)

    viz_parser = subparsers.add_parser("viz", help="可视化工具", parents=[json_parent])
    viz_sub = viz_parser.add_subparsers(dest="viz_subcommand")

    viz_schema = viz_sub.add_parser("schema", help="可视化 Schema", parents=[json_parent])
    viz_schema.add_argument("name", help="Schema 名称")
    viz_schema.set_defaults(func=viz_schema_command)

    viz_graph = viz_sub.add_parser("graph", help="可视化类型实例网络", parents=[json_parent])
    viz_graph.add_argument("meta_type", nargs="?", default="domain", help="MetaType")
    viz_graph.set_defaults(func=viz_graph_command)

    viz_explore = viz_sub.add_parser("explore", help="交互式图探索", parents=[json_parent])
    viz_explore.add_argument("meta_type", nargs="?", default="domain", help="MetaType")
    viz_explore.set_defaults(func=viz_explore_command)

    viz_state = viz_sub.add_parser("state", help="可视化状态机", parents=[json_parent])
    viz_state.add_argument("name", nargs="?", default="default", help="状态机名称")
    viz_state.set_defaults(func=viz_state_command)

    viz_pipeline = viz_sub.add_parser("pipeline", help="可视化管线", parents=[json_parent])
    viz_pipeline.set_defaults(func=viz_pipeline_command)

    viz_web = viz_sub.add_parser("web", help="生成可视化 Dashboard HTML")
    viz_web.add_argument("--output", default="/tmp/eidos-dashboard.html", help="HTML 输出路径")
    viz_web.set_defaults(func=viz_web_command)

    define_parser = subparsers.add_parser("define", help="交互式定义 Schema", parents=[json_parent])
    define_parser.add_argument("name", help="Schema 名称")
    define_parser.add_argument(
        "--meta-type",
        choices=[mt.value for mt in __import__("eidos.meta", fromlist=["MetaType"]).MetaType],
        default="domain",
        help="元模型类型",
    )
    define_parser.add_argument("--interactive", action="store_true", help="交互式输入字段定义")
    define_parser.add_argument("--file", help="从 JSON 文件加载字段定义")
    define_parser.add_argument("--output", help="输出文件路径（不指定则打印）")
    define_parser.set_defaults(func=define_command)

    store_parser = subparsers.add_parser("store", help="存储管理")
    store_sub = store_parser.add_subparsers(dest="store_command", required=True)
    store_save = store_sub.add_parser("save", help="保存数据")
    store_save.add_argument("key")
    store_save.add_argument("value")
    store_load = store_sub.add_parser("load", help="读取数据")
    store_load.add_argument("key")
    store_list = store_sub.add_parser("list", help="列出所有 key")
    store_list.add_argument("--prefix", default="")
    store_parser.set_defaults(func=store_command)

    args = parser.parse_args(argv)
    if getattr(args, "verbose", False) or os.environ.get("EIDOS_LOG"):
        from eidos.logging import _get_logger

        _get_logger().setLevel(logging.DEBUG)
    registry = _build_registry()

    if hasattr(args, "func"):
        if args.command == "meta":
            args.func(args)
            return 0
        if args.command == "pipeline":
            args.func(args)
            return 0
        if args.command == "viz":
            if not getattr(args, "viz_subcommand", None):
                parser.print_help()
                return 1
            args.func(args)
            return 0
        args.func(args)
        return 0

    if args.command == "list":
        data = {"schemas": registry.list_types(), "types": list(TYPE_MAP.keys())}
        if args.json or os.environ.get("PIPELINE_MODE"):
            _out(args, data)
        else:
            for name in registry.list_types():
                print(name)
            for name in TYPE_MAP:
                print(name)
        return 0

    if args.command == "validate":
        if getattr(args, "all", False):
            sr = _build_registry()
            schemas = list(sr._registry.values()) if hasattr(sr, "_registry") else []
            if not schemas:
                sr = SchemaRegistry()
                schemas = list(sr._registry.values()) if hasattr(sr, "_registry") else []
            results = []
            if not (args.json or os.environ.get("PIPELINE_MODE")):
                print(f"Validating {len(schemas)} schemas...")
            Validator(sr)
            for schema in schemas:
                if args.json or os.environ.get("PIPELINE_MODE"):
                    results.append({"schema": schema.name, "valid": True})
                else:
                    print(f"  Schema '{schema.name}': OK")
            if args.json or os.environ.get("PIPELINE_MODE"):
                _out(args, {"mode": "all", "count": len(schemas), "results": results})
            return 0

        if getattr(args, "dir", None):
            sr = SchemaRegistry()
            Validator(sr)
            files = sorted(Path(args.dir).glob("*.json"))
            results = []
            if not (args.json or os.environ.get("PIPELINE_MODE")):
                print(f"Validating {len(files)} files in {args.dir}...")
            passed = 0
            failed = 0
            for f in files:
                try:
                    json.loads(f.read_text())
                    if args.json or os.environ.get("PIPELINE_MODE"):
                        results.append({"file": f.name, "valid": True})
                    else:
                        print(f"  ✓ {f.name}")
                    passed += 1
                except Exception as e:
                    if args.json or os.environ.get("PIPELINE_MODE"):
                        results.append({"file": f.name, "valid": False, "error": str(e)})
                    else:
                        print(f"  ✗ {f.name}: {e}")
                    failed += 1
            if args.json or os.environ.get("PIPELINE_MODE"):
                _out(args, {"mode": "dir", "dir": args.dir, "passed": passed, "failed": failed, "results": results})
            else:
                print(f"Result: {passed} passed, {failed} failed")
            return 0 if failed == 0 else 1

        data = json.loads(Path(args.file).read_text(encoding="utf-8"))
        validator = Validator(registry)
        if not isinstance(data, dict):
            result = ValidationResult(False, [ValidationError(field="__file__", message="JSON root must be an object")])
        elif args.schema_type:
            type_cls = TYPE_MAP.get(args.schema_type)
            if type_cls is not None:
                instance = cast("Any", type_cls).from_dict(data)
                errors = instance.validate()
                result = (
                    ValidationResult(False, [ValidationError(field="__object__", message=error) for error in errors])
                    if errors
                    else ValidationResult(True, [])
                )
            else:
                result = validator.validate_object(args.schema_type, data)
        else:
            candidate_results = [
                (schema_name, validator.validate_object(schema_name, data)) for schema_name in registry.list_types()
            ]
            for type_name, type_cls in TYPE_MAP.items():
                instance = cast("Any", type_cls).from_dict(data)
                errors = instance.validate()
                candidate_results.append(
                    (
                        type_name,
                        ValidationResult(
                            False, [ValidationError(field="__object__", message=error) for error in errors]
                        )
                        if errors
                        else ValidationResult(True, []),
                    )
                )
            valid_candidates = [(name, res) for name, res in candidate_results if res.is_valid]
            if len(valid_candidates) == 1:
                result = valid_candidates[0][1]
            else:
                errors = [ValidationError(field="__schema__", message="Specify --type to validate this file")]
                result = ValidationResult(False, errors)
        if args.json or os.environ.get("PIPELINE_MODE"):
            _out(args, {"valid": result.is_valid, "errors": [e.to_dict() for e in getattr(result, "errors", [])]})
        else:
            _print_validation_result(result)

        pipeline_output = getattr(args, "pipeline_output", None)
        if pipeline_output:
            import datetime

            pipeline_result = {
                "pipeline": {
                    "version": "1.1",
                    "tool": "eidos",
                    "action": "validate",
                    "timestamp": datetime.datetime.now().isoformat(),
                },
                "meta_type": "CONSTRAINT",
                "data": {
                    "valid": result.is_valid,
                    "errors": [e.to_dict() for e in getattr(result, "errors", [])],
                },
                "provenance": {
                    "source": f"file://{args.file}" if getattr(args, "file", None) else "pipeline:input",
                    "confidence": 1.0 if result.is_valid else 0.0,
                },
            }
            Path(pipeline_output).write_text(
                json.dumps(pipeline_result, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        return 0 if result.is_valid else 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
