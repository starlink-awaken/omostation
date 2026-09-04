---
lifecycle: entry
owner: auto-fix-loop
last_updated: 2026-08-29
type: ssot
last_updated: 2026-09-03
---
# Product P0 WP1 Honest Scene Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `make scene-card-check` exit nonzero whenever any card is blocked, while preserving deterministic counts, the all-ready/no-card success cases, and value=`NOT_PROVEN`.

**Architecture:** Keep the existing Python per-card validator authoritative and change only the Make aggregate. Add injectable root/glob variables solely to execute the real Make entrypoint against isolated test fixtures; do not alter Scene Card content or lifecycle rules.

**Tech Stack:** GNU Make, Python 3.13, pytest, `bin/ssot/scene-card-lifecycle.py`, Agent Workflow, GitHub Actions.

## Global Constraints

- BET: `BET-Y1Q3-T4-03`; WorkPacket: `WP-BET-Y1Q3-T4-03`.
- Accepted Spec: `docs/superpowers/specs/2026-08-28-product-p0-wp1-honest-scene-gate-design.md`.
- Root-only implementation: `Makefile` and `tests/test_scene_card_lifecycle_check.py`.
- Do not modify `docs/scene-cards/**`, journeys, approval evidence, runtime state, or blockers.
- A real mainline blocker canary is required for operational=`PROVEN`; value remains `NOT_PROVEN`.
- Final state is `delivery_accepted`, never `outcome_accepted`.

---

### Task 1: Amend the WP1 Operational Acceptance Text

**Files:**
- Modify: `docs/superpowers/specs/2026-08-28-product-p0-wp1-honest-scene-gate-design.md`
- Modify: `docs/plans/3y-bet-ledger.yaml`

**Interfaces:**
- Consumes: merged parent `delivery_accepted` semantics.
- Produces: a child Spec stating engineering=`VERIFIED`, real blocker canary operational=`PROVEN`, value=`NOT_PROVEN`.

- [ ] **Step 1: Start a WP1 Spec-amendment workflow and claim both files**

Use `BET-Y1Q3-T4-03`, generate an affected receipt for `workspace-root`, and claim the exact Spec and ledger paths before editing.

- [ ] **Step 2: Replace the contradictory acceptance sentence**

Use this exact requirement:

```text
该 BET 的 engineering 轴由测试、diff 和 merged mainline 推进 VERIFIED；
真实仓库 blocker canary 通过后 operational 推进 PROVEN；
value 始终保持 NOT_PROVEN，overall 只能推导 delivery_accepted。
```

- [ ] **Step 3: Recalculate and bind the Spec digest**

```bash
shasum -a 256 docs/superpowers/specs/2026-08-28-product-p0-wp1-honest-scene-gate-design.md
PYTHONDONTWRITEBYTECODE=1 uv run --with pyyaml python -c \
  "from pathlib import Path; import importlib.util,sys; p=Path('bin/plan/bet-ledger.py'); s=importlib.util.spec_from_file_location('bl',p); m=importlib.util.module_from_spec(s); sys.modules[s.name]=m; s.loader.exec_module(m); m.prepare_bet_execution('BET-Y1Q3-T4-03',workspace=Path.cwd(),require_startable=False); print('WP1 binding PASS')"
```

Expected: binding compiles after updating only T4-03's `content_digest`.

- [ ] **Step 4: Commit, merge, and restart from the merged binding**

Commit docs and docs-data in separate lane commits, merge the amendment PR after required checks, close the pre-amendment run as blocked/superseded, and start a fresh WP1 implementation run from main.

---

### Task 2: Add RED Tests at the Real Make Entry Point

**Files:**
- Modify: `tests/test_scene_card_lifecycle_check.py`

**Interfaces:**
- Consumes: the existing `_write_scene_card` helper and Python lifecycle validator.
- Produces: subprocess-level coverage of `make scene-card-check` for mixed, all-ready, and empty fixtures.

- [ ] **Step 1: Add fixture helpers**

```python
import os
import subprocess


def _write_external_trial(root: Path) -> None:
    trial = root / ".omo" / "_knowledge" / "workflow-mesh" / "external-scene-trials.jsonl"
    trial.parent.mkdir(parents=True, exist_ok=True)
    trial.write_text("{}\n", encoding="utf-8")


def _run_scene_card_check(root: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run(
        [
            "make",
            "--no-print-directory",
            f"SCENE_CARD_GLOB={root / 'docs/scene-cards/*.yaml'}",
            f"SCENE_CARD_ROOT={root}",
            "scene-card-check",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
```

- [ ] **Step 2: Add the three aggregate tests**

```python
def test_make_aggregate_mixed_cards_exits_nonzero(tmp_path: Path) -> None:
    cards = tmp_path / "docs" / "scene-cards"
    _write_scene_card(cards / "ready.yaml")
    _write_scene_card(
        cards / "blocked.yaml",
        scene_id="blocked-scene",
        activation_blockers=["human approval missing"],
    )
    _write_external_trial(tmp_path)

    result = _run_scene_card_check(tmp_path)

    assert "scene-cards: ready=1 with-blockers=1" in result.stdout
    assert result.returncode != 0


def test_make_aggregate_all_ready_exits_zero(tmp_path: Path) -> None:
    cards = tmp_path / "docs" / "scene-cards"
    _write_scene_card(cards / "one.yaml")
    _write_scene_card(cards / "two.yaml", scene_id="test-scene-two")
    _write_external_trial(tmp_path)

    result = _run_scene_card_check(tmp_path)

    assert "scene-cards: ready=2 with-blockers=0" in result.stdout
    assert result.returncode == 0


def test_make_aggregate_no_cards_exits_zero(tmp_path: Path) -> None:
    (tmp_path / "docs" / "scene-cards").mkdir(parents=True)
    result = _run_scene_card_check(tmp_path)
    assert "scene-cards: ready=0 with-blockers=0" in result.stdout
    assert result.returncode == 0
```

