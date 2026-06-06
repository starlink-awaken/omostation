"""Pipeline commands: pipeline, pipelines, pipeline-define."""

from __future__ import annotations

import asyncio
import json

from agora.core.router import Router  # type: ignore[import-not-found]
from agora.core.state import get_registry  # type: ignore[import-not-found]
from agora.pipeline import Pipeline  # type: ignore[import-not-found]


def cmd_pipeline(args):
    """Run a named pipeline."""
    registry = get_registry()
    router = Router(registry)
    pl = Pipeline(registry, router)
    variables = {"goal": args.goal, "context": args.context, "project": args.project}

    if args.stream:

        async def _stream():
            async for step in pl.run_stream(args.name, variables):
                icon = "OK" if step["status"] == "ok" else "FAIL"
                print(f"  {icon} Step {step['step']}: {step['tool']} - {step['status']}")
                if "error" in step:
                    print(f"     Error: {step['error']}")

        asyncio.run(_stream())
    elif args.parallel:
        result = asyncio.run(pl.run_parallel(args.name, variables))
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"Pipeline: {result['pipeline']} (parallel)")
            for r in result["results"]:
                status_icon = "OK" if r["status"] == "ok" else "FAIL"
                print(f"  {status_icon} Step {r['step']}: {r['tool']} - {r['status']}")
                if "error" in r:
                    print(f"     Error: {r['error']}")
    else:
        result = asyncio.run(pl.run(args.name, variables))
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"Pipeline: {result['pipeline']}")
            for r in result["results"]:
                status_icon = "OK" if r["status"] == "ok" else "FAIL"
                print(f"  {status_icon} Step {r['step']}: {r['tool']} - {r['status']}")
                if "error" in r:
                    print(f"     Error: {r['error']}")


def cmd_pipelines(_args):
    """List available pipelines."""
    registry = get_registry()
    router = Router(registry)
    pl = Pipeline(registry, router)
    for name in pl.list_pipelines():
        print(f"• {name}")
        steps = pl.get_pipeline(name)
        if steps:
            for s in steps:
                print(f"    -> {s['tool']}")


def cmd_pipeline_define(args):
    """Define a custom pipeline from JSON file."""
    registry = get_registry()
    router = Router(registry)
    pl = Pipeline(registry, router)
    name = pl.load_definition(args.file)
    print(f"Pipeline loaded: {name}")
