---
status: active
lifecycle: plan
owner: family-hub
created: 2026-08-30
last-reviewed: 2026-08-30
bet_id: BET-Y1Q3-T10-111
spec_ref: repo://docs/superpowers/specs/2026-08-31-family-dashboard-owner-migration-phase-a-design.md
type: ssot
last_updated: 2026-09-03
---

# Family Dashboard Workspace Owner Migration Phase A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish `projects/family-hub/apps/dashboard` as the canonical Git-owned source for the mature Next.js family dashboard without importing private/runtime payloads, mutating Documents, or cutting over consumers.

**Architecture:** A deterministic Python importer in `family-hub` selects only reviewed source classes and emits hash-bound provenance receipts. The nested Next.js package gains explicit Documents/state path adapters, synthetic build fixtures, and fail-closed write policy while the existing Vite, Express, Python, and FastMCP surfaces remain independent. Delivery is child-first: merge and replay the family-hub PR, then update and merge the root gitlink/evidence PR.

**Tech Stack:** Python 3.13, pytest, Bun, TypeScript 5, Next.js 16, React 19, Vitest, Playwright, Git submodules, Agent Workflow, GitHub Actions.

## Global Constraints

- Accepted specification digest: `sha256:d833693de0a212a8a00e7ab6974c8511817291bd8254c609191c71884f4e186b`.
- Source is `/Users/xiamingxing/Documents/@家庭生活/family-dashboard-app`; it is read-only throughout Phase A.
- Target is exactly `projects/family-hub/apps/dashboard` in the existing `omostation-family-hub` repository.
- Never import `node_modules`, `.next`, `app-data`, real `data-manifest`, SQLite, indexes, embeddings, AI caches, logs, credentials, browser auth state, build output, `.trae`, `.DS_Store`, or TypeScript build info.
- Never rely on `process.cwd()/..`, an absolute `/Users/...` fallback, or live household data in tests/build.
- `FAMILY_DOCUMENTS_ROOT` is explicit and read-only; `FAMILY_DASHBOARD_STATE_ROOT` is explicit and outside Git/Documents in production.
- Direct Documents writes remain disabled; an environment flag alone cannot authorize writes.
- Do not change Cockpit, runtime services, ports, cron, LaunchAgents, deployment, consumers, the old Documents app, or migration-family status in Phase A.
- Use RED → GREEN for each new behavior and commit each lane-scoped deliverable with a durable tag.
- Child required CI, child mainline replay, root required CI, root merge, and root mainline replay are mandatory. PR creation alone is not delivery.
- Phase B runtime relocation, Phase C cutover/retirement, and principal-bound value remain `NOT_PROVEN`.

## File and responsibility map

### Family-hub child repository

- `tools/dashboard_import.py`: source classification, private-token scan, exact copy, deterministic private-token substitution for reviewed text source, immutable inventory, and verification.
- `tests/test_dashboard_import.py`: importer RED/GREEN contract, drift/collision/unsafe-node/private-data cases.
- `apps/dashboard/`: imported and adapted Next.js package.
- `apps/dashboard/src/lib/paths.ts`: sole Documents/state path resolver.
- `apps/dashboard/src/lib/write-policy.ts`: typed fail-closed Documents-write policy.
- `apps/dashboard/src/lib/ssot.ts`: compatibility facade delegating to `paths.ts`; no parent fallback.
- `apps/dashboard/src/lib/data-loader.ts`: generated-state reads through `statePath`.
- `apps/dashboard/scripts/build-all.ts` and builders: generated-state writes through `statePath` and manifest reads through the state root.
- `apps/dashboard/scripts/run-next-build.ts`: production build using synthetic roots, never live household data.
- `apps/dashboard/tests/fixtures/documents/`: synthetic read-only Markdown/YAML fixture.
- `apps/dashboard/tests/fixtures/state/`: synthetic manifests/generated JSON required by unit/build/E2E.
- `apps/dashboard/tests/boundaries/`: explicit-root, traversal, symlink, state-isolation, and write-policy tests.
- `apps/dashboard/e2e/pages.spec.ts`: representative read journeys and disabled-write assertions.
- `apps/dashboard/migration/source-receipt.json`: selected source inventory and fingerprint; no private values.
- `apps/dashboard/migration/target-receipt.json`: initial imported target parity receipt.
- `.github/workflows/ci.yml`: add nested dashboard tests without weakening existing jobs.
- `.gitignore`: ignore nested dashboard runtime/build/auth/audit products.
- `README.md`, `ARCHITECTURE.md`, `BOUNDARY.md`, `CALLCHAIN.md`, `CAPABILITY-MAP.md`: document the nested owner and explicitly unproven cutover.

### Workspace root repository

- `projects/family-hub`: advance gitlink only to the merged child `origin/main` SHA.
- `docs/reports/2026-08-31-family-dashboard-owner-migration-phase-a.md`: evidence matrix, child/root merges, receipts, tests, and remaining Phase B/C work.
- `.omo/_knowledge/retros/BET-Y1Q3-T10-111.md`: Phase A retrospective and lessons.
- `docs/plans/3y-bet-ledger.yaml`: Phase A completion evidence only after authoritative mainline proof.

---

### Task 1: Create the isolated full delivery and bind the workflow

**Files:**
- Runtime evidence: `.omo/evidence/$RUN_ID/affected-graph-receipt.json`
- Runtime run record: `.omo/_delivery/agent-workflows/runs/$RUN_ID.yaml`
- No product file changes in this task.

**Interfaces:**
- Consumes: `BET-Y1Q3-T10-111`, accepted spec digest, root `origin/main` containing PR #2775.
- Produces: one ready full delivery clone, one BET-bound run ID, and claims covering `projects/family-hub` plus later root evidence paths.

- [ ] **Step 1: Onboard a fresh delivery clone with the family-hub submodule**

Run from a clean root-main verification clone:

```bash
python3 bin/gac/clone-lifecycle.py onboard \
  --agent-id codex-documents-convergence \
  --delivery-attempt-id t10-111-family-dashboard-implementation-20260831-01 \
  --source . \
  --revision origin/main \
  --destination /Users/xiamingxing/agents/codex-documents-convergence/attempts/t10-111-family-dashboard-implementation-20260831-01/ws \
  --submodule projects/family-hub
```

Expected: `status=ready`; identity binds the exact actor, attempt, root branch, and `projects/family-hub` gitlink.

- [ ] **Step 2: Verify root and child authority before branch creation**

```bash
git rev-parse HEAD
git rev-parse origin/main
git ls-tree HEAD projects/family-hub
git -C projects/family-hub remote -v
git -C projects/family-hub rev-parse HEAD
git -C projects/family-hub fetch origin main
git -C projects/family-hub merge-base --is-ancestor HEAD origin/main
```

Expected: root `HEAD == origin/main`; child gitlink exists on child `origin/main`; remote is `starlink-awaken/omostation-family-hub`.

- [ ] **Step 3: Start the BET-bound workflow**

