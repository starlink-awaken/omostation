---
name: governance-ssot-edit
description: "Edit governance SSOT (governance-checks.yaml / gac-*.py / write-owners / x*-rules / mutation-surfaces) safely in a concurrent multi-agent workspace. Aligns ALL source copies, commits via pathspec to avoid clobbering concurrent staged work, pushes immediately so concurrent PRs can't silently revert, and verifies the change survives. Use when changing GaC rules/executor enums, governance registries, or any multi-source governance field."
---

# Governance SSOT Edit — Multi-Source Align + Concurrent-Safe Workflow

The disciplined edit flow for omostation governance SSOT. Two risks closed:
1. **Multi-source drift** — governance fields are duplicated across N sources; a partial edit = drift复发.
2. **Concurrent silent revert** — uncommitted working-tree changes get flushed by concurrent PR merges / git operations.

Validated by PR #60 (2026-07-03, GaC executor enum 5-source align after PR #59 reverted a first pass).

## When To Use

- Changing GaC rules / executor enum / checker registration (`governance-checks.yaml`, `bin/gac-*.py`)
- Changing `write-owners.yaml` / `mutation-surfaces.yaml` / `x1-x4-rules.yaml`
- Changing any governance registry field that exists in **multiple sources**
- Editing `.omo/_truth/registry/*` during concurrent agent activity
- Any time you're about to report "X is missing/zero-impl/dangling" about a governance path

## The Workflow

### Step 1: Survey ALL sources (multi-source map)

Before editing, list every source holding the field. For GaC executor — **5 sources**:

| # | Source | Edit? |
|---|--------|-------|
| ① | `.omo/_truth/registry/governance-checks.yaml::gac.rules` (rule SSOT) | direct |
| ② | `.omo/_truth/registry/governance-checks.yaml::gac.schema.executor_enum` | direct |
| ③ | `bin/gac-drift.py::EXECUTOR_ENUM` | direct |
| ④ | MOF M1 `projects/ecos/.../m1/governance/GAC-RULE-CR-*.yaml` | **派生** — `gac-m1-sync.py --sync` |
| ⑤ | `bin/gac-executor.py::EXECUTOR_PRESENCE` | direct |

For other SSOT fields:
```bash
rg "<field>" .omo/_truth/registry/ bin/ projects/ -l
```
List every holder. A field not in this list = a source you'll miss.

### Step 2: Migration lookup (don't trust stale paths)

Before claiming "file/dir missing / zero-impl / dangling ref", check **5 locations**:
1. **ADR** — `.omo/_knowledge/decisions/*.md` (`migrate` / `physical-migration` / `superseded` / `convergence`)
2. **archive** — `.omo/_archive/legacy-*` + top-level `_archived/`
3. **`_control/`** — `.omo/_control/<name>-dashboard/` (governance dashboards migrated here, e.g. debt-dashboard)
4. **mutation-surfaces.yaml** — declared write-surfaces are created at runtime; **empty = normal, not drift** (e.g. `.omo/debt/`)
5. **ingress delivery** — `runtime/omo/_delivery/` + `change-log/mutations.jsonl` (artifacts may not have projected to the formal tree)

eCOS has 7+ migrations. Stale path assumptions = wrong conclusions (3 times in one session).

### Step 3: Check write boundary

```bash
grep "<target-file>" .omo/_truth/registry/write-owners.yaml
```
Restricted (script/daemon-owned) files need an omo CLI/broker, **not** direct file I/O.

### Step 4: Edit ALL sources (align)

Use `Edit` on each direct source. Never `sed`. After SSOT change, derive M1:
```bash
python3 bin/gac-m1-sync.py --sync   # source ④ auto-aligns
```

### Step 5: Pathspec commit IMMEDIATELY (concurrent-safe)

Commit **only** the target files. Do NOT drag concurrent agents' staged work:

```bash
git status --short                              # see what's staged (concurrent agents)
git commit <file1> <file2> ... -m "fix(...): ..." -m "<body, name the sources aligned>"
```

| ❌ Don't | ✅ Do |
|---------|-------|
| `git add -A` / `git commit -a` | `git commit <specific files>` |
| Leave changes in working tree | Commit before doing anything else |
| Trust "already fixed" without re-checking each source | Verify all N sources aligned |

