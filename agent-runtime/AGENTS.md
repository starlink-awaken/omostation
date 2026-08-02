<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-08-02 | Updated: 2026-08-02 -->

# agent-runtime/

## Purpose
`agent-runtime/` is the **agent execution log and runtime state** directory. It stores the JSONL-based execution log that records agent delegation events, dialog completions, and session lifecycle markers. This is a lightweight runtime artifact directory — not a source code directory — that supports observability and auditing of agent activity across the workspace.

## Key Files
| File | Description |
|------|-------------|
| `execution_log.jsonl` | JSONL execution log — records agent delegation events with timestamps, task IDs, status, turn counts, token usage, and source |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| *(none — single file)* | |

## For AI Agents

### Working In This Directory
- **This is runtime observability data.** The `execution_log.jsonl` is append-only.
- Each line is a JSON object with fields: `ts`, `task_id`, `status`, `summary`, `turns`, `tokens_used`, `source`.
- Don't manually edit this file — it's written by the agent runtime hook system.
- Useful for debugging agent delegation chains and auditing token usage across sessions.

### Testing Requirements
- No specific tests for this directory. Agent workflow tests in `tests/test_agent_workflow.py` cover the runtime behavior.

### Common Patterns
- JSONL format: one JSON object per line, newline-delimited.
- Query with: `jq '. | select(.task_id=="dialog")' agent-runtime/execution_log.jsonl`

## Dependencies

### Internal
- Agent runtime hooks — write to `execution_log.jsonl`
- `bin/agent-workflow.py` — orchestrates the workflows being logged

### External
- No direct external dependencies

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