- [ ] **Step 3: Run RED**

```bash
uv run --with pyyaml --with pytest python -m pytest \
  tests/test_scene_card_lifecycle_check.py -k 'make_aggregate' -q
```

Expected: mixed fixture fails because the target ignores fixture variables and exits through the final help `echo`; all-ready fixture does not use the isolated root correctly.

---

### Task 3: Implement the Minimal Aggregate Fix

**Files:**
- Modify: `Makefile`

**Interfaces:**
- Consumes: `SCENE_CARD_GLOB` and `SCENE_CARD_ROOT` with production-safe defaults.
- Produces: unchanged human output and an authoritative final `test "$blocked" -eq 0`.

- [ ] **Step 1: Add defaults and replace the recipe**

```make
SCENE_CARD_GLOB ?= docs/scene-cards/*.yaml
SCENE_CARD_ROOT ?= .

scene-card-check:  ## 场景卡就绪度报告 — blockers 为阻断门
	@ready=0; blocked=0; for f in $(SCENE_CARD_GLOB); do \
		[ -e "$$f" ] || continue; \
		if python3 bin/ssot/scene-card-lifecycle.py \
			--root "$(SCENE_CARD_ROOT)" check --scene-card "$$f" \
			>/dev/null 2>&1; then \
			ready=$$((ready+1)); else blocked=$$((blocked+1)); fi; \
	done; \
	echo "scene-cards: ready=$$ready with-blockers=$$blocked"; \
	echo "单卡详情: python3 bin/ssot/scene-card-lifecycle.py check --scene-card PATH"; \
	test "$$blocked" -eq 0
```

- [ ] **Step 2: Run GREEN**

```bash
uv run --with pyyaml --with pytest python -m pytest tests/test_scene_card_lifecycle_check.py -q
```

Expected: all tests PASS.

- [ ] **Step 3: Run the real blocker canary**

```bash
bash -c 'if PYTHONDONTWRITEBYTECODE=1 make scene-card-check; then
  echo unexpected-green
  exit 1
else
  echo honest-block
fi'
```

Expected: output contains the real `ready=N with-blockers=M` count and `honest-block`; wrapper exits 0 because it proved the inner command failed honestly.

- [ ] **Step 4: Commit the root implementation**

```bash
git add Makefile tests/test_scene_card_lifecycle_check.py
git commit -m "fix(scene): fail aggregate gate on blockers"
```

---

### Task 4: Review, Merge, and Close WP1

**Files:**
- Review: `Makefile`
- Review: `tests/test_scene_card_lifecycle_check.py`
- Coordinator-only completion: `docs/plans/3y-bet-ledger.yaml`
- Coordinator-only retro: `.omo/_knowledge/retros/BET-Y1Q3-T4-03.md`

**Interfaces:**
- Consumes: Task 3 commit and real blocker canary.
- Produces: merged root main, engineering=`VERIFIED`, operational=`PROVEN`, value=`NOT_PROVEN`, overall=`delivery_accepted`.

- [ ] **Step 1: Run independent review and exact-scope checks**

```bash
git diff --name-only origin/main...HEAD
git diff --check origin/main...HEAD
uv run --with pyyaml --with pytest python -m pytest tests/test_scene_card_lifecycle_check.py -q
```

Expected: implementation diff is only Make/test; no Scene Card bytes change.

- [ ] **Step 2: Push and create the unique root PR**

```bash
git push -u origin HEAD
gh pr create --base main --head "$(git branch --show-current)" \
  --title "fix(scene): fail aggregate gate on blockers" \
  --body "Implements BET-Y1Q3-T4-03; value remains NOT_PROVEN."
P0_WP1_PR="$(gh pr view --json number --jq .number)"
gh pr checks "$P0_WP1_PR" --watch --interval 10
```

Expected: required checks pass; no merge while checks are pending or failed.

- [ ] **Step 3: Merge and re-run the canary from main**

```bash
gh pr merge "$P0_WP1_PR" --squash --delete-branch
git fetch --no-recurse-submodules origin main
git show origin/main:Makefile | rg 'test "\$\$blocked" -eq 0'
```

- [ ] **Step 4: Serialize completion evidence and retire the clone**

The coordinator writes tests/diff/rollback/main receipt, real canary/fresh receipt/replay/cleanup, `done_at`, and retro in a separate governed commit. Expected: T4-03 becomes `done` through `delivery_accepted`; value has no evidence and remains `NOT_PROVEN`; owned locks, branch, and clone are retired.

---

## Self-Review

- Spec coverage: mixed/all-ready/empty semantics, real canary, exact scope, rollback, completion axes, and cleanup are explicit.
- Placeholder scan: every runtime ID/PR is resolved by an exact command; no prose placeholder remains.
- Type consistency: subprocess helper returns `CompletedProcess[str]`; Make variables have production-safe defaults.
