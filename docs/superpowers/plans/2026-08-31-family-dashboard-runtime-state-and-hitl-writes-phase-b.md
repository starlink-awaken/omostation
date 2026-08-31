---
status: active
lifecycle: plan
owner: family-hub
created: 2026-08-30
last-reviewed: 2026-08-30
title: Family dashboard runtime-state and HITL writes Phase B implementation plan
type: doc
bet_id: BET-Y1Q3-T10-122
spec_ref: repo://docs/superpowers/specs/2026-08-31-family-dashboard-runtime-state-and-hitl-writes-phase-b-design.md
spec_version: 1.0.0
spec_digest: sha256:1d76adb508dca1a13f57148d0d48f309770d141bc165b49f85a45ae2c33b85fb
---

# Family Dashboard Runtime-State and HITL Writes Phase B Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Materialize the real family dashboard state in Workspace and replace every direct Documents mutation with a Cockpit-approved, OMO-recorded, uncached Agora-routed, family-hub CAS transaction.

**Architecture:** Delivery is child-first and split into two family-hub releases around the authority chain. Family-hub first provides deterministic runtime and mutation primitives; OMO then becomes the single proposal/receipt writer; Agora registers the internal zero-cache route; Cockpit authenticates ingress and approval; a second family-hub PR wires Dashboard routes to the now-available authorities. Root adopts only child-main commits, then executes real read-only state migration and a separately confirmed reversible canary.

**Tech Stack:** Python 3.13, pytest, Pydantic/PyYAML, TypeScript, Bun/Vitest/Playwright, FastAPI, OMO atomic YAML IO, Agora BOS internal resolver, Git submodules, GitHub required checks.

## Global Constraints

- Source specification is immutable at `sha256:1d76adb508dca1a13f57148d0d48f309770d141bc165b49f85a45ae2c33b85fb`.
- Documents is the content plane; Workspace owns execution, runtime, state, proposal payloads, receipts, and rollback bytes.
- Dashboard never opens a Documents file for writing.
- Cockpit is the only human approval entry; callers may not choose `approved_by`.
- OMO is the only `.omo/state/proposals` and durable HITL receipt writer.
- Agora is routing fabric only; use one declarative `internal` service and never `tools/call` or shell command construction.
- The mutation BOS prefix has `cache_ttl: 0`; a successful mutation response may never be replayed from cache.
- Runtime roots must be absolute, outside Git/Documents, non-symlink, private-mode, and collision-free.
- `.next`, `node_modules`, `.env.local`, credentials, browser auth, raw Documents content, and legacy AI cache are never copied into active state or Git.
- Direct Documents writes, direct `.omo` writes, environment bypasses, parent-directory fallback, and Git backup behavior are prohibited.
- Every code change uses RED → GREEN, exact claims, child commit/tag/PR/CI/merge before root gitlink adoption, and mainline replay.
- A real Documents canary is forbidden until the separately tracked danger-gate approval file exists.
- Phase C entry cutover, persistent service/port/schedule, old-app retirement, migration terminal state, value, and Documents-wide purity remain out of scope.

## File and Interface Map

| Owner | File | Responsibility |
|---|---|---|
| family-hub | `src/family_hub/dashboard_runtime.py` | runtime inventory, plan, staging, parity, promote, verify |
| family-hub | `src/family_hub/dashboard_mutation.py` | private payload staging and approved CAS mutation/rollback |
| family-hub | `src/family_hub/dashboard_phase_b.py` | stable CLI for plan/apply/verify runtime and canary |
| family-hub | `tests/test_dashboard_phase_b.py` | Python runtime/mutation contract tests |
| family-hub dashboard | `src/lib/hitl-proposals.ts` | stage payload and call authenticated Cockpit proposal ingress |
| family-hub dashboard | `src/app/api/file/save/route.ts` | HTTP 202 proposal-only file-save route |
| family-hub dashboard | `src/lib/ssot-writer.ts` | render vaccine/milestone proposed bytes, never write Documents |
| family-hub dashboard | `src/lib/state-snapshot.ts` | write pathless Documents integrity snapshot receipt to state |
| family-hub dashboard | `tests/boundaries/write-policy.test.ts` | no-direct-write and proposal behavior |
| OMO | `src/omo/omo_cockpit_bridge.py` | unique HITL proposal ingress/list/approve/reject and terminal receipts |
| OMO | `tests/test_omo_cockpit_bridge.py` | broker and receipt tests |
| Agora | `etc/bos-services.yaml` | exact internal family-hub mutation service |
| Agora | `src/agora/agora-bos-rates.yaml` | zero TTL for mutation URI |
| Agora | `tests/unit/test_bos_resolver.py` | exact route/function/no-cache execution |
| Cockpit | `src/cockpit/adapters/omo.py` | thin re-export of canonical OMO bridge |
| Cockpit | `src/cockpit/web/api_proposals.py` | strict proposal create/approve/reject HTTP API |
| Cockpit | `src/cockpit/tests/test_api_proposals.py` | authenticated principal and BOS result tests |
| root | `.omo/_truth/registry/mutation-surfaces.yaml` | canonical OMO writer registration |
| root | `.omo/_truth/registry/documents-content-plane-migrations.yaml` | Phase B progress evidence, still non-terminal |
| root | `tests/test_documents_content_plane_migration_check.py` | non-terminal Phase B registry contract |
| runtime | `runtime/family-hub/dashboard/**` | private real state, payload, mutation and migration receipts |

## Execution Topology

Use one official root delivery clone per root/design/closeout attempt and one separate root delivery clone per child PR. In a child attempt, initialize the target submodule plus every declared local path dependency, create the feature branch only inside the target child, and commit there before changing the root gitlink. Never reuse the shared `/Users/xiamingxing/Workspace` checkout or a different attempt's submodule worktree. Each writer must:

```bash
make agent-workflow-bootstrap
make agent-workflow-status
START_JSON="$(uv run --with pyyaml python bin/agent-workflow.py start bet-execution \
  --profile governance-agent --bet BET-Y1Q3-T10-122 \
  --objective "Implement the current T10-122 plan task" --json)"
RUN_ID="$(printf '%s' "$START_JSON" | jq -r '.run_id')"
python3 bin/gac/affected-graph.py \
  --changed-projects workspace-root family-hub omo agora cockpit \
  --workspace-root . \
  --output ".omo/evidence/$RUN_ID/affected-graph-receipt.json" --json
```

Use the run id and affected-graph receipt literally for every exact path listed in the task's **Files** block. For child commits, use the child repository's own branch, commit, tag, PR, required CI, and merged child `origin/main`. Root gitlink SHAs must come from `git -C projects/family-hub rev-parse origin/main`, `git -C projects/omo rev-parse origin/main`, `git -C projects/agora rev-parse origin/main`, and `git -C projects/cockpit rev-parse origin/main` after fetch.

Create these exact child/root branches from each repository's fetched `origin/main` before its first edit:

| Delivery | Repository | Branch |
|---|---|---|
| family-hub PR A | `projects/family-hub` | `agent/codex-documents-convergence--t10-122-family-core-20260831-01` |
| OMO | `projects/omo` | `agent/codex-documents-convergence--t10-122-omo-hitl-20260831-01` |
| Agora | `projects/agora` | `agent/codex-documents-convergence--t10-122-agora-hitl-20260831-01` |
| Cockpit | `projects/cockpit` | `agent/codex-documents-convergence--t10-122-cockpit-hitl-20260831-01` |
| family-hub PR B | `projects/family-hub` | `agent/codex-documents-convergence--t10-122-family-dashboard-routes-20260831-01` |
| root authority | root | `agent/codex-documents-convergence--t10-122-root-authorities-20260831-01` |

For example, family-hub PR A starts with:

```bash
git -C projects/family-hub fetch origin main
git -C projects/family-hub switch -c \
  agent/codex-documents-convergence--t10-122-family-core-20260831-01 origin/main
```

Apply the same exact `fetch` plus `switch -c` operation using the literal branch string from the table for each named repository. Collision with an existing branch stops the attempt; inspect its PR/main ancestry rather than force-reusing it.

---

### Task 1: Family-Hub Runtime Inventory and Deterministic Plan

**Files:**
- Create: `projects/family-hub/src/family_hub/dashboard_runtime.py`
- Create: `projects/family-hub/src/family_hub/dashboard_phase_b.py`
- Create: `projects/family-hub/tests/test_dashboard_phase_b.py`

**Interfaces:**
- Produces: `plan_runtime(documents_root: Path, legacy_app_root: Path, state_root: Path) -> dict[str, Any]`, `plan_fingerprint(plan: dict[str, Any]) -> str`, and `main(argv: list[str] | None) -> int`.
- Consumes later: Task 2 calls `plan_runtime`; Task 10 invokes `python -m family_hub.dashboard_phase_b`.

- [ ] **Step 1: Write failing plan-contract tests**

```python
from pathlib import Path
from types import SimpleNamespace

import pytest

import family_hub.dashboard_runtime as runtime
from family_hub.dashboard_runtime import PhaseBError, plan_runtime


def _seed_runtime_source(tmp_path: Path) -> tuple[Path, Path, Path]:
    documents = tmp_path / "Documents" / "family"
    legacy = documents / "family-dashboard-app"
    manifests = legacy / "data-manifest"
    generated = legacy / "app-data"
    manifests.mkdir(parents=True)
    generated.mkdir()
    for name in ("summary", "members", "health", "growth", "daily", "assets"):
        (manifests / f"{name}.yaml").write_text(f"title: {name}\n", encoding="utf-8")
    (generated / "summary.json").write_text('{"value": 1}\n', encoding="utf-8")
    state = tmp_path / "Workspace" / "runtime" / "family-hub" / "dashboard"
    return documents, legacy, state


def test_runtime_plan_is_private_pathless_and_deterministic(tmp_path: Path) -> None:
    documents, legacy, state = _seed_runtime_source(tmp_path)
    first = plan_runtime(documents, legacy, state)
    second = plan_runtime(documents, legacy, state)
    assert first == second
    assert first["schema"] == "family-dashboard-runtime-plan/v1"
    assert first["manifest_count"] == 6
    assert first["legacy_generated_count"] == 1
    assert first["state_root_ref"] == "runtime://family-hub/dashboard"
    assert str(tmp_path) not in str(first)


def test_runtime_plan_rejects_existing_target_and_symlink(tmp_path: Path) -> None:
    documents, legacy, state = _seed_runtime_source(tmp_path)
    state.mkdir(parents=True)
    with pytest.raises(PhaseBError, match="target must be absent"):
        plan_runtime(documents, legacy, state)


def test_runtime_plan_rejects_insufficient_disk(tmp_path: Path, monkeypatch) -> None:
    documents, legacy, state = _seed_runtime_source(tmp_path)
    monkeypatch.setattr(runtime.shutil, "disk_usage", lambda _path: SimpleNamespace(free=0))
    with pytest.raises(PhaseBError, match="insufficient disk"):
        plan_runtime(documents, legacy, state)
```

- [ ] **Step 2: Run the tests and prove RED**

Run:

```bash
cd projects/family-hub
uv run pytest tests/test_dashboard_phase_b.py -q
```

Expected: collection fails because `family_hub.dashboard_runtime` does not exist.

- [ ] **Step 3: Implement the plan model and guarded inventory**

```python
# src/family_hub/dashboard_runtime.py
from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any, Final

import yaml

PLAN_SCHEMA: Final = "family-dashboard-runtime-plan/v1"
MANIFEST_NAMES: Final = ("summary", "members", "health", "growth", "daily", "assets")


class PhaseBError(ValueError):
    """A Phase B runtime or mutation transaction cannot proceed safely."""


def _regular_root(path: Path, label: str, *, must_exist: bool = True) -> Path:
    raw = path.expanduser()
    if must_exist and (not raw.is_dir() or raw.is_symlink()):
        raise PhaseBError(f"{label} must be a regular directory")
    if raw.exists() and raw.is_symlink():
        raise PhaseBError(f"{label} must not be a symlink")
    return raw.resolve()


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _entry(path: Path, base: Path) -> dict[str, Any]:
    stat = path.stat(follow_symlinks=False)
    if not path.is_file() or path.is_symlink():
        raise PhaseBError("inventory contains a non-regular node")
    return {
        "relative_path": path.relative_to(base).as_posix(),
        "sha256": _sha(path),
        "bytes": stat.st_size,
        "mode": oct(stat.st_mode & 0o7777),
    }


def _fingerprint(entries: list[dict[str, Any]]) -> str:
    raw = json.dumps(entries, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


def plan_runtime(documents_root: Path, legacy_app_root: Path, state_root: Path) -> dict[str, Any]:
    documents = _regular_root(documents_root, "Documents root")
    legacy = _regular_root(legacy_app_root, "legacy app root")
    target = _regular_root(state_root, "state root", must_exist=False)
    if not legacy.is_relative_to(documents):
        raise PhaseBError("legacy app must be below Documents")
    if target.exists():
        raise PhaseBError("target must be absent")
    if target.is_relative_to(documents) or target.is_relative_to(legacy):
        raise PhaseBError("state root must be outside Documents")
    manifest_root = legacy / "data-manifest"
    manifests = [manifest_root / f"{name}.yaml" for name in MANIFEST_NAMES]
    if any(not path.is_file() or path.is_symlink() for path in manifests):
        raise PhaseBError("exact six manifests are required")
    for path in manifests:
        if not isinstance(yaml.safe_load(path.read_text(encoding="utf-8")), dict):
            raise PhaseBError("manifest must be a mapping")
    generated_root = legacy / "app-data"
    generated = sorted(path for path in generated_root.glob("*.json") if path.is_file() and not path.is_symlink())
    entries = [_entry(path, legacy) for path in [*manifests, *generated]]
    disk_probe = target.parent
    while not disk_probe.exists() and disk_probe != disk_probe.parent:
        disk_probe = disk_probe.parent
    required_bytes = sum(int(entry["bytes"]) for entry in entries) * 2 + 64 * 1024 * 1024
    if shutil.disk_usage(disk_probe).free < required_bytes:
        raise PhaseBError("insufficient disk for runtime staging")
    return {
        "schema": PLAN_SCHEMA,
        "status": "planned",
        "state_root_ref": "runtime://family-hub/dashboard",
        "manifest_count": len(manifests),
        "legacy_generated_count": len(generated),
        "required_free_bytes": required_bytes,
        "entries": entries,
        "fingerprint": _fingerprint(entries),
        "writes_documents": False,
    }


def plan_fingerprint(plan: dict[str, Any]) -> str:
    value = plan.get("fingerprint")
    if plan.get("schema") != PLAN_SCHEMA or not isinstance(value, str):
        raise PhaseBError("runtime plan is invalid")
    return value
```

