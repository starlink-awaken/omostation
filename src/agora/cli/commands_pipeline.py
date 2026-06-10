"""Pipeline commands: pipeline, pipelines, pipeline-define."""

from __future__ import annotations

import asyncio
import json

from agora.cli.errors import CLIError
from agora.cli.output import OutputFormatter
from agora.core.router import Router  # type: ignore[import-not-found]
from agora.core.state import get_registry  # type: ignore[import-not-found]
from agora.pipeline import Pipeline  # type: ignore[import-not-found]


def cmd_pipeline(args):
    """Run a named pipeline."""
    out = OutputFormatter(json_mode=getattr(args, "json", False))
    try:
        registry = get_registry()
        router = Router(registry)
        pl = Pipeline(registry, router)
        variables = {
            "goal": args.goal,
            "context": args.context,
            "project": args.project,
        }

        if args.stream:

            async def _stream():
                async for step in pl.run_stream(args.name, variables):
                    icon = "OK" if step["status"] == "ok" else "FAIL"
                    print(
                        f"  {icon} Step {step['step']}: {step['tool']} - {step['status']}"
                    )
                    if "error" in step:
                        print(f"     Error: {step['error']}")

            try:
                asyncio.run(_stream())
            except Exception as e:
                raise CLIError(
                    f"Pipeline stream failed: {e}",
                    suggestion="检查 Pipeline 定义和工具状态",
                )
        elif args.parallel:
            try:
                result = asyncio.run(pl.run_parallel(args.name, variables))
            except Exception as e:
                raise CLIError(
                    f"Pipeline parallel execute failed: {e}",
                    suggestion="检查 Pipeline 定义和工具状态",
                )
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print(f"Pipeline: {result['pipeline']} (parallel)")
                for r in result["results"]:
                    status_icon = "OK" if r["status"] == "ok" else "FAIL"
                    print(
                        f"  {status_icon} Step {r['step']}: {r['tool']} - {r['status']}"
                    )
                    if "error" in r:
                        print(f"     Error: {r['error']}")
        else:
            try:
                result = asyncio.run(pl.run(args.name, variables))
            except Exception as e:
                raise CLIError(
                    f"Pipeline execute failed: {e}",
                    suggestion="检查 Pipeline 定义和工具状态",
                )
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print(f"Pipeline: {result['pipeline']}")
                for r in result["results"]:
                    status_icon = "OK" if r["status"] == "ok" else "FAIL"
                    print(
                        f"  {status_icon} Step {r['step']}: {r['tool']} - {r['status']}"
                    )
                    if "error" in r:
                        print(f"     Error: {r['error']}")
        return 0
    except CLIError as e:
        out.print_error(e.message, e.suggestion)
        return e.exit_code
    except Exception as e:
        out.print_error(str(e), "使用 'agora --help' 获取帮助")
        return 1


def cmd_pipelines(args):
    """List available pipelines."""
    out = OutputFormatter(json_mode=getattr(args, "json", False))
    try:
        registry = get_registry()
        router = Router(registry)
        pl = Pipeline(registry, router)
        for name in pl.list_pipelines():
            print(f"• {name}")
            steps = pl.get_pipeline(name)
            if steps:
                for s in steps:
                    print(f"    -> {s['tool']}")
        return 0
    except CLIError as e:
        out.print_error(e.message, e.suggestion)
        return e.exit_code
    except Exception as e:
        out.print_error(str(e), "使用 'agora --help' 获取帮助")
        return 1


def cmd_pipeline_define(args):
    """Define a custom pipeline from JSON file."""
    out = OutputFormatter(json_mode=getattr(args, "json", False))
    try:
        registry = get_registry()
        router = Router(registry)
        pl = Pipeline(registry, router)
        name = pl.load_definition(args.file)
        print(f"Pipeline loaded: {name}")
        return 0
    except CLIError as e:
        out.print_error(e.message, e.suggestion)
        return e.exit_code
    except Exception as e:
        out.print_error(str(e), "使用 'agora --help' 获取帮助")
        return 1