```bash
uv run --with pyyaml python bin/agent-workflow.py bootstrap
uv run --with pyyaml python bin/agent-workflow.py status --json
RUN_ID="$(uv run --with pyyaml python bin/agent-workflow.py start bet-execution \
  --profile governance-agent \
  --bet BET-Y1Q3-T10-111 \
  --objective "Implement and merge family dashboard Workspace owner migration Phase A" \
  | awk '/^started / {print $2}')"
test -n "$RUN_ID"
```

Expected: a new active run whose `bet_id` is exactly `BET-Y1Q3-T10-111`.

- [ ] **Step 4: Generate the affected graph and claim all known write surfaces**

```bash
uv run --with pyyaml python bin/gac/affected-graph.py \
  --workspace-root . \
  --changed-projects workspace-root family-hub \
  --output ".omo/evidence/$RUN_ID/affected-graph-receipt.json" --json
uv run --with pyyaml python bin/agent-workflow.py claim "$RUN_ID" \
  --path projects/family-hub \
  --affected-receipt ".omo/evidence/$RUN_ID/affected-graph-receipt.json"
uv run --with pyyaml python bin/agent-workflow.py claim "$RUN_ID" \
  --path docs/reports/2026-08-31-family-dashboard-owner-migration-phase-a.md \
  --affected-receipt ".omo/evidence/$RUN_ID/affected-graph-receipt.json"
uv run --with pyyaml python bin/agent-workflow.py claim "$RUN_ID" \
  --path .omo/_knowledge/retros/BET-Y1Q3-T10-111.md \
  --affected-receipt ".omo/evidence/$RUN_ID/affected-graph-receipt.json"
uv run --with pyyaml python bin/agent-workflow.py claim "$RUN_ID" \
  --path docs/plans/3y-bet-ledger.yaml \
  --affected-receipt ".omo/evidence/$RUN_ID/affected-graph-receipt.json"
```

Expected: every claim succeeds; no broad `projects` claim is used.

- [ ] **Step 5: Create the child delivery branch**

```bash
git -C projects/family-hub switch -c agent/codex-documents-convergence--t10-111-family-dashboard-phase-a origin/main
git -C projects/family-hub status --short
```

Expected: exact branch created from child `origin/main`; status clean.

### Task 2: Build the deterministic allowlist importer test-first

**Files:**
- Create: `projects/family-hub/tools/dashboard_import.py`
- Create: `projects/family-hub/tests/test_dashboard_import.py`

**Interfaces:**
- Consumes: explicit source/destination paths and a closed private-token replacement mapping.
- Produces: `ImportPlan`, `FileRecord`, `SanitizedRecord`, `derive_redaction_map()`, `plan_import()`, `apply_import()`, `verify_receipts()`, and CLI JSON envelopes.

- [ ] **Step 1: Write RED tests for allowed and forbidden classes**

Add tests that construct temporary trees and call this public interface:

```python
from pathlib import Path

from tools.dashboard_import import (
    ImportErrorClosed,
    apply_import,
    derive_redaction_map,
    plan_import,
)


def test_plan_selects_only_canonical_source(tmp_path: Path) -> None:
    source = tmp_path / "source"
    (source / "src").mkdir(parents=True)
    (source / "src" / "page.tsx").write_text("export default function Page() {}\n")
    (source / "package.json").write_text('{"private":true}\n')
    (source / "node_modules").mkdir()
    (source / "node_modules" / "ignored.js").write_text("generated\n")
    (source / "app-data").mkdir()
    (source / "app-data" / "health.json").write_text('{"private":true}\n')

    plan = plan_import(source, tmp_path / "target", replacements={})

    assert [record.relative_path for record in plan.files] == [
        "package.json",
        "src/page.tsx",
    ]
    assert plan.excluded_counts["runtime_or_private"] == 2


def test_plan_rejects_symlink_and_unknown_root(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "src").symlink_to(tmp_path, target_is_directory=True)
    (source / "mystery.bin").write_bytes(b"unknown")

    with pytest.raises(ImportErrorClosed, match="unsafe node|unknown root"):
        plan_import(source, tmp_path / "target", replacements={})


def test_plan_separates_private_text_for_deterministic_substitution(tmp_path: Path) -> None:
    source = tmp_path / "source"
    (source / "src").mkdir(parents=True)
    (source / "src" / "member.ts").write_text('export const member = "Private Person";\n')

    plan = plan_import(
        source,
        tmp_path / "target",
        replacements={"Private Person": "Synthetic Member"},
    )

    assert plan.files == ()
    assert [record.relative_path for record in plan.sanitized_files] == ["src/member.ts"]


def test_derived_redaction_map_never_emits_private_values(tmp_path: Path) -> None:
    source = tmp_path / "source"
    manifest = source / "data-manifest" / "members.yaml"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("members:\n  - name: Private Person\n", encoding="utf-8")

    result = derive_redaction_map(source)

    assert result.replacements == {"Private Person": "Synthetic Member 01"}
    assert "Private Person" not in result.public_summary
    assert result.public_summary["replacement_count"] == 1
```

Also cover duplicate normalized paths, source drift, target collision, target extras, absolute `/Users/` content, unmapped private tokens, env files, `.auth.json`, `src/app/data/*.json`, and malformed receipt.

- [ ] **Step 2: Run tests and prove RED**

```bash
cd projects/family-hub
uv run pytest tests/test_dashboard_import.py -q
```

Expected: collection fails because `tools.dashboard_import` does not exist.

- [ ] **Step 3: Implement immutable records and policy constants**

Use frozen dataclasses and closed root policy:

```python
from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

import yaml

ALLOWED_ROOTS = frozenset({"src", "scripts", "public", "e2e", "_deploy"})
ALLOWED_FILES = frozenset({
    ".dockerignore",
    ".env.example",
    ".gitignore",
    "CRON_SETUP.md",
    "README.md",
    "bun.lock",
    "docker-compose.yml",
    "eslint.config.mjs",
    "next.config.ts",
    "package.json",
    "playwright.config.ts",
    "postcss.config.mjs",
    "tsconfig.json",
    "vitest.config.ts",
    "vitest.setup.ts",
})
FORBIDDEN_PARTS = frozenset({
    ".next", ".trae", "app-data", "node_modules", "test-results",
    "coverage", ".local-audit", "data-manifest",
})
FORBIDDEN_NAMES = frozenset({".DS_Store", ".env.local", ".auth.json", "tsconfig.tsbuildinfo"})
FORBIDDEN_RELATIVE_PATHS = frozenset({"public/tailwind.css"})


class ImportErrorClosed(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class FileRecord:
    relative_path: str
    mode: int
    size: int
    sha256: str


@dataclass(frozen=True, slots=True)
class SanitizedRecord:
    relative_path: str
    mode: int
    source_size: int
    source_sha256: str
    target_size: int
    target_sha256: str
    transform: str


@dataclass(frozen=True, slots=True)
class ImportPlan:
    schema: str
    files: tuple[FileRecord, ...]
    sanitized_files: tuple[SanitizedRecord, ...]
    selected_count: int
    selected_bytes: int
    selected_fingerprint: str
    excluded_counts: dict[str, int]
    redaction_map_digest: str | None


@dataclass(frozen=True, slots=True)
class ApplyResult:
    copied_files: tuple[FileRecord, ...]
    sanitized_files: tuple[SanitizedRecord, ...]


@dataclass(frozen=True, slots=True)
class RedactionMapResult:
    replacements: dict[str, str]
    public_summary: dict[str, int | str]


def derive_redaction_map(source: Path) -> RedactionMapResult:
    manifest = source / "data-manifest" / "members.yaml"
    loaded: Any = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    names: set[str] = set()

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "name" and isinstance(child, str) and child.strip():
                    names.add(child.strip())
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(loaded)
    replacements = {
        name: f"Synthetic Member {index:02d}"
        for index, name in enumerate(sorted(names), start=1)
    }
    documents_dir = next(
        (parent for parent in source.resolve().parents if parent.name == "Documents"),
        None,
    )
    if documents_dir is not None:
        replacements[str(documents_dir)] = "/absolute/path/to/read-only/documents"
    if not replacements:
        raise ImportErrorClosed("no private member tokens derived")
    digest = sha256(
        json.dumps(replacements, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return RedactionMapResult(
        replacements=replacements,
        public_summary={"replacement_count": len(replacements), "sha256": digest},
    )
```

