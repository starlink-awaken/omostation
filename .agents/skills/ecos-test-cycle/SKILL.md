---
name: ecos-test-cycle
description: "Edit→test→commit cycle for the ecos project. Run full test suite after code changes, verify results, commit on pass, recover on failure. Use whenever modifying ecos source code."
---

# Ecos Test Cycle — Edit → Verify → Commit

The most common development loop in this workspace: edit ecos code, run the test suite, verify results, and commit. This skill standardizes the cycle to prevent forgotten commits (kairon-style silent resets) and ensure verification before marking work complete.

## When To Use

- After any file edit under `projects/ecos/`
- Before switching context away from ecos work
- When recovering from a failed test run (checkout broken files, retest)

## The Cycle

### Step 1: Run Full Test Suite

```bash
cd projects/ecos && uv run pytest tests/ -q 2>&1 | tail -5
```

For verbose output (when debugging failures):

```bash
cd projects/ecos && uv run pytest tests/ -q --tb=short 2>&1 | tail -10
```

For a specific test file:

```bash
cd projects/ecos && uv run pytest tests/test_l0/test_governance.py -q 2>&1 | tail -3
```

### Step 2: Interpret Results

- **All passed** → proceed to Step 3 (commit)
- **Failures** → check if failures are pre-existing or caused by your changes
  - Run `git diff --name-only` to see what you changed
  - Run the failing test in isolation with `--tb=short` for full traceback
  - Fix the issue, then re-run from Step 1

### Step 3: Commit

Stage only the files you changed (not unrelated dirty files):

```bash
cd projects/ecos && git add <specific-files> && git commit -m "<type>(ecos): <description>"
```

**Commit discipline** (from project rules): kairon project history has `git reset` operations that silently roll back uncommitted changes. AI agents MUST immediately `git commit` after making file changes. The same caution applies to ecos.

### Step 4: Push (If Ready)

```bash
cd projects/ecos && git push origin main 2>&1 | head -5
```

Then update root pointer if pushing to a tracked branch:

```bash
cd /Users/xiamingxing/Workspace && git add projects/ecos && git commit -m "chore: update ecos pointer" && git push origin main
```

## Recovery Workflow

When tests fail and you need to revert broken changes:

```bash
# Check which files are broken
cd projects/ecos && git diff --name-only

# Revert specific files (keeps other changes)
cd projects/ecos && git checkout -- src/ecos/l1/runtime/__init__.py src/ecos/l2/engine/__init__.py

# Re-run tests to confirm recovery
cd projects/ecos && uv run pytest tests/ -q 2>&1 | tail -3
```

**Caution**: Only revert the specific broken files. Do not `git checkout -- .` as it destroys all uncommitted work.

## Lint Check (Optional, Before Commit)

```bash
cd projects/ecos && uv run ruff check src/ecos/l1/ src/ecos/l2/ src/ecos/l3/ 2>&1
```

## MOF Schema Validation (If Modifying M1/M2 YAML)

```bash
cd projects/ecos && uv run python src/ecos/ssot/tools/mof-schema-validate.py --strict 2>&1 | grep -E "ERROR|FAIL|Summary|passed|failed" | tail -10
```

This runs automatically via pre-commit hook, but useful for pre-flight checks.

## Key Files Reference

| Path | Purpose |
|------|---------|
| `projects/ecos/tests/` | Full test suite |
| `projects/ecos/tests/test_l0/` | L0 governance tests |
| `projects/ecos/src/ecos/` | Source code |
| `projects/ecos/src/ecos/ssot/mof/` | MOF M1/M2 YAML |
| `projects/ecos/src/ecos/ssot/tools/mof-schema-validate.py` | MOF validation |

## Anti-patterns

- **DON'T** commit without running tests first — the whole point is verification
- **DON'T** use `git checkout -- .` for recovery — it destroys all uncommitted work
- **DON'T** hardcode exact test counts in assertions — use `>=` thresholds (integration test count drift pattern)
- **DON'T** run `git push` from root before submodule — push submodule first, then update root pointer
