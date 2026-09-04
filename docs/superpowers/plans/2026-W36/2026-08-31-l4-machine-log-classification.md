---
lifecycle: plan
owner: governance-team
created: 2026-08-30
last_updated: 2026-08-30
last_updated: 2026-09-03
title: L4 context-aware machine-log classification implementation plan
type: doc
---

# L4 Context-Aware Machine-Log Classification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the canonical L4 Documents audit detect machine-generated operational `.log` files without reclassifying arbitrary or archive-governed historical logs.

**Architecture:** Add one private, path-only predicate to the existing L4 classifier and call it after content-archive resolution in both regular-file and safe-symlink branches. Reuse the existing `cache` kind and `L4-CONTENT-009`; deliver through an L4 child PR followed by a root gitlink/evidence PR.

**Tech Stack:** Python 3.13, `pathlib`, pytest, Ruff, uv, Git submodules, root Agent Workflow and GaC.

## Global Constraints

- Do not classify every `.log` as cache.
- Do not bypass valid or invalid `CONTENT_ARCHIVE.yaml` authority.
- Do not change artifact/report/CLI schemas, issue codes, or public entry points.
- Do not write, move, truncate, delete, or open any Documents file for writing.
- Do not mutate host processes, schedules, LaunchAgents, applications, or migration-family status.
- Use RED-to-GREEN before every production-code behavior change.
- Merge the L4 child PR before deriving the root gitlink from child `origin/main`.
- Keep engineering, operational cleanup, and principal-bound value verdicts separate; value remains `NOT_PROVEN`.

---

### Task 1: Prove the classifier blind spot and preservation boundaries

**Files:**
- Modify: `projects/l4-kernel/tests/test_content_plane.py`
- Modify: `projects/l4-kernel/tests/test_content_archive.py`
- Modify: `projects/l4-kernel/tests/test_cli_contracts.py`

**Interfaces:**
- Consumes: `classify_artifact(root: Path, path: Path) -> ArtifactClassification` and `audit_content_plane(root: Path) -> ContentPlaneReport`.
- Produces: regression tests for operational contexts, safe-symlink parity, archive precedence, arbitrary-log preservation, and unchanged CLI JSON shape.

- [ ] **Step 1: Create an isolated child branch at the root gitlink**

Run inside the verified root clone:

```bash
git -C projects/l4-kernel fetch origin main
git -C projects/l4-kernel switch -c agent/codex-documents-convergence--t10-109-machine-log-classifier origin/main
git -C projects/l4-kernel status --short
```

Expected: child branch starts at the exact L4 `origin/main` commit and is clean.

- [ ] **Step 2: Add the selected-context and preservation tests**

Append these tests to `projects/l4-kernel/tests/test_content_plane.py`:

```python
def test_machine_generated_logs_are_cache_only_in_operational_contexts(tmp_path: Path) -> None:
    selected = [
        "@cockpit/_generated/governance-cron.log",
        "@work/_runtime/reports/cron.log",
        "@learning/_control/logs/launchd.stderr.log",
        "_inbox/hourly_runner.log",
        "_inbox/hourly_runner_err.log",
    ]
    preserved = [
        "_knowledge/meeting.log",
        "_inbox/meeting.log",
        "_inbox/nested/hourly_runner.log",
        "_inbox/hourly_runner.txt",
    ]

    for relative in selected:
        result = classify_artifact(tmp_path, _write(tmp_path, relative))
        assert result.kind == "cache"
        assert result.code == "L4-CONTENT-009"

    for relative in preserved:
        assert classify_artifact(tmp_path, _write(tmp_path, relative)).kind == "content"


def test_machine_generated_log_symlink_has_cache_parity(tmp_path: Path) -> None:
    root = tmp_path / "domain"
    root.mkdir()
    external = _write(tmp_path, "external.log", "runtime output")
    link = root / "_inbox" / "hourly_runner.log"
    link.parent.mkdir()
    link.symlink_to(external)

    result = classify_artifact(root, link)

    assert result.kind == "cache"
    assert result.code == "L4-CONTENT-009"
```

Append this archive-precedence test to `projects/l4-kernel/tests/test_content_archive.py`:

```python
def test_valid_archive_machine_log_context_remains_content_archive(tmp_path: Path) -> None:
    archive = tmp_path / "_archive" / "legacy"
    log = archive / "_runtime" / "daemon.log"
    log.parent.mkdir(parents=True)
    log.write_text("historical output\n", encoding="utf-8")
    _write_archive_manifest(archive)

    assert classify_artifact(tmp_path, log).kind == "content_archive"


def test_invalid_archive_machine_log_context_remains_invalid_archive(tmp_path: Path) -> None:
    archive = tmp_path / "_archive" / "legacy"
    log = archive / "_runtime" / "daemon.log"
    log.parent.mkdir(parents=True)
    log.write_text("historical output\n", encoding="utf-8")
    manifest = _write_archive_manifest(archive)
    manifest.write_text("schema: l4.content-archive/v1\n", encoding="utf-8")

    result = classify_artifact(tmp_path, log)

    assert result.kind == "invalid_archive"
    assert result.code == "L4-CONTENT-011"
```

Append this CLI contract test to `projects/l4-kernel/tests/test_cli_contracts.py`:

```python
def test_content_audit_json_reports_machine_log_as_existing_cache_issue(
    tmp_path, monkeypatch, capsys
) -> None:
    root = tmp_path / "domain"
    root.mkdir()
    log = root / "_inbox" / "hourly_runner.log"
    log.parent.mkdir()
    log.write_text("", encoding="utf-8")

    code, payload = invoke(monkeypatch, capsys, "content", "audit", str(root), "--json")

    assert code == 1
    assert payload["ok"] is False
    assert payload["data"]["counts"] == {"cache": 1}
    assert payload["data"]["violations"] == [
        {
            "path": str(log),
            "relative_path": "_inbox/hourly_runner.log",
            "kind": "cache",
            "reason": "derived cache or mutable local store belongs in Workspace",
            "code": "L4-CONTENT-009",
        }
    ]
```

- [ ] **Step 3: Run the selected tests and record RED**

Run:

```bash
cd projects/l4-kernel
uv run pytest \
  tests/test_content_plane.py::test_machine_generated_logs_are_cache_only_in_operational_contexts \
  tests/test_content_plane.py::test_machine_generated_log_symlink_has_cache_parity \
  tests/test_cli_contracts.py::test_content_audit_json_reports_machine_log_as_existing_cache_issue \
  -q
```

Expected: failure because the current classifier returns `projection` or `content`, not `cache`. Failures must be assertions about the missing behavior, not import, syntax, or fixture errors.

- [ ] **Step 4: Run archive characterization tests before production edits**

Run:

```bash
uv run pytest \
  tests/test_content_archive.py::test_valid_archive_machine_log_context_remains_content_archive \
  tests/test_content_archive.py::test_invalid_archive_machine_log_context_remains_invalid_archive \
  -q
```

Expected: both pass and establish the behavior the new predicate must preserve.

- [ ] **Step 5: Commit the RED tests in the child repository**

```bash
git add tests/test_content_plane.py tests/test_content_archive.py tests/test_cli_contracts.py
git commit -m "test(l4): expose machine-log classification blind spot"
```

Expected: one child test commit; the selected new behavior tests remain RED until Task 2.

---

### Task 2: Add the minimal context-aware predicate

**Files:**
- Modify: `projects/l4-kernel/src/l4_kernel/content_plane.py`
- Test: `projects/l4-kernel/tests/test_content_plane.py`
- Test: `projects/l4-kernel/tests/test_content_archive.py`
- Test: `projects/l4-kernel/tests/test_cli_contracts.py`

**Interfaces:**
- Consumes: normalized POSIX `relative` path already computed by `classify_artifact`.
- Produces: `_machine_generated_log(relative: str) -> bool`, used only inside `classify_artifact` after archive resolution.

- [ ] **Step 1: Add the private pure predicate**

Add after `_has_shebang` in `src/l4_kernel/content_plane.py`:

```python
def _machine_generated_log(relative: str) -> bool:
    """Identify mutable machine logs without treating historical logs as cache."""

    relative_path = Path(relative)
    if relative_path.suffix.lower() != ".log":
        return False
    parts = tuple(part.lower() for part in relative_path.parts)
    if "_generated" in parts or "_runtime" in parts:
        return True
    if any(parts[index : index + 2] == ("_control", "logs") for index in range(len(parts) - 1)):
        return True
    if len(parts) != 2 or parts[0] != "_inbox":
        return False
    stem = relative_path.stem.lower()
    return stem.endswith("_runner") or stem.endswith("_runner_err")
```

- [ ] **Step 2: Apply it after archive authority in both branches**

In the symlink branch, insert after the archive branch and before runtime suffix classification:

```python
        elif _machine_generated_log(relative):
            kind, reason = "cache", "derived cache or mutable local store belongs in Workspace"
```

In the regular-file branch, insert the same branch after `resolver.lookup` and before runtime suffix/shebang classification:

```python
        elif _machine_generated_log(relative):
            kind, reason = "cache", "derived cache or mutable local store belongs in Workspace"
```

Do not move the existing cache, bridge, archive, runtime, projection, or contract branches.

- [ ] **Step 3: Run focused GREEN verification**

Run:

```bash
uv run pytest \
  tests/test_content_plane.py::test_machine_generated_logs_are_cache_only_in_operational_contexts \
  tests/test_content_plane.py::test_machine_generated_log_symlink_has_cache_parity \
  tests/test_content_archive.py::test_valid_archive_machine_log_context_remains_content_archive \
  tests/test_content_archive.py::test_invalid_archive_machine_log_context_remains_invalid_archive \
  tests/test_cli_contracts.py::test_content_audit_json_reports_machine_log_as_existing_cache_issue \
  -q
```

Expected: `5 passed`.

- [ ] **Step 4: Run the focused modules and Ruff**

```bash
uv run pytest tests/test_content_plane.py tests/test_content_archive.py tests/test_cli_contracts.py -q
uv run ruff check src/l4_kernel/content_plane.py tests/test_content_plane.py tests/test_content_archive.py tests/test_cli_contracts.py
uv run ruff format --check src/l4_kernel/content_plane.py tests/test_cli_contracts.py
git show origin/main:tests/test_content_plane.py | uv run ruff format --check --stdin-filename tests/test_content_plane.py -
git show origin/main:tests/test_content_archive.py | uv run ruff format --check --stdin-filename tests/test_content_archive.py -
```

Expected: focused tests and Ruff lint pass; changed production/CLI files are formatted. The two baseline stdin checks return nonzero and prove inherited whole-file format drift without reformatting unrelated tests.

- [ ] **Step 5: Commit the minimal child implementation**

```bash
git add src/l4_kernel/content_plane.py
git commit -m "fix(l4): classify machine-generated logs as cache"
```

Expected: implementation commit contains only production code; tests remain in the prior RED commit.

---

### Task 3: Verify, review, and merge the L4 child delivery

**Files:**
- Review: `projects/l4-kernel/src/l4_kernel/content_plane.py`
- Review: `projects/l4-kernel/tests/test_content_plane.py`
- Review: `projects/l4-kernel/tests/test_content_archive.py`
- Review: `projects/l4-kernel/tests/test_cli_contracts.py`

**Interfaces:**
- Consumes: child commits from Tasks 1 and 2.
- Produces: a child authoritative-main commit reachable from `origin/main` and suitable as the sole root gitlink source.

- [ ] **Step 1: Run the complete child verification matrix**

```bash
cd projects/l4-kernel
uv run pytest tests/ -q
uv run ruff check src/ tests/
uv run ruff format --check src/l4_kernel/content_plane.py tests/test_cli_contracts.py
git diff origin/main...HEAD --check
git status --short
```

Expected: full suite and Ruff lint pass, changed files are formatted, diff check is clean, and child worktree is clean. Existing whole-file format debt in `test_content_plane.py` and `test_content_archive.py` is recorded but not expanded.

- [ ] **Step 2: Review exact requirements against the child diff**

```bash
git diff --stat origin/main...HEAD
git diff origin/main...HEAD -- src/l4_kernel/content_plane.py tests/test_content_plane.py tests/test_content_archive.py tests/test_cli_contracts.py
```

Require all of the following before push: no global `.log` suffix set, archive lookup remains before the new predicate, both regular/symlink branches call the same helper, no public schema/API change, and no unrelated file.

- [ ] **Step 3: Push the child branch and create its PR**

```bash
git push -u origin agent/codex-documents-convergence--t10-109-machine-log-classifier
gh pr create --base main --head agent/codex-documents-convergence--t10-109-machine-log-classifier
CHILD_PR="$(gh pr list --state open --head agent/codex-documents-convergence--t10-109-machine-log-classifier --json number --jq '.[0].number')"
test -n "$CHILD_PR"
```

PR body must include RED evidence, focused/full test and Ruff commands, archive-preservation boundary, and the statement that no Documents or host mutation occurred.

- [ ] **Step 4: Wait for current-tip required child checks and squash merge**

```bash
gh pr checks "$CHILD_PR" --watch
gh pr view "$CHILD_PR" --json state,mergeable,mergeStateStatus,statusCheckRollup,headRefOid
gh pr merge "$CHILD_PR" --squash --delete-branch=false
```

Expected: no failing/pending required check, `mergeable=MERGEABLE`, `mergeStateStatus=CLEAN`, and the PR becomes `MERGED`.