- [ ] **Step 4: Implement canonical inventory, privacy scan, apply, and verify**

The implementation must sort by POSIX relative path, use `lstat`, reject every symlink/non-regular file, re-sample source immediately before each copy, use exclusive destination creation, and hash canonical JSON:

```python
def _digest_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _digest_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


def _record(path: Path, relative_path: str) -> FileRecord:
    stat = path.lstat()
    if not path.is_file() or path.is_symlink():
        raise ImportErrorClosed(f"unsafe node: {relative_path}")
    return FileRecord(
        relative_path=relative_path,
        mode=stat.st_mode & 0o777,
        size=stat.st_size,
        sha256=_digest_file(path),
    )


def _canonical_fingerprint(records: Iterable[FileRecord]) -> str:
    payload = [asdict(record) for record in sorted(records, key=lambda item: item.relative_path)]
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return sha256(encoded).hexdigest()


def _is_allowed(relative: PurePosixPath) -> bool:
    if relative.as_posix() in FORBIDDEN_RELATIVE_PATHS:
        return False
    if relative.name in FORBIDDEN_NAMES or any(part in FORBIDDEN_PARTS for part in relative.parts):
        return False
    if relative.parts[:3] == ("src", "app", "data") and relative.suffix == ".json":
        return False
    return relative.as_posix() in ALLOWED_FILES or relative.parts[0] in ALLOWED_ROOTS


def _redact(raw: bytes, replacements: dict[str, str]) -> bytes:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ImportErrorClosed("private token found in non-UTF-8 file") from exc
    for token in sorted(replacements, key=len, reverse=True):
        replacement = replacements[token]
        if not token or not replacement:
            raise ImportErrorClosed("redaction map contains an empty token or replacement")
        text = text.replace(token, replacement)
    if any(token in text for token in replacements):
        raise ImportErrorClosed("private token remains after substitution")
    return text.encode("utf-8")


def apply_import(
    plan: ImportPlan,
    source: Path,
    target: Path,
    replacements: dict[str, str],
) -> ApplyResult:
    if target.exists():
        raise ImportErrorClosed("destination collision")
    target.mkdir(parents=True, exist_ok=False)
    copied: list[FileRecord] = []
    for expected in plan.files:
        source_file = source / expected.relative_path
        actual = _record(source_file, expected.relative_path)
        if actual != expected:
            raise ImportErrorClosed(f"source drift: {expected.relative_path}")
        destination = target / expected.relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        with source_file.open("rb") as reader, destination.open("xb") as writer:
            shutil.copyfileobj(reader, writer)
        destination.chmod(expected.mode)
        copied.append(_record(destination, expected.relative_path))
    if tuple(copied) != plan.files:
        raise ImportErrorClosed("target parity mismatch")
    sanitized: list[SanitizedRecord] = []
    for expected in plan.sanitized_files:
        source_file = source / expected.relative_path
        raw = source_file.read_bytes()
        if _digest_bytes(raw) != expected.source_sha256:
            raise ImportErrorClosed(f"source drift: {expected.relative_path}")
        transformed = _redact(raw, replacements)
        if _digest_bytes(transformed) != expected.target_sha256:
            raise ImportErrorClosed(f"sanitized target drift: {expected.relative_path}")
        destination = target / expected.relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as writer:
            writer.write(transformed)
        destination.chmod(expected.mode)
        sanitized.append(expected)
    return ApplyResult(tuple(copied), tuple(sanitized))
```

For allowlisted UTF-8 source files that contain a private token, `plan_import()` must move the path from `files` to `sanitized_files`. It requires an exact non-empty replacement for every matched token, applies replacements longest-token-first, verifies no source token remains, and records source/target hash plus `transform=private-token-substitution/v1`. Binary files, data files, or a text file with an unmapped token fail closed. The exact-copy group retains source/target record equality; the sanitized group is a separately declared derivative and never places raw private text in Git.

On any apply failure, move the incomplete target to a uniquely named sibling quarantine; never overwrite or delete it silently. Receipts contain only relative paths, modes, sizes, hashes, aggregate fingerprints, exclusion counts, transform IDs, and the hash of the external redaction map—not token or replacement values.

- [ ] **Step 5: Run importer tests and project Python regression**

```bash
cd projects/family-hub
uv run pytest tests/test_dashboard_import.py -q
uv run pytest tests -q
```

Expected: all importer and existing Python/FastMCP tests pass.

- [ ] **Step 6: Commit and tag the importer**

```bash
git add tools/dashboard_import.py tests/test_dashboard_import.py
git commit -m "feat(family-hub): add deterministic dashboard importer"
git tag -a t10-111-family-hub-importer -m "T10-111 deterministic dashboard importer"
```

### Task 3: Produce the source receipt and import the safe application surface

**Files:**
- Create: `projects/family-hub/apps/dashboard/**` from allowlisted source
- Create: `projects/family-hub/apps/dashboard/migration/source-receipt.json`
- Create: `projects/family-hub/apps/dashboard/migration/target-receipt.json`
- Modify: `projects/family-hub/.gitignore`

**Interfaces:**
- Consumes: `tools/dashboard_import.py`, exact Documents source, and an operator-owned redaction map outside Git.
- Produces: exact parity for the copied group, deterministic sanitized derivatives for private text source, and two immutable receipts without private token/replacement values.

- [ ] **Step 1: Re-measure the full source and freeze its pre-import fingerprint**

