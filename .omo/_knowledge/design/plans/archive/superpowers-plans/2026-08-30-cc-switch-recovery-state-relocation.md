---
type: ssot
owner: governance-team
last_updated: 2026-09-03
---

# CC Switch Recovery-State Relocation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build, merge, and operate a reversible Workspace transaction that moves the two inactive CC Switch recovery roots out of Documents into durable native App Support recovery storage.

**Architecture:** A focused library owns deterministic inventory, policy checks, staged movement, manifest verification, and rollback. The existing registered `bin/gac/documents-domain-owner-job.py` entry exposes a narrow `client-recovery` subcommand with `plan`, `apply`, `verify`, and `rollback`; the existing migration registry remains the sole family authority. Delivery is split into an implementation PR and a later host-closeout PR so host mutation uses code already reachable from main.

**Tech Stack:** Python 3.9-compatible standard library, pytest, YAML registries, Agent Workflow, GitHub Actions.

## Global Constraints

- Source roots are exactly `Documents/.codex-optimize-log` and `Documents/.cc-switch-recovery2`.
- Final target is exactly `~/Library/Application Support/CC_Switch Recovery/2026-08-30`.
- Never touch active `~/Library/Application Support/CC_Switch` or either iCloud `SharedConf/CC_Switch*` tree.
- Never follow symlinks, overwrite a target/source collision, accept a partial inventory, or expose a force/permanent-delete mode.
- Require a fresh `documents.consumer-audit.v1` receipt with `status=ok`, `forbidden_executors=0`, and `unmatched=0`.
- Preserve every regular file byte, mode, relative path, root name, and canonical tree fingerprint.
- Recognizable non-empty SQLite databases must run read-only `PRAGMA quick_check`; healthy files remain `ok`, pre-existing damaged recovery files replay byte-identical as `corrupt-preserved`, and at least one database must be healthy.
- Production code must parse and execute on `/usr/bin/python3` (Python 3.9); do not use `X | None`, `list[str]`, or APIs newer than Python 3.9.
- Keep L4 classifier changes, `_inbox/hourly_runner*.log`, public-runtime loss, and historical root-oneoff receipt loss outside this BET.
- Engineering, operational, and value evidence remain separate; value stays `NOT_PROVEN`.

---

### Task 1: Deterministic inventory and preflight policy

**Files:**
- Create: `lib/documents_client_recovery_relocation.py`
- Create: `tests/test_documents_client_recovery_relocation.py`

**Interfaces:**
- Produces: `RelocationPaths`, `RelocationError`, `inventory_sources()`, `plan_relocation()`.
- Consumes: a parsed consumer receipt, optional injected handle list, and optional injected available-byte value.
- Later tasks consume the exact manifest entry shape emitted here.

- [ ] **Step 1: Write failing inventory and policy tests**

Add fixtures that create both hidden source roots with one valid SQLite file,
one SQL dump, one zero-byte file, and one configuration backup. Add these tests:

