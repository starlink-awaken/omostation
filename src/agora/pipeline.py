"""Pipeline Orchestrator — chain multiple MCP tool calls into a workflow.

Usage:
    pipeline = Pipeline(registry, router)
    # Sequential
    result = await pipeline.run("full-pipeline", {"goal": "...", "project": "."})
    # Streaming (yield each step)
    async for step in pipeline.run_stream("full-pipeline", {"goal": "...", "project": "."}):
        print(step)
    # Parallel (independent steps)
    result = await pipeline.run_parallel("full-pipeline", {"goal": "...", "project": "."})
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import structlog

from agora.auth.identity import normalize_identity  # type: ignore[import-not-found]

logger = structlog.get_logger(__name__)


class Pipeline:
    """Defines and executes multi-step MCP tool call pipelines.

    Supports three execution modes:
    - Sequential (run): each step waits for the previous
    - Streaming (run_stream): yield each step as it completes
    - Parallel (run_parallel): independent steps execute concurrently

    When event_bus is provided, each step publishes pipeline events:
      pipeline:started, pipeline:step:ok, pipeline:step:error, pipeline:completed
    """

    def __init__(self, registry, router, event_bus=None):
        self.registry = registry
        self.router = router
        self._event_bus = event_bus
        self._definitions: dict[str, list[dict]] = {}
        self._load_builtins()

    def _load_builtins(self):
        """Load built-in pipeline definitions from external config."""
        builtin_path = (
            Path(__file__).with_suffix("").parent / "pipelines" / "builtin.json"
        )
        try:
            data = json.loads(builtin_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self._definitions.update(data)
        except FileNotFoundError:
            logger.warning("builtin_pipelines_not_found", path=str(builtin_path))
        except Exception as e:
            logger.warning(
                "builtin_pipelines_load_failed", path=str(builtin_path), error=str(e)
            )

    def define(self, name: str, steps: list[dict]):
        """Register a custom pipeline definition."""
        self._definitions[name] = steps

    def list_pipelines(self) -> list[str]:
        """List available pipeline names."""
        return list(self._definitions.keys())

    def get_pipeline(self, name: str) -> list[dict] | None:
        """Get pipeline definition by name."""
        return self._definitions.get(name)

    async def run(
        self,
        name: str,
        variables: dict[str, Any],
        caller_identity: Any = None,
    ) -> dict[str, Any]:
        """Execute a named pipeline sequentially."""
        results = []
        async for step in self.run_stream(
            name, variables, caller_identity=caller_identity
        ):
            results.append(step)
        return {
            "pipeline": name,
            "variables": variables,
            "results": results,
            "outputs": {
                r["tool"]: r.get("output", "")[:200]
                for r in results
                if r["status"] == "ok"
            },
        }

    def _publish(self, event_type: str, payload: dict):
        """Publish event via event bus if configured."""
        if self._event_bus:
            self._event_bus.publish(event_type, payload, source="pipeline")

    def _identity_payload(self, caller_identity: Any) -> dict[str, Any] | None:
        identity = normalize_identity(caller_identity)
        return identity.to_payload() if identity else None

    async def run_stream(
        self,
        name: str,
        variables: dict[str, Any],
        caller_identity: Any = None,
    ) -> AsyncIterator[dict]:
        """Execute pipeline and yield each step as it completes (streaming)."""
        steps = self._definitions.get(name)
        if not steps:
            yield {"status": "error", "error": f"Pipeline not found: {name}"}
            return

        outputs: dict[str, Any] = {}
        identity_payload = self._identity_payload(caller_identity)
        started_payload = {
            "pipeline": name,
            "variables": variables,
            "step_count": len(steps),
        }
        if identity_payload:
            started_payload["identity"] = identity_payload
        self._publish("pipeline:started", started_payload)

        for i, step in enumerate(steps):
            tool_name = step["tool"]
            args = self._render_args(step.get("args", {}), variables, outputs)
            label = step.get("output_as", f"step_{i}")

            logger.info("pipeline_step", pipeline=name, step=i, tool=tool_name)

            try:
                result = await self.router.route(
                    tool_name, args, caller_id=caller_identity or "pipeline"
                )
                outputs[label] = result
                ok_payload = {
                    "pipeline": name,
                    "step": i,
                    "tool": tool_name,
                    "output_as": label,
                }
                if identity_payload:
                    ok_payload["identity"] = identity_payload
                self._publish("pipeline:step:ok", ok_payload)
                yield {
                    "step": i,
                    "tool": tool_name,
                    "status": "ok",
                    "output": str(result)[:200],
                }
            except Exception as e:
                logger.error(
                    "pipeline_step_failed", pipeline=name, step=i, error=str(e)
                )
                error_payload = {
                    "pipeline": name,
                    "step": i,
                    "tool": tool_name,
                    "error": str(e),
                }
                if identity_payload:
                    error_payload["identity"] = identity_payload
                self._publish("pipeline:step:error", error_payload)
                yield {"step": i, "tool": tool_name, "status": "error", "error": str(e)}
                if step.get("critical", False):
                    break

        completed_payload = {"pipeline": name}
        if identity_payload:
            completed_payload["identity"] = identity_payload
        self._publish("pipeline:completed", completed_payload)

    async def run_parallel(
        self,
        name: str,
        variables: dict[str, Any],
        caller_identity: Any = None,
    ) -> dict[str, Any]:
        """Execute independent pipeline steps in parallel.

        Groups steps by dependency level — each level runs concurrently.
        Steps within a level that have no inter-dependencies execute in parallel.
        """
        steps = self._definitions.get(name)
        if not steps:
            return {"status": "error", "error": f"Pipeline not found: {name}"}

        outputs: dict[str, Any] = {}

        # Group steps by whether they have unmet dependencies
        remaining = list(enumerate(steps))
        results = []

        while remaining:
            # Find steps with all dependencies met
            ready = []
            still_waiting = []
            for i, step in remaining:
                deps = step.get("depends_on", [])
                if all(d in outputs for d in deps):
                    ready.append((i, step))
                else:
                    still_waiting.append((i, step))

            if not ready and still_waiting:
                # Deadlock: remaining steps have unresolvable deps
                for i, step in still_waiting:
                    results.append(
                        {
                            "step": i,
                            "tool": step["tool"],
                            "status": "error",
                            "error": "Unresolved dependency",
                        }
                    )
                break

            # Execute ready steps in parallel
            async def _exec(i, step):
                tool_name = step["tool"]
                args = self._render_args(step.get("args", {}), variables, outputs)
                label = step.get("output_as", f"step_{i}")
                try:
                    result = await self.router.route(
                        tool_name, args, caller_id=caller_identity or "pipeline"
                    )
                    return i, label, result, None
                except Exception as e:
                    return i, label, None, str(e)

            tasks = [_exec(i, step) for i, step in ready]
            batch_results = await asyncio.gather(*tasks)

            critical_failed = False
            for i, label, result, error in batch_results:
                step = steps[i]
                if error:
                    results.append(
                        {
                            "step": i,
                            "tool": step["tool"],
                            "status": "error",
                            "error": error,
                        }
                    )
                    if step.get("critical", False):
                        critical_failed = True
                        break
                else:
                    outputs[label] = result
                    results.append({"step": i, "tool": step["tool"], "status": "ok"})

            remaining = [] if critical_failed else still_waiting

        return {
            "pipeline": name,
            "variables": variables,
            "results": results,
            "outputs": {k: str(v)[:500] for k, v in outputs.items()},
        }

    def _render_args(
        self,
        args: dict[str, Any],
        variables: dict[str, Any],
        previous_outputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Render template variables in args: {{goal}} → variables['goal']"""
        rendered = {}
        for key, value in args.items():
            if isinstance(value, str) and "{{" in value:
                # Simple template substitution
                result = value
                for vk, vv in variables.items():
                    result = result.replace(f"{{{{{vk}}}}}", str(vv))
                rendered[key] = result
            else:
                rendered[key] = value
        return rendered

    def save_definition(self, name: str, path: str | Path):
        """Save a pipeline definition to a JSON file."""
        steps = self._definitions.get(name)
        if not steps:
            raise ValueError(f"Pipeline not found: {name}")
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps({"name": name, "steps": steps}, indent=2, ensure_ascii=False)
        )

    def load_definition(self, path: str | Path):
        """Load a pipeline definition from a JSON file."""
        data = json.loads(Path(path).read_text())
        self.define(data["name"], data["steps"])
        return data["name"]