- [ ] **Step 5: Prove child authoritative-main ancestry**

```bash
git fetch origin main
CHILD_MERGE_SHA="$(gh pr view "$CHILD_PR" --json mergeCommit --jq .mergeCommit.oid)"
test -n "$CHILD_MERGE_SHA"
git merge-base --is-ancestor "$CHILD_MERGE_SHA" origin/main
```

Expected: all commands exit zero. Keep the child branch until the root gitlink PR merges.

---

### Task 4: Merge the root gitlink delivery before terminal claims

**Files:**
- Modify: `projects/l4-kernel` gitlink
- Modify: `docs/superpowers/plans/2026-08-31-l4-machine-log-classification.md`

**Interfaces:**
- Consumes: child merge SHA from Task 3 and root main specification digest.
- Produces: a root main commit whose gitlink reaches the child authoritative-main merge. BET status remains `candidate` until this root PR is merged and replayed.

- [ ] **Step 1: Update the root pointer only from child `origin/main`**

```bash
git -C projects/l4-kernel fetch origin main
git -C projects/l4-kernel switch --detach origin/main
git -C projects/l4-kernel rev-parse HEAD
git -C projects/l4-kernel merge-base --is-ancestor HEAD origin/main
git diff --submodule=log -- projects/l4-kernel
```

Expected: root pointer advances from the old gitlink to the exact child authoritative-main tip containing the merged PR.

- [ ] **Step 2: Run root implementation verification and the read-only host canary**

```bash
uv run --with pyyaml python bin/plan/bet-ledger.py verify BET-Y1Q3-T10-109 --execute
uv run --with pyyaml python bin/ssot/doc-ssot-lint.py --json
make ssot-guardian
make gac-local-gate
uv run --project projects/l4-kernel python -c "from pathlib import Path; from l4_kernel.content_plane import classify_artifact; root=Path('/Users/xiamingxing/Documents'); paths=[root/'_inbox/hourly_runner.log',root/'_inbox/hourly_runner_err.log']; before=[(p.stat().st_size,p.stat().st_mtime_ns) for p in paths]; results=[classify_artifact(root,p) for p in paths]; after=[(p.stat().st_size,p.stat().st_mtime_ns) for p in paths]; assert before==after and all(r.kind=='cache' and r.code=='L4-CONTENT-009' for r in results)"
```

Expected: BET commands, doc SSOT, SSOT guardian, and GaC pass; both live paths remain byte/mtime unchanged and classify as existing cache issues.

- [ ] **Step 3: Commit root pointer and plan lanes separately**

```bash
git add projects/l4-kernel
git commit -m "chore(l4): advance machine-log classifier pointer"

git add docs/superpowers/plans/2026-08-31-l4-machine-log-classification.md
git commit -m "docs: align T10-109 evidence sequencing"
```

Expected: no commit mixes `submodule_pointer` and `docs` lanes.

- [ ] **Step 4: Push, review, and merge the root implementation PR**

```bash
git push origin agent/codex-documents-convergence--t10-109-implementation-20260831-01
gh pr create --base main --head agent/codex-documents-convergence--t10-109-implementation-20260831-01
ROOT_IMPL_PR="$(gh pr list --state open --head agent/codex-documents-convergence--t10-109-implementation-20260831-01 --json number --jq '.[0].number')"
test -n "$ROOT_IMPL_PR"
gh pr checks "$ROOT_IMPL_PR" --watch
gh pr view "$ROOT_IMPL_PR" --json state,mergeable,mergeStateStatus,statusCheckRollup,headRefOid
gh pr merge "$ROOT_IMPL_PR" --squash --delete-branch=false
```

Expected: current-tip required checks succeed, merge state is CLEAN, and the implementation PR is merged.

- [ ] **Step 5: Prove the root implementation merge and gitlink on main**

```bash
git fetch origin main
ROOT_IMPL_MERGE_SHA="$(gh pr view "$ROOT_IMPL_PR" --json mergeCommit --jq .mergeCommit.oid)"
test -n "$ROOT_IMPL_MERGE_SHA"
git merge-base --is-ancestor "$ROOT_IMPL_MERGE_SHA" origin/main
git ls-tree origin/main projects/l4-kernel
```

Expected: root implementation merge is reachable and the main gitlink is the child merge SHA.

---

### Task 5: Replay main, merge terminal evidence, and close the workflow