```python
# src/family_hub/dashboard_phase_b.py
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .dashboard_runtime import plan_runtime


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="family-dashboard-phase-b")
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan-runtime")
    plan.add_argument("--documents-root", type=Path, required=True)
    plan.add_argument("--legacy-app-root", type=Path, required=True)
    plan.add_argument("--state-root", type=Path, required=True)
    plan.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    payload = plan_runtime(args.documents_root, args.legacy_app_root, args.state_root)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True) if args.json else payload["fingerprint"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run focused tests and Ruff**

Run:

```bash
cd projects/family-hub
uv run pytest tests/test_dashboard_phase_b.py -q
uv run ruff check src/family_hub/dashboard_runtime.py src/family_hub/dashboard_phase_b.py tests/test_dashboard_phase_b.py
uv run ruff format --check src/family_hub/dashboard_runtime.py src/family_hub/dashboard_phase_b.py tests/test_dashboard_phase_b.py
```

Expected: tests pass; Ruff emits zero findings.

- [ ] **Step 5: Commit and tag**

```bash
git add src/family_hub/dashboard_runtime.py src/family_hub/dashboard_phase_b.py tests/test_dashboard_phase_b.py
git commit -m "feat: plan family dashboard runtime state"
git tag -a t10-122-family-runtime-plan -m "T10-122 family runtime plan"
```

---

### Task 2: Family-Hub Runtime Apply, Parity, Promotion, and Verification

**Files:**
- Modify: `projects/family-hub/src/family_hub/dashboard_runtime.py`
- Modify: `projects/family-hub/src/family_hub/dashboard_phase_b.py`
- Modify: `projects/family-hub/tests/test_dashboard_phase_b.py`

**Interfaces:**
- Consumes: `plan_runtime`, `plan_fingerprint`, `PhaseBError` from Task 1.
- Produces: `apply_runtime(plan: dict[str, Any], *, documents_root: Path, legacy_app_root: Path, state_root: Path, expected_fingerprint: str, build_runner: BuildRunner) -> dict[str, Any]`, `verify_runtime(documents_root: Path, legacy_app_root: Path, state_root: Path, *, expected_fingerprint: str) -> dict[str, Any]`, CLI commands `apply-runtime` and `verify-runtime`.

- [ ] **Step 1: Add failing apply/rollback/parity tests**

```python
def test_apply_runtime_builds_in_staging_and_promotes_atomically(tmp_path: Path) -> None:
    documents, legacy, state = _seed_runtime_source(tmp_path)
    plan = plan_runtime(documents, legacy, state)

    def build(env: dict[str, str]) -> None:
        generated = Path(env["FAMILY_DASHBOARD_STATE_ROOT"]) / "generated"
        generated.mkdir(parents=True)
        (generated / "summary.json").write_text('{"value": 1}\n', encoding="utf-8")

    result = apply_runtime(
        plan,
        documents_root=documents,
        legacy_app_root=legacy,
        state_root=state,
        expected_fingerprint=plan["fingerprint"],
        build_runner=build,
    )
    assert result["status"] == "verified"
    assert (state / "manifests" / "summary.yaml").stat().st_mode & 0o777 == 0o600
    assert (state / "generated" / "summary.json").stat().st_mode & 0o777 == 0o600
    assert json.loads((state / "generated" / "summary.json").read_text())["value"] == 1
    assert not list(state.parent.glob(".dashboard.staging-*"))


def test_apply_runtime_failure_removes_staging_and_preserves_source(tmp_path: Path) -> None:
    documents, legacy, state = _seed_runtime_source(tmp_path)
    plan = plan_runtime(documents, legacy, state)
    before = (legacy / "data-manifest" / "summary.yaml").read_bytes()
    with pytest.raises(PhaseBError, match="build failed"):
        apply_runtime(
            plan,
            documents_root=documents,
            legacy_app_root=legacy,
            state_root=state,
            expected_fingerprint=plan["fingerprint"],
            build_runner=lambda _env: (_ for _ in ()).throw(RuntimeError("boom")),
        )
    assert not state.exists()
    assert (legacy / "data-manifest" / "summary.yaml").read_bytes() == before


def test_apply_runtime_parity_difference_names_product_and_does_not_promote(tmp_path: Path) -> None:
    documents, legacy, state = _seed_runtime_source(tmp_path)
    plan = plan_runtime(documents, legacy, state)

    def build(env: dict[str, str]) -> None:
        generated = Path(env["FAMILY_DASHBOARD_STATE_ROOT"]) / "generated"
        generated.mkdir(parents=True)
        (generated / "summary.json").write_text('{"value": 2}\n', encoding="utf-8")

    with pytest.raises(PhaseBError, match="normalized parity differs: summary.json"):
        apply_runtime(
            plan,
            documents_root=documents,
            legacy_app_root=legacy,
            state_root=state,
            expected_fingerprint=plan["fingerprint"],
            build_runner=build,
        )
    assert not state.exists()
    assert not list(state.parent.glob(".dashboard.staging-*"))
```

- [ ] **Step 2: Run the new tests and prove RED**

Run: `cd projects/family-hub && uv run pytest tests/test_dashboard_phase_b.py -q`

Expected: FAIL because `apply_runtime` is undefined.

- [ ] **Step 3: Implement staged apply and normalized parity**

Add these exact public signatures and behavior:

```python
from collections.abc import Callable
import shutil
import tempfile

BuildRunner = Callable[[dict[str, str]], None]


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def _normalized_json(path: Path) -> Any:
    value = json.loads(path.read_text(encoding="utf-8"))
    if path.name == "build-meta.json" and isinstance(value, dict):
        value = {key: item for key, item in value.items() if key != "builtAt"}
    if path.name in {"summary.json", "members.json", "health.json", "growth.json", "daily.json", "assets.json"} and isinstance(value, dict):
        value = {key: item for key, item in value.items() if key != "updatedAt"}
    return value


def apply_runtime(
    plan: dict[str, Any],
    *,
    documents_root: Path,
    legacy_app_root: Path,
    state_root: Path,
    expected_fingerprint: str,
    build_runner: BuildRunner,
) -> dict[str, Any]:
    fresh = plan_runtime(documents_root, legacy_app_root, state_root)
    if fresh != plan or plan_fingerprint(plan) != expected_fingerprint:
        raise PhaseBError("source changed after plan")
    target = state_root.expanduser().resolve()
    staging = target.parent / f".dashboard.staging-{expected_fingerprint.removeprefix('sha256:')[:12]}"
    if staging.exists() or target.exists():
        raise PhaseBError("state target collision")
    try:
        (staging / "manifests").mkdir(parents=True)
        for name in MANIFEST_NAMES:
            destination = staging / "manifests" / f"{name}.yaml"
            shutil.copyfile(legacy_app_root / "data-manifest" / f"{name}.yaml", destination)
            destination.chmod(0o600)
        (staging / "cache").mkdir(mode=0o700)
        (staging / "migration").mkdir(mode=0o700)
        _atomic_json(staging / "migration" / "plan.json", plan)
        env = {
            "FAMILY_DOCUMENTS_ROOT": str(documents_root.resolve()),
            "FAMILY_DASHBOARD_STATE_ROOT": str(staging),
        }
        try:
            build_runner(env)
        except Exception as exc:
            raise PhaseBError("build failed") from exc
        staging.chmod(0o700)
        for node in sorted(staging.rglob("*")):
            if node.is_symlink():
                raise PhaseBError("staging contains a symlink")
            node.chmod(0o700 if node.is_dir() else 0o600)
        parity: dict[str, str] = {}
        for legacy_path in sorted((legacy_app_root / "app-data").glob("*.json")):
            generated_path = staging / "generated" / legacy_path.name
            if not generated_path.is_file():
                raise PhaseBError(f"generated product missing: {legacy_path.name}")
            parity[legacy_path.name] = "equal" if _normalized_json(legacy_path) == _normalized_json(generated_path) else "different"
        _atomic_json(staging / "migration" / "parity.json", {"schema": "family-dashboard-parity/v1", "results": parity})
        differences = sorted(name for name, result in parity.items() if result != "equal")
        if differences:
            raise PhaseBError(f"normalized parity differs: {','.join(differences)}")
        os.replace(staging, target)
        receipt = verify_runtime(documents_root, legacy_app_root, target, expected_fingerprint=expected_fingerprint)
        _atomic_json(target / "migration" / "receipt.json", receipt)
        return receipt
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        if target.exists() and not (target / "migration" / "receipt.json").exists():
            shutil.rmtree(target)
        raise


def verify_runtime(
    documents_root: Path,
    legacy_app_root: Path,
    state_root: Path,
    *,
    expected_fingerprint: str,
) -> dict[str, Any]:
    target = _regular_root(state_root, "state root")
    if not (target / "migration" / "parity.json").is_file():
        raise PhaseBError("parity receipt missing")
    manifests = sorted((target / "manifests").glob("*.yaml"))
    generated = sorted((target / "generated").glob("*.json"))
    if [path.stem for path in manifests] != sorted(MANIFEST_NAMES):
        raise PhaseBError("manifest set mismatch")
    source_entries = plan_runtime(documents_root, legacy_app_root, target.parent / "verification-absent")["entries"]
    if _fingerprint(source_entries) != expected_fingerprint:
        raise PhaseBError("Documents source fingerprint changed")
    return {
        "schema": "family-dashboard-runtime-receipt/v1",
        "status": "verified",
        "source_fingerprint": expected_fingerprint,
        "manifest_count": len(manifests),
        "generated_count": len(generated),
        "cache_seed_count": 0,
        "writes_documents": False,
    }
```

The CLI must invoke the real build with an argv list, never a shell string:

```python
def _bun_build_runner(app_root: Path) -> BuildRunner:
    def run(env: dict[str, str]) -> None:
        import subprocess

        completed = subprocess.run(
            ["bun", "run", "scripts/verify-paths.ts"],
            cwd=app_root,
            env={"PATH": os.environ.get("PATH", ""), **env},
            check=False,
        )
        if completed.returncode != 0:
            raise PhaseBError("path verification failed")
        subprocess.run(
            ["bun", "run", "scripts/build-all.ts"],
            cwd=app_root,
            env={"PATH": os.environ.get("PATH", ""), **env},
            check=True,
        )

    return run
```

- [ ] **Step 4: Add CLI parsing for `apply-runtime` and `verify-runtime`**

`apply-runtime` requires `--documents-root`, `--legacy-app-root`, `--state-root`, `--expected-fingerprint`, `--app-root`, and `--json`; there is no implicit host path. `verify-runtime` must match the immutable BET command: it accepts only `--documents-root`, `--state-root`, and `--json`, loads `state_root/migration/plan.json`, validates its schema/ref, reads the bound fingerprint, and resolves the legacy app only as `documents_root / "family-dashboard-app"` before calling `verify_runtime`.

- [ ] **Step 5: Run focused and full child tests**

```bash
cd projects/family-hub
uv run pytest tests/test_dashboard_phase_b.py -q
uv run pytest tests -q
```

Expected: all tests pass and existing family-hub tests remain green.

- [ ] **Step 6: Commit and tag**

```bash
git add src/family_hub/dashboard_runtime.py src/family_hub/dashboard_phase_b.py tests/test_dashboard_phase_b.py
git commit -m "feat: apply family dashboard runtime transaction"
git tag -a t10-122-family-runtime-transaction -m "T10-122 runtime transaction"
```

---

### Task 3: Family-Hub Approved Mutation Owner

**Files:**
- Create: `projects/family-hub/src/family_hub/dashboard_mutation.py`
- Modify: `projects/family-hub/src/family_hub/dashboard_phase_b.py`
- Modify: `projects/family-hub/tests/test_dashboard_phase_b.py`

**Interfaces:**
- Produces: `stage_payload(state_root: Path, proposal_id: str, content: bytes) -> dict[str, Any]`, `build_canary_proposal(documents_root: Path, state_root: Path, proposal_id: str) -> dict[str, Any]`, `execute_approved_mutation(args: dict[str, Any]) -> dict[str, Any]`, and CLI `plan-canary`.
- Consumed by: Agora internal BOS route in Task 5 and Dashboard proposal client in Task 7.

- [ ] **Step 1: Add failing proposal/CAS/rollback tests**

```python
import hashlib
import json
import yaml

from family_hub.dashboard_mutation import execute_approved_mutation, stage_payload
from family_hub.dashboard_runtime import PhaseBError


def test_stage_payload_is_private_and_returns_digest_only(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    result = stage_payload(state, "proposal-1", b"new body\n")
    payload = state / result["payload_ref"]
    assert payload.read_bytes() == b"new body\n"
    assert payload.stat().st_mode & 0o777 == 0o600
    assert "new body" not in json.dumps(result)


def test_execute_approved_mutation_applies_exact_cas_and_writes_receipts(tmp_path: Path, monkeypatch) -> None:
    documents = tmp_path / "Documents"
    state = tmp_path / "state"
    target = documents / "_knowledge" / "note.md"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"old\n")
    state.mkdir()
    staged = stage_payload(state, "proposal-1", b"new\n")
    proposal = {
        "id": "proposal-1",
        "type": "family_dashboard_document_write",
        "status": "approved",
        "approved_by": "operator://cockpit-api/abc",
        "approved_at": "2026-08-30T23:00:00Z",
        "target_relative": "_knowledge/note.md",
        "expected_source_exists": True,
        "expected_source_sha256": "sha256:" + hashlib.sha256(b"old\n").hexdigest(),
        "expected_source_mode": "0o644",
        "expected_source_bytes": 4,
        **staged,
    }
    omo = tmp_path / ".omo"
    approval = omo / "state" / "proposals" / "proposal-1.processing"
    approval.parent.mkdir(parents=True)
    approval.write_text(yaml.safe_dump(proposal), encoding="utf-8")
    monkeypatch.setenv("FAMILY_DOCUMENTS_ROOT", str(documents))
    monkeypatch.setenv("FAMILY_DASHBOARD_STATE_ROOT", str(state))
    monkeypatch.setenv("OMO_DIR", str(omo))
    result = execute_approved_mutation(
        {
            "proposal": proposal,
        }
    )
    assert result["status"] == "verified"
    assert target.read_bytes() == b"new\n"
    assert (state / result["verify_receipt_ref"]).is_file()