```python
def test_plan_inventories_both_exact_roots_and_fingerprints_all_files(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    plan = relocation.plan_relocation(
        _paths(layout),
        consumer_receipt=_consumer_receipt(),
        source_handles=[],
        available_bytes=10**9,
    )
    assert plan["schema"] == "documents-client-recovery-relocation/v1"
    assert plan["status"] == "planned"
    assert plan["summary"] == {"files": 7, "bytes": _fixture_bytes(layout)}
    assert {item["relative_path"].split("/", 1)[0] for item in plan["files"]} == {
        ".codex-optimize-log",
        ".cc-switch-recovery2",
    }
    assert plan["source_fingerprint"].startswith("sha256:")


@pytest.mark.parametrize("bad_node", ("file-symlink", "directory-symlink", "fifo"))
def test_plan_rejects_symlink_and_non_regular_nodes(tmp_path: Path, bad_node: str) -> None:
    layout = _layout(tmp_path)
    _add_bad_node(layout, bad_node)
    with pytest.raises(relocation.RelocationError, match="regular non-symlink"):
        relocation.plan_relocation(
            _paths(layout),
            consumer_receipt=_consumer_receipt(),
            source_handles=[],
            available_bytes=10**9,
        )


def test_plan_rejects_wrong_source_names_target_boundary_and_active_data_overlap(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    for paths in _unsafe_path_variants(layout):
        with pytest.raises(relocation.RelocationError, match="boundary"):
            relocation.plan_relocation(
                paths,
                consumer_receipt=_consumer_receipt(),
                source_handles=[],
                available_bytes=10**9,
            )


def test_plan_rejects_handles_disk_shortage_and_unhealthy_consumer(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    with pytest.raises(relocation.RelocationError, match="open handle"):
        relocation.plan_relocation(
            _paths(layout),
            consumer_receipt=_consumer_receipt(),
            source_handles=[str(layout.source_roots[0] / "backup.db")],
            available_bytes=10**9,
        )
    with pytest.raises(relocation.RelocationError, match="insufficient disk"):
        relocation.plan_relocation(
            _paths(layout),
            consumer_receipt=_consumer_receipt(),
            source_handles=[],
            available_bytes=1,
        )
    with pytest.raises(relocation.RelocationError, match="consumer"):
        relocation.plan_relocation(
            _paths(layout),
            consumer_receipt=_consumer_receipt(forbidden=1),
            source_handles=[],
            available_bytes=10**9,
        )
```

- [ ] **Step 2: Run RED and confirm missing module/API is the failure**

Run:

```bash
uv run --with pyyaml --with pytest python -m pytest \
  tests/test_documents_client_recovery_relocation.py -q
```

Expected: collection fails because `lib.documents_client_recovery_relocation`
does not exist. Fix fixture-only errors until the failure is exclusively the
missing production module.

- [ ] **Step 3: Implement the data model, inventory, and policy checks**

Create the following public surface and keep all helper annotations compatible
with Python 3.9:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

SCHEMA = "documents-client-recovery-relocation/v1"
SOURCE_NAMES = (".codex-optimize-log", ".cc-switch-recovery2")
ACTIVE_DATA_NAME = "CC_Switch"


class RelocationError(RuntimeError):
    """Stable fail-closed recovery relocation error."""

    def __init__(self, message: str, *, code: str = "RELOCATION_FAILED") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class RelocationPaths:
    documents_root: Path
    source_roots: Tuple[Path, Path]
    target_root: Path
    rollback_receipt: Path

    @property
    def staging_root(self) -> Path:
        return self.target_root.parent / ("." + self.target_root.name + ".staging")


def inventory_sources(paths: RelocationPaths) -> List[Dict[str, Any]]:
    _validate_path_boundaries(paths)
    first = _inventory_once(paths)
    second = _inventory_once(paths)
    if first != second:
        raise RelocationError("source tree changed during inventory")
    return first


def plan_relocation(
    paths: RelocationPaths,
    *,
    consumer_receipt: Dict[str, Any],
    source_handles: Optional[Sequence[str]] = None,
    available_bytes: Optional[int] = None,
) -> Dict[str, Any]:
    files = inventory_sources(paths)
    _validate_consumer_receipt(consumer_receipt)
    handles = list(source_handles) if source_handles is not None else _open_handles(paths.source_roots)
    if handles:
        raise RelocationError("source recovery state has an open handle")
    total = sum(int(item["bytes"]) for item in files)
    free = available_bytes if available_bytes is not None else _available_bytes(paths.target_root.parent)
    if free < total + 1024 * 1024:
        raise RelocationError("insufficient disk space for staged recovery relocation")
    _require_targets_absent(paths)
    sqlite = _sqlite_checks(Path(str(item["source"])) for item in files)
    return {
        "schema": SCHEMA,
        "status": "planned",
        "documents_root": str(paths.documents_root.resolve()),
        "source_roots": [str(root.resolve()) for root in paths.source_roots],
        "target_root": str(paths.target_root.resolve()),
        "staging_root": str(paths.staging_root.resolve()),
        "files": files,
        "summary": {"files": len(files), "bytes": total},
        "source_fingerprint": _canonical_fingerprint(files),
        "sqlite_checks": sqlite,
        "consumer_summary": dict(consumer_receipt["summary"]),
        "permanent_deletion": False,
    }