```bash
REDACTION_MAP_FILE="/Users/xiamingxing/agents/codex-documents-convergence/runtime/t10-111-redaction-map.json"
IMPORT_EVIDENCE_DIR="$(mktemp -d)"
SOURCE_RECEIPT="$IMPORT_EVIDENCE_DIR/source-receipt.json"
TARGET_RECEIPT="$IMPORT_EVIDENCE_DIR/target-receipt.json"
python3 tools/dashboard_import.py derive-redaction-map \
  --source /Users/xiamingxing/Documents/@家庭生活/family-dashboard-app \
  --output "$REDACTION_MAP_FILE" \
  --json
chmod 600 "$REDACTION_MAP_FILE"
test -s "$REDACTION_MAP_FILE"
python3 tools/dashboard_import.py plan \
  --source /Users/xiamingxing/Documents/@家庭生活/family-dashboard-app \
  --target "$PWD/apps/dashboard" \
  --redaction-map "$REDACTION_MAP_FILE" \
  --source-receipt "$SOURCE_RECEIPT" \
  --json
```

Expected: redaction-map creation reports only count/digest and never token/replacement values; source exists, destination absent, exact-copy and sanitized-derivative records are deterministic, every private token is mapped, forbidden findings are zero, and two consecutive plans have equal records and fingerprints. The 2026-08-31 discovery baseline contains private-text matches in reviewed TypeScript/config files; a changed path set is a circuit breaker requiring review before apply.

- [ ] **Step 2: Snapshot non-target source identity**

Run the importer inventory in full-tree no-copy mode and retain aggregate `full_source_count`, `full_source_bytes`, and `full_source_fingerprint` in the source receipt. Expected: the snapshot includes forbidden classes as non-target evidence without storing their content.

- [ ] **Step 3: Apply exactly once**

```bash
python3 tools/dashboard_import.py apply \
  --source /Users/xiamingxing/Documents/@家庭生活/family-dashboard-app \
  --target "$PWD/apps/dashboard" \
  --redaction-map "$REDACTION_MAP_FILE" \
  --source-receipt "$SOURCE_RECEIPT" \
  --target-receipt "$TARGET_RECEIPT" \
  --json
```

Expected: exact-copy source/target count, bytes, per-file records, and fingerprint are equal; every sanitized target matches its declared source hash, target hash, and transform; source full-tree fingerprint is unchanged; raw private tokens are absent from the target.

- [ ] **Step 4: Move the receipts into the target and harden ignores**

Add these child-root ignore rules:

```gitignore
apps/dashboard/node_modules/
apps/dashboard/.next/
apps/dashboard/out/
apps/dashboard/app-data/
apps/dashboard/.local-audit/
apps/dashboard/test-results/
apps/dashboard/e2e/.auth.json
apps/dashboard/*.tsbuildinfo
apps/dashboard/.env*
!apps/dashboard/.env.example
apps/dashboard/public/tailwind.css
```

Receipts must not contain the redaction-map path, private token/replacement values, file content, or current household JSON/YAML values.

- [ ] **Step 5: Verify forbidden paths and absolute host paths are absent from the staged tree**

```bash
git ls-files --others --exclude-standard apps/dashboard | sort
find apps/dashboard -type l -print
rg -n --hidden '/Users/|FAMILY_SSOT_ROOT=.*/Documents|BEGIN .*PRIVATE KEY|BARK_API_KEY=[^y]' apps/dashboard \
  -g '!migration/*.json'
```

Expected: no symlink; no forbidden absolute/secret/private-token match. Review every imported `*.json`, `*.yaml`, and `*.yml`; only package/config/synthetic files may remain. Verify all paths listed in `sanitized_files` are text source/config and every target hash matches the receipt.

- [ ] **Step 6: Commit the exact initial import before semantic adaptation**

```bash
git add .gitignore apps/dashboard
git commit -m "feat(family-hub): import canonical dashboard source"
git tag -a t10-111-family-dashboard-source-import -m "T10-111 source import receipts"
```

Expected: commit contains no generated/private class; exact-copy receipt records equal their targets and every sanitized derivative is explicitly hash-bound. No commit or tag contains the raw private version of a sanitized file.

### Task 4: Introduce explicit Documents and state path boundaries

**Files:**
- Create: `projects/family-hub/apps/dashboard/src/lib/paths.ts`
- Create: `projects/family-hub/apps/dashboard/tests/boundaries/paths.test.ts`
- Modify: `projects/family-hub/apps/dashboard/src/lib/ssot.ts`
- Modify: `projects/family-hub/apps/dashboard/src/lib/data-loader.ts`
- Modify: all imported call sites found by `rg 'process\.cwd\(\).*(app-data|data-manifest)|FAMILY_SSOT_ROOT|getSsotRoot|ssotPath'`.

**Interfaces:**
- Produces: `documentsRoot()`, `resolveDocumentsPath()`, `stateRoot()`, `statePath()`.
- Compatibility: `getSsotRoot()` and `ssotPath()` delegate to the explicit Documents resolver during Phase A.

- [ ] **Step 1: Write RED boundary tests**

```typescript
import { mkdtempSync, mkdirSync, symlinkSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterEach, describe, expect, test, vi } from "vitest";

import {
  documentsRoot,
  resolveDocumentsPath,
  statePath,
  stateRoot,
} from "@/lib/paths";

afterEach(() => vi.unstubAllEnvs());

test("requires both explicit roots", () => {
  vi.stubEnv("FAMILY_DOCUMENTS_ROOT", "");
  vi.stubEnv("FAMILY_DASHBOARD_STATE_ROOT", "");
  expect(() => documentsRoot()).toThrow("FAMILY_DOCUMENTS_ROOT is required");
  expect(() => stateRoot()).toThrow("FAMILY_DASHBOARD_STATE_ROOT is required");
});

test("keeps Documents and state disjoint", () => {
  vi.stubEnv("FAMILY_DOCUMENTS_ROOT", "/content/family");
  vi.stubEnv("FAMILY_DASHBOARD_STATE_ROOT", "/workspace/runtime/family-hub/dashboard");
  expect(documentsRoot()).toBe("/content/family");
  expect(statePath("tasks.json")).toBe("/workspace/runtime/family-hub/dashboard/tasks.json");
});

test("rejects traversal and symlink escape", () => {
  const root = mkdtempSync(path.join(os.tmpdir(), "family-documents-"));
  mkdirSync(path.join(root, "safe"));
  symlinkSync(os.tmpdir(), path.join(root, "safe", "escape"));
  vi.stubEnv("FAMILY_DOCUMENTS_ROOT", root);
  expect(resolveDocumentsPath("../outside.md")).toBeNull();
  expect(resolveDocumentsPath("/absolute.md")).toBeNull();
  expect(resolveDocumentsPath("safe/escape/secret.md")).toBeNull();
});
```

- [ ] **Step 2: Run the focused test and prove RED**

```bash
bun --cwd apps/dashboard test tests/boundaries/paths.test.ts
```

Expected: FAIL because `@/lib/paths` is absent.

- [ ] **Step 3: Implement the path adapter**

