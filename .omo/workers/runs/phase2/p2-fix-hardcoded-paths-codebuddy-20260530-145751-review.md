# Review Note

## Summary of work done

All 11 remaining hardcoded `/Users/xiamingxing` paths have been fixed across 8 files.

### Files Modified (11 paths in 8 files)

| # | File | Hardcoded Path | Fix Method |
|---|------|---------------|------------|
| 1 | `eidos/src/eidos/adapters/sharedbrain.py:99` | `/Users/xiamingxing/Workspace/SharedBrain` | Removed — `expanduser` already covers this |
| 2 | `ecos/tests/test_phase9_push.py:8` | `/Users/xiamingxing/Workspace/eCOS` | `os.environ.get("ECOS_ROOT", Path.home() / ...)` |
| 3 | `ssot/scripts/evaluate_extraction.py:19,28` | `/Users/xiamingxing/Documents/国转中心/...` | `os.environ.get("SSOT_DOCUMENTS_ROOT", ...)` |
| 4 | `agent-runtime/scripts/run-agent-task.sh:5` | `/Users/xiamingxing/Workspace/agent-runtime` | `$HOME/Workspace/agent-runtime` |
| 5 | `agent-runtime/scripts/codexbar-quota.sh:5` | `/Users/xiamingxing/Workspace/SharedBrain` | `$HOME/Workspace/SharedBrain` |
| 6 | `agent-runtime/scripts/ops_tts.py:6` | `/Users/xiamingxing/Workspace/Forge/...` | `os.environ.get("FORGE_ROOT", ...)` |
| 7 | `agent-runtime/scripts/agent_autonomy.py:6` | `/Users/xiamingxing/Workspace/agent-runtime/...` | `Path(__file__).resolve()` |
| 8 | `agent-runtime/scripts/agent-read-budget` | `/Users/xiamingxing/Workspace/agent-runtime/...` | `$AGENT_RUNTIME_HOME` + `$HOME` fallback |
| 9 | `agent-runtime/scripts/agent-inject-budget` | `/Users/xiamingxing/Workspace/agent-runtime/...` | `$AGENT_RUNTIME_HOME` + `$HOME` fallback |
| 10 | `agent-runtime/scripts/cost_digest.sh` | `/Users/xiamingxing/Workspace/agent-runtime/...` | `$AGENT_RUNTIME_HOME` + `$HOME` fallback |
| 11 | `metaos/.omc/state/last-tool-error.json` | `/Users/xiamingxing/Workspace/...` | Deleted (stale tool log) |

### Verification

- `grep -rn "/Users/xiamingxing"` on all 5 touched packages returns **zero matches**.
- Used env vars (`SHAREDBRAIN_ROOT`, `ECOS_ROOT`, `SSOT_DOCUMENTS_ROOT`, `FORGE_ROOT`, `AGENT_RUNTIME_HOME`) with `$HOME`-based fallback.
- Python wrappers use `Path(__file__).resolve()` where applicable.
- Shell wrappers use `$AGENT_RUNTIME_HOME` with `$HOME/Workspace/agent-runtime` as fallback.

### Remaining (intentionally not fixed)

- `kos/manifest.json` (6 matches) — legitimate zone definitions
- `iris/cli/registry.yaml` — CLI auto-detected paths
- `codeanalyze/commands/documents_cmd.py` — documentation examples
- P3 items in docs/scripts

### Evidence

- `rg "/Users/xiamingxing"` across 5 packages after changes: **clean** (exit code 1, no matches)
