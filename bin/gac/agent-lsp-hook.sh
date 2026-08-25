#!/bin/bash
# Agent LSP Hook: Predictive Subconscious Escort
# Triggers after write_to_file or replace_file_content to heal structural drift silently.

payload=$(cat)
cd ..
uv run python bin/gac/auto-fix-loop.py --apply > /tmp/agent-lsp-hook.log 2>&1
echo "{}"
