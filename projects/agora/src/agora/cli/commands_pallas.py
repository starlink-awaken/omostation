"""Pallas commands — Knowledge engineering toolset (merged from pallas CLI).

Usage via agora:
    agora pallas match "xxx"              # ToolForge tool matching
    agora pallas derive --project .       # OntoDerive derivation
    agora pallas check --project .        # Protocol check
    agora pallas pipeline --goal "xxx"    # Full pipeline: match -> derive -> check
    agora pallas init myproject           # Initialize project
    agora pallas toolbox search "query"   # Forge toolbox
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from agora.cli.errors import CLIError
from agora.cli.output import OutputFormatter

EXPECTED_FORMAT_VERSION = "ontoderive-v1"


def _validate_json_output(output: str, desc: str = "") -> dict | None:
    try:
        data = json.loads(output)
        if isinstance(data, dict) and "format_version" in data:
            ver = data["format_version"]
            if ver != EXPECTED_FORMAT_VERSION:
                print(
                    json.dumps(
                        {
                            "ok": False,
                            "description": desc,
                            "error": f"Format version mismatch: expected {EXPECTED_FORMAT_VERSION}, got {ver}",
                        }
                    )
                )
                sys.exit(1)
        return data
    except (json.JSONDecodeError, ValueError):
        return None


def _run_cli(cmd: list[str], desc: str = "") -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        error = {
            "ok": False,
            "format_version": "pallas-v1",
            "cmd": " ".join(cmd),
            "exit_code": result.returncode,
            "stderr": result.stderr.strip()[:500],
            "description": desc,
        }
        print(json.dumps(error, ensure_ascii=False))
        sys.exit(result.returncode)
    if result.stdout:
        _validate_json_output(result.stdout, desc)
        print(result.stdout)
    return result


def _find_cli(cmd: str, pkg: str) -> str | None:
    path = shutil.which(cmd)
    if path:
        return cmd
    venv_bin = Path(sys.executable).parent
    full = venv_bin / cmd
    if full.exists():
        return str(full)
    try:
        workspace = Path(__file__).resolve().parent.parent.parent.parent.parent
        fallback = workspace / cmd / ".venv" / "bin" / cmd
        if fallback.exists():
            return str(fallback)
    except Exception:
        pass
    print(f"  {cmd} CLI not found -> pip install ontoderive")
    return None


def pcmd_match(args):
    out = OutputFormatter(json_mode=getattr(args, "json", False))
    try:
        _ontoderive_cmd = _find_cli("ontoderive", "ontoderive")
        if not _ontoderive_cmd:
            return 1
        cmd = [_ontoderive_cmd, "toolforge", args.goal]
        if args.context:
            cmd.extend(["--context", args.context])
        if args.inference_guide:
            cmd.append("--inference-guide")
        elif args.json:
            cmd.append("--json")
        _run_cli(cmd, "ontoderive toolforge")
    except CLIError as e:
        out.print_error(e.message, e.suggestion)
        return e.exit_code
    except Exception as e:
        out.print_error(str(e), "使用 'agora --help' 获取帮助")
        return 1


def pcmd_derive(args):
    out = OutputFormatter(json_mode=getattr(args, "json", False))
    try:
        _ontoderive_cmd = _find_cli("ontoderive", "ontoderive")
        if not _ontoderive_cmd:
            return 1
        cmd = [_ontoderive_cmd, "derive", "--project", args.project]
        if args.with_tools:
            cmd.append("--with-tools")
            if args.goal:
                cmd.extend(["--goal", args.goal])
            if args.tool_context:
                cmd.extend(["--tool-context", args.tool_context])
        _run_cli(cmd, "ontoderive derive")
    except CLIError as e:
        out.print_error(e.message, e.suggestion)
        return e.exit_code
    except Exception as e:
        out.print_error(str(e), "使用 'agora --help' 获取帮助")
        return 1


def pcmd_check(args):
    out = OutputFormatter(json_mode=getattr(args, "json", False))
    try:
        _ontoderive_cmd = _find_cli("ontoderive", "ontoderive")
        if not _ontoderive_cmd:
            return 1
        cmd = [_ontoderive_cmd, "check", "--project", args.project]
        _run_cli(cmd, "ontoderive check")
    except CLIError as e:
        out.print_error(e.message, e.suggestion)
        return e.exit_code
    except Exception as e:
        out.print_error(str(e), "使用 'agora --help' 获取帮助")
        return 1


def pcmd_pipeline(args):
    out = OutputFormatter(json_mode=getattr(args, "json", False))
    try:
        _ontoderive_cmd = _find_cli("ontoderive", "ontoderive")
        if not _ontoderive_cmd:
            return 1
        goal = args.goal
        project = args.project
        context = args.context or ""

        print(f"\n{'=' * 60}")
        print("  Pallas full pipeline")
        print(f"  Goal: {goal}")
        print(f"  Project: {project}")
        print(f"{'=' * 60}\n")

        print("- Step 1/3: ToolForge matching")
        cmd = [_ontoderive_cmd, "toolforge", goal, "--inference-guide"]
        if context:
            cmd.extend(["--context", context])
        subprocess.run(cmd)

        print("\n- Step 2/3: OntoDerive derivation")
        cmd = [
            _ontoderive_cmd,
            "derive",
            "--project",
            project,
            "--with-tools",
            "--goal",
            goal,
        ]
        if context:
            cmd.extend(["--tool-context", context])
        _run_cli(cmd, "pipeline derive")

        print("\n- Step 3/3: Protocol check")
        _run_cli([_ontoderive_cmd, "check", "--project", project], "pipeline check")

        print(f"\n{'=' * 60}")
        print("  Pipeline complete")
        print(f"  Guide: {project}/inferences/_toolforge_guide.md")
        print(f"{'=' * 60}\n")
    except CLIError as e:
        out.print_error(e.message, e.suggestion)
        return e.exit_code
    except Exception as e:
        out.print_error(str(e), "使用 'agora --help' 获取帮助")
        return 1


def pcmd_init(args):
    out = OutputFormatter(json_mode=getattr(args, "json", False))
    try:
        _ontoderive_cmd = _find_cli("ontoderive", "ontoderive")
        if not _ontoderive_cmd:
            return 1
        cmd = [_ontoderive_cmd, "init", args.name]
        subprocess.run(cmd)
    except CLIError as e:
        out.print_error(e.message, e.suggestion)
        return e.exit_code
    except Exception as e:
        out.print_error(str(e), "使用 'agora --help' 获取帮助")
        return 1


def pcmd_serve(args):
    out = OutputFormatter(json_mode=getattr(args, "json", False))
    try:
        out.print_info("Starting Agora MCP Hub...")
        agora_path = shutil.which("agora")
        if agora_path:
            _run_cli(["agora", "sync"], "agora sync")
    except CLIError as e:
        out.print_error(e.message, e.suggestion)
        return e.exit_code
    except Exception as e:
        out.print_error(str(e), "使用 'agora --help' 获取帮助")
        return 1


FORGE_MCP = "forge-bridge"


def _forge_mcp_call(tool_name: str, arguments: dict | None = None) -> dict | None:
    forge_path = _find_cli(FORGE_MCP, "forge")
    if not forge_path:
        return None
    try:
        if tool_name in ("ai_toolbox_status", "ai_toolbox_health"):
            cmd = [forge_path, "status"]
        elif tool_name == "search_tools_mcp":
            q = (arguments or {}).get("query", "")
            cmd = [forge_path, "search", q]
        elif tool_name == "query_graph_mcp":
            q = (arguments or {}).get("query", "")
            cmd = [forge_path, "graph", q]
        else:
            print(f"  Forge: unknown tool {tool_name}", file=sys.stderr)
            return None
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if cp.returncode != 0:
            print(f"  Forge error: {cp.stderr.strip()[:200]}", file=sys.stderr)
            return None
        return json.loads(cp.stdout)
    except Exception as e:
        print(f"  Forge call failed: {e}", file=sys.stderr)
        return None


def pcmd_toolbox(args):
    out = OutputFormatter(json_mode=getattr(args, "json", False))
    try:
        if args.toolbox_command == "search":
            print(f"Searching tools: {args.query}")
            result = _forge_mcp_call("search_tools_mcp", {"query": args.query})
            if result:
                tools = result.get("tools", [])
                print(f"  Matched {len(tools)} tools")
                for tool in tools[:10]:
                    cats = ", ".join(tool.get("category", []))
                    print(f"  [{cats}] {tool.get('name', '?')}")
                    print(f"    {tool.get('notes', '')[:120]}")
        elif args.toolbox_command == "status":
            result = _forge_mcp_call("ai_toolbox_status")
            if result:
                print("Forge status")
                print(
                    f"  Tool count: {result.get('tools', result.get('tool_count', '?'))}"
                )
                g = result.get("graph", {})
                print(f"  Graph nodes: {g.get('total_nodes', '?')}")
                print(f"  Graph edges: {g.get('total_edges', '?')}")
        elif args.toolbox_command == "graph":
            print(f"Querying knowledge graph: {args.query}")
            result = _forge_mcp_call("query_graph_mcp", {"query": args.query})
            if result:
                nodes = result.get("nodes", result)
                count = result.get(
                    "count", len(nodes) if isinstance(nodes, list) else 0
                )
                print(f"  Matched {count} nodes")
                for node in (nodes if isinstance(nodes, list) else [])[:20]:
                    print(
                        f"  - {node.get('label', node.get('id', '?'))}  [{node.get('type', '?')}]"
                    )
        return 0
    except CLIError as e:
        out.print_error(e.message, e.suggestion)
        return e.exit_code
    except Exception as e:
        out.print_error(str(e), "使用 'agora --help' 获取帮助")
        return 1


def add_pallas_subparser(subparsers):
    """Add the 'pallas' subcommand group to an argparse subparsers object."""
    p = subparsers.add_parser(
        "pallas",
        help="Knowledge engineering toolset (match/derive/check/pipeline/toolbox)",
    )
    p_sub = p.add_subparsers(dest="pallas_cmd", help="Pallas subcommand")

    # match
    m = p_sub.add_parser("match", help="ToolForge tool matching")
    m.add_argument("goal", help="Goal description")
    m.add_argument("--context", default="", help="Context keywords")
    m.add_argument(
        "--inference-guide", action="store_true", help="Output inference guide"
    )
    m.add_argument("--json", action="store_true", help="JSON output")

    # derive
    d = p_sub.add_parser("derive", help="OntoDerive fact derivation")
    d.add_argument("--project", default=".", help="Project path")
    d.add_argument(
        "--with-tools", action="store_true", help="Pre-run ToolForge matching"
    )
    d.add_argument("--goal", default="", help="Goal description")
    d.add_argument("--tool-context", default="", help="ToolForge context")

    # check
    c = p_sub.add_parser("check", help="Protocol check")
    c.add_argument("--project", default=".", help="Project path")

    # pipeline
    pl = p_sub.add_parser("pipeline", help="Full pipeline: match -> derive -> check")
    pl.add_argument("--goal", required=True, help="Goal description")
    pl.add_argument("--project", default=".", help="Project path")
    pl.add_argument("--context", default="", help="Context keywords")

    # init
    i = p_sub.add_parser("init", help="Initialize new project")
    i.add_argument("name", help="Project name")

    # serve
    p_sub.add_parser("serve", help="Start Agora MCP Hub")

    # toolbox
    tb = p_sub.add_parser("toolbox", help="Forge toolbox -- search/status/graph")
    tb_sub = tb.add_subparsers(dest="toolbox_command", help="Toolbox subcommand")
    tb_search = tb_sub.add_parser("search", help="Search Forge registry")
    tb_search.add_argument("query", help="Search keyword")
    tb_sub.add_parser("status", help="Forge status overview")
    tb_graph = tb_sub.add_parser("graph", help="Query knowledge graph")
    tb_graph.add_argument("query", help="Graph query keyword")


def dispatch_pallas(args):
    """Dispatch pallas subcommand."""
    out = OutputFormatter(json_mode=getattr(args, "json", False))
    try:
        commands = {
            "match": pcmd_match,
            "derive": pcmd_derive,
            "check": pcmd_check,
            "pipeline": pcmd_pipeline,
            "init": pcmd_init,
            "serve": pcmd_serve,
            "toolbox": pcmd_toolbox,
        }
        handler = commands.get(args.pallas_cmd)
        if handler:
            return handler(args)
        else:
            print(
                "Usage: agora pallas {match|derive|check|pipeline|init|serve|toolbox} [options]"
            )
            return 1
    except CLIError as e:
        out.print_error(e.message, e.suggestion)
        return e.exit_code
    except Exception as e:
        out.print_error(str(e), "使用 'agora --help' 获取帮助")
        return 1
