# OMO Validation Solidification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create one canonical Workspace `.omo` verification entrypoint and make local commands, CI, and operator documentation all delegate to the same validation chain.

**Architecture:** Add a dedicated runner script that owns the authoritative `.omo` verification pipeline (`sync -> validate -> test`). Repoint the root `Makefile`, GitHub workflow, and `.omo/AGENT.md` to that runner, then add a regression test that guards against future drift between those surfaces.

**Tech Stack:** Bash, Python, pytest, GitHub Actions YAML, Makefile, Markdown

---

## File map

- Create: `/Users/xiamingxing/Workspace/scripts/verify_omo.sh`
- Create: `/Users/xiamingxing/Workspace/.omo/tests/test_omo_verification_contract.py`
- Modify: `/Users/xiamingxing/Workspace/Makefile`
- Modify: `/Users/xiamingxing/Workspace/.github/workflows/governance-check.yml`
- Modify: `/Users/xiamingxing/Workspace/.omo/AGENT.md`

---

### Task 1: Lock the canonical verification contract with a failing test

**Files:**
- Create: `/Users/xiamingxing/Workspace/.omo/tests/test_omo_verification_contract.py`

- [ ] **Step 1: Write the failing test**

Create `/Users/xiamingxing/Workspace/.omo/tests/test_omo_verification_contract.py` with this content:

```python
from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def test_canonical_runner_exists_and_keeps_stage_order() -> None:
    script = _read("scripts/verify_omo.sh")

    sync_cmd = "python3 scripts/sync_omo_state.py --omo-dir .omo"
    validate_cmd = "python3 scripts/omo_worker.py task validate --all-active"
    test_cmd = "python3 -m pytest .omo/tests -q"

    assert "#!/usr/bin/env bash" in script
    assert "set -euo pipefail" in script
    assert sync_cmd in script
    assert validate_cmd in script
    assert test_cmd in script
    assert script.index(sync_cmd) < script.index(validate_cmd) < script.index(test_cmd)


def test_makefile_delegates_to_canonical_runner() -> None:
    makefile = _read("Makefile")

    assert ".PHONY: help kairon-test kairon-build kairon-lint governance-check governance-sync governance-validate governance-index-check governance-verify" in makefile
    assert "governance-verify:" in makefile
    assert "\tbash scripts/verify_omo.sh" in makefile
    assert "governance-check: governance-verify governance-index-check" in makefile


def test_governance_workflow_uses_canonical_runner() -> None:
    workflow = _read(".github/workflows/governance-check.yml")

    assert "- name: Canonical .omo verification" in workflow
    assert "run: bash scripts/verify_omo.sh" in workflow


def test_omo_agent_documents_canonical_verification_command() -> None:
    agent = _read(".omo/AGENT.md")

    assert "canonical `.omo` verification command" in agent
    assert "`bash scripts/verify_omo.sh`" in agent
    assert "`make governance-verify`" in agent
    assert "partial checks only" in agent
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_verification_contract.py -q
```

Expected: FAIL because `scripts/verify_omo.sh` does not exist yet and the current `Makefile` / workflow / `.omo/AGENT.md` do not all reference one canonical runner.

- [ ] **Step 3: Keep the failing baseline in place**

Do not edit production files yet. Leave the new test as the proof of the missing contract.

- [ ] **Step 4: Run test again to confirm the failure is stable**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_verification_contract.py -q
```

Expected: FAIL for the same missing canonical-runner reasons, not because of syntax or import errors.

- [ ] **Step 5: Commit**

```bash
cd /Users/xiamingxing/Workspace && git add .omo/tests/test_omo_verification_contract.py && git -c core.hooksPath=/dev/null commit -m $'test(omo): add verification contract coverage\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

---

### Task 2: Add the canonical `.omo` verification runner

**Files:**
- Create: `/Users/xiamingxing/Workspace/scripts/verify_omo.sh`
- Test: `/Users/xiamingxing/Workspace/.omo/tests/test_omo_verification_contract.py`

- [ ] **Step 1: Write the minimal runner**

Create `/Users/xiamingxing/Workspace/scripts/verify_omo.sh` with this content:

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[1/3] Syncing .omo state"
python3 scripts/sync_omo_state.py --omo-dir .omo

echo "[2/3] Validating active tasks"
python3 scripts/omo_worker.py task validate --all-active

echo "[3/3] Running .omo regression tests"
python3 -m pytest .omo/tests -q
```

- [ ] **Step 2: Make the runner executable**

Run:

```bash
cd /Users/xiamingxing/Workspace && chmod +x scripts/verify_omo.sh
```

Expected: `scripts/verify_omo.sh` is executable.

- [ ] **Step 3: Run the contract test**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_verification_contract.py::test_canonical_runner_exists_and_keeps_stage_order -q
```

Expected: PASS. The remaining tests in `test_omo_verification_contract.py` should still fail because `Makefile`, workflow, and docs have not been updated yet.

- [ ] **Step 4: Run the runner itself**

Run:

```bash
cd /Users/xiamingxing/Workspace && bash scripts/verify_omo.sh
```

Expected: the three stages run in order; use the current repo baseline as the source of truth for pass/fail while the rest of the integration work is still incomplete.

- [ ] **Step 5: Commit**