def test_execute_cas_mismatch_refuses_before_write(tmp_path: Path, monkeypatch) -> None:
    documents = tmp_path / "Documents"
    state = tmp_path / "state"
    target = documents / "_knowledge" / "note.md"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"old\n")
    state.mkdir()
    staged = stage_payload(state, "proposal-2", b"new\n")
    before = target.read_bytes()
    proposal = {
        "id": "proposal-2",
        "type": "family_dashboard_document_write",
        "status": "approved",
        "approved_by": "operator://cockpit-api/abc",
        "approved_at": "2026-08-30T23:00:00Z",
        "target_relative": "_knowledge/note.md",
        "expected_source_exists": True,
        "expected_source_sha256": "sha256:" + "0" * 64,
        "expected_source_mode": "0o644",
        "expected_source_bytes": 4,
        **staged,
    }
    omo = tmp_path / ".omo"
    approval = omo / "state" / "proposals" / "proposal-2.processing"
    approval.parent.mkdir(parents=True)
    approval.write_text(yaml.safe_dump(proposal), encoding="utf-8")
    monkeypatch.setenv("FAMILY_DOCUMENTS_ROOT", str(documents))
    monkeypatch.setenv("FAMILY_DASHBOARD_STATE_ROOT", str(state))
    monkeypatch.setenv("OMO_DIR", str(omo))
    with pytest.raises(PhaseBError, match="source CAS mismatch"):
        execute_approved_mutation({"proposal": proposal})
    assert target.read_bytes() == before
    assert not (state / "mutations" / "proposal-2").exists()
```

- [ ] **Step 2: Run focused test and prove RED**

Run: `cd projects/family-hub && uv run pytest tests/test_dashboard_phase_b.py -q`

Expected: FAIL because `dashboard_mutation` does not exist.

- [ ] **Step 3: Implement private staging and atomic CAS execution**

```python
# src/family_hub/dashboard_mutation.py
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Final

import yaml

from .dashboard_runtime import PhaseBError, _atomic_json

PROPOSAL_TYPE: Final = "family_dashboard_document_write"
ALLOWED_ROOTS: Final = ("_control/", "_entities/", "_knowledge/", "_meta/", "_storage/inbox/", "_storage/99-中转/")
ALLOWED_SUFFIXES: Final = {".md", ".markdown", ".yaml", ".yml", ".json", ".txt"}