```typescript
import { existsSync, lstatSync, realpathSync } from "node:fs";
import path from "node:path";

function requireAbsoluteRoot(name: string): string {
  const raw = process.env[name]?.trim();
  if (!raw) throw new Error(`${name} is required`);
  if (!path.isAbsolute(raw)) throw new Error(`${name} must be absolute`);
  return path.resolve(raw);
}

export function documentsRoot(): string {
  return requireAbsoluteRoot("FAMILY_DOCUMENTS_ROOT");
}

export function stateRoot(): string {
  const root = requireAbsoluteRoot("FAMILY_DASHBOARD_STATE_ROOT");
  const documents = documentsRoot();
  if (root === documents || root.startsWith(`${documents}${path.sep}`)) {
    throw new Error("FAMILY_DASHBOARD_STATE_ROOT must be outside Documents");
  }
  return root;
}

function hasSymlinkComponent(root: string, candidate: string): boolean {
  const relative = path.relative(root, candidate);
  let cursor = root;
  for (const part of relative.split(path.sep).filter(Boolean)) {
    cursor = path.join(cursor, part);
    if (existsSync(cursor) && lstatSync(cursor).isSymbolicLink()) return true;
  }
  return false;
}

export function resolveDocumentsPath(relativePath: string): string | null {
  if (!relativePath || path.isAbsolute(relativePath) || relativePath.includes("\0")) return null;
  const root = documentsRoot();
  const candidate = path.resolve(root, relativePath);
  if (candidate === root || !candidate.startsWith(`${root}${path.sep}`)) return null;
  if (hasSymlinkComponent(root, candidate)) return null;
  return candidate;
}

export function statePath(...parts: string[]): string {
  const root = stateRoot();
  const candidate = path.resolve(root, ...parts);
  if (candidate !== root && !candidate.startsWith(`${root}${path.sep}`)) {
    throw new Error("state path escapes FAMILY_DASHBOARD_STATE_ROOT");
  }
  return candidate;
}
```

- [ ] **Step 4: Replace every direct `app-data` and manifest path**

Use `statePath("generated", fileName)` for generated JSON, `statePath("manifests", fileName)` for dashboard manifests, `statePath("cache", ...)` for AI/index cache, and `statePath("audit", ...)` for audit output. Do not retain a compatibility fallback to `process.cwd()`.

- [ ] **Step 5: Run focused and full unit tests**

```bash
bun --cwd apps/dashboard test tests/boundaries/paths.test.ts src/lib/ssot.test.ts src/lib/data-loader.test.ts
bun --cwd apps/dashboard test
```

Expected: explicit-root and existing unit tests pass; `rg` finds no direct `process.cwd()/app-data`, `process.cwd()/data-manifest`, or `FAMILY_SSOT_ROOT` usage.

- [ ] **Step 6: Commit and tag the path boundary**

```bash
git add apps/dashboard/src apps/dashboard/scripts apps/dashboard/tests
git commit -m "refactor(family-hub): isolate dashboard content and state roots"
git tag -a t10-111-dashboard-path-boundaries -m "T10-111 explicit dashboard roots"
```

### Task 5: Fail closed on Documents writes and relocate local writes to state

**Files:**
- Create: `projects/family-hub/apps/dashboard/src/lib/write-policy.ts`
- Create: `projects/family-hub/apps/dashboard/tests/boundaries/write-policy.test.ts`
- Modify: `src/app/api/file/save/route.ts`
- Modify: `src/app/api/cron/ssot-backup/route.ts`
- Modify: `src/lib/ssot-writer.ts`
- Modify: `src/lib/actions/milestones.ts`
- Modify: state-writing task, rebuild, AI cache, embedding, and audit routes/scripts discovered by the write scan.

**Interfaces:**
- Produces: `DocumentsWriteDisabledError`, `assertDocumentsWriteDisabled()`, `documentsWriteDisabledResponse()`.
- Consumes: `statePath()` for permitted generated/runtime writes.

- [ ] **Step 1: Write RED tests for every write class**

```typescript
import { expect, test } from "vitest";
import {
  DocumentsWriteDisabledError,
  assertDocumentsWriteDisabled,
  documentsWriteDisabledResponse,
} from "@/lib/write-policy";

test("Documents writes are always disabled in Phase A", async () => {
  expect(() => assertDocumentsWriteDisabled()).toThrow(DocumentsWriteDisabledError);
  const response = documentsWriteDisabledResponse();
  expect(response.status).toBe(403);
  await expect(response.json()).resolves.toEqual({
    code: "DOCUMENTS_WRITE_DISABLED",
    error: "Documents writes require OMO proposal and approval",
  });
});
```

Add route tests that call file save and backup POST handlers and assert `403` without touching temp Documents. Mock vaccine/milestone write functions and assert the typed error. For task/AI/generated-data routes, set a temp state root and assert all writes land under it.

- [ ] **Step 2: Run focused tests and prove RED**

```bash
bun --cwd apps/dashboard test tests/boundaries/write-policy.test.ts
```

Expected: FAIL because the policy module does not exist.

- [ ] **Step 3: Implement the closed write policy**

```typescript
import { NextResponse } from "next/server";

export class DocumentsWriteDisabledError extends Error {
  readonly code = "DOCUMENTS_WRITE_DISABLED";

  constructor() {
    super("Documents writes require OMO proposal and approval");
    this.name = "DocumentsWriteDisabledError";
  }
}

export function assertDocumentsWriteDisabled(): never {
  throw new DocumentsWriteDisabledError();
}

export function documentsWriteDisabledResponse(): NextResponse {
  return NextResponse.json(
    {
      code: "DOCUMENTS_WRITE_DISABLED",
      error: "Documents writes require OMO proposal and approval",
    },
    { status: 403 },
  );
}
```

Do not read an enabling environment variable. File-save/backup routes return the response before parsing payload or opening a file; domain writer functions throw before reading Documents.

- [ ] **Step 4: Route permitted writes to state**

Replace task JSON, generated milestones, embeddings, AI summaries, build metadata, and audit targets with `statePath(...)`. Ensure parent creation happens only below the state root and that tests use `mkdtemp` roots.

- [ ] **Step 5: Execute a write-surface audit**

```bash
rg -n 'writeFile|appendFile|mkdir|rename|rm\(|unlink|execFileSync|spawn' apps/dashboard/src apps/dashboard/scripts
```

Expected: every match is either guarded by `documentsWriteDisabledResponse/assertDocumentsWriteDisabled`, writes through `statePath`, writes a tracked build asset intentionally, or is test-only. Record the reviewed match list in the Phase A report later.

- [ ] **Step 6: Run write-policy and full unit tests**

```bash
bun --cwd apps/dashboard test tests/boundaries/write-policy.test.ts
bun --cwd apps/dashboard test
```

Expected: all tests pass; no Documents fixture mutation.

- [ ] **Step 7: Commit and tag write isolation**

```bash
git add apps/dashboard/src apps/dashboard/scripts apps/dashboard/tests
git commit -m "fix(family-hub): disable direct Documents writes"
git tag -a t10-111-dashboard-write-isolation -m "T10-111 fail-closed Documents writes"
```

### Task 6: Make unit tests, lint, and production build independent of live data