### Step 6: Push + PR IMMEDIATELY (prevent flush)

```bash
git push -u origin <branch>
gh pr create --base main --head <branch> --title "..." --body '...'
```
An uncommitted or unpushed change WILL be silently reverted by the next concurrent PR merge. PR body must state: which sources changed / why / verification / scope (didn't touch concurrent work).

### Step 7: Verify survival (don't let silent revert fool you)

```bash
git diff --stat <branch>~1 <branch>             # confirm commit still has target files
python3 bin/gac-drift.py                        # 0 drift
python3 bin/gac-bootstrap.py                    # 层5 ✅
python3 bin/gac-executor.py                     # all executors present
```
**If working-tree change vanished** (git status empty but shouldn't be): a concurrent op reverted you. Re-apply Step 4-6.

### Step 8: CI triage (pre-existing vs introduced)

```bash
gh pr checks <PR> --watch
gh run view <fail-run-id> --log-failed | grep -iE "fail|error|drift"
```

| My change caused it? | Action |
|----------------------|--------|
| Yes (gac-drift/gac-gate fail on my field) | **Must fix**, don't merge |
| No, pre-existing (KOS SQLite missing, OIDC, main already red) | Merge OK (UNSTABLE but MERGEABLE) |

**Key proof**: if your change flipped a check FAIL→PASS (PR #60 made `gac-drift` pass), that's positive evidence the rest are pre-existing.

### Step 9: Merge

```bash
gh pr merge <PR> --squash --delete-branch
```
- `MERGEABLE` + `UNSTABLE` (pre-existing fails) → merge OK
- `BLOCKED` → needs `--admin` or fix the blocking check first

## Common Pitfalls

| Pitfall | Consequence | Prevention |
|---------|-------------|------------|
| Edit 1 source, skip others | drift复发, gac-drift re-red | Step 1 survey + Step 4 align ALL |
| `git add -A` with concurrent staged | Drag another agent's WIP into your PR | Step 5 pathspec commit |
| Working tree left uncommitted | Concurrent PR silently reverts | Step 5-6 commit + push immediately |
| Verify once, trust it persists | Silent revert makes you report "green" falsely | Step 7 re-check after commit |
| Can't distinguish CI fail types | Either blocked needlessly or merge broken code | Step 8 triage matrix |
| Edit a write-owners restricted file directly | Red-line violation | Step 3 check boundary |
| Trust stale memory / "already fixed N" | Memory drifts (e.g. "129 缺口" was actually 3) | Re-verify against real data every time |
| Survey sinks to one tree only | Missed `.agents/skills/` vs `.omo/_knowledge/` | Step 2 — check ALL 5 locations, including non-.omo trees |

## Anti-patterns

- **DON'T** edit a governance field without first listing all sources that hold it
- **DON'T** claim "zero implementation" without checking the 5 migration locations
- **DON'T** leave governance edits uncommitted in a shared working tree
- **DON'T** merge a PR without triaging whether fails are yours or pre-existing
- **DON'T** trust a single `health_score=100` — cross-check `bin/evidence-smoke.py`
- **DON'T** survey skill/workflow sinks by looking only at `.omo/_knowledge/` — `.agents/skills/` is the project-level agent skill home

## Integration

- **Full isolation** (root fix for concurrency): `worktree-ci-isolate` skill + `docs/AGENT-ISOLATION-ROLLOUT.md`
- **The "why" (principles & traps)**: `.omo/_knowledge/patterns/p73-truth-driven-engineering-pattern.md`
- **GaC architecture**: `.omo/_knowledge/decisions/0106-gac-governance-as-code.md`
- **Governance surfaces contract**: `.omo/standards/omo-governance-surfaces.md`

## Provenance

Validated by PR #60 (2026-07-03): GaC executor enum drift — first pass reverted by concurrent PR #59, second pass with this workflow merged cleanly (`3bd4edc`). 5-source align, pathspec commit `9e71c0d`, CI pre-existing fails triaged, gac-drift flipped FAIL→PASS. Skill itself was reverted once during authoring (working-tree flush) before being PR-locked.
