"""Eidos Pipeline — registered as an Agora MCP service."""

import subprocess
from typing import Any

EIDOS_PIPELINE_SERVICE: dict[str, Any] = {
    "name": "eidos-pipeline",
    "type": "service",
    "version": "0.1.0",
    "description": "Eidos ontology pipeline service",
    "capabilities": [
        "pipeline:knowledge-base",
        "pipeline:reasoning",
        "tool:validate",
        "tool:meta",
        "tool:list",
        "tool:define",
        "tool:mcp-server",
    ],
    "transport": "stdio",
    "commands": {
        "knowledge-base": "eidos pipeline --name knowledge-base --verbose",
        "reasoning": "eidos pipeline --name reasoning --verbose",
        "validate": "eidos validate --type KnowledgeCard",
        "meta": "eidos meta",
        "list": "eidos list",
    },
}


def route(action: str) -> list[str]:
    cmd_str = EIDOS_PIPELINE_SERVICE["commands"].get(action)
    if not cmd_str:
        raise ValueError(f"Unknown: {action}. Available: {list(EIDOS_PIPELINE_SERVICE['commands'].keys())}")
    return cmd_str.split()


def execute(action: str, *args, **kwargs):
    cmd = route(action)
    if args:
        cmd.extend(str(a) for a in args)
    for k, v in kwargs.items():
        cmd.extend([f"--{k.replace('_', '-')}", str(v)])
    return subprocess.run(cmd, capture_output=True, text=True)