```bash
cd /Users/xiamingxing/Workspace && git add scripts/verify_omo.sh .omo/tests/test_omo_verification_contract.py && git -c core.hooksPath=/dev/null commit -m $'feat(omo): add canonical verification runner\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

---

### Task 3: Repoint local entrypoints, CI, and operator guidance to the canonical runner

**Files:**
- Modify: `/Users/xiamingxing/Workspace/Makefile`
- Modify: `/Users/xiamingxing/Workspace/.github/workflows/governance-check.yml`
- Modify: `/Users/xiamingxing/Workspace/.omo/AGENT.md`
- Test: `/Users/xiamingxing/Workspace/.omo/tests/test_omo_verification_contract.py`

- [ ] **Step 1: Update the root Makefile**

Change `/Users/xiamingxing/Workspace/Makefile` to this shape:

```make
.PHONY: help kairon-test kairon-build kairon-lint governance-check governance-sync governance-validate governance-index-check governance-verify

help:
	@echo "Workspace 根 Makefile — 委派到 projects/"
	@echo ""
	@echo "make kairon-test    运行 kairon 全部测试"
	@echo "make kairon-lint    ruff 检查所有包"
	@echo "make kairon-build   安装 kairon 依赖 (uv sync)"
	@echo "make governance-verify  运行 canonical .omo 验证链 (sync → validate → test)"
	@echo "make governance-check   全量治理检查 (canonical verify → index)"
	@echo "make governance-sync    同步 .omo/state/system.yaml"
	@echo "make governance-validate 验证任务 Schema"
	@echo "make governance-index-check 检查 INDEX.md 覆盖率"
	@echo "make help           显示本消息"

kairon-test:
	cd projects/kairon && make test

kairon-lint:
	cd projects/kairon && ruff check packages/

kairon-build:
	cd projects/kairon && uv sync

governance-verify:
	bash scripts/verify_omo.sh

governance-check: governance-verify governance-index-check
	@echo "Governance checks complete."

governance-sync:
	python3 scripts/sync_omo_state.py --omo-dir .omo

governance-validate:
	python3 scripts/omo_task_schema.py --all-active

governance-index-check:
	python3 scripts/check-index-coverage.py
```

- [ ] **Step 2: Update the GitHub workflow**

In `/Users/xiamingxing/Workspace/.github/workflows/governance-check.yml`, replace the three separate canonical-gate steps:

- `State-Goals Alignment Check`
- `Validate active tasks`
- `Run .omo test suite`

with one visible canonical step plus explicit extra checks:

```yaml
      - name: Canonical .omo verification
        run: bash scripts/verify_omo.sh
```

Keep `INDEX.md Coverage Check`, `System consistency check`, and any other non-canonical policy steps as separate layers after the canonical step.

- [ ] **Step 3: Update `.omo/AGENT.md`**

Add a short operator-facing subsection under the consistency / execution guidance with this wording:

```markdown
### Canonical `.omo` verification command

Use this command when you need proof that the Workspace `.omo` governance surface is green:

- `bash scripts/verify_omo.sh`

Equivalent local wrapper:

- `make governance-verify`

This canonical chain covers:

1. `python3 scripts/sync_omo_state.py --omo-dir .omo`
2. `python3 scripts/omo_worker.py task validate --all-active`
3. `python3 -m pytest .omo/tests -q`

The following are partial checks only and must not be mistaken for full `.omo` verification:

- `make governance-sync`
- `make governance-validate`
- `make governance-index-check`
```

- [ ] **Step 4: Run the contract test to verify all four surfaces align**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_verification_contract.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/xiamingxing/Workspace && git add Makefile .github/workflows/governance-check.yml .omo/AGENT.md .omo/tests/test_omo_verification_contract.py && git -c core.hooksPath=/dev/null commit -m $'feat(omo): align verification entrypoints\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

---

### Task 4: Verify the solidified path end-to-end

**Files:**
- Verify only: `/Users/xiamingxing/Workspace/scripts/verify_omo.sh`
- Verify only: `/Users/xiamingxing/Workspace/Makefile`
- Verify only: `/Users/xiamingxing/Workspace/.github/workflows/governance-check.yml`
- Verify only: `/Users/xiamingxing/Workspace/.omo/AGENT.md`
- Verify only: `/Users/xiamingxing/Workspace/.omo/tests/test_omo_verification_contract.py`

- [ ] **Step 1: Run the canonical runner directly**

Run:

```bash
cd /Users/xiamingxing/Workspace && bash scripts/verify_omo.sh
```

Expected: PASS with the sync, validate, and `.omo` test stages printed in order.

- [ ] **Step 2: Run the Make wrapper**

Run:

```bash
cd /Users/xiamingxing/Workspace && make governance-verify
```

Expected: PASS and delegate to `bash scripts/verify_omo.sh`.

- [ ] **Step 3: Run the regression test guarding drift**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_verification_contract.py -q
```

Expected: PASS.

- [ ] **Step 4: Run the full `.omo` suite again**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/xiamingxing/Workspace && git add scripts/verify_omo.sh Makefile .github/workflows/governance-check.yml .omo/AGENT.md .omo/tests/test_omo_verification_contract.py && git -c core.hooksPath=/dev/null commit -m $'test(omo): verify solidified validation flow\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```