**Files:**
- Modify: `docs/plans/3y-bet-ledger.yaml`
- Create: `docs/reports/2026-08-31-l4-machine-log-classification.md`
- Create: `.omo/_knowledge/retros/BET-Y1Q3-T10-109.md`
- Runtime evidence: `.omo/evidence/20260830T172828Z-bet-execution-22b95054/`

**Interfaces:**
- Consumes: child merge and root implementation merge proven on their authoritative main branches.
- Produces: historical report, retrospective, digest-valid completion matrix, closeout PR/mainline replay, and closed workflow with released locks.

- [ ] **Step 1: Start a clean closeout branch from replayed root main**

```bash
git switch -c agent/codex-documents-convergence--t10-109-closeout-20260831-01 origin/main
git status --short
uv run --with pyyaml python bin/plan/bet-ledger.py verify BET-Y1Q3-T10-109 --execute
```

Expected: branch starts at root authoritative main, is clean, and mainline implementation replay passes before terminal evidence is written.

- [ ] **Step 2: Write report, retro, and completion matrix from immutable evidence**

The report records child PR/merge SHA, root implementation PR/merge SHA, old/new gitlinks, RED/GREEN evidence, complete child/root verification, live canary pre/post metadata equality, inherited unrelated debt, and zero Documents/host mutation. The retro answers intent, result, design changes, surface accounting, T10-110 follow-up, and value boundary.

Set the BET to `done` with `done_at: 2026-08-31`, preserve specification `1.0.0`, and add `completion-evidence-matrix/v1`. Engineering is `VERIFIED`; operational classifier behavior is `PROVEN` by the live canary and mainline replay; value remains `NOT_PROVEN`. The report must state that physical cleanup is outside T10-109 and remains unproven until T10-110.

- [ ] **Step 3: Commit closeout lanes separately and verify**

```bash
git add docs/reports/2026-08-31-l4-machine-log-classification.md
git commit -m "docs: report T10-109 machine-log classification"
git add .omo/_knowledge/retros/BET-Y1Q3-T10-109.md
git commit -m "chore(governance): record T10-109 retrospective"
git add docs/plans/3y-bet-ledger.yaml
git commit -m "chore(plan): close T10-109 classifier delivery"

uv run --with pyyaml python bin/plan/bet-ledger.py verify BET-Y1Q3-T10-109 --execute
uv run --with pyyaml python bin/agent-workflow.py verify 20260830T172828Z-bet-execution-22b95054 --from-diff --execute
uv run --with pyyaml python bin/ssot/doc-ssot-lint.py --json
make ssot-guardian
make gac-local-gate
git diff origin/main...HEAD --check
```

Expected: T10-109 BET/workflow verification, doc SSOT, SSOT guardian, GaC, and diff checks pass. Inherited global ledger findings are listed by exact BET and not represented as T10-109 failures.

- [ ] **Step 4: Push and merge the closeout PR**

```bash
git push -u origin agent/codex-documents-convergence--t10-109-closeout-20260831-01
gh pr create --base main --head agent/codex-documents-convergence--t10-109-closeout-20260831-01
ROOT_CLOSEOUT_PR="$(gh pr list --state open --head agent/codex-documents-convergence--t10-109-closeout-20260831-01 --json number --jq '.[0].number')"
test -n "$ROOT_CLOSEOUT_PR"
gh pr checks "$ROOT_CLOSEOUT_PR" --watch
gh pr view "$ROOT_CLOSEOUT_PR" --json state,mergeable,mergeStateStatus,statusCheckRollup,headRefOid
gh pr merge "$ROOT_CLOSEOUT_PR" --squash --delete-branch=false
```

Expected: current-tip required checks succeed, merge state is CLEAN, and closeout PR is merged.

- [ ] **Step 5: Replay terminal main and close workflow**

```bash
git fetch origin main
gh pr view "$ROOT_CLOSEOUT_PR" --json state,mergeCommit
git show origin/main:docs/plans/3y-bet-ledger.yaml | rg -n -A 70 'BET-Y1Q3-T10-109'
git ls-tree origin/main projects/l4-kernel
uv run --with pyyaml python bin/plan/bet-ledger.py verify BET-Y1Q3-T10-109 --execute
uv run --with pyyaml python bin/agent-workflow.py closeout \
  20260830T172828Z-bet-execution-22b95054 --status ok \
  --evidence "child and root PR merge SHAs, mainline replay, live read-only canary, and released gitlink proof"
```

Expected: root main records T10-109 `done`, points to child authoritative main, mainline BET replay exits zero, and workflow closes `ok`. Do not mark the broader Documents convergence goal complete; proceed to the separate T10-110 physical quarantine BET.