def _sha_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def stage_payload(state_root: Path, proposal_id: str, content: bytes) -> dict[str, Any]:
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", proposal_id) is None or not content or len(content) > 2_000_000:
        raise PhaseBError("proposal payload is invalid")
    root = state_root.expanduser().resolve()
    path = root / "proposals" / proposal_id / "payload"
    if path.exists() or path.is_symlink():
        raise PhaseBError("proposal payload collision")
    path.parent.mkdir(parents=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    return {
        "payload_ref": path.relative_to(root).as_posix(),
        "payload_sha256": _sha_bytes(content),
        "payload_bytes": len(content),
    }


def build_canary_proposal(documents_root: Path, state_root: Path, proposal_id: str) -> dict[str, Any]:
    relative = "_meta/family-dashboard-write-canary.md"
    target = _safe_target(documents_root, relative)
    if target.exists() or target.is_symlink():
        raise PhaseBError("canary target must be absent")
    staged = stage_payload(state_root, proposal_id, b"family-dashboard Phase B write canary\n")
    base = {
        "id": proposal_id,
        "type": PROPOSAL_TYPE,
        "debt_id": "family-dashboard-content",
        "source": "family-dashboard-phase-b-operator",
        "target": f"documents://family/{relative}",
        "expected_change": "create and immediately roll back controlled canary",
        "operation_level": "L3",
        "approval_required": True,
        "rollback": "restore exact source absence in the same transaction",
        "verification": "verify apply, verify, rollback receipts and final absence",
        "auto_apply": "disabled",
        "operation": "replace_text",
        "target_relative": relative,
        "expected_source_exists": False,
        "expected_source_sha256": _sha_bytes(b""),
        "expected_source_mode": "0o600",
        "expected_source_bytes": 0,
        "canary_rollback": True,
        **staged,
    }
    canonical = json.dumps(base, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return {**base, "proposal_digest": _sha_bytes(canonical)}


def _safe_target(documents_root: Path, relative: str) -> Path:
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts or not relative.startswith(ALLOWED_ROOTS):
        raise PhaseBError("unsafe Documents target")
    if rel.suffix.lower() not in ALLOWED_SUFFIXES or rel.name.startswith("."):
        raise PhaseBError("unsafe Documents target")
    root = documents_root.expanduser().resolve()
    target = (root / rel).resolve()
    if not target.is_relative_to(root):
        raise PhaseBError("unsafe Documents target")
    cursor = root
    for part in rel.parts:
        cursor = cursor / part
        if cursor.exists() and cursor.is_symlink():
            raise PhaseBError("Documents target crosses a symlink")
    return target


def _atomic_bytes(path: Path, content: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def execute_approved_mutation(args: dict[str, Any]) -> dict[str, Any]:
    proposal = args.get("proposal")
    if not isinstance(proposal, dict) or proposal.get("type") != PROPOSAL_TYPE:
        raise PhaseBError("proposal schema invalid")
    if proposal.get("status") != "approved" or not str(proposal.get("approved_by", "")).startswith("operator://cockpit-api/"):
        raise PhaseBError("verified human approval required")
    documents_raw = os.environ.get("FAMILY_DOCUMENTS_ROOT", "")
    state_raw = os.environ.get("FAMILY_DASHBOARD_STATE_ROOT", "")
    omo_raw = os.environ.get("OMO_DIR", "")
    if not documents_raw or not state_raw or not omo_raw:
        raise PhaseBError("mutation authority roots unavailable")
    documents = Path(documents_raw).expanduser().resolve()
    state = Path(state_raw).expanduser().resolve()
    omo = Path(omo_raw).expanduser().resolve()
    if not documents.is_dir() or documents.is_symlink() or not state.is_dir() or state.is_symlink():
        raise PhaseBError("mutation roots invalid")
    approval_path = omo / "state" / "proposals" / f"{proposal['id']}.processing"
    if not approval_path.is_file() or approval_path.is_symlink():
        raise PhaseBError("OMO approval record unavailable")
    approved = yaml.safe_load(approval_path.read_text(encoding="utf-8"))
    if approved != proposal:
        raise PhaseBError("OMO approval binding mismatch")
    target = _safe_target(documents, str(proposal["target_relative"]))
    payload = (state / str(proposal["payload_ref"])).resolve()
    if not payload.is_relative_to(state / "proposals") or not payload.is_file() or payload.is_symlink():
        raise PhaseBError("payload ref invalid")
    if payload.stat().st_mode & 0o777 != 0o600:
        raise PhaseBError("payload mode invalid")
    proposed = payload.read_bytes()
    if _sha_bytes(proposed) != proposal.get("payload_sha256") or len(proposed) != proposal.get("payload_bytes"):
        raise PhaseBError("payload drift")
    existed = target.is_file()
    original = target.read_bytes() if existed else b""
    canary_rollback = proposal.get("canary_rollback") is True
    if canary_rollback and (proposal["target_relative"] != "_meta/family-dashboard-write-canary.md" or existed):
        raise PhaseBError("canary rollback requires exact absent target")
    source_mode = oct(target.stat().st_mode & 0o7777) if existed else "0o600"
    if (
        bool(proposal.get("expected_source_exists")) != existed
        or _sha_bytes(original) != proposal.get("expected_source_sha256")
        or len(original) != proposal.get("expected_source_bytes")
        or source_mode != proposal.get("expected_source_mode")
    ):
        raise PhaseBError("source CAS mismatch")
    mutation_root = state / "mutations" / str(proposal["id"])
    mutation_root.mkdir(parents=True, mode=0o700, exist_ok=False)
    original_path = mutation_root / "original"
    if existed:
        original_path.write_bytes(original)
        original_path.chmod(0o600)
    prepared = {
        "schema": "family-dashboard-mutation-prepared/v1",
        "proposal_id": proposal["id"],
        "target_relative": proposal["target_relative"],
        "source_sha256": _sha_bytes(original),
        "proposed_sha256": _sha_bytes(proposed),
        "source_existed": existed,
    }
    _atomic_json(mutation_root / "prepared.json", prepared)
    mode = target.stat().st_mode & 0o7777 if existed else 0o600
    try:
        _atomic_bytes(target, proposed, mode)
        if _sha_bytes(target.read_bytes()) != proposal["payload_sha256"]:
            raise PhaseBError("post-write verification failed")
        apply = {**prepared, "schema": "family-dashboard-mutation-apply/v1", "status": "applied"}
        verify = {**prepared, "schema": "family-dashboard-mutation-verify/v1", "status": "verified"}
        _atomic_json(mutation_root / "apply.json", apply)
        _atomic_json(mutation_root / "verify.json", verify)
        result = {
            "status": "verified",
            "proposal_id": proposal["id"],
            "verify_receipt_ref": (mutation_root / "verify.json").relative_to(state).as_posix(),
            "verify_receipt_sha256": _sha_bytes((mutation_root / "verify.json").read_bytes()),
        }
        if canary_rollback:
            target.unlink()
            if target.exists():
                raise PhaseBError("canary rollback verification failed")
            rollback = {**prepared, "schema": "family-dashboard-mutation-rollback/v1", "status": "rolled_back"}
            _atomic_json(mutation_root / "rollback.json", rollback)
            result.update(
                {
                    "canary_rolled_back": True,
                    "rollback_receipt_ref": (mutation_root / "rollback.json").relative_to(state).as_posix(),
                    "rollback_receipt_sha256": _sha_bytes((mutation_root / "rollback.json").read_bytes()),
                }
            )
        return result
    except BaseException as exc:
        restored = False
        try:
            if existed:
                _atomic_bytes(target, original, mode)
            else:
                target.unlink(missing_ok=True)
            restored = target.is_file() == existed and (not existed or target.read_bytes() == original)
        except OSError:
            restored = False
        _atomic_json(
            mutation_root / "rollback.json",
            {**prepared, "schema": "family-dashboard-mutation-rollback/v1", "status": "rolled_back" if restored else "unknown"},
        )
        if not restored:
            raise PhaseBError("mutation final state unknown") from exc
        raise PhaseBError("mutation failed and rolled back") from exc
```

Extend `dashboard_phase_b.py` with an operator-only `plan-canary` subcommand:

```python
from .dashboard_mutation import build_canary_proposal

canary = sub.add_parser("plan-canary")
canary.add_argument("--documents-root", type=Path, required=True)
canary.add_argument("--state-root", type=Path, required=True)
canary.add_argument("--proposal-id", required=True)
canary.add_argument("--output", type=Path, required=True)
canary.add_argument("--json", action="store_true")

# In main(), before the runtime-plan branch:
if args.command == "plan-canary":
    proposal = build_canary_proposal(args.documents_root, args.state_root, args.proposal_id)
    output = args.output.expanduser().resolve()
    state = args.state_root.expanduser().resolve()
    if not output.is_relative_to(state) or output.exists() or output.is_symlink():
        raise PhaseBError("canary proposal output must be a new state-root file")
    output.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(proposal, handle, ensure_ascii=False, sort_keys=True, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    print(json.dumps({"status": "planned", "proposal_id": proposal["id"], "proposal_digest": proposal["proposal_digest"]}, sort_keys=True))
    return 0
```

Add `os` and `PhaseBError` imports to the CLI. No HTTP route or browser request can set `canary_rollback`; only this exact operator command can create that envelope.

- [ ] **Step 4: Complete negative tests**

```python
import family_hub.dashboard_mutation as mutation


@pytest.mark.parametrize(
    "relative",
    ("../escape.md", "/absolute.md", "_knowledge/.hidden.md", "_knowledge/file.exe"),
)
def test_unsafe_documents_targets_are_rejected(tmp_path: Path, relative: str) -> None:
    documents = tmp_path / "Documents"
    documents.mkdir()
    with pytest.raises(PhaseBError, match="unsafe Documents target"):
        mutation._safe_target(documents, relative)


def test_payload_collision_and_drift_are_rejected(tmp_path: Path, monkeypatch) -> None:
    documents = tmp_path / "Documents"
    state = tmp_path / "state"
    documents.mkdir()
    state.mkdir()
    staged = stage_payload(state, "proposal-drift", b"new\n")
    with pytest.raises(PhaseBError, match="proposal payload collision"):
        stage_payload(state, "proposal-drift", b"other\n")
    proposal = {
        "id": "proposal-drift",
        "type": "family_dashboard_document_write",
        "status": "approved",
        "approved_by": "operator://cockpit-api/abc",
        "approved_at": "2026-08-30T23:00:00Z",
        "target_relative": "_knowledge/new.md",
        "expected_source_exists": False,
        "expected_source_sha256": "sha256:" + hashlib.sha256(b"").hexdigest(),
        "expected_source_mode": "0o600",
        "expected_source_bytes": 0,
        **staged,
    }
    omo = tmp_path / ".omo"
    approval = omo / "state" / "proposals" / "proposal-drift.processing"
    approval.parent.mkdir(parents=True)
    approval.write_text(yaml.safe_dump(proposal), encoding="utf-8")
    (state / staged["payload_ref"]).write_bytes(b"changed\n")
    (state / staged["payload_ref"]).chmod(0o600)
    monkeypatch.setenv("FAMILY_DOCUMENTS_ROOT", str(documents))
    monkeypatch.setenv("FAMILY_DASHBOARD_STATE_ROOT", str(state))
    monkeypatch.setenv("OMO_DIR", str(omo))
    with pytest.raises(PhaseBError, match="payload drift"):
        execute_approved_mutation({"proposal": proposal})


def test_missing_omo_approval_refuses_before_write(tmp_path: Path, monkeypatch) -> None:
    documents = tmp_path / "Documents"
    state = tmp_path / "state"
    omo = tmp_path / ".omo"
    documents.mkdir()
    state.mkdir()
    omo.mkdir()
    staged = stage_payload(state, "proposal-no-approval", b"new\n")
    proposal = {
        "id": "proposal-no-approval",
        "type": "family_dashboard_document_write",
        "status": "approved",
        "approved_by": "operator://cockpit-api/forged",
        "approved_at": "2026-08-30T23:00:00Z",
        "target_relative": "_knowledge/new.md",
        "expected_source_exists": False,
        "expected_source_sha256": "sha256:" + hashlib.sha256(b"").hexdigest(),
        "expected_source_mode": "0o600",
        "expected_source_bytes": 0,
        **staged,
    }
    monkeypatch.setenv("FAMILY_DOCUMENTS_ROOT", str(documents))
    monkeypatch.setenv("FAMILY_DASHBOARD_STATE_ROOT", str(state))
    monkeypatch.setenv("OMO_DIR", str(omo))
    with pytest.raises(PhaseBError, match="OMO approval record unavailable"):
        execute_approved_mutation({"proposal": proposal})
    assert not (documents / "_knowledge" / "new.md").exists()


def test_apply_receipt_failure_restores_existing_file(tmp_path: Path, monkeypatch) -> None:
    documents = tmp_path / "Documents"
    state = tmp_path / "state"
    target = documents / "_knowledge" / "note.md"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"old\n")
    state.mkdir()
    staged = stage_payload(state, "proposal-rollback", b"new\n")
    proposal = {
        "id": "proposal-rollback",
        "type": "family_dashboard_document_write",
        "status": "approved",
        "approved_by": "operator://cockpit-api/abc",
        "approved_at": "2026-08-30T23:00:00Z",
        "target_relative": "_knowledge/note.md",
        "expected_source_exists": True,
        "expected_source_sha256": "sha256:" + hashlib.sha256(b"old\n").hexdigest(),
        "expected_source_mode": "0o644",
        "expected_source_bytes": 4,
        **staged,
    }
    omo = tmp_path / ".omo"
    approval = omo / "state" / "proposals" / "proposal-rollback.processing"
    approval.parent.mkdir(parents=True)
    approval.write_text(yaml.safe_dump(proposal), encoding="utf-8")
    monkeypatch.setenv("FAMILY_DOCUMENTS_ROOT", str(documents))
    monkeypatch.setenv("FAMILY_DASHBOARD_STATE_ROOT", str(state))
    monkeypatch.setenv("OMO_DIR", str(omo))
    real_atomic_json = mutation._atomic_json

    def fail_apply_receipt(path: Path, payload: dict) -> None:
        if path.name == "apply.json":
            raise OSError("receipt unavailable")
        real_atomic_json(path, payload)

    monkeypatch.setattr(mutation, "_atomic_json", fail_apply_receipt)
    with pytest.raises(PhaseBError, match="failed and rolled back"):
        execute_approved_mutation({"proposal": proposal})
    assert target.read_bytes() == b"old\n"
    rollback = json.loads((state / "mutations" / "proposal-rollback" / "rollback.json").read_text())
    assert rollback["status"] == "rolled_back"


def test_apply_receipt_failure_removes_new_file(tmp_path: Path, monkeypatch) -> None:
    documents = tmp_path / "Documents"
    state = tmp_path / "state"
    documents.mkdir()
    state.mkdir()
    staged = stage_payload(state, "proposal-create-rollback", b"new\n")
    proposal = {
        "id": "proposal-create-rollback",
        "type": "family_dashboard_document_write",
        "status": "approved",
        "approved_by": "operator://cockpit-api/abc",
        "approved_at": "2026-08-30T23:00:00Z",
        "target_relative": "_knowledge/canary.md",
        "expected_source_exists": False,
        "expected_source_sha256": "sha256:" + hashlib.sha256(b"").hexdigest(),
        "expected_source_mode": "0o600",
        "expected_source_bytes": 0,
        **staged,
    }
    omo = tmp_path / ".omo"
    approval = omo / "state" / "proposals" / "proposal-create-rollback.processing"
    approval.parent.mkdir(parents=True)
    approval.write_text(yaml.safe_dump(proposal), encoding="utf-8")
    monkeypatch.setenv("FAMILY_DOCUMENTS_ROOT", str(documents))
    monkeypatch.setenv("FAMILY_DASHBOARD_STATE_ROOT", str(state))
    monkeypatch.setenv("OMO_DIR", str(omo))
    real_atomic_json = mutation._atomic_json

    def fail_apply_receipt(path: Path, payload: dict) -> None:
        if path.name == "apply.json":
            raise OSError("receipt unavailable")
        real_atomic_json(path, payload)

    monkeypatch.setattr(mutation, "_atomic_json", fail_apply_receipt)
    with pytest.raises(PhaseBError, match="failed and rolled back"):
        execute_approved_mutation({"proposal": proposal})
    assert not (documents / "_knowledge" / "canary.md").exists()
    rollback = json.loads((state / "mutations" / "proposal-create-rollback" / "rollback.json").read_text())
    assert rollback["status"] == "rolled_back"


def test_exact_canary_is_applied_verified_and_immediately_rolled_back(tmp_path: Path, monkeypatch) -> None:
    documents = tmp_path / "Documents"
    state = tmp_path / "state"
    documents.mkdir()
    state.mkdir()
    staged = stage_payload(state, "proposal-canary", b"non-private canary\n")
    proposal = {
        "id": "proposal-canary",
        "type": "family_dashboard_document_write",
        "status": "approved",
        "approved_by": "operator://cockpit-api/abc",
        "approved_at": "2026-08-30T23:00:00Z",
        "target_relative": "_meta/family-dashboard-write-canary.md",
        "expected_source_exists": False,
        "expected_source_sha256": "sha256:" + hashlib.sha256(b"").hexdigest(),
        "expected_source_mode": "0o600",
        "expected_source_bytes": 0,
        "canary_rollback": True,
        **staged,
    }
    omo = tmp_path / ".omo"
    approval = omo / "state" / "proposals" / "proposal-canary.processing"
    approval.parent.mkdir(parents=True)
    approval.write_text(yaml.safe_dump(proposal), encoding="utf-8")
    monkeypatch.setenv("FAMILY_DOCUMENTS_ROOT", str(documents))
    monkeypatch.setenv("FAMILY_DASHBOARD_STATE_ROOT", str(state))
    monkeypatch.setenv("OMO_DIR", str(omo))
    result = execute_approved_mutation({"proposal": proposal})
    assert result["status"] == "verified"
    assert result["canary_rolled_back"] is True
    assert not (documents / "_meta" / "family-dashboard-write-canary.md").exists()
    mutation_root = state / "mutations" / "proposal-canary"
    assert {path.name for path in mutation_root.glob("*.json")} == {"prepared.json", "apply.json", "verify.json", "rollback.json"}


def test_rollback_write_failure_reports_unknown_final_state(tmp_path: Path, monkeypatch) -> None:
    documents = tmp_path / "Documents"
    state = tmp_path / "state"
    target = documents / "_knowledge" / "note.md"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"old\n")
    state.mkdir()
    staged = stage_payload(state, "proposal-unknown", b"new\n")
    proposal = {
        "id": "proposal-unknown",
        "type": "family_dashboard_document_write",
        "status": "approved",
        "approved_by": "operator://cockpit-api/abc",
        "approved_at": "2026-08-30T23:00:00Z",
        "target_relative": "_knowledge/note.md",
        "expected_source_exists": True,
        "expected_source_sha256": "sha256:" + hashlib.sha256(b"old\n").hexdigest(),
        "expected_source_mode": "0o644",
        "expected_source_bytes": 4,
        **staged,
    }
    omo = tmp_path / ".omo"
    approval = omo / "state" / "proposals" / "proposal-unknown.processing"
    approval.parent.mkdir(parents=True)
    approval.write_text(yaml.safe_dump(proposal), encoding="utf-8")
    monkeypatch.setenv("FAMILY_DOCUMENTS_ROOT", str(documents))
    monkeypatch.setenv("FAMILY_DASHBOARD_STATE_ROOT", str(state))
    monkeypatch.setenv("OMO_DIR", str(omo))
    real_bytes = mutation._atomic_bytes
    real_json = mutation._atomic_json
    calls = 0

    def fail_second_write(path: Path, content: bytes, mode: int) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("rollback unavailable")
        real_bytes(path, content, mode)

    monkeypatch.setattr(mutation, "_atomic_bytes", fail_second_write)

    def fail_apply_json(path: Path, payload: dict) -> None:
        if path.name == "apply.json":
            raise OSError("receipt unavailable")
        real_json(path, payload)

    monkeypatch.setattr(mutation, "_atomic_json", fail_apply_json)
    with pytest.raises(PhaseBError, match="mutation final state unknown"):
        execute_approved_mutation({"proposal": proposal})
```

- [ ] **Step 5: Run tests and commit core family-hub PR**

```bash
cd projects/family-hub
uv run pytest tests/test_dashboard_phase_b.py tests/test_dashboard_import.py tests/test_dashboard_import_cli.py -q
uv run pytest tests -q
uv run ruff check src/family_hub tests/test_dashboard_phase_b.py
git add src/family_hub/dashboard_mutation.py tests/test_dashboard_phase_b.py
git commit -m "feat: add approved family Documents mutation owner"
git tag -a t10-122-family-mutation-owner -m "T10-122 mutation owner"
git push -u origin agent/codex-documents-convergence--t10-122-family-core-20260831-01
gh pr create --base main \
  --head agent/codex-documents-convergence--t10-122-family-core-20260831-01 \
  --title "feat: add family dashboard Phase B owner primitives"
```

Wait for child required checks, squash merge, fetch child `origin/main`, and record the merged SHA. This is **family-hub PR A**; do not wire Dashboard routes yet.

---

### Task 4: Restore OMO as the Canonical HITL Proposal and Receipt Writer

**Files:**
- Create: `projects/omo/src/omo/omo_cockpit_bridge.py`
- Create: `projects/omo/tests/test_omo_cockpit_bridge.py`

**Interfaces:**
- Produces: `record_hitl_proposal`, `list_hitl_proposals`, `approve_hitl_proposal_async`, `reject_hitl_proposal`, `append_hitl_override`.
- Consumed by: Cockpit adapter Task 6.
- `approve_hitl_proposal_async` calls `execute_mutation(proposal) -> dict`, not bool, and archives a terminal receipt before queue cleanup.

- [ ] **Step 1: Write failing OMO broker tests**

```python
from pathlib import Path

import pytest

from omo.omo_cockpit_bridge import (
    approve_hitl_proposal_async,
    list_hitl_proposals,
    record_hitl_proposal,
    reject_hitl_proposal,
)


def _proposal(expected_change: str = "create controlled canary") -> dict:
    base = {
        "id": "family-write-1",
        "type": "family_dashboard_document_write",
        "debt_id": "family-dashboard-content",
        "source": "family-dashboard",
        "target": "documents://family/_knowledge/canary.md",
        "expected_change": expected_change,
        "operation_level": "L3",
        "approval_required": True,
        "rollback": "remove canary after verified apply",
        "verification": "verify receipt digest",
        "auto_apply": "disabled",
    }
    canonical = json.dumps(base, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return {**base, "proposal_digest": "sha256:" + hashlib.sha256(canonical).hexdigest()}


def test_record_is_exclusive_idempotent_and_pathless(tmp_path: Path) -> None:
    omo = tmp_path / ".omo"
    first = record_hitl_proposal(omo, _proposal(), requested_by="service://family-dashboard", now="2026-08-30T23:00:00Z")
    second = record_hitl_proposal(omo, _proposal(), requested_by="service://family-dashboard", now="2026-08-30T23:00:00Z")
    assert first == second
    assert list_hitl_proposals(omo)[0]["status"] == "pending"
    changed = _proposal("different controlled canary")
    with pytest.raises(ValueError, match="proposal id collision"):
        record_hitl_proposal(omo, changed, requested_by="service://family-dashboard", now="2026-08-30T23:00:00Z")


@pytest.mark.asyncio
async def test_approve_binds_principal_and_archives_execution_receipt(tmp_path: Path) -> None:
    omo = tmp_path / ".omo"
    record_hitl_proposal(omo, _proposal(), requested_by="service://family-dashboard", now="2026-08-30T23:00:00Z")
    success, error, receipt = await approve_hitl_proposal_async(
        omo,
        "family-write-1",
        principal_ref="operator://cockpit-api/abc",
        approved_at="2026-08-30T23:01:00Z",
        execute_mutation=lambda proposal: {"status": "verified", "verify_receipt_ref": "mutations/1/verify.json", "verify_receipt_sha256": "sha256:" + "c" * 64},
    )
    assert success is True and error is None
    assert receipt["status"] == "verified"
    assert receipt["approved_by"] == "operator://cockpit-api/abc"
    assert not (omo / "state" / "proposals" / "family-write-1.yaml").exists()
    assert (omo / "_delivery" / "hitl" / "family-dashboard" / "family-write-1.yaml").is_file()
```

- [ ] **Step 2: Run tests and prove RED**

Run: `cd projects/omo && uv run pytest tests/test_omo_cockpit_bridge.py -q`

Expected: import failure because the canonical bridge does not exist.

- [ ] **Step 3: Implement the canonical bridge**

Use `omo_io.write_yaml_atomic`, `omo_io.write_text_atomic`, `omo_io.fcntl_lock`, and `omo_shared.load_yaml`. Required broker rules:

```python
import hashlib
import hmac
import inspect
import json
import re
from pathlib import Path
from typing import Any, Awaitable, Callable

from .omo_io import AppendOnlyLog, fcntl_lock, write_yaml_atomic
from .omo_redaction import redact_sensitive_text
from .omo_shared import load_yaml

REQUIRED_PROPOSAL_FIELDS = frozenset({
    "id", "type", "debt_id", "source", "target", "expected_change",
    "operation_level", "approval_required", "rollback", "verification",
    "auto_apply", "proposal_digest",
})


def _contains_secret_like_value(value: object) -> bool:
    if isinstance(value, str):
        return redact_sensitive_text(value) != value
    if isinstance(value, dict):
        return any(_contains_secret_like_value(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_secret_like_value(item) for item in value)
    return False


def _proposal_digest(proposal: dict[str, Any]) -> str:
    canonical = {key: value for key, value in proposal.items() if key != "proposal_digest"}
    encoded = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def record_hitl_proposal(omo_dir: Path, proposal: dict[str, Any], *, requested_by: str, now: str) -> dict[str, Any]:
    missing = sorted(REQUIRED_PROPOSAL_FIELDS - proposal.keys())
    if missing or proposal.get("approval_required") is not True or proposal.get("auto_apply") != "disabled":
        raise ValueError("proposal envelope invalid")
    if proposal.get("operation_level") != "L3" or not str(proposal.get("proposal_digest", "")).startswith("sha256:"):
        raise ValueError("proposal envelope invalid")
    if not hmac.compare_digest(str(proposal["proposal_digest"]), _proposal_digest(proposal)):
        raise ValueError("proposal digest mismatch")
    if _contains_secret_like_value(proposal):
        raise ValueError("proposal contains secret-like raw values")
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", str(proposal.get("id", ""))) is None:
        raise ValueError("proposal id invalid")
    payload = {**proposal, "status": "pending", "requested_by": requested_by, "created_at": now}
    path = omo_dir / "state" / "proposals" / f"{payload['id']}.yaml"
    lock = path.with_suffix(".lock")
    with fcntl_lock(lock):
        if path.exists():
            current = load_yaml(path)
            if current != payload:
                raise ValueError("proposal id collision")
            return current
        write_yaml_atomic(path, payload)
    return payload


def list_hitl_proposals(omo_dir: Path) -> list[dict[str, Any]]:
    directory = omo_dir / "state" / "proposals"
    rows = [load_yaml(path) for path in sorted(directory.glob("*.yaml"))] if directory.exists() else []
    return sorted((row for row in rows if isinstance(row, dict)), key=lambda row: str(row.get("created_at", "")), reverse=True)


def _terminal_path(omo_dir: Path, proposal_id: str) -> Path:
    return omo_dir / "_delivery" / "hitl" / "family-dashboard" / f"{proposal_id}.yaml"


async def approve_hitl_proposal_async(
    omo_dir: Path,
    proposal_id: str,
    *,
    principal_ref: str,
    approved_at: str,
    execute_mutation: Callable[[dict[str, Any]], dict[str, Any] | Awaitable[dict[str, Any]]],
) -> tuple[bool, str | None, dict[str, Any] | None]:
    if not principal_ref.startswith("operator://cockpit-api/"):
        return False, "verified principal required", None
    pending = omo_dir / "state" / "proposals" / f"{proposal_id}.yaml"
    processing = pending.with_suffix(".processing")
    if not pending.exists() and not processing.exists():
        return False, f"Proposal {proposal_id} not found", None
    try:
        pending.rename(processing)
    except OSError:
        return False, f"Proposal {proposal_id} is already being processed or locked.", None
    try:
        proposal = load_yaml(processing)
        proposal = {**proposal, "status": "approved", "approved_by": principal_ref, "approved_at": approved_at}
        write_yaml_atomic(processing, proposal)
        outcome = execute_mutation(proposal)
        if inspect.isawaitable(outcome):
            outcome = await outcome
        if not isinstance(outcome, dict) or outcome.get("status") != "verified":
            raise ValueError("mutation did not return verified receipt")
        receipt = {
            "schema": "omo-hitl-execution-receipt/v1",
            "proposal_id": proposal_id,
            "proposal_digest": proposal["proposal_digest"],
            "status": "verified",
            "approved_by": principal_ref,
            "approved_at": approved_at,
            "bos_uri": "bos://governance/hitl/execute/family_dashboard_document_write",
            "runtime_receipt_ref": outcome["verify_receipt_ref"],
            "runtime_receipt_sha256": outcome["verify_receipt_sha256"],
        }
        if outcome.get("canary_rolled_back") is True:
            receipt.update(
                {
                    "canary_rolled_back": True,
                    "rollback_receipt_ref": outcome["rollback_receipt_ref"],
                    "rollback_receipt_sha256": outcome["rollback_receipt_sha256"],
                }
            )
        terminal = _terminal_path(omo_dir, proposal_id)
        if terminal.exists() and load_yaml(terminal) != receipt:
            raise ValueError("terminal receipt collision")
        write_yaml_atomic(terminal, receipt)
        processing.unlink()
        return True, None, receipt
    except Exception as exc:
        if processing.exists():
            processing.rename(pending)
        return False, str(exc), None


def reject_hitl_proposal(
    omo_dir: Path,
    proposal_id: str,
    *,
    principal_ref: str,
    rejected_at: str,
) -> dict[str, Any]:
    if not principal_ref.startswith("operator://cockpit-api/"):
        raise ValueError("verified principal required")
    pending = omo_dir / "state" / "proposals" / f"{proposal_id}.yaml"
    proposal = load_yaml(pending)
    receipt = {
        "schema": "omo-hitl-execution-receipt/v1",
        "proposal_id": proposal_id,
        "proposal_digest": proposal["proposal_digest"],
        "status": "rejected",
        "rejected_by": principal_ref,
        "rejected_at": rejected_at,
    }
    write_yaml_atomic(_terminal_path(omo_dir, proposal_id), receipt)
    pending.unlink()
    return receipt


def append_hitl_override(omo_dir: Path, stream_name: str, record: dict[str, Any]) -> str:
    path = omo_dir / "state" / stream_name
    AppendOnlyLog(path, lock=fcntl_lock(path.with_suffix(path.suffix + ".lock"))).append(record, sort_keys=False)
    return str(path)
```

- [ ] **Step 4: Run focused and OMO governance regression tests**

```bash
cd projects/omo
uv run pytest tests/test_omo_cockpit_bridge.py tests/test_omo_governance.py -q
```

Expected: both suites pass.

- [ ] **Step 5: Commit, tag, PR, and merge OMO**

```bash
git add src/omo/omo_cockpit_bridge.py tests/test_omo_cockpit_bridge.py
git commit -m "feat: own durable HITL proposal receipts"
git tag -a t10-122-omo-hitl-broker -m "T10-122 OMO HITL broker"
git push -u origin agent/codex-documents-convergence--t10-122-omo-hitl-20260831-01
gh pr create --base main \
  --head agent/codex-documents-convergence--t10-122-omo-hitl-20260831-01 \
  --title "feat: own durable family HITL receipts"
```

Push an independent OMO branch, open the child PR, wait for required CI, squash merge, fetch OMO `origin/main`, and record the merged SHA.

---

### Task 5: Register the Uncached Agora Internal Mutation Route

**Files:**
- Modify: `projects/agora/etc/bos-services.yaml`
- Modify: `projects/agora/src/agora/agora-bos-rates.yaml`
- Modify: `projects/agora/tests/unit/test_bos_resolver.py`

**Interfaces:**
- Consumes: `family_hub.dashboard_mutation.execute_approved_mutation(args)` from merged family-hub PR A.
- Produces: exact URI `bos://governance/hitl/execute/family_dashboard_document_write`.

- [ ] **Step 1: Add failing route and cache tests**

```python
def test_family_dashboard_hitl_route_is_internal_and_exact() -> None:
    service = api.get_service("bos://governance/hitl/execute/family_dashboard_document_write")
    assert service is not None
    assert service.transport == "internal"
    assert service.package == "family-hub"
    assert service.module_path == "family_hub.dashboard_mutation"
    assert service.func_name == "execute_approved_mutation"


def test_family_dashboard_mutation_route_has_zero_cache_ttl() -> None:
    from agora.server._response import _get_cache_ttl

    assert _get_cache_ttl("bos://governance/hitl/execute/family_dashboard_document_write") == 0
```

- [ ] **Step 2: Run tests and prove RED**

Run: `cd projects/agora && uv run pytest tests/unit/test_bos_resolver.py -q`

Expected: route lookup is `None` and cache TTL is not zero.

- [ ] **Step 3: Add the declarative service and exact rate rule**

Add this service to `etc/bos-services.yaml`:

```yaml
- uri: bos://governance/hitl/execute/family_dashboard_document_write
  domain: governance
  package: family-hub
  action: hitl/execute/family_dashboard_document_write
  transport: internal
  module_path: family_hub.dashboard_mutation
  func_name: execute_approved_mutation
  description: Execute one Cockpit-approved family Documents CAS transaction through the family-hub owner.
  status: active
```

Add the longest-prefix rate row before broader governance rows:

```yaml
- prefix: "bos://governance/hitl/execute/family_dashboard_document_write"
  qps: 1
  cache_ttl: 0
```

- [ ] **Step 4: Add an execution test that clears resolver/cache globals**

```python
import asyncio
import sys
import types

from agora.mcp.bos_middleware import bos_cache


def test_family_dashboard_mutation_route_never_replays_cached_result(monkeypatch) -> None:
    uri = "bos://governance/hitl/execute/family_dashboard_document_write"
    calls: list[str] = []
    module = types.ModuleType("family_hub.dashboard_mutation")

    def execute_approved_mutation(args: dict) -> dict:
        proposal_id = str(args["proposal"]["id"])
        calls.append(proposal_id)
        return {
            "status": "verified",
            "proposal_id": proposal_id,
            "verify_receipt_ref": f"mutations/{proposal_id}/verify.json",
            "verify_receipt_sha256": "sha256:" + "c" * 64,
        }

    module.execute_approved_mutation = execute_approved_mutation
    monkeypatch.setitem(sys.modules, "family_hub.dashboard_mutation", module)
    api._service_index = None
    bos_cache.invalidate(uri)
    first = asyncio.run(api.resolve_bos_uri(uri, proposal={"id": "p1"}))
    second = asyncio.run(api.resolve_bos_uri(uri, proposal={"id": "p2"}))
    assert first["result"]["proposal_id"] == "p1"
    assert second["result"]["proposal_id"] == "p2"
    assert calls == ["p1", "p2"]
```

- [ ] **Step 5: Run tests, commit, tag, PR, and merge Agora**

```bash
cd projects/agora
uv run pytest tests/unit/test_bos_resolver.py -q
git add etc/bos-services.yaml src/agora/agora-bos-rates.yaml tests/unit/test_bos_resolver.py
git commit -m "feat: route family dashboard HITL writes"
git tag -a t10-122-agora-family-hitl-route -m "T10-122 Agora HITL route"
git push -u origin agent/codex-documents-convergence--t10-122-agora-hitl-20260831-01
gh pr create --base main \
  --head agent/codex-documents-convergence--t10-122-agora-hitl-20260831-01 \
  --title "feat: route family dashboard HITL writes"
```

Push, open the child PR, wait for required CI, squash merge, and record Agora child-main SHA.

---

### Task 6: Cockpit Authenticated Proposal Ingress and Approval Binding

**Files:**
- Modify: `projects/cockpit/src/cockpit/adapters/omo.py`
- Modify: `projects/cockpit/src/cockpit/web/api_proposals.py`
- Modify: `projects/cockpit/src/cockpit/tests/test_api_proposals.py`

**Interfaces:**
- Consumes: OMO Task 4 bridge and Agora Task 5 BOS route.
- Produces: strict `POST /api/v1/proposals` and credential-bound approve/reject routes.

- [ ] **Step 1: Add failing authentication and result-binding tests**

```python
def test_create_proposal_requires_family_documents_scope(client, monkeypatch):
    monkeypatch.setenv("COCKPIT_API_KEY", "valid-secret")
    auth.reload_api_keys()
    response = client.post("/api/v1/proposals", json={"id": "p1"})
    assert response.status_code == 401


def test_approve_uses_authenticated_principal_not_body_actor(client, monkeypatch):
    monkeypatch.setenv("COCKPIT_API_KEY", "valid-secret")
    auth.reload_api_keys()
    captured = {}

    async def approve(_omo, _proposal_id, *, principal_ref, approved_at, execute_mutation):
        captured["principal_ref"] = principal_ref
        return True, None, {"status": "verified"}

    monkeypatch.setattr(api_proposals, "approve_hitl_proposal_async", approve)
    response = client.post(
        "/api/v1/proposals/p1/approve",
        headers={"X-Api-Key": "valid-secret"},
        json={"approved_by": "attacker"},
    )
    assert response.status_code == 200
    assert captured["principal_ref"].startswith("operator://cockpit-api/")
    assert captured["principal_ref"] != "attacker"


@pytest.mark.asyncio
async def test_bos_error_or_unverified_result_is_not_success(monkeypatch):
    monkeypatch.setattr(api_proposals, "resolve_bos_uri", AsyncMock(return_value={"status": "ok", "result": {"status": "rolled_back"}}))
    assert await api_proposals._execute_mutation({"type": "family_dashboard_document_write"}) == {"status": "rolled_back"}
```

- [ ] **Step 2: Run tests and prove RED**

Run: `cd projects/cockpit && uv run pytest src/cockpit/tests/test_api_proposals.py -q`

Expected: create route missing, approve accepts no Request/principal, and `_execute_mutation` returns bool.

- [ ] **Step 3: Make the adapter a thin canonical re-export**

Import `record_hitl_proposal`, `list_hitl_proposals`, `approve_hitl_proposal_async`, and `reject_hitl_proposal` directly from `omo.omo_cockpit_bridge`. Delete their local fallback definitions from `cockpit.adapters.omo`; do not retain a dormant second writer. Unrelated compatibility helpers such as scenario receipt projection may remain local. Add a source-contract test asserting the adapter does not define `_proposal_dir`, does not call `write_yaml_atomic` for proposals, and exposes the imported OMO function objects by identity. If OMO is unavailable, `api_proposals` must enter its existing structured degraded state and perform no write.

- [ ] **Step 4: Implement strict create/approve/reject routes**

Use:

```python
from fastapi import Request
from cockpit.web.auth import (
    ApiAuthenticationError,
    ApiAuthorizationError,
    authenticate_api_principal,
)

_FAMILY_WRITE_SCOPES = frozenset({"family-documents-write"})


def _principal(request: Request):
    return authenticate_api_principal(dict(request.headers), any_scope=_FAMILY_WRITE_SCOPES)


@router.post("/api/v1/proposals")
async def api_create_proposal(request: Request):
    try:
        principal = _principal(request)
    except ApiAuthenticationError:
        return JSONResponse({"status": "unauthorized", "error": "proposal_auth_required"}, status_code=401)
    except ApiAuthorizationError:
        return JSONResponse({"status": "forbidden", "error": "proposal_scope_required"}, status_code=403)
    body = await request.json()
    if not isinstance(body, dict):
        return JSONResponse({"status": "error", "error": "proposal_object_required"}, status_code=400)
    try:
        proposal = record_hitl_proposal(
            WORKSPACE_ROOT / ".omo",
            body,
            requested_by=principal.principal_ref,
            now=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )
    except (OSError, TypeError, ValueError) as exc:
        return JSONResponse({"status": "error", "error": str(exc)}, status_code=409)
    return JSONResponse({"status": "pending", "proposal_id": proposal["id"]}, status_code=202)


async def _execute_mutation(proposal: dict[str, Any]) -> dict[str, Any]:
    p_type = str(proposal.get("type") or "")
    if p_type in {"budget_increase", "model_swap", "quota_reset"}:
        stream = {
            "budget_increase": "budget_overrides.jsonl",
            "model_swap": "model_overrides.jsonl",
            "quota_reset": "quota_resets.jsonl",
        }[p_type]
        ref = append_hitl_override(
            WORKSPACE_ROOT / ".omo",
            stream,
            {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "proposal_id": proposal["id"], "status": "applied"},
        )
        digest = "sha256:" + hashlib.sha256(Path(ref).read_bytes()).hexdigest()
        return {"status": "verified", "verify_receipt_ref": ref, "verify_receipt_sha256": digest}
    response = await resolve_bos_uri(f"bos://governance/hitl/execute/{p_type}", proposal=proposal)
    if response.get("status") != "ok" or not isinstance(response.get("result"), dict):
        return {"status": "error", "error": "bos_execution_failed"}
    return dict(response["result"])


@router.post("/api/v1/proposals/{proposal_id}/approve")
async def api_approve_proposal(proposal_id: str, request: Request):
    try:
        principal = _principal(request)
    except ApiAuthenticationError:
        return JSONResponse({"status": "unauthorized", "error": "proposal_auth_required"}, status_code=401)
    except ApiAuthorizationError:
        return JSONResponse({"status": "forbidden", "error": "proposal_scope_required"}, status_code=403)
    success, error, receipt = await approve_hitl_proposal_async(
        WORKSPACE_ROOT / ".omo",
        proposal_id,
        principal_ref=principal.principal_ref,
        approved_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        execute_mutation=_execute_mutation,
    )
    if success:
        return JSONResponse({"status": "verified", "proposal_id": proposal_id, "receipt": receipt})
    status_code = 404 if error and "not found" in error else (409 if error and "processed" in error else 400)
    return JSONResponse({"status": "error", "error": error or "proposal_execution_failed"}, status_code=status_code)


@router.post("/api/v1/proposals/{proposal_id}/reject")
async def api_reject_proposal(proposal_id: str, request: Request):
    try:
        principal = _principal(request)
    except ApiAuthenticationError:
        return JSONResponse({"status": "unauthorized", "error": "proposal_auth_required"}, status_code=401)
    except ApiAuthorizationError:
        return JSONResponse({"status": "forbidden", "error": "proposal_scope_required"}, status_code=403)
    try:
        receipt = reject_hitl_proposal(
            WORKSPACE_ROOT / ".omo",
            proposal_id,
            principal_ref=principal.principal_ref,
            rejected_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )
    except (OSError, TypeError, ValueError) as exc:
        return JSONResponse({"status": "error", "error": str(exc)}, status_code=409)
    return JSONResponse({"status": "rejected", "proposal_id": proposal_id, "receipt": receipt})
```

Add module-level imports for `hashlib`, `Path`, `Any`, and `resolve_bos_uri` used by this implementation. Existing built-in proposal types remain compatible by returning a verified append-only override receipt; family writes use only the exact BOS route.

- [ ] **Step 5: Run tests, commit, tag, PR, and merge Cockpit**

```bash
cd projects/cockpit
uv run pytest src/cockpit/tests/test_api_proposals.py -q
git add src/cockpit/adapters/omo.py src/cockpit/web/api_proposals.py src/cockpit/tests/test_api_proposals.py
git commit -m "feat: authenticate family HITL proposals"
git tag -a t10-122-cockpit-family-hitl -m "T10-122 Cockpit family HITL"
git push -u origin agent/codex-documents-convergence--t10-122-cockpit-hitl-20260831-01
gh pr create --base main \
  --head agent/codex-documents-convergence--t10-122-cockpit-hitl-20260831-01 \
  --title "feat: authenticate family HITL proposals"
```

Push, open child PR, wait required CI, squash merge, and record Cockpit child-main SHA.

---

### Task 7: Dashboard Proposal Client and Generic File Save

**Files:**
- Create: `projects/family-hub/apps/dashboard/src/lib/hitl-proposals.ts`
- Modify: `projects/family-hub/apps/dashboard/src/app/api/file/save/route.ts`
- Modify: `projects/family-hub/apps/dashboard/tests/boundaries/write-policy.test.ts`
- Modify: `projects/family-hub/apps/dashboard/.env.example`

**Interfaces:**
- Consumes: Cockpit `POST /api/v1/proposals`, state payload layout, existing CSRF/path helpers.
- Produces: `stageHitlProposal(input: StageInput) -> Promise<{proposal, payloadPath}>`, `submitHitlProposal(staged) -> Promise<PendingWrite>`, HTTP 202 save response.

- [ ] **Step 1: Replace the unconditional-disabled test with proposal-only failing tests**

```typescript
test("file save stages private payload and returns pending proposal", async () => {
  const documentsRoot = await mkdtemp(path.join(os.tmpdir(), "family-documents-"));
  const stateRoot = await mkdtemp(path.join(os.tmpdir(), "family-state-"));
  const target = path.join(documentsRoot, "_knowledge", "note.md");
  await mkdir(path.dirname(target), { recursive: true });
  await writeFile(target, "old\n");
  vi.stubEnv("FAMILY_DOCUMENTS_ROOT", documentsRoot);
  vi.stubEnv("FAMILY_DASHBOARD_STATE_ROOT", stateRoot);
  vi.stubEnv("COCKPIT_INTERNAL_URL", "http://cockpit.internal");
  vi.stubEnv("FAMILY_HITL_COCKPIT_API_KEY", "test-key");
  vi.stubEnv("FAMILY_CSRF_TOKEN", "csrf");
  vi.stubGlobal("fetch", vi.fn(async (_url, init) => {
    const proposal = JSON.parse(String(init?.body));
    return new Response(JSON.stringify({ status: "pending", proposal_id: proposal.id }), { status: 202 });
  }));

  const response = await saveFile(new Request("http://localhost/api/file/save", {
    method: "POST",
    headers: { "content-type": "application/json", "x-family-dashboard-csrf": "csrf" },
    body: JSON.stringify({ path: "_knowledge/note.md", content: "new\n" }),
  }));
  expect(response.status).toBe(202);
  const payload = await response.json();
  expect(payload).toMatchObject({ status: "pending", code: "DOCUMENTS_WRITE_PENDING_APPROVAL" });
  expect(payload.proposalId).toMatch(/^family-write-/u);
  expect(await readFile(target, "utf8")).toBe("old\n");
});
```

- [ ] **Step 2: Run test and prove RED**

Run: `cd projects/family-hub/apps/dashboard && bun run test tests/boundaries/write-policy.test.ts`

Expected: current route returns 403.

- [ ] **Step 3: Implement server-only proposal staging**

`hitl-proposals.ts` must:

- reject missing Cockpit URL/key rather than fallback;
- accept only `canWriteSsotPath` targets and UTF-8 payloads <= 2 MB;
- read current source and compute existence/hash/mode/bytes;
- create payload beneath `statePath("proposals", id, "payload")` with `wx` and mode 0600;
- return an envelope with refs/digests and no content;
- POST with `X-Api-Key` to Cockpit and treat only HTTP 202 as pending success;
- remove a newly staged payload if ingress fails; and
- never log content, key, Documents absolute path, or payload bytes.

Use Node `crypto.randomUUID`, `createHash("sha256")`, `open(path, "wx", 0o600)`, and an `AbortSignal.timeout(5000)` request timeout.

```typescript
// src/lib/hitl-proposals.ts
import { createHash, randomUUID } from "node:crypto";
import { mkdir, open, readFile, rm, stat } from "node:fs/promises";
import path from "node:path";
import { statePath, stateRoot } from "@/lib/paths";
import { canWriteSsotPath, resolveSsotPath } from "@/lib/ssot";

type Operation = "replace_text" | "vaccine_update" | "milestone_achieve";
export type PendingWrite = { status: "pending"; proposalId: string };
type StageInput = { operation: Operation; targetRelative: string; content: string; summary: string };

function sha256(value: Uint8Array | string): string {
  return `sha256:${createHash("sha256").update(value).digest("hex")}`;
}

function canonical(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([key, item]) => [key, canonical(item)]),
    );
  }
  return value;
}

async function sourceState(target: string) {
  try {
    const [content, metadata] = await Promise.all([readFile(target), stat(target)]);
    if (!metadata.isFile()) throw new Error("Documents target must be a regular file");
    return { exists: true, sha256: sha256(content), mode: `0o${(metadata.mode & 0o7777).toString(8)}`, bytes: content.length };
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") {
      return { exists: false, sha256: sha256(new Uint8Array()), mode: "0o600", bytes: 0 };
    }
    throw error;
  }
}

export async function stageHitlProposal(input: StageInput): Promise<{ proposal: Record<string, unknown>; payloadPath: string }> {
  if (!canWriteSsotPath(input.targetRelative)) throw new Error("Documents target is not allowed");
  const target = resolveSsotPath(input.targetRelative);
  if (!target) throw new Error("Documents target is unsafe");
  const bytes = Buffer.from(input.content, "utf8");
  if (!bytes.length || bytes.length > 2_000_000) throw new Error("proposal payload is invalid");
  const current = await sourceState(target);
  const proposalId = `family-write-${randomUUID()}`;
  const payloadPath = statePath("proposals", proposalId, "payload");
  await mkdir(path.dirname(payloadPath), { recursive: true, mode: 0o700 });
  const handle = await open(payloadPath, "wx", 0o600);
  try {
    await handle.writeFile(bytes);
    await handle.sync();
  } finally {
    await handle.close();
  }
  const base = {
    id: proposalId,
    type: "family_dashboard_document_write",
    debt_id: "family-dashboard-content",
    source: "family-dashboard",
    target: `documents://family/${input.targetRelative}`,
    expected_change: input.summary,
    operation_level: "L3",
    approval_required: true,
    rollback: "restore exact source bytes or absence",
    verification: "verify runtime receipt digest",
    auto_apply: "disabled",
    operation: input.operation,
    target_relative: input.targetRelative,
    expected_source_exists: current.exists,
    expected_source_sha256: current.sha256,
    expected_source_mode: current.mode,
    expected_source_bytes: current.bytes,
    payload_ref: path.relative(stateRoot(), payloadPath).split(path.sep).join("/"),
    payload_sha256: sha256(bytes),
    payload_bytes: bytes.length,
  };
  return { proposal: { ...base, proposal_digest: sha256(JSON.stringify(canonical(base))) }, payloadPath };
}

export async function submitHitlProposal(staged: { proposal: Record<string, unknown>; payloadPath: string }): Promise<PendingWrite> {
  const cockpit = process.env.COCKPIT_INTERNAL_URL?.replace(/\/$/u, "");
  const key = process.env.FAMILY_HITL_COCKPIT_API_KEY;
  if (!cockpit || !key) {
    await rm(path.dirname(staged.payloadPath), { recursive: true, force: true });
    throw new Error("Cockpit HITL ingress is unavailable");
  }
  try {
    const response = await fetch(`${cockpit}/api/v1/proposals`, {
      method: "POST",
      headers: { "content-type": "application/json", "x-api-key": key },
      body: JSON.stringify(staged.proposal),
      signal: AbortSignal.timeout(5_000),
    });
    const result = (await response.json()) as { status?: string; proposal_id?: string };
    if (response.status !== 202 || result.status !== "pending" || result.proposal_id !== staged.proposal.id) {
      throw new Error("Cockpit rejected HITL proposal");
    }
    return { status: "pending", proposalId: result.proposal_id };
  } catch (error) {
    await rm(path.dirname(staged.payloadPath), { recursive: true, force: true });
    throw error;
  }
}
```

- [ ] **Step 4: Implement the save route**

Order is CSRF → JSON shape/size → path allowlist → stage → Cockpit ingress. Return:

```json
{"status":"pending","proposalId":"family-write-123","code":"DOCUMENTS_WRITE_PENDING_APPROVAL"}
```

Never return `ok: true` or `saved` before terminal receipt.

```typescript
// src/app/api/file/save/route.ts
import path from "node:path";
import { NextResponse } from "next/server";
import { hasValidCsrfHeader } from "@/lib/csrf";
import { stageHitlProposal, submitHitlProposal } from "@/lib/hitl-proposals";

export async function POST(request: Request) {
  if (!hasValidCsrfHeader(request.headers)) {
    return NextResponse.json({ error: "缺少 CSRF 校验" }, { status: 403 });
  }
  try {
    const body = (await request.json()) as { path?: unknown; content?: unknown };
    if (typeof body.path !== "string" || typeof body.content !== "string") {
      return NextResponse.json({ error: "缺少 path 或 content" }, { status: 400 });
    }
    const pending = await submitHitlProposal(
      await stageHitlProposal({
        operation: "replace_text",
        targetRelative: body.path,
        content: body.content,
        summary: `Replace approved family document ${path.posix.basename(body.path)}`,
      }),
    );
    return NextResponse.json({ ...pending, code: "DOCUMENTS_WRITE_PENDING_APPROVAL" }, { status: 202 });
  } catch (error) {
    return NextResponse.json({ error: error instanceof Error ? error.message : "提案创建失败" }, { status: 409 });
  }
}
```

- [ ] **Step 5: Run dashboard unit/lint/build tests**

```bash
cd projects/family-hub/apps/dashboard
bun run test
bun run lint
bun run build
```

Expected: unit tests pass, lint has zero errors, and production build succeeds without live data.

- [ ] **Step 6: Commit and tag**

```bash
git add src/lib/hitl-proposals.ts src/app/api/file/save/route.ts tests/boundaries/write-policy.test.ts .env.example
git commit -m "feat: submit family file writes for approval"
git tag -a t10-122-dashboard-file-proposals -m "T10-122 dashboard file proposals"
```

---

### Task 8: Vaccine/Milestone Proposals and Workspace Snapshot Receipt

**Files:**
- Modify: `projects/family-hub/apps/dashboard/src/lib/ssot-writer.ts`
- Create: `projects/family-hub/apps/dashboard/src/lib/state-snapshot.ts`
- Modify: `projects/family-hub/apps/dashboard/src/app/api/cron/ssot-backup/route.ts`
- Modify: `projects/family-hub/apps/dashboard/tests/boundaries/write-policy.test.ts`

**Interfaces:**
- Consumes: `stageHitlProposal` from Task 7.
- Produces: structured proposal ids for vaccine/milestone actions and pathless state snapshot receipt.

- [ ] **Step 1: Add failing pure-render and snapshot tests**

```typescript
import { createDocumentsSnapshotReceipt } from "@/lib/state-snapshot";

test("vaccine update creates a proposal from an explicit private target binding", async () => {
  const documentsRoot = await mkdtemp(path.join(os.tmpdir(), "family-documents-"));
  const stateRoot = await mkdtemp(path.join(os.tmpdir(), "family-state-"));
  const relative = "_knowledge/health/vaccines.md";
  const target = path.join(documentsRoot, relative);
  await mkdir(path.dirname(target), { recursive: true });
  const original = "| 月龄 | 疫苗 | 剂次 | 日期 | 实际 | 状态 | 备注 |\n| 1 | A | 1 | x |  | ⏳ | |\n";
  await writeFile(target, original);
  vi.stubEnv("FAMILY_DOCUMENTS_ROOT", documentsRoot);
  vi.stubEnv("FAMILY_DASHBOARD_STATE_ROOT", stateRoot);
  vi.stubEnv("FAMILY_VACCINE_DOCUMENT_RELATIVE", relative);
  vi.stubEnv("COCKPIT_INTERNAL_URL", "http://cockpit.internal");
  vi.stubEnv("FAMILY_HITL_COCKPIT_API_KEY", "test-key");
  vi.stubGlobal("fetch", vi.fn(async (_url, init) => {
    const proposal = JSON.parse(String(init?.body));
    return new Response(JSON.stringify({ status: "pending", proposal_id: proposal.id }), { status: 202 });
  }));
  const result = await updateVaccineStatus("A", "1", "2026-08-30");
  expect(result.status).toBe("pending");
  expect(await readFile(target, "utf8")).toBe(original);
});


test("snapshot route writes only an aggregate state receipt", async () => {
  const documentsRoot = await mkdtemp(path.join(os.tmpdir(), "family-documents-"));
  const stateRoot = await mkdtemp(path.join(os.tmpdir(), "family-state-"));
  await writeFile(path.join(documentsRoot, "note.md"), "private body\n");
  vi.stubEnv("FAMILY_DOCUMENTS_ROOT", documentsRoot);
  vi.stubEnv("FAMILY_DASHBOARD_STATE_ROOT", stateRoot);
  const receipt = await createDocumentsSnapshotReceipt();
  const serialized = JSON.stringify(receipt);
  expect(receipt).toMatchObject({ schema: "family-documents-snapshot/v1", fileCount: 1, writesDocuments: false });
  expect(serialized).not.toContain("private body");
  expect(serialized).not.toContain(documentsRoot);
});
```

- [ ] **Step 2: Run focused tests and prove RED**

Run: `cd projects/family-hub/apps/dashboard && bun run test tests/boundaries/write-policy.test.ts`

Expected: domain writers still throw `DOCUMENTS_WRITE_DISABLED` and backup returns 403.

- [ ] **Step 3: Extract deterministic renderers and submit proposals**

Keep `stripMd` and table parsing pure. `updateVaccineStatus` and `markMilestoneAchieved` must produce proposed whole-file text and call `stageHitlProposal`; they never call `writeFile` on Documents. Change their return type to:

```typescript
type PendingWrite = { status: "pending"; proposalId: string };
```

Update server actions to refresh generated JSON only after a terminal verified receipt is observed; Phase B request-time behavior returns pending and does not refresh from uncommitted Documents.

```typescript
// src/lib/ssot-writer.ts — public boundaries
import { readFile } from "node:fs/promises";
import { ssotPath } from "@/lib/ssot";
import { stageHitlProposal, submitHitlProposal, type PendingWrite } from "@/lib/hitl-proposals";

function requiredTarget(name: "FAMILY_VACCINE_DOCUMENT_RELATIVE" | "FAMILY_MILESTONE_DOCUMENT_RELATIVE"): string {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`${name} is required`);
  return value;
}

export function renderVaccineUpdate(content: string, matchName: string, matchDose: string, actualDate: string, note?: string): string {
  let found = false;
  const updated = content.split("\n").map((line) => {
    const cells = parseTableRow(line);
    if (!cells || stripMd(cells[1]) !== stripMd(matchName) || stripMd(cells[2]) !== stripMd(matchDose)) return line;
    found = true;
    cells[4] = actualDate;
    cells[5] = "✅ 已接种";
    if (note !== undefined) cells[6] = note;
    return `| ${cells.join(" | ")} |`;
  });
  if (!found) throw new Error("疫苗未找到");
  return updated.join("\n");
}

export async function updateVaccineStatus(matchName: string, matchDose: string, actualDate: string, note?: string): Promise<PendingWrite> {
  const relative = requiredTarget("FAMILY_VACCINE_DOCUMENT_RELATIVE");
  const current = await readFile(ssotPath(relative), "utf8");
  return submitHitlProposal(await stageHitlProposal({
    operation: "vaccine_update",
    targetRelative: relative,
    content: renderVaccineUpdate(current, matchName, matchDose, actualDate, note),
    summary: `Record approved vaccine dose ${stripMd(matchDose)}`,
  }));
}

function transformMilestoneTable(content: string, normalizedTitle: string, achievedDate: string): string {
  const lines = content.split("\n");
  let section = "";
  let removed: string[] | null = null;
  let removedIndex = -1;
  for (let index = 0; index < lines.length; index += 1) {
    if (lines[index].startsWith("## ")) {
      section = lines[index];
      continue;
    }
    if (section.includes("已达成里程碑")) continue;
    const cells = parseTableRow(lines[index]);
    if (!cells || stripMd(cells[2]) !== normalizedTitle) continue;
    removed = [cells[0], cells[1], normalizedTitle];
    removedIndex = index;
    break;
  }
  if (!removed || removedIndex < 0) throw new Error("里程碑未找到");
  lines.splice(removedIndex, 1);
  const newRow = `| ${removed[0]} | ${removed[1]} | ${removed[2]} | ${achievedDate} | ✅ |`;
  const achievedStart = lines.findIndex((line) => line.startsWith("## 已达成里程碑"));
  if (achievedStart < 0) {
    const header = `## 已达成里程碑\n\n### 当前新增\n\n| 月龄 | 领域 | 里程碑 | 达成日期 | 备注 |\n|------|------|--------|----------|------|\n${newRow}`;
    lines.splice(1, 0, "", header);
  } else {
    let insertAt = achievedStart + 1;
    for (let index = achievedStart + 1; index < lines.length; index += 1) {
      if (lines[index].startsWith("## ") && !lines[index].startsWith("### ")) break;
      if (parseTableRow(lines[index])) insertAt = index + 1;
    }
    lines.splice(insertAt, 0, newRow);
  }
  return lines.join("\n");
}

export function renderMilestoneAchievement(content: string, matchTitle: string, achievedDate: string): string {
  return transformMilestoneTable(content, stripMd(matchTitle), achievedDate);
}

export async function markMilestoneAchieved(matchTitle: string, achievedDate: string): Promise<PendingWrite> {
  const relative = requiredTarget("FAMILY_MILESTONE_DOCUMENT_RELATIVE");
  const current = await readFile(ssotPath(relative), "utf8");
  return submitHitlProposal(await stageHitlProposal({
    operation: "milestone_achieve",
    targetRelative: relative,
    content: renderMilestoneAchievement(current, matchTitle, achievedDate),
    summary: "Record approved milestone achievement",
  }));
}
```

- [ ] **Step 4: Implement state snapshot receipt**

Walk regular `.md/.yaml/.yml/.json/.txt` files beneath `FAMILY_DOCUMENTS_ROOT`, reject symlinks, hash `relativePath\0mode\0bytes\0sha256`, and atomically write a 0600 receipt under `statePath("audit")`. The receipt contains schema, file count, byte count, tree SHA, and `writes_documents: false` only.

```typescript
// src/lib/state-snapshot.ts
import { createHash, randomUUID } from "node:crypto";
import { chmod, mkdir, open, readdir, rename, rm, stat } from "node:fs/promises";
import path from "node:path";
import { documentsRoot, statePath } from "@/lib/paths";

const ALLOWED = new Set([".md", ".markdown", ".yaml", ".yml", ".json", ".txt"]);
const EXCLUDED_TOP_LEVEL = new Set(["family-dashboard-app"]);

async function regularFiles(root: string, current = root): Promise<string[]> {
  const entries = await readdir(current, { withFileTypes: true });
  const result: string[] = [];
  for (const entry of entries.sort((a, b) => a.name.localeCompare(b.name))) {
    const candidate = path.join(current, entry.name);
    const relative = path.relative(root, candidate);
    if (!relative.includes(path.sep) && EXCLUDED_TOP_LEVEL.has(relative)) continue;
    if (entry.isSymbolicLink()) throw new Error("Documents snapshot crosses a symlink");
    if (entry.isDirectory()) result.push(...(await regularFiles(root, candidate)));
    else if (entry.isFile() && ALLOWED.has(path.extname(entry.name).toLowerCase())) result.push(candidate);
  }
  return result;
}

export async function createDocumentsSnapshotReceipt() {
  const root = documentsRoot();
  const files = await regularFiles(root);
  let bytes = 0;
  const tree = createHash("sha256");
  for (const file of files) {
    const metadata = await stat(file);
    const content = await import("node:fs/promises").then((fs) => fs.readFile(file));
    bytes += metadata.size;
    const relative = path.relative(root, file).split(path.sep).join("/");
    const digest = createHash("sha256").update(content).digest("hex");
    tree.update(`${relative}\0${(metadata.mode & 0o7777).toString(8)}\0${metadata.size}\0${digest}\n`);
  }
  const receipt = {
    schema: "family-documents-snapshot/v1",
    fileCount: files.length,
    byteCount: bytes,
    treeSha256: `sha256:${tree.digest("hex")}`,
    writesDocuments: false,
  };
  const directory = statePath("audit");
  await mkdir(directory, { recursive: true, mode: 0o700 });
  const target = path.join(directory, `documents-snapshot-${randomUUID()}.json`);
  const temporary = `${target}.tmp`;
  const handle = await open(temporary, "wx", 0o600);
  try {
    await handle.writeFile(`${JSON.stringify(receipt, null, 2)}\n`);
    await handle.sync();
  } finally {
    await handle.close();
  }
  await rename(temporary, target);
  await chmod(target, 0o600);
  await rm(temporary, { force: true });
  return receipt;
}
```

The cron route first runs existing `authenticateCron(request)`, then calls `createDocumentsSnapshotReceipt`, returns the receipt, and contains no `child_process`, Git command, Documents write, or cwd-derived path.

- [ ] **Step 5: Run unit/lint/build/E2E and full child regression**

```bash
cd projects/family-hub/apps/dashboard
bun run test && bun run lint && bun run build && bun run test:e2e
cd ../..
uv run pytest tests -q
bun run build
```

- [ ] **Step 6: Commit, tag, PR, and merge family-hub PR B**

```bash
git add apps/dashboard/src/lib/ssot-writer.ts apps/dashboard/src/lib/state-snapshot.ts \
  apps/dashboard/src/app/api/cron/ssot-backup/route.ts \
  apps/dashboard/tests/boundaries/write-policy.test.ts
git commit -m "feat: complete family dashboard proposal-only writes"
git tag -a t10-122-dashboard-hitl-writes -m "T10-122 Dashboard HITL writes"
git push -u origin agent/codex-documents-convergence--t10-122-family-dashboard-routes-20260831-01
gh pr create --base main \
  --head agent/codex-documents-convergence--t10-122-family-dashboard-routes-20260831-01 \
  --title "feat: wire family dashboard proposal-only writes"
```

Push the second family-hub branch, open PR B, wait all required child checks, squash merge, fetch child `origin/main`, and record the final family-hub SHA.

---

### Task 9: Root Authority, Mutation Registry, and Phase-B Progress Contract

**Files:**
- Modify: `projects/family-hub` gitlink
- Modify: `projects/omo` gitlink
- Modify: `projects/agora` gitlink
- Modify: `projects/cockpit` gitlink
- Modify: `.omo/_truth/registry/mutation-surfaces.yaml`
- Modify: `.omo/_truth/registry/documents-content-plane-migrations.yaml`
- Modify: `tests/test_documents_content_plane_migration_check.py`

**Interfaces:**
- Consumes: all four authoritative child-main SHAs.
- Produces: root authority and non-terminal Phase B registry evidence.

- [ ] **Step 1: Add failing root registry tests**

```python
def test_family_dashboard_phase_b_is_registered_but_non_terminal(registry):
    family = next(item for item in registry["families"] if item["id"] == "family-dashboard-app")
    assert family["status"] == "in_progress"
    phase_b = family["progress_evidence"]["phase_b"]
    assert phase_b["runtime_owner"] == "family-hub"
    assert phase_b["proposal_owner"] == "omo"
    assert phase_b["approval_entry"] == "cockpit"
    assert phase_b["route"] == "bos://governance/hitl/execute/family_dashboard_document_write"
    assert phase_b["phase_c_pending"] is True
```

- [ ] **Step 2: Run test and prove RED**

Run: `uv run --with pyyaml --with pytest python -m pytest tests/test_documents_content_plane_migration_check.py -q`

Expected: missing Phase B block.

- [ ] **Step 3: Register the unique mutation surface**

Add one entry to `.omo/_truth/registry/mutation-surfaces.yaml`:

```yaml
- name: omo-hitl-family-dashboard-documents
  entrypoint: Cockpit /api/v1/proposals -> OMO omo_cockpit_bridge
  runtime_ref: projects/omo/src/omo/omo_cockpit_bridge.py:record_hitl_proposal + approve_hitl_proposal_async
  mutation_target: Documents family content through approved family-hub CAS owner
  broker_ref: projects/omo/src/omo/omo_cockpit_bridge.py
```

- [ ] **Step 4: Record non-terminal Phase B progress**

Set `family-dashboard-app.status: in_progress`; add owner/route/spec refs and `phase_c_pending: true`. Do not set `completed`, `retired`, or terminal migration status before Phase C.

- [ ] **Step 5: Adopt exact child-main gitlinks**

```bash
git -C projects/family-hub fetch origin main
git -C projects/omo fetch origin main
git -C projects/agora fetch origin main
git -C projects/cockpit fetch origin main
```

Set each root index entry only to the fetched `origin/main` SHA and prove each is reachable. No child worktree SHA or PR-head SHA is accepted.

- [ ] **Step 6: Run root tests and commit/tag/PR**

```bash
uv run --with pyyaml --with pytest python -m pytest tests/test_documents_content_plane_migration_check.py -q
uv run --with pyyaml python bin/gac/documents-content-plane-migration-check.py --json
make gac-local-gate
git add projects/family-hub projects/omo projects/agora projects/cockpit \
  .omo/_truth/registry/mutation-surfaces.yaml \
  .omo/_truth/registry/documents-content-plane-migrations.yaml \
  tests/test_documents_content_plane_migration_check.py
git commit -m "chore(submodule): adopt family dashboard Phase B authorities"
git tag -a t10-122-root-authorities -m "T10-122 root authorities"
git push -u origin agent/codex-documents-convergence--t10-122-root-authorities-20260831-01
gh pr create --base main \
  --head agent/codex-documents-convergence--t10-122-root-authorities-20260831-01 \
  --title "chore(submodule): adopt family dashboard Phase B authorities"
```

Push root branch, open PR, wait required CI, squash merge, and replay exact child gitlinks from root main.

---

### Task 10: Real Read-Only Runtime Materialization

**Files:**
- Create at runtime: `runtime/family-hub/dashboard/**`
- Create evidence: `.omo/evidence/$RUN_ID/family-dashboard-runtime-plan.json`
- Create evidence: `.omo/evidence/$RUN_ID/family-dashboard-runtime-receipt.json`

**Interfaces:**
- Consumes: merged root main and family-hub CLI.
- Produces: real canonical state and source/parity receipts.

- [ ] **Step 1: Prove target absence and source stability**

```bash
test ! -e /Users/xiamingxing/Workspace/runtime/family-hub/dashboard
test -d /Users/xiamingxing/Documents/@家庭生活/family-dashboard-app/data-manifest
test -d /Users/xiamingxing/Documents/@家庭生活/family-dashboard-app/app-data
```

- [ ] **Step 2: Generate and review a pathless plan**

```bash
cd projects/family-hub
uv run python -m family_hub.dashboard_phase_b plan-runtime \
  --documents-root /Users/xiamingxing/Documents/@家庭生活 \
  --legacy-app-root /Users/xiamingxing/Documents/@家庭生活/family-dashboard-app \
  --state-root /Users/xiamingxing/Workspace/runtime/family-hub/dashboard \
  --json
```

Expected: six manifests, legacy generated inventory, no raw path or content in JSON, and one fingerprint.

- [ ] **Step 3: Apply with exact fingerprint**

```bash
uv run python -m family_hub.dashboard_phase_b apply-runtime \
  --documents-root /Users/xiamingxing/Documents/@家庭生活 \
  --legacy-app-root /Users/xiamingxing/Documents/@家庭生活/family-dashboard-app \
  --state-root /Users/xiamingxing/Workspace/runtime/family-hub/dashboard \
  --app-root /Users/xiamingxing/Workspace/projects/family-hub/apps/dashboard \
  --expected-fingerprint "$EXPECTED_FINGERPRINT" \
  --json
```

Before execution, assign `EXPECTED_FINGERPRINT` to the literal reviewed `sha256:` value printed by Step 2. Do not derive it through command substitution; the human-readable evidence must show the exact reviewed digest.

- [ ] **Step 4: Verify canonical state and source unchanged**

Run the immutable BET command exactly:

```bash
cd /Users/xiamingxing/Workspace/projects/family-hub
uv run python -m family_hub.dashboard_phase_b verify-runtime \
  --documents-root /Users/xiamingxing/Documents/@家庭生活 \
  --state-root /Users/xiamingxing/Workspace/runtime/family-hub/dashboard \
  --json
```

Confirm private modes, six manifests, required generated products, cache seed count zero, normalized parity, no staging directory, and unchanged source fingerprint read from the bound plan.

- [ ] **Step 5: Run representative real read-only canary**

```bash
DASHBOARD_CANARY_PORT="$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')"
cd /Users/xiamingxing/Workspace/projects/family-hub/apps/dashboard
FAMILY_DOCUMENTS_ROOT=/Users/xiamingxing/Documents/@家庭生活 \
FAMILY_DASHBOARD_STATE_ROOT=/Users/xiamingxing/Workspace/runtime/family-hub/dashboard \
  bun run start -- -H 127.0.0.1 -p "$DASHBOARD_CANARY_PORT" \
  > /Users/xiamingxing/Workspace/runtime/family-hub/dashboard/migration/server-canary.log 2>&1 &
DASHBOARD_CANARY_PID=$!
for attempt in 1 2 3 4 5 6 7 8 9 10; do
  curl --fail --silent "http://127.0.0.1:$DASHBOARD_CANARY_PORT/api/health" && break
  sleep 1
done
curl --fail --silent "http://127.0.0.1:$DASHBOARD_CANARY_PORT/api/health"
kill "$DASHBOARD_CANARY_PID"
wait "$DASHBOARD_CANARY_PID" || true
```

Only the PID created by this command may be stopped. Run `verify-paths`, `verify-summary`, and `verify-domain-data` against the real roots before server start; those commands cover summary/members/health/growth/daily/assets/search/tasks/files source bindings without requiring a logged-in browser. Do not register a persistent service or mutate Cockpit contracts.

---

### Task 11: Danger-Gated Real Write Canary and Verified Rollback

**Files:**
- Create: `.omo/_truth/governance-evidence/approval-2026-08-31-t10-122-family-dashboard-canary.md`
- Runtime receipts: `runtime/family-hub/dashboard/mutations/{proposal_id}/**`
- OMO receipt: `.omo/_delivery/hitl/family-dashboard/{proposal_id}.yaml`

**Interfaces:**
- Consumes: complete merged authority chain and real runtime state.
- Produces: one approved create transaction and one verified rollback to absence.

- [ ] **Step 1: Pause and request explicit confirmation**

Present the exact target:

```text
@家庭生活/_meta/family-dashboard-write-canary.md
```

State that it is a new non-private canary document, no existing household file is selected, and rollback restores absence. Do not proceed until the user explicitly approves this exact canary.

- [ ] **Step 2: Record the approval evidence**

The approval file must quote the user, bind target, proposal digest, expected absence, runtime root, rollback contract, and expiry. Commit/tag/PR this evidence before the live write.

- [ ] **Step 3: Create the proposal through Cockpit ingress**

Require `FAMILY_HITL_COCKPIT_API_KEY` to be present in the operator environment and mapped to `family-documents-write` or admin scope. Start one owned Cockpit canary process with explicit authority roots:

```bash
test -n "$FAMILY_HITL_COCKPIT_API_KEY"
COCKPIT_CANARY_PORT="$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')"
cd /Users/xiamingxing/Workspace/projects/cockpit
COCKPIT_DASHBOARD_PORT="$COCKPIT_CANARY_PORT" \
COCKPIT_API_KEY="$FAMILY_HITL_COCKPIT_API_KEY" \
OMO_DIR=/Users/xiamingxing/Workspace/.omo \
FAMILY_DOCUMENTS_ROOT=/Users/xiamingxing/Documents/@家庭生活 \
FAMILY_DASHBOARD_STATE_ROOT=/Users/xiamingxing/Workspace/runtime/family-hub/dashboard \
  uv run cockpit-dashboard \
  > /Users/xiamingxing/Workspace/runtime/family-hub/dashboard/migration/cockpit-canary.log 2>&1 &
COCKPIT_CANARY_PID=$!
```

Create the exact operator envelope and submit it:

```bash
PROPOSAL_ID=family-dashboard-phase-b-canary-20260831
PROPOSAL_FILE="/Users/xiamingxing/Workspace/runtime/family-hub/dashboard/proposals/$PROPOSAL_ID/envelope.json"
cd /Users/xiamingxing/Workspace/projects/family-hub
uv run python -m family_hub.dashboard_phase_b plan-canary \
  --documents-root /Users/xiamingxing/Documents/@家庭生活 \
  --state-root /Users/xiamingxing/Workspace/runtime/family-hub/dashboard \
  --proposal-id "$PROPOSAL_ID" --output "$PROPOSAL_FILE" --json
curl --fail --silent --request POST \
  --header "X-Api-Key: $FAMILY_HITL_COCKPIT_API_KEY" \
  --header 'Content-Type: application/json' \
  --data-binary "@$PROPOSAL_FILE" \
  "http://127.0.0.1:$COCKPIT_CANARY_PORT/api/v1/proposals"
test ! -e /Users/xiamingxing/Documents/@家庭生活/_meta/family-dashboard-write-canary.md
```

- [ ] **Step 4: Approve in Cockpit and verify immediate execution**

```bash
curl --fail --silent --request POST \
  --header "X-Api-Key: $FAMILY_HITL_COCKPIT_API_KEY" \
  "http://127.0.0.1:$COCKPIT_CANARY_PORT/api/v1/proposals/$PROPOSAL_ID/approve"
test ! -e /Users/xiamingxing/Documents/@家庭生活/_meta/family-dashboard-write-canary.md
test -f "/Users/xiamingxing/Workspace/.omo/_delivery/hitl/family-dashboard/$PROPOSAL_ID.yaml"
test -f "/Users/xiamingxing/Workspace/runtime/family-hub/dashboard/mutations/$PROPOSAL_ID/apply.json"
test -f "/Users/xiamingxing/Workspace/runtime/family-hub/dashboard/mutations/$PROPOSAL_ID/verify.json"
test -f "/Users/xiamingxing/Workspace/runtime/family-hub/dashboard/mutations/$PROPOSAL_ID/rollback.json"
kill "$COCKPIT_CANARY_PID"
wait "$COCKPIT_CANARY_PID" || true
```

Require terminal OMO receipt, `apply.json`, `verify.json`, `rollback.json`, `canary_rolled_back: true`, final target absence, and no cache hit. No client-supplied actor is accepted. Only the owned canary PID may be stopped.

- [ ] **Step 5: Verify the single-approval rollback contract**

Do not create a second proposal. Verify that the exact approved `canary_rollback: true` transaction performed create → digest verification → remove → absence verification in one owner call, that the rollback receipt status is `rolled_back`, and that all receipts remain immutable.

- [ ] **Step 6: Re-run consumer and Documents audits**

Require `forbidden_executors=0`, no unmatched consumer, no source drift outside the controlled canary lifecycle, and no new runtime/cache surface inside Documents.

---

### Task 12: Final Mainline Replay, Report, Retro, and BET Closeout

**Files:**
- Create: `docs/reports/2026-08-31-family-dashboard-runtime-state-and-hitl-writes-phase-b.md`
- Create: `.omo/_knowledge/retros/BET-Y1Q3-T10-122.md`
- Modify: `docs/plans/3y-bet-ledger.yaml`
- Modify: `.omo/_truth/registry/documents-content-plane-migrations.yaml`

**Interfaces:**
- Consumes: child/root merges, real runtime receipt, OMO receipt, canary approval and rollback.
- Produces: truthful `delivery_accepted` Phase B completion with value `NOT_PROVEN` and Phase C pending.

- [ ] **Step 1: Replay every registered verify command from fresh root main**

Initialize all four exact submodules and path dependencies. Run the eight T10-122 verify groups exactly as registered. Any missing dependency is environment setup, not a reason to weaken commands.

- [ ] **Step 2: Write the evidence report**

Separate:

- child/root engineering authority;
- runtime materialization/parity;
- HITL proposal/approval/BOS/CAS receipts;
- canary apply and rollback;
- consumer/source preservation;
- Phase C, production availability, value, and Documents-wide purity as `NOT_PROVEN`.

- [ ] **Step 3: Write the six-question retro**

Cover intent, actual result, architecture changes, source/runtime effects, remaining Phase C work, and proven value boundary. Include all clone/workflow/PR failure lessons without turning them into completion evidence.

- [ ] **Step 4: Update registry and completion matrix**

Keep family migration non-terminal and Phase C pending. Mark T10-122 `done` only with:

```yaml
completion_evidence:
  schema_version: completion-evidence-matrix/v1
  axes:
    engineering:
      status: VERIFIED
    operational:
      status: PROVEN
    value:
      status: NOT_PROVEN
      evidence: {}
  overall_state: delivery_accepted
```

Every report/retro reference carries the actual final SHA-256.

- [ ] **Step 5: Commit/tag/push/PR and merge closeout**

Use lane-separated commits if ledger/registry and Markdown conflict. Push the branch and tags, open root closeout PR, wait every required check including final governance verify, squash merge, then verify remote main, child gitlinks, report/retro digests, T10-122 status, runtime receipt, and non-terminal family migration.

- [ ] **Step 6: Close workflows and preserve execution clones**

Use formal closeout where the final retro is present. Record any phase-level runs with official `close` evidence. Do not delete harness-owned clones or use destructive cleanup.

## Plan Self-Review Checklist

- [x] Every Phase B acceptance criterion maps to Tasks 1–12.
- [x] No task performs Phase C cutover, persistent service registration, old-app deletion, or value acceptance.
- [x] All interfaces use the same proposal type, BOS URI, principal prefix, receipt schemas, runtime layout, and CLI module.
- [x] Every mutation failure either proves no write or proves rollback.
- [x] Every child merge precedes root pointer adoption.
- [x] The real canary remains behind an explicit second human approval.
- [x] No unresolved marker, dynamic-value ambiguity, or abbreviated source test remains before implementation begins.
