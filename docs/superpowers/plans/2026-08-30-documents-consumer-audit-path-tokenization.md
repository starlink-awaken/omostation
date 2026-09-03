---
type: ssot
owner: governance-team
last_updated: 2026-09-03
---

# Documents Consumer Audit Path Tokenization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the canonical Documents consumer audit detect executable paths with trailing argv without breaking quoted paths containing spaces.

**Architecture:** Keep `lib/documents_consumer_audit.py` as the single parser and classifier. Add quote-aware token termination to path extraction, reuse `_is_execution_candidate()` inside execution classification, and extend the predicate only for governed extensionless executor surfaces.

**Tech Stack:** Python 3.9-compatible standard library, PyYAML, pytest, Ruff, root GaC.

## Global Constraints

- No host schedule, Documents content, migration registry, or quarantine mutation.
- No new registry, dispatcher, parser module, or owner command.
- Preserve `documents.consumer-audit.v1` and existing fields/exit semantics.
- Use RED → GREEN before production edits.

---

### Task 1: Reproduce command-path false negatives

**Files:**
- Modify: `tests/test_documents_consumer_audit.py`
- Test: `tests/test_documents_consumer_audit.py`

**Interfaces:**
- Consumes: `documents-domain-owner-job.py consumer-audit` JSON contract.
- Produces: regression assertions for Scheduled, quoted, and extensionless paths.

- [ ] **Step 1: Write the failing tests**

```python
def test_scheduled_home_executor_with_trailing_argv_is_forbidden(tmp_path: Path) -> None:
    # Write `bash ~/Documents/@学习进化/_control/l4-kernel.sh all` to SKILL.md.
    # Assert one learning-runtime documents-executor and forbidden_executors == 1.

def test_quoted_absolute_executor_path_preserves_spaces(tmp_path: Path) -> None:
    # Write a quoted `.../job with space.sh --check` command.
    # Assert relative_path ends with `job with space.sh` and excludes argv.

def test_extensionless_control_executor_is_forbidden(tmp_path: Path) -> None:
    # Write `.../_control/executors/kems-mcp --stdio` to SKILL.md.
    # Assert it is a learning-runtime documents-executor.
```

- [ ] **Step 2: Run tests and verify RED**

Run: `uv run --with pyyaml --with pytest python -m pytest tests/test_documents_consumer_audit.py -q`

Expected: the new tests fail because HOME/absolute paths include argv and the
extensionless control executor is not considered a candidate.

### Task 2: Implement one quote-aware path boundary

**Files:**
- Modify: `lib/documents_consumer_audit.py`
- Test: `tests/test_documents_consumer_audit.py`

**Interfaces:**
- Consumes: `_paths_in_text(text, documents_root)` and `_is_execution_candidate(relative)`.
- Produces: argv-free relative paths and one shared execution predicate.

- [ ] **Step 1: Make HOME paths stop at whitespace**

```python
_HOME_MARKER = re.compile(r'(?:\$HOME|~)/Documents(?:/([^\s"\'`;&)|<>]+))?')
```

- [ ] **Step 2: Make absolute paths quote-aware**

```python
quote = text[index - 1] if index > 0 and text[index - 1] in {'"', "'"} else None
while end < len(text):
    if quote and text[end] == quote:
        break
    if not quote and (text[end].isspace() or text[end] in _PATH_DELIMITERS):
        break
    end += 1
```

- [ ] **Step 3: Reuse and extend the candidate predicate**

```python
markers = (
    '/_runtime/', '/_scripts/', '/tools/', '/.kems/',
    '/_control/executors/', '/.githooks/', '/family-dashboard-app/',
)
executable_path = _is_execution_candidate(relative)
```

- [ ] **Step 4: Run focused GREEN verification**

Run: `uv run --with pyyaml --with pytest python -m pytest tests/test_documents_consumer_audit.py -q`

Expected: all focused tests pass.

- [ ] **Step 5: Run style and Python 3.9 checks**

Run: `uv run --with ruff ruff check lib/documents_consumer_audit.py tests/test_documents_consumer_audit.py`

Run: `python3 -c 'import ast, pathlib; [ast.parse(pathlib.Path(p).read_text(), feature_version=(3, 9)) for p in ("lib/documents_consumer_audit.py", "tests/test_documents_consumer_audit.py")]'`

Expected: both commands exit 0.

### Task 3: Prove the live cutover gate and deliver

**Files:**
- Create: `docs/reports/2026-08-30-documents-consumer-audit-path-tokenization.md`
- Create: `.omo/_knowledge/retros/BET-Y1Q3-T10-102.md`
- Modify: `docs/plans/3y-bet-ledger.yaml`

**Interfaces:**
- Consumes: fixed consumer audit and actual host Scheduled tree.
- Produces: bounded live receipt, report, completion evidence, and PR.

- [ ] **Step 1: Run the live audit**

Run: `uv run --project projects/l4-kernel python bin/gac/documents-domain-owner-job.py consumer-audit --documents-root /Users/xiamingxing/Documents --registry .omo/_truth/registry/documents-content-plane-migrations.yaml --crontab /dev/null --launch-agents-root /Users/xiamingxing/Library/LaunchAgents --scheduled-root /Users/xiamingxing/Documents/Claude/Scheduled --workspace-root "$PWD" --json`

Expected: `vault-daily-health` appears as `documents-executor`; forbidden count
is nonzero until the separate host cutover wave.

- [ ] **Step 2: Run broad verification**

Run: `uv run --with pyyaml python bin/plan/bet-ledger.py lint`

Run: `uv run --with pyyaml python bin/ssot/doc-ssot-lint.py --json`

Run: `make gac-local-gate`

Expected: all commands exit 0.

- [ ] **Step 3: Commit by change lane and submit PR**

```bash
git add <lane-scoped paths>
git commit -m "fix(documents): detect scheduled executor argv correctly"
git push -u origin <branch>
gh pr create --base main --head <branch>
```

Expected: required checks pass; squash merge is reachable from `origin/main`.
