"""Eidos Pipeline — orchestrate ontology tool chains sequentially."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PipelineStep:
    tool: str
    action: str
    args: dict = field(default_factory=dict)
    positionals: list = field(default_factory=list)
    input_file: str = ""
    output_file: str = ""

    def to_cli(self) -> list[str]:
        cmd = []
        if self.tool == "eidos":
            cmd = [sys.executable, "-m", "eidos.cli", self.action]
        elif self.tool == "kos":
            cmd = [sys.executable, "-m", "kos.cli", self.action]
        elif self.tool == "minerva":
            cmd = [sys.executable, "-m", "minerva.cli", self.action]
        elif self.tool == "ontoderive":
            cmd = [sys.executable, "-m", "ontoderive.cli", self.action]
        else:
            raise ValueError(f"Unknown tool: {self.tool}")
        for p in self.positionals:
            cmd.append(str(p))
        for k, v in self.args.items():
            if isinstance(v, bool):
                if v:
                    cmd.append(f"--{k}")
            else:
                cmd.extend([f"--{k}", str(v)])
        if self.input_file:
            cmd.extend(["--pipeline-input", self.input_file])
        if self.output_file:
            cmd.extend(["--pipeline-output", self.output_file])
        return cmd


@dataclass
class Pipeline:
    name: str
    steps: list[PipelineStep]
    description: str = ""
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> Pipeline:
        steps = [PipelineStep(**s) for s in d.get("steps", [])]
        return cls(
            name=d.get("name", ""), steps=steps, description=d.get("description", ""), metadata=d.get("metadata", {})
        )

    @classmethod
    def load(cls, path: str | Path) -> Pipeline:
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def run_pipeline(pipeline: Pipeline, verbose: bool = False) -> int:
    import os

    _base = Path(__file__).resolve().parents[3]  # Workspace/
    temp_dir = Path("/tmp/eidos-pipeline")
    temp_dir.mkdir(parents=True, exist_ok=True)
    prev_output = ""
    for i, step in enumerate(pipeline.steps):
        step_output = str(temp_dir / f"step_{i}.json")
        if prev_output and not step.input_file:
            step.input_file = prev_output
        if not step.output_file:
            step.output_file = step_output
        cmd = step.to_cli()
        if verbose:
            print(f"[{i + 1}/{len(pipeline.steps)}] {' '.join(cmd)}", file=sys.stderr)
        env = {
            **os.environ,
            "PYTHONPATH": (
                f"{_base / 'eidos' / 'src'}:{_base / 'kos'}:{_base / 'minerva' / 'src'}:{_base / 'ontoderive'}"
            ),
            "PIPELINE_MODE": "1",
        }
        result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=300)
        if result.returncode != 0:
            print(f"Step {step.tool} {step.action} FAILED: {result.stderr[:300]}", file=sys.stderr)
            return 1
        if verbose and result.stdout.strip():
            print(result.stdout[:200])
        prev_output = step.output_file
    if verbose:
        print(f"\nPipeline '{pipeline.name}' done.", file=sys.stderr)
    return 0
