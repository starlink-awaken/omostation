# Forge design asset adapter

This package provides a read-only adapter for the external `awesome-design-md` corpus.

## Usage

```bash
PYTHONPATH=src python3 -m forge.forge design-assets /Users/xiamingxing/ToolBox/awesome-design-md --query claude --limit 3
PYTHONPATH=src python3 -m forge.forge design --query "ai assistant" --platform ai-assistant --limit 5
```

The adapter scans `DESIGN.md` files, extracts frontmatter metadata, and builds a structured `design_context` and prompt for downstream UI generation.

It intentionally remains read-only and does not mutate the upstream external repository.