```

`_inventory_once()` must use `os.walk(root, followlinks=False)`, `lstat()`,
`stat.S_ISREG`, lexical containment, one MiB streaming SHA-256, and sorted POSIX
relative paths prefixed by the source root name. `_validate_path_boundaries()`
must require exact direct-child source names, a target below Application Support,
and a target outside `Application Support/CC_Switch`.

- [ ] **Step 4: Run GREEN and Python 3.9 syntax checks**

Run:

```bash
uv run --with pyyaml --with pytest python -m pytest \
  tests/test_documents_client_recovery_relocation.py -q
/usr/bin/python3 -m py_compile lib/documents_client_recovery_relocation.py
```

Expected: all Task 1 tests pass and `/usr/bin/python3` exits 0.

- [ ] **Step 5: Commit the Task 1 code lane**

```bash
git add lib/documents_client_recovery_relocation.py \
  tests/test_documents_client_recovery_relocation.py
git commit --only lib/documents_client_recovery_relocation.py \
  tests/test_documents_client_recovery_relocation.py \
  -m "feat(documents): inventory CC Switch recovery state"
```

---

### Task 2: Reversible staged transaction, verification, and rollback

**Files:**
- Modify: `lib/documents_client_recovery_relocation.py`
- Modify: `tests/test_documents_client_recovery_relocation.py`

**Interfaces:**
- Consumes: `RelocationPaths` and planned manifest shape from Task 1.
- Produces: `apply_relocation()`, `verify_relocation()`, `rollback_relocation()`.
- Guarantees: completed manifest is the only authority for verify/rollback.

- [ ] **Step 1: Add failing transaction and SQLite tests**

```python
def test_apply_moves_complete_snapshot_through_staging_and_publishes_manifest(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    result = relocation.apply_relocation(
        _paths(layout),
        consumer_receipt=_consumer_receipt(),
        source_handles=[],
        available_bytes=10**9,
    )
    assert result["status"] == "completed"
    assert not any(root.exists() for root in layout.source_roots)
    assert layout.target_root.is_dir()
    assert not _paths(layout).staging_root.exists()
    manifest = json.loads((layout.target_root / "manifest.json").read_text())
    assert manifest["target_fingerprint"] == manifest["source_fingerprint"]
    assert manifest["summary"]["files"] == 7


def test_apply_rolls_back_every_move_when_late_verification_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    layout = _layout(tmp_path)
    monkeypatch.setattr(relocation, "_verify_staging", _raise_verification_error)
    with pytest.raises(relocation.RelocationError, match="target verification"):
        relocation.apply_relocation(
            _paths(layout),
            consumer_receipt=_consumer_receipt(),
            source_handles=[],
            available_bytes=10**9,
        )
    assert all(root.is_dir() for root in layout.source_roots)
    assert not layout.target_root.exists()
    assert not _paths(layout).staging_root.exists()


def test_apply_rejects_source_drift_and_target_collision_without_partial_move(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    plan = relocation.plan_relocation(
        _paths(layout),
        consumer_receipt=_consumer_receipt(),
        source_handles=[],
        available_bytes=10**9,
    )
    (layout.source_roots[0] / "late.txt").write_text("drift")
    with pytest.raises(relocation.RelocationError, match="source tree changed"):
        relocation.apply_plan(_paths(layout), plan)
    assert all(root.is_dir() for root in layout.source_roots)


def test_sqlite_quick_check_records_preexisting_corruption_for_byte_preservation(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    (layout.source_roots[0] / "corrupt.db").write_bytes(b"SQLite format 3\x00broken")
    plan = relocation.plan_relocation(
        _paths(layout),
        consumer_receipt=_consumer_receipt(),
        source_handles=[],
        available_bytes=10**9,
    )
    record = next(item for item in plan["sqlite_checks"] if item["relative_path"].endswith("corrupt.db"))
    assert record["status"] == "corrupt-preserved"
    assert record["details_sha256"].startswith("sha256:")


def test_verify_and_rollback_use_manifest_and_never_overwrite_source(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    relocation.apply_relocation(
        _paths(layout),
        consumer_receipt=_consumer_receipt(),
        source_handles=[],
        available_bytes=10**9,
    )
    verified = relocation.verify_relocation(_paths(layout), consumer_receipt=_consumer_receipt())
    assert verified["status"] == "verified"
    layout.source_roots[0].mkdir()
    with pytest.raises(relocation.RelocationError, match="source collision"):
        relocation.rollback_relocation(_paths(layout), target_handles=[])
    layout.source_roots[0].rmdir()
    rolled_back = relocation.rollback_relocation(_paths(layout), target_handles=[])
    assert rolled_back["status"] == "rolled_back"
    assert all(root.is_dir() for root in layout.source_roots)
    assert layout.rollback_receipt.is_file()
```

- [ ] **Step 2: Run RED and confirm missing transaction functions**

Run the focused test file. Expected: tests fail because `apply_plan`,
`apply_relocation`, `verify_relocation`, and `rollback_relocation` are absent.

- [ ] **Step 3: Implement staged move, manifest publication, verify, and rollback**

Add these exact orchestration functions:

```python
def apply_relocation(
    paths: RelocationPaths,
    *,
    consumer_receipt: Dict[str, Any],
    source_handles: Optional[Sequence[str]] = None,
    available_bytes: Optional[int] = None,
) -> Dict[str, Any]:
    plan = plan_relocation(
        paths,
        consumer_receipt=consumer_receipt,
        source_handles=source_handles,
        available_bytes=available_bytes,
    )
    return apply_plan(paths, plan)


def apply_plan(paths: RelocationPaths, plan: Dict[str, Any]) -> Dict[str, Any]:
    if plan.get("schema") != SCHEMA or plan.get("status") != "planned":
        raise RelocationError("relocation plan is malformed")
    if inventory_sources(paths) != _source_entries(plan):
        raise RelocationError("source tree changed before apply")
    moved: List[Tuple[Path, Path]] = []
    try:
        paths.staging_root.mkdir(parents=True, mode=0o700)
        for item in plan["files"]:
            source = Path(str(item["source"]))
            target = paths.staging_root / str(item["relative_path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(str(source), str(target))
            moved.append((source, target))
        _verify_staging(paths.staging_root, plan)
        completed = _completed_manifest(plan, paths.staging_root)
        _atomic_write_json(paths.staging_root / "manifest.json", completed, mode=0o600)
        _fsync_tree_boundary(paths.staging_root)
        _remove_empty_source_roots(paths)
        os.replace(str(paths.staging_root), str(paths.target_root))
        _fsync_directory(paths.target_root.parent)
        return _load_manifest(paths.target_root / "manifest.json")
    except Exception as exc:
        _restore_moves(moved)
        _remove_empty_staging(paths.staging_root)
        if isinstance(exc, RelocationError):
            raise
        raise RelocationError("relocation apply failed: " + str(exc))


def verify_relocation(
    paths: RelocationPaths,
    *,
    consumer_receipt: Dict[str, Any],
) -> Dict[str, Any]:
    manifest = _load_manifest(paths.target_root / "manifest.json")
    _validate_consumer_receipt(consumer_receipt)
    _verify_final_target(paths, manifest)
    return {
        "schema": SCHEMA,
        "status": "verified",
        "manifest": str(paths.target_root / "manifest.json"),
        "summary": dict(manifest["summary"]),
        "target_fingerprint": manifest["target_fingerprint"],
        "rollback_available": True,
        "source_roots_absent": True,
        "sqlite_checks": list(manifest["sqlite_checks"]),
        "consumer_summary": dict(consumer_receipt["summary"]),
    }


def rollback_relocation(
    paths: RelocationPaths,
    *,
    target_handles: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    manifest = _load_manifest(paths.target_root / "manifest.json")
    _verify_final_target(paths, manifest)
    handles = list(target_handles) if target_handles is not None else _open_handles((paths.target_root,))
    if handles:
        raise RelocationError("target recovery state has an open handle")
    if any(root.exists() or root.is_symlink() for root in paths.source_roots):
        raise RelocationError("source collision prevents rollback")
    moved = _move_manifest_files_back(paths, manifest)
    _verify_restored_sources(paths, manifest)
    receipt = _rollback_receipt(manifest, moved)
    _atomic_write_json(paths.rollback_receipt, receipt, mode=0o600)
    _move_manifest_to_receipt_parent(paths)
    return receipt
```

All lower-level helpers must compare `node_type`, `bytes`, `mode`, `sha256`,
and relative path; rollback must iterate reversed manifest order. Directory
cleanup uses `Path.rmdir()` only after checking exact emptiness and never calls
recursive delete.

- [ ] **Step 4: Run GREEN, mutation-focused regressions, and Python 3.9 compile**

```bash
uv run --with pyyaml --with pytest python -m pytest \
  tests/test_documents_client_recovery_relocation.py -q
/usr/bin/python3 -m py_compile lib/documents_client_recovery_relocation.py
git diff --check
```

Expected: all tests pass, compile exits 0, and diff check is clean.

- [ ] **Step 5: Commit the Task 2 code lane**

```bash
git add lib/documents_client_recovery_relocation.py \
  tests/test_documents_client_recovery_relocation.py
git commit --only lib/documents_client_recovery_relocation.py \
  tests/test_documents_client_recovery_relocation.py \
  -m "feat(documents): relocate client recovery state safely"
```

---

### Task 3: Existing owner-job CLI and required CI wiring

**Files:**
- Modify: `lib/documents_client_recovery_relocation.py`
- Modify: `bin/gac/documents-domain-owner-job.py`
- Modify: `tests/test_documents_client_recovery_relocation.py`
- Modify: `.github/workflows/phase-gate-enforce.yml`

**Interfaces:**
- Existing entry: `documents-domain-owner-job.py client-recovery <command>`.
- Commands: `plan`, `apply`, `verify`, `rollback`.
- JSON success schema: `documents-client-recovery-relocation/v1`.
- JSON error schema: `documents-client-recovery-relocation-error/v1` with stable `code`, `command`, and `error`.

- [ ] **Step 1: Write failing owner-dispatch and phase-gate tests**

Test that the existing owner job accepts `client-recovery plan`, emits structured
JSON without mutation, returns stable errors, dispatches the real transaction,
and that phase-gate covers the library and focused test. Assert the existing
`bin/_registry/scripts/governance/documents-domain-owner-job.yaml` remains the
only script registration.

- [ ] **Step 2: Run RED and confirm the subcommand/wiring is absent**

Run the focused tests. Expected failures: `client-recovery` is not dispatched
and the new library/test paths are absent from phase-gate.

- [ ] **Step 3: Add library CLI main and delegate from the existing owner**

The library owns argparse and JSON rendering. Add this dispatch before the
existing generic job parser in `documents-domain-owner-job.py`:

```python
if arguments and arguments[0] == "client-recovery":
    from lib.documents_client_recovery_relocation import main as client_recovery_main

    return client_recovery_main(arguments[1:])
```

`plan` and `apply` require `--consumer-receipt`; `verify` also requires a fresh
receipt; `rollback` does not. Never add `--force`, `--delete`, mutable source
count overrides, or arbitrary default source names.

- [ ] **Step 4: Wire focused CI without adding a bin entry**

Add only `lib/documents_client_recovery_relocation.py` and
`tests/test_documents_client_recovery_relocation.py` to the Documents path
filter, focused pytest command, and Ruff command. The existing owner job path is
already wired and registered. Run `check-bin-quota-diff.py --base origin/main`
and require zero net bin growth.

- [ ] **Step 5: Run GREEN and real Python 3.9 owner execution**

```bash
uv run --with pyyaml --with pytest python -m pytest \
  tests/test_documents_client_recovery_relocation.py -q
/usr/bin/python3 bin/gac/documents-domain-owner-job.py client-recovery --help
python3 bin/ssot/script-registry.py validate
python3 bin/gac/check-bin-quota-diff.py --base origin/main
```

Expected: all commands exit 0 and the bin count remains flat.

- [ ] **Step 6: Commit by lane**

Commit the library/test code lane, the existing owner governance-code lane, and
the phase-gate config lane separately. Do not create a new script registration.

---

### Task 4: Migration-family ownership and implementation PR

**Files:**
- Modify: `.omo/_truth/registry/documents-content-plane-migrations.yaml`
- Modify: `tests/test_documents_client_recovery_relocation.py`
- Modify: `tests/test_documents_content_plane_migration_check.py`
- Create: `docs/reports/2026-08-30-cc-switch-recovery-state-relocation.md`

**Interfaces:**
- Produces one nonterminal `cc-switch-recovery-state` family.
- Removes only `.codex-optimize-log/**` from `root-oneoff-assets`.
- Does not alter root-oneoff historical evidence or terminal status.

- [ ] **Step 1: Write a failing unique-ownership registry test**

```python
def test_cc_switch_recovery_roots_have_one_nonterminal_owner() -> None:
    registry = yaml.safe_load(REGISTRY.read_text())
    families = {item["id"]: item for item in registry["families"]}
    root = families["root-oneoff-assets"]
    client = families["cc-switch-recovery-state"]
    assert ".codex-optimize-log/**" not in root["source_globs"]
    assert client["source_globs"] == [
        ".codex-optimize-log/**",
        ".cc-switch-recovery2/**",
    ]
    assert client["disposition"] == "relocate"
    assert client["owner"] == "cc-switch"
    assert client["status"] == "in_progress"
```

- [ ] **Step 2: Run RED and confirm the family is absent**

```bash
uv run --with pyyaml --with pytest python -m pytest \
  tests/test_documents_client_recovery_relocation.py \
  -k cc_switch_recovery_roots -q
```

Expected: failure because `cc-switch-recovery-state` is missing.

Update the existing workspace-registry expectation to keep
`candidate_count == 17`, add `cc-switch-recovery-state` to the expected family
set, and change `root-oneoff-assets` expected sample count from 2 to 1.

- [ ] **Step 3: Add the nonterminal family and implementation report**

Add this registry record without terminal evidence:

```yaml
- id: cc-switch-recovery-state
  source_globs:
  - .codex-optimize-log/**
  - .cc-switch-recovery2/**
  artifact_kind:
  - cache
  - runtime
  disposition: relocate
  owner: cc-switch
  replacement: $HOME/Library/Application Support/CC_Switch Recovery/2026-08-30
  consumer_refs:
  - bin/gac/documents-domain-owner-job.py
  - audit://documents/root-oneoff/consumer-scan-pending
  rollback: Use the completed manifest and rollback command; never overwrite a recreated source root.
  confirmation_gate: before_external_state
  status: in_progress
```

The report records implementation tests and explicitly says host `apply` is
pending. Do not add `evidence`, `transactions`, `verified_at`, or a terminal
status before the live move succeeds.

- [ ] **Step 4: Run all implementation verification**

```bash
uv run --with pyyaml --with pytest python -m pytest \
  tests/test_documents_client_recovery_relocation.py \
  tests/test_documents_content_plane_migration_check.py -q
/usr/bin/python3 bin/gac/documents-domain-owner-job.py client-recovery --help
uv run --with pyyaml python bin/gac/documents-content-plane-migration-check.py --json
uv run --with pyyaml python bin/ssot/doc-ssot-lint.py --json
make gac-local-gate
git diff --check
```

Expected: focused tests, migration check, doc SSOT, and GaC all pass.

- [ ] **Step 5: Commit registry and report in separate lanes**

```bash
git add .omo/_truth/registry/documents-content-plane-migrations.yaml \
  tests/test_documents_client_recovery_relocation.py \
  tests/test_documents_content_plane_migration_check.py
git commit --only .omo/_truth/registry/documents-content-plane-migrations.yaml \
  tests/test_documents_client_recovery_relocation.py \
  tests/test_documents_content_plane_migration_check.py \
  -m "governance(documents): assign CC Switch recovery ownership"

git add docs/reports/2026-08-30-cc-switch-recovery-state-relocation.md
git commit --only docs/reports/2026-08-30-cc-switch-recovery-state-relocation.md \
  -m "docs(documents): record recovery capability evidence"
```

- [ ] **Step 6: Verify workflow, push, merge the implementation PR, and prove main**

Run Agent Workflow verify with `--from-diff --execute`, push the independent
branch, open a PR, wait until every required check is completed and successful,
squash merge, fetch main, and prove the merge SHA is reachable. Do not run host
`apply` from the unmerged branch.

---

### Task 5: Mainline host cutover and closeout PR

**Files:**
- Modify: `.omo/_truth/registry/documents-content-plane-migrations.yaml`
- Modify: `docs/plans/3y-bet-ledger.yaml`
- Modify: `docs/reports/2026-08-30-cc-switch-recovery-state-relocation.md`
- Create: `.omo/_knowledge/retros/BET-Y1Q3-T10-108.md`
- Modify: `.omo/_truth/governance-evidence/waiver-2026-08-30-t10-108-bootstrap.md`

**Interfaces:**
- Consumes the implementation merge from authoritative main.
- Produces the durable App Support manifest, verified registry evidence, BET completion matrix, and closeout PR.

- [ ] **Step 1: Create a fresh full-profile clone from authoritative main and start the formal host run**

Bootstrap/status, start `bet-execution --profile governance-agent --bet
BET-Y1Q3-T10-108`, generate an affected-graph receipt, and claim all five
repository write surfaces before editing. Record the host target as an external
mutation surface in the run evidence. Bind the actual run identifier once:

```bash
export T10_108_RUN_ID="$(
  uv run --with pyyaml python bin/agent-workflow.py status --json |
    jq -r '.active_runs[] | select(.bet_id == "BET-Y1Q3-T10-108") | .run_id' |
    tail -1
)"
test -n "$T10_108_RUN_ID"
mkdir -p ".omo/evidence/$T10_108_RUN_ID"
```

- [ ] **Step 2: Generate a fresh consumer receipt and run a no-write plan**

```bash
uv run --project projects/l4-kernel python \
  bin/gac/documents-domain-owner-job.py consumer-audit \
  --documents-root /Users/xiamingxing/Documents \
  --registry .omo/_truth/registry/documents-content-plane-migrations.yaml \
  --launch-agents-root /Users/xiamingxing/Library/LaunchAgents \
  --scheduled-root /Users/xiamingxing/Documents/Claude/Scheduled \
  --workspace-root "$PWD" --json \
  > ".omo/evidence/$T10_108_RUN_ID/documents-consumer-audit.json"

/usr/bin/python3 bin/gac/documents-domain-owner-job.py client-recovery plan \
  --consumer-receipt ".omo/evidence/$T10_108_RUN_ID/documents-consumer-audit.json" \
  --json > ".omo/evidence/$T10_108_RUN_ID/cc-switch-recovery-plan.json"
```

Inspect the JSON and require exactly 21 files, 417772968 bytes, both exact
source roots, target absence, source handles zero, six healthy SQLite checks,
one byte-identical `corrupt-preserved` check, and
matching source fingerprint. Any changed count/bytes requires stopping for a
new reviewed snapshot; do not override it.

- [ ] **Step 3: Recheck quiescence and apply from mainline code**

Run `lsof +D` for both source roots and require no output. Then execute:

```bash
/usr/bin/python3 bin/gac/documents-domain-owner-job.py client-recovery apply \
  --consumer-receipt ".omo/evidence/$T10_108_RUN_ID/documents-consumer-audit.json" \
  --json | tee ".omo/evidence/$T10_108_RUN_ID/cc-switch-recovery-apply.json"
```

Expected: exit 0, `status=completed`, target manifest present, both source roots
absent, and no staging directory.

- [ ] **Step 4: Replay verify, SQLite checks, consumer audit, and full-tree L4 audit**

```bash
/usr/bin/python3 bin/gac/documents-domain-owner-job.py client-recovery verify \
  --consumer-receipt ".omo/evidence/$T10_108_RUN_ID/documents-consumer-audit-post.json" \
  --json | tee ".omo/evidence/$T10_108_RUN_ID/cc-switch-recovery-verify.json"
```

Regenerate the postflight consumer receipt before this command. Also run one
stable full-tree L4 audit and record counts without claiming that L4 classifier
semantics were fixed. Require target fingerprint parity, source absence,
rollback available, six recognizable SQLite checks `ok`, the known damaged
`current.db` check unchanged as `corrupt-preserved`, consumer
`forbidden_executors=0`, and `unmatched=0`.

- [ ] **Step 5: Write terminal evidence and completion matrix**

Update the family to `status: verified` with source/target fingerprints,
manifest SHA-256, exact counts/bytes, consumer receipt, rollback reference, and
target path. Append the host evidence to the report, write the retro, mark the
waiver formal execution complete, and set T10-108 `status: done`. Generate the
exact completion matrix from measured evidence before applying the ledger patch:

```bash
export T10_108_IMPLEMENTATION_SHA="$(git rev-parse origin/main)"
export T10_108_REPORT_SHA="sha256:$(
  shasum -a 256 docs/reports/2026-08-30-cc-switch-recovery-state-relocation.md |
    awk '{print $1}'
)"
export T10_108_RETRO_SHA="sha256:$(
  shasum -a 256 .omo/_knowledge/retros/BET-Y1Q3-T10-108.md |
    awk '{print $1}'
)"

uv run --with pyyaml python - <<'PY'
import os
import yaml

report = {
    "ref": "receipt://docs/reports/2026-08-30-cc-switch-recovery-state-relocation.md",
    "sha256": os.environ["T10_108_REPORT_SHA"],
}
spec = {
    "ref": "receipt://docs/superpowers/specs/2026-08-30-cc-switch-recovery-state-relocation-design.md",
    "sha256": "sha256:2c73609e12406af70db5a0a6f82b3516e8b6c460c8759022a72494592bf32cd9",
}
retro = {
    "ref": "receipt://.omo/_knowledge/retros/BET-Y1Q3-T10-108.md",
    "sha256": os.environ["T10_108_RETRO_SHA"],
}
matrix = {
    "schema_version": "completion-evidence-matrix/v1",
    "axes": {
        "engineering": {
            "status": "VERIFIED",
            "evidence": {
                "merged_reachable_commit": {
                    "ref": "git://origin/main@" + os.environ["T10_108_IMPLEMENTATION_SHA"]
                },
                "tests": report,
                "diff": spec,
                "rollback": report,
            },
        },
        "operational": {
            "status": "PROVEN",
            "evidence": {
                "live_canary": report,
                "fresh_receipt": report,
                "replay": retro,
                "cleanup": report,
            },
        },
        "value": {"status": "NOT_PROVEN", "evidence": {}},
    },
    "overall_state": "delivery_accepted",
}
print(yaml.safe_dump({"completion_evidence": matrix}, sort_keys=False), end="")
PY
```

Use the rendered block verbatim in the T10-108 record after independently
proving `T10_108_IMPLEMENTATION_SHA` is an ancestor of `origin/main`.

- [ ] **Step 6: Verify, commit by lane, merge closeout PR, and replay main**

Run focused tests, migration check, direct T10-108 completion-matrix validation,
doc SSOT, SSOT guardian, GaC, and workflow verify. Commit governance state,
docs-data ledger, and docs evidence separately. Push, open the closeout PR, wait
for every required check, squash merge, verify the merge SHA on origin/main,
re-run `documents-domain-owner-job.py client-recovery verify` from mainline code, and close the
formal workflow `ok`.

---

## Plan self-review

- Spec coverage: every preflight, apply, verification, rollback, registry,
  testing, host, evidence, PR, and value-boundary requirement maps to Tasks 1–5.
- Scope: L4 classification and runner-log cleanup remain deliberately separate
  follow-up BETs, as required by the approved specification.
- Interfaces: `RelocationPaths`, manifest schema, command names, source names,
  target path, and evidence filenames are consistent across all tasks.
- Delivery topology: implementation merges before host mutation; closeout uses a
  fresh mainline clone and a separate PR.