**Files:**
- Create: `apps/dashboard/tests/fixtures/documents/**`
- Create: `apps/dashboard/tests/fixtures/state/manifests/*.yaml`
- Create: `apps/dashboard/tests/fixtures/state/generated/*.json`
- Create: `apps/dashboard/scripts/run-next-build.ts`
- Modify: `apps/dashboard/package.json`
- Modify: `apps/dashboard/.env.example`
- Modify: `apps/dashboard/next.config.ts` and build scripts only as required by explicit roots.

**Interfaces:**
- Produces: deterministic synthetic fixture set and `bun run build` wrapper.
- Consumes: path adapter and state layout from Task 4.

- [ ] **Step 1: Add a minimal synthetic household fixture**

Use fictional identities and non-medical values only. Include one Markdown document per representative domain, manifests for summary/members/health/growth/daily/assets, and generated JSON for search/tasks/timeline/build metadata. No copied household values or source hashes belong in fixture content.

- [ ] **Step 2: Write a RED test proving the build wrapper supplies explicit roots**

Expose this function from `scripts/run-next-build.ts`:

```typescript
export function fixtureBuildEnv(projectRoot: string): Record<string, string> {
  return {
    ...process.env,
    FAMILY_DOCUMENTS_ROOT: path.join(projectRoot, "tests", "fixtures", "documents"),
    FAMILY_DASHBOARD_STATE_ROOT: path.join(projectRoot, "tests", "fixtures", "state"),
  } as Record<string, string>;
}
```

Test that both values are absolute, disjoint, below `tests/fixtures`, and contain no `/Users/` prefix.

- [ ] **Step 3: Implement the build wrapper**

```typescript
import path from "node:path";

export function fixtureBuildEnv(projectRoot: string): Record<string, string> {
  return {
    ...process.env,
    FAMILY_DOCUMENTS_ROOT: path.join(projectRoot, "tests", "fixtures", "documents"),
    FAMILY_DASHBOARD_STATE_ROOT: path.join(projectRoot, "tests", "fixtures", "state"),
  } as Record<string, string>;
}

if (import.meta.main) {
  const projectRoot = process.cwd();
  const css = Bun.spawnSync(["bun", "run", "scripts/build-css.mjs"], {
    cwd: projectRoot,
    env: fixtureBuildEnv(projectRoot),
    stdout: "inherit",
    stderr: "inherit",
  });
  if (css.exitCode !== 0) process.exit(css.exitCode);
  const next = Bun.spawnSync(["./node_modules/.bin/next", "build"], {
    cwd: projectRoot,
    env: fixtureBuildEnv(projectRoot),
    stdout: "inherit",
    stderr: "inherit",
  });
  process.exit(next.exitCode);
}
```

Set package scripts to `"build": "bun run scripts/run-next-build.ts"`. Keep `dev` explicit: it must fail with a clear message if roots are unset rather than select live/default data.

- [ ] **Step 4: Normalize `.env.example` without host paths or secrets**

```dotenv
NEXT_PUBLIC_APP_NAME=family-dashboard
FAMILY_DOCUMENTS_ROOT=/absolute/path/to/read-only/family-documents
FAMILY_DASHBOARD_STATE_ROOT=/absolute/path/to/workspace/runtime/family-hub/dashboard
FAMILY_DASHBOARD_PASSWORD=change_me
FAMILY_DASHBOARD_COOKIE_TTL_DAYS=7
FAMILY_AI_GATEWAY=http://127.0.0.1:4000
FAMILY_AI_REDACT_CONTEXT=true
FAMILY_CRON_TOKEN=change_me
BARK_API_KEY=change_me
```

- [ ] **Step 5: Install and run the package verification matrix**

```bash
bun --cwd apps/dashboard install --frozen-lockfile
bun --cwd apps/dashboard test
bun --cwd apps/dashboard run lint
bun --cwd apps/dashboard run build
git status --short
```

Expected: all commands exit 0; build creates only ignored products; no tracked file changes after build.

- [ ] **Step 6: Run privacy and forbidden-class scans**

```bash
find apps/dashboard -type l -print
git ls-files apps/dashboard | rg '(^|/)(node_modules|\.next|app-data|data-manifest|test-results|\.trae)(/|$)|\.env\.local$|e2e/\.auth\.json$|\.tsbuildinfo$'
rg -n --hidden '/Users/|FAMILY_SSOT_ROOT|process\.cwd\(\).*\.\.|BEGIN .*PRIVATE KEY' apps/dashboard
```

Expected: no symlink, forbidden tracked path, absolute host path, parent-root fallback, or private key marker.

- [ ] **Step 7: Commit and tag reproducible build support**

```bash
git add apps/dashboard
git commit -m "test(family-hub): build dashboard from synthetic fixtures"
git tag -a t10-111-dashboard-synthetic-build -m "T10-111 synthetic dashboard build"
```

### Task 7: Add representative E2E, child CI, and owner documentation

**Files:**
- Modify: `apps/dashboard/playwright.config.ts`
- Modify: `apps/dashboard/e2e/auth.setup.ts`
- Modify: `apps/dashboard/e2e/pages.spec.ts`
- Modify: `.github/workflows/ci.yml`
- Modify: `.gitignore`, `README.md`, `ARCHITECTURE.md`, `BOUNDARY.md`, `CALLCHAIN.md`, `CAPABILITY-MAP.md`

**Interfaces:**
- Produces: synthetic Playwright smoke and CI jobs for dashboard unit/lint/build plus existing surfaces.
- Consumes: synthetic roots and disabled-write code.

- [ ] **Step 1: Configure Playwright to use synthetic roots**

The web server environment must include absolute fixture Documents/state roots, `FAMILY_DASHBOARD_PASSWORD=family-test-password`, and `FAMILY_CSRF_TOKEN=family-test-csrf`. Use `reuseExistingServer: false` in CI to prevent accidental attachment to a live app.

- [ ] **Step 2: Expand the read-journey matrix**

Use one parameterized test for:

```typescript
const pages = [
  ["home", "/"],
  ["members", "/members"],
  ["health", "/health"],
  ["growth", "/growth"],
  ["assets", "/assets"],
  ["search", "/search"],
  ["tasks", "/tasks"],
  ["files", "/files"],
  ["graph", "/graph"],
] as const;

for (const [name, route] of pages) {
  test(`${name} renders from synthetic data`, async ({ page }) => {
    await page.goto(route);
    await expect(page.locator("body")).not.toContainText("Application error");
    await expect(page.locator("main")).toBeVisible();
  });
}
```

Add one request test asserting `/api/file/save` and `/api/cron/ssot-backup` return `403` with `DOCUMENTS_WRITE_DISABLED`.

- [ ] **Step 3: Run E2E and prove GREEN**

```bash
bun --cwd apps/dashboard run test:e2e
```

Expected: authentication setup, nine representative pages, and disabled-write API assertions pass.

- [ ] **Step 4: Add child CI without weakening existing jobs**

