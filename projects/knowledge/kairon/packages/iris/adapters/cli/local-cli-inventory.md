---
title: local-cli-inventory
type: doc
---

# Local CLI Inventory

Detected on 2026-05-14.

| Command | Role |
|---|---|
| `codex` | coding agent and repo worker |
| `copilot` | high-throughput scoped worker; supports prompt and ACP modes |
| `claude` | reasoning, writing, and coding assistant |
| `gemini` | alternate reasoning and analysis agent |
| `opencode` | coding agent |
| `qwen` | alternate model CLI |
| `ollama` | local model runtime |
| `bun` | TypeScript/JavaScript runtime |
| `node` | JavaScript runtime |
| `npm` | JavaScript package manager |
| `pnpm` | JavaScript package manager |
| `uv` | Python environment and package tool |
| `python3` | Python runtime |
| `git` | version control |
| `gh` | GitHub CLI |
| `jq` | JSON processor |
| `rg` | fast text search |
| `fd` | fast file search |
| `fzf` | fuzzy finder |

## Candidate Project CLIs

These may exist after installing or activating their project environments:

| Command | Source project | Candidate role |
|---|---|---|
| `kos` | `kos` | knowledge search and indexing |
| `minerva` | `minerva` | deep research |
| `sophia` | `sophia` | paradigm compilation |
| `agora` | `agora` | MCP service registry and routing |
| `agentmesh` | `agentmesh` | agent execution gateway |
| `honeycomb` | `honeycomb` | project orchestration |

## Adapter Policy

CLI tools must be wrapped before use in automated workflows. A wrapper records:

- command
- arguments
- working directory
- expected outputs
- timeout
- risk level
- audit event
- approval requirement
