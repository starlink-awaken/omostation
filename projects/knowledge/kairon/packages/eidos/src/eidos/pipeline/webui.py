"""Pipeline Web UI — generate an interactive HTML page for pipeline visualization.

Usage:
    python -m eidos.pipeline.webui  # Prints HTML to stdout
    python -m eidos.pipeline.webui --output pipeline.html  # Saves to file
"""

from __future__ import annotations

import argparse
from pathlib import Path

from eidos.pipeline.presets import PRESETS


def generate_html(pipeline_name: str | None = None) -> str:
    """Generate an HTML page showing pipeline(s) as interactive Mermaid+JS.

    Args:
        pipeline_name: Specific pipeline to show, or None for all
    """
    pipelines = {k: v for k, v in PRESETS.items() if not pipeline_name or k == pipeline_name}

    steps_html = ""
    for i, (_name, p) in enumerate(pipelines.items()):
        steps_html += f"""
        <div class="pipeline">
            <h2>{p.name}</h2>
            <p>{p.description}</p>
            <div class="mermaid" id="mermaid-{i}">
                flowchart LR
                {" --> ".join([f'{s.tool}_{j}["{s.tool}: {s.action}"]' for j, s in enumerate(p.steps)])}
            </div>
            <div class="details">
                <p>{len(p.steps)} steps</p>
            </div>
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>Eidos Pipeline Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<style>
  body {{ font-family: -apple-system, sans-serif; max-width: 960px; margin: 0 auto; padding: 20px; }}
  .pipeline {{ background: #f5f5f5; border-radius: 8px; padding: 20px; margin: 20px 0; }}
  h1 {{ color: #333; }}
  h2 {{ color: #555; }}
  .details {{ color: #777; font-size: 0.9em; }}
</style>
</head>
<body>
<h1>🔷 Eidos Pipeline Dashboard</h1>
{steps_html}
<script>mermaid.initialize({{startOnLoad:true}});</script>
</body>
</html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Pipeline Web UI")
    parser.add_argument("--output", help="Output HTML file path")
    parser.add_argument("--pipeline", help="Specific pipeline name")
    args = parser.parse_args()
    html = generate_html(args.pipeline)
    if args.output:
        Path(args.output).write_text(html, encoding="utf-8")
        print(f"Written to {args.output}")
    else:
        print(html)


if __name__ == "__main__":
    main()