Keep existing root `lint` and `build` jobs. Add a `dashboard` job that runs:

```yaml
- uses: oven-sh/setup-bun@v2
- run: bun install --frozen-lockfile
  working-directory: apps/dashboard
- run: bun test
  working-directory: apps/dashboard
- run: bun run lint
  working-directory: apps/dashboard
- run: bun run build
  working-directory: apps/dashboard
```

Add Playwright browser installation and `bun run test:e2e` in a separate `dashboard-e2e` job so unit/build failure remains distinguishable from browser failure. Do not add `continue-on-error`.

- [ ] **Step 5: Document the new owner boundary**

Update family-hub docs to state:

- `apps/dashboard` is the canonical Git-owned Next source;
- Vite quest UI, Express API, and FastMCP remain current independent owner surfaces;
- Documents is explicit read-only input;
- generated state belongs to Workspace runtime;
- direct Documents writes, Cockpit cutover, deployment, runtime parity, and old-app retirement are not active in Phase A.

Do not hard-code ports, test counts, or mutable health values.

- [ ] **Step 6: Run the complete child regression**

```bash
uv run pytest tests -q
bun run lint
bun run build
bun --cwd apps/dashboard test
bun --cwd apps/dashboard run lint
bun --cwd apps/dashboard run build
bun --cwd apps/dashboard run test:e2e
git diff --check
git status --short
```

Expected: all exit 0; only intended tracked changes remain.

- [ ] **Step 7: Commit and tag CI/docs/E2E**

Split lanes if the child lane gate requires it:

```bash
git add apps/dashboard/e2e apps/dashboard/playwright.config.ts .github/workflows/ci.yml
git commit -m "test(family-hub): verify dashboard owner journeys"
git tag -a t10-111-dashboard-e2e -m "T10-111 dashboard E2E"
git add README.md ARCHITECTURE.md BOUNDARY.md CALLCHAIN.md CAPABILITY-MAP.md
git commit -m "docs(family-hub): document dashboard owner boundary"
git tag -a t10-111-dashboard-owner-docs -m "T10-111 dashboard owner docs"
```

### Task 8: Merge the family-hub child PR and replay child main

**Files:**
- No new source files; this task establishes authoritative child evidence.

**Interfaces:**
- Consumes: clean child branch and full local verification.
- Produces: merged child PR, child merge SHA, required-check receipt, and child-main replay.

- [ ] **Step 1: Re-read child main and check duplicate delivery**

```bash
git fetch origin main
git log origin/main --oneline -8
git diff --stat origin/main...HEAD
git diff --name-status origin/main...HEAD
```

Expected: no concurrent equivalent import on main; diff contains only the planned family-hub surfaces and no unexplained deletion.

- [ ] **Step 2: Push the child branch and its T10-111 tags**

```bash
git push -u origin agent/codex-documents-convergence--t10-111-family-dashboard-phase-a
git push origin refs/tags/t10-111-family-hub-importer refs/tags/t10-111-family-dashboard-source-import refs/tags/t10-111-dashboard-path-boundaries refs/tags/t10-111-dashboard-write-isolation refs/tags/t10-111-dashboard-synthetic-build refs/tags/t10-111-dashboard-e2e refs/tags/t10-111-dashboard-owner-docs
```

Expected: branch and exact tags accepted; no broad `--tags` push.

- [ ] **Step 3: Create the child PR**

Title: `feat(family-hub): absorb canonical family dashboard source`

PR body must separate: imported source ownership, explicit path/write boundaries, synthetic build/E2E, forbidden/private classes absent, existing family-hub regression, and unproven Phase B/C/value.

- [ ] **Step 4: Wait for every required child check and merge**

```bash
CHILD_PR="$(gh pr list --state open --head agent/codex-documents-convergence--t10-111-family-dashboard-phase-a --json number --jq '.[0].number')"
test -n "$CHILD_PR"
gh pr checks "$CHILD_PR" --watch --interval 10
gh pr view "$CHILD_PR" --json mergeable,mergeStateStatus,statusCheckRollup
gh pr merge "$CHILD_PR" --squash
```

Expected: all required checks success/skipped-by-design; merge state clean; PR state becomes `MERGED`.

- [ ] **Step 5: Replay from authoritative child main**

Use a fresh child checkout at the merge SHA:

```bash
uv run pytest tests -q
bun run build
bun --cwd apps/dashboard install --frozen-lockfile
bun --cwd apps/dashboard test
bun --cwd apps/dashboard run lint
bun --cwd apps/dashboard run build
bun --cwd apps/dashboard run test:e2e
python3 tools/dashboard_import.py verify \
  --source /Users/xiamingxing/Documents/@家庭生活/family-dashboard-app \
  --target "$PWD/apps/dashboard" \
  --source-receipt apps/dashboard/migration/source-receipt.json \
  --target-receipt apps/dashboard/migration/target-receipt.json \
  --allow-adapted-target --json
```

Expected: tests/build/E2E pass. Verification proves source still equals its receipt and the initial import commit/receipt is reachable, while later Git adaptations are expected and separately auditable.

### Task 9: Advance the root gitlink and publish Phase A evidence

**Files:**
- Modify: `projects/family-hub` gitlink
- Create: `docs/reports/2026-08-31-family-dashboard-owner-migration-phase-a.md`
- Create: `.omo/_knowledge/retros/BET-Y1Q3-T10-111.md`
- Modify: `docs/plans/3y-bet-ledger.yaml`

**Interfaces:**
- Consumes: child merge SHA, CI checks, child-main replay, import receipts, unchanged source proof.
- Produces: merged root pointer/evidence PR and Phase A completion matrix only.

- [ ] **Step 1: Verify the gitlink candidate is exactly child origin/main**

```bash
git -C projects/family-hub fetch origin main
CHILD_MAIN_SHA="$(git -C projects/family-hub rev-parse origin/main)"
CHILD_PR="$(gh pr list --repo starlink-awaken/omostation-family-hub --state merged --head agent/codex-documents-convergence--t10-111-family-dashboard-phase-a --json number --jq '.[0].number')"
CHILD_MERGE_SHA="$(gh pr view "$CHILD_PR" --repo starlink-awaken/omostation-family-hub --json mergeCommit --jq '.mergeCommit.oid')"
test "$CHILD_MAIN_SHA" = "$CHILD_MERGE_SHA"
git -C projects/family-hub merge-base --is-ancestor "$CHILD_MAIN_SHA" origin/main
```

Expected: exact equality and ancestry; do not copy a SHA from abbreviated logs.

- [ ] **Step 2: Advance only the family-hub submodule checkout and stage the gitlink**

```bash
git -C projects/family-hub checkout --detach "$CHILD_MAIN_SHA"
git add projects/family-hub
git diff --cached --submodule=log -- projects/family-hub
```

Expected: one forward gitlink change from the previous root pointer to child main.

- [ ] **Step 3: Write the evidence report**

The report must include:

- source/full and selected inventory counts, bytes, fingerprints, and receipt digests;
- explicit forbidden/private class scan results;
- path/write boundary test commands and results;
- dashboard unit/lint/build/E2E and existing family-hub regression results;
- child PR URL, merge SHA, required checks, and replay checkout SHA;
- root PR placeholder until merged;
- source unchanged, Documents/host/consumers untouched, migration family pending;
- engineering status `VERIFIED`, operational status `NOT_PROVEN`, value status `NOT_PROVEN` before root merge.

- [ ] **Step 4: Write the retrospective**

Record at least these lessons: source bytes were mostly reproducible caches; private household manifests cannot enter public Git; source ownership must precede runtime relocation; implicit parent roots are migration hazards; child merge and root gitlink are separate authority proofs.

- [ ] **Step 5: Add Phase A completion evidence only after child proof**

Update T10-111 with an engineering candidate matrix referencing the child main SHA and report/spec digests. Keep operational/value `NOT_PROVEN`, family pending, and BET not yet `done` until root merge/mainline replay and workflow closeout.

- [ ] **Step 6: Split root commits by lane and tag them**

```bash
git add projects/family-hub
git commit --only projects/family-hub -m "chore(submodule): advance family-hub dashboard owner"
git tag -a t10-111-family-hub-root-pointer -m "T10-111 family-hub root pointer"
git add docs/reports/2026-08-31-family-dashboard-owner-migration-phase-a.md .omo/_knowledge/retros/BET-Y1Q3-T10-111.md
git commit -m "docs(family-hub): record Phase A owner migration evidence"
git tag -a t10-111-family-dashboard-phase-a-evidence -m "T10-111 Phase A evidence"
git add docs/plans/3y-bet-ledger.yaml
git commit --only docs/plans/3y-bet-ledger.yaml -m "chore(plan): close T10-111 Phase A engineering delivery"
git tag -a t10-111-family-dashboard-phase-a-ledger -m "T10-111 Phase A ledger"
```

- [ ] **Step 7: Run root verification before push**

```bash
git diff --check origin/main...HEAD
git ls-tree HEAD projects/family-hub
git -C projects/family-hub rev-parse HEAD
uv run --with pyyaml python bin/gac/documents-content-plane-migration-check.py --json
uv run --with pyyaml python bin/plan/bet-ledger.py show BET-Y1Q3-T10-111
uv run --with pyyaml python bin/agent-workflow.py verify "$RUN_ID" --from-diff --execute
make gac-local-gate
```

Expected: gitlink equality; migration family still pending; T10-111 spec/digests valid; workflow verify and GaC pass except only explicitly proven inherited baseline findings.

### Task 10: Merge the root PR, replay main, and close Phase A

**Files:**
- Modify only if merge SHA placeholders must be replaced in a separate closeout PR: report, retro, and ledger.

**Interfaces:**
- Consumes: root branch, required checks, child main SHA.
- Produces: root-main adoption, final evidence digests, closed workflow, and Phase B admission readiness.

- [ ] **Step 1: Re-read root main before push and reject stale/redundant work**

```bash
git fetch origin main
git log origin/main --oneline -8
git diff --name-status origin/main...HEAD
git ls-tree origin/main projects/family-hub
```

Expected: no equivalent concurrent root gitlink/evidence merge and no unrelated deletion.

- [ ] **Step 2: Push exact root branch/tags and create the root PR**

Push only the delivery branch and T10-111 root tags. PR body must state child merge SHA, gitlink equality, focused/full test evidence, unchanged Documents/consumer state, and Phase B/C/value not proven.

- [ ] **Step 3: Wait for all required root checks and merge**

```bash
ROOT_PR="$(gh pr list --state open --head agent/codex-documents-convergence--t10-111-family-dashboard-implementation-20260831-01 --json number --jq '.[0].number')"
test -n "$ROOT_PR"
gh pr checks "$ROOT_PR" --watch --interval 10
gh pr view "$ROOT_PR" --json mergeable,mergeStateStatus,statusCheckRollup
gh pr merge "$ROOT_PR" --squash
```

Expected: required checks green and root PR `MERGED`; capture the root merge SHA.

- [ ] **Step 4: Replay from a fresh root-main clone**

```bash
git ls-tree origin/main projects/family-hub
git -C projects/family-hub fetch origin main
git -C projects/family-hub rev-parse HEAD
git -C projects/family-hub rev-parse origin/main
uv run --with pyyaml python bin/gac/documents-content-plane-migration-check.py --json
uv run --with pyyaml python bin/plan/bet-ledger.py show BET-Y1Q3-T10-111
make gac-local-gate
```

Then replay the child dashboard unit/lint/build/E2E matrix from the exact root gitlink checkout.

- [ ] **Step 5: Publish a closeout PR if final root merge evidence changes tracked receipts**

Update report/retro/ledger with root merge SHA and fresh digests in a new claimed delivery attempt. Merge that closeout PR and replay its merge SHA. Do not rewrite the accepted specification digest.

- [ ] **Step 6: Close the workflow only after vision-to-retro and mainline proof**

```bash
uv run --with pyyaml python bin/agent-workflow.py closeout "$RUN_ID"
uv run --with pyyaml python bin/agent-workflow.py status --json
uv run --with pyyaml python bin/plan/bet-ledger.py status
```

Expected: run closes `ok`; T10-111 is done only for Phase A engineering ownership; no overdue retro; operational/value remain `NOT_PROVEN`.

- [ ] **Step 7: Derive the next admitted work without overclaim**

Open a separate Phase B design/BET for Workspace runtime-state relocation and governed writes. Phase C remains dependent on Phase B real-data parity, unique Cockpit contract, observation window, and recoverable old-app retirement.

## Final acceptance matrix

| Requirement | Authoritative evidence | Required verdict |
|---|---|---|
| Canonical child source exists | child main tree at `apps/dashboard` | VERIFIED |
| Forbidden/private classes absent | importer receipts + Git tracked-path/private scans | VERIFIED |
| Source unchanged | fresh source full-tree fingerprint vs receipt | VERIFIED |
| Explicit Documents/state roots | boundary tests + source scan | VERIFIED |
| Direct Documents writes disabled | route/domain tests + write audit | VERIFIED |
| Dashboard reproducible without live data | clean child unit/lint/build/E2E | VERIFIED |
| Existing family-hub unaffected | clean child Vite/Python/FastMCP regression | VERIFIED |
| Child authority | merged child PR + child-main replay | VERIFIED |
| Root authority | merged root gitlink PR + root-main replay | VERIFIED |
| Live runtime relocation | Phase B evidence | NOT_PROVEN |
| Cockpit/consumer cutover | Phase C evidence | NOT_PROVEN |
| Old Documents app retirement | Phase C recoverable transaction | NOT_PROVEN |
| Principal-bound user value | real user adjudication | NOT_PROVEN |

## Execution choice

The plan supports either fresh-agent-per-task execution with two-stage review or inline batch execution with checkpoints. Because the current tool surface does not expose a subagent dispatcher, inline execution through `superpowers:executing-plans` is the immediately executable path unless the user selects a separate orchestrated worker environment.
