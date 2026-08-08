#!/usr/bin/env python3
"""Digital Organism Dashboard — standalone HTML dashboard (P3-T1).

Reads agent registry, scene cards, journey specs, mesh events,
outcomes, problems, and proposals. Generates standalone HTML.

Usage: python3 bin/ssot/dashboard.py [--output dashboard.html]
       Then open the HTML file in a browser.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    result = []
    for line in path.read_text(encoding="utf-8").strip().split("\n"):
        if line:
            try:
                result.append(json.loads(line))
            except Exception:
                pass
    return result


def _count_yaml(dir_path: Path) -> int:
    return len(list(dir_path.glob("*.yaml"))) if dir_path.is_dir() else 0


def gather_status() -> dict[str, Any]:
    """Gather all status data for dashboard."""
    # Agents
    agents = []
    agents_dir = ROOT / ".omo" / "_truth" / "registry" / "agents"
    if agents_dir.is_dir():
        import yaml
        for p in sorted(agents_dir.glob("*.yaml")):
            try:
                d = yaml.safe_load(p.read_text(encoding="utf-8"))
                if isinstance(d, dict):
                    agents.append(d)
            except Exception:
                pass

    # Counts
    cards = _count_yaml(ROOT / "docs" / "scene-cards")
    journeys = _count_yaml(ROOT / "docs" / "journey-specs")

    # Recent events
    mesh_events = _load_jsonl(ROOT / ".omo" / "_knowledge" / "workflow-mesh" / "mesh-events.jsonl")
    outcomes = _load_jsonl(ROOT / ".omo" / "_knowledge" / "workflow-mesh" / "scene-outcomes.jsonl")
    reflections = _load_jsonl(ROOT / ".omo" / "_knowledge" / "workflow-mesh" / "scene-reflections.jsonl")

    # Problems (inline)
    problems = []
    try:
        r = subprocess.run(["python3", str(ROOT / "bin/ssot/problem-detector.py"), "--json"],
                           capture_output=True, text=True, timeout=10, check=False)
        if r.stdout:
            problems = json.loads(r.stdout).get("problems", [])
    except Exception:
        pass

    # Evolution proposals (inline)
    proposals = []
    try:
        r = subprocess.run(["python3", str(ROOT / "bin/ssot/evolution-agent.py"), "--json"],
                           capture_output=True, text=True, timeout=10, check=False)
        if r.stdout:
            proposals = json.loads(r.stdout).get("proposals", [])
    except Exception:
        pass

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "agents": agents, "agent_count": len(agents),
        "scene_cards": cards, "journey_specs": journeys,
        "mesh_events": len(mesh_events), "outcomes": len(outcomes),
        "reflections": len(reflections),
        "problems": problems, "problem_count": len(problems),
        "proposals": proposals, "proposal_count": len(proposals),
        "recent_outcomes": outcomes[-5:],
        "recent_mesh_events": mesh_events[-5:],
    }


def generate_html(status: dict[str, Any]) -> str:
    """Generate standalone HTML dashboard."""
    agents_html = "".join(
        f"<tr><td>{a.get('agent_id','?')}</td><td>{a.get('tier','?')}</td>"
        f"<td>{a.get('status','?')}</td><td>{a.get('version','?')}</td>"
        f"<td>{a.get('performance',{}).get('trust_score',0.5)}</td>"
        f"<td>{a.get('identity',{}).get('role','?')}</td></tr>"
        for a in status["agents"]
    )
    problems_html = "".join(
        f"<li><b>[{p.get('severity','?').upper()}]</b> {p.get('type','?')}: {p.get('detail','')}</li>"
        for p in status["problems"]
    ) or "<li>✅ No problems detected</li>"
    proposals_html = "".join(
        f"<li><b>[{p.get('level','?')}]</b> {p.get('proposal','')}</li>"
        for p in status["proposals"]
    ) or "<li>✅ No proposals</li>"
    outcomes_html = "".join(
        f"<li>{o.get('ts','?')[:19]} {o.get('scene_id','?')} → <b>{o.get('adjudication','?')}</b></li>"
        for o in status["recent_outcomes"]
    ) or "<li>No outcomes recorded</li>"

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>数字生命体 Dashboard</title>
<style>
body {{ font-family: system-ui; margin: 20px; background: #1a1a2e; color: #e0e0e0; }}
h1 {{ color: #0f3460; }} h2 {{ color: #16213e; border-bottom: 1px solid #333; }}
.grid {{ display: grid; grid-template-columns: repeat(4,1fr); gap: 15px; margin: 20px 0; }}
.card {{ background: #16213e; padding: 15px; border-radius: 8px; text-align: center; }}
.card .num {{ font-size: 2em; font-weight: bold; color: #e94560; }}
.card .label {{ color: #aaa; font-size: 0.9em; }}
table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
th,td {{ padding: 8px; text-align: left; border-bottom: 1px solid #333; }}
th {{ color: #e94560; }} ul {{ list-style: none; padding: 0; }}
li {{ padding: 4px 0; }}
</style></head><body>
<h1>🧬 数字生命体 Dashboard</h1>
<p>Generated: {status["generated_at"][:19]}</p>
<div class="grid">
<div class="card"><div class="num">{status["agent_count"]}</div><div class="label">Agents</div></div>
<div class="card"><div class="num">{status["scene_cards"]}</div><div class="label">Scene Cards</div></div>
<div class="card"><div class="num">{status["journey_specs"]}</div><div class="label">Journey Specs</div></div>
<div class="card"><div class="num">{status["outcomes"]}</div><div class="label">Outcomes</div></div>
<div class="card"><div class="num">{status["mesh_events"]}</div><div class="label">Mesh Events</div></div>
<div class="card"><div class="num">{status["reflections"]}</div><div class="label">Reflections</div></div>
<div class="card"><div class="num">{status["problem_count"]}</div><div class="label">Problems</div></div>
<div class="card"><div class="num">{status["proposal_count"]}</div><div class="label">Proposals</div></div>
</div>
<h2>🤖 Agents</h2><table><tr><th>ID</th><th>Tier</th><th>Status</th><th>Version</th><th>Trust</th><th>Role</th></tr>
{agents_html}</table>
<h2>⚠️ Problems</h2><ul>{problems_html}</ul>
<h2>🧬 Evolution Proposals</h2><ul>{proposals_html}</ul>
<h2>📋 Recent Outcomes</h2><ul>{outcomes_html}</ul>
</body></html>"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="digital-organism-dashboard.html")
    args = parser.parse_args(argv)

    status = gather_status()
    html = generate_html(status)
    output_path = ROOT / args.output
    output_path.write_text(html, encoding="utf-8")
    print(f"Dashboard generated: {output_path} ({len(html)} bytes)")
    print(f"Open with: open '{output_path}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
