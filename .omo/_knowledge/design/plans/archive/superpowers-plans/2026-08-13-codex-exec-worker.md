---
status: active
lifecycle: plan
owner: governance-team
last-reviewed: 2026-08-13
last_updated: 2026-09-03
title: Codex Exec Unattended Worker Implementation Plan
type: doc
---

# Codex Exec Unattended Worker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Codex 通过 Orca 受监督运行时不再等待人工点击，同时保留独立 clone、workspace-write 沙箱、超时回收、OMO admission 和独立验证。

**Architecture:** 根仓 bounded adapter 在一次性 execution clone 中固定调用 `codex exec --approve-for-me --ephemeral --ignore-user-config --json`，再把通过 OMO 写面审计的 binary patch 应用回真实独立 clone。Orca 只追踪 Run/Task/Dispatch，OMO 继续拥有任务与完成真相；adapter 只输出最终消息和脱敏回执。

**Tech Stack:** Python 3.9+ 标准库、pytest、PyYAML、Codex CLI 0.147+、Orca CLI。

## Global Constraints

- 禁止 `--dangerously-bypass-approvals-and-sandbox`、shell command string 和 arbitrary extra argv。
- 只在 `.git/agent-clone-identity.json` 证明的独立 clone 中执行。
- 真实完成必须有 adapter receipt、Orca Dispatch settlement 和独立 reviewer；任何单一信号不足以完成。
- 不修改 Orca、本地 Codex 配置、模型路由、Workflow Mesh 状态机或 Ledger DDL。

---

### Task 1: Bounded adapter TDD

**Files:**
- Create: `bin/gac/codex-worker-adapter.py`
- Create: `tests/unit/gac/test_codex_worker_adapter.py`

**Interfaces:**
- Produces CLI: `codex-worker-adapter.py run [--execute] --workspace-root PATH --prompt TEXT [--expect-exact TEXT] [--receipt PATH] [--timeout-seconds N]`
- Produces receipt schema: `codex-worker-execution/v1`

- [x] **Step 1: Write failing tests**

Cover exact argv, no shell, stripped secret env, dry-run default, real clone identity validation,
linked/symlink/shared root rejection, version validation, JSONL final-message projection, timeout
TERM/KILL/wait, nonzero/empty/malformed output, exact marker, exclusive temp receipt and receipt
redaction. Also cover execution-clone isolation, allowlisted patch apply, out-of-scope/commit/ignored
write rejection and preservation of pre-existing clone changes.

- [x] **Step 2: Prove RED**

Run:

```bash
uv run --no-project --with pytest --with pyyaml python -m pytest tests/unit/gac/test_codex_worker_adapter.py -q
```

Expected: collection fails because `bin/gac/codex-worker-adapter.py` does not exist.

- [x] **Step 3: Implement the minimum adapter**

Use `subprocess.Popen(argv, shell=False, start_new_session=True, text=True)`; parse JSONL from
captured stdout; select the last assistant message from `item.completed`/message events; emit only
that message. Compute receipt digest with canonical JSON. On timeout call `os.killpg(pid,
SIGTERM)`, wait, then `SIGKILL`, wait. Never include raw prompt/stdout/stderr/env/user identity.

- [x] **Step 4: Prove GREEN**

```bash
uv run --no-project --with pytest --with pyyaml python -m pytest tests/unit/gac/test_codex_worker_adapter.py -q
uv run --with ruff ruff check bin/gac/codex-worker-adapter.py tests/unit/gac/test_codex_worker_adapter.py
git diff --check
```

Expected: all commands exit 0.

### Task 2: Registry admission and collaboration contract

**Files:**
- Modify: `.omo/_truth/registry/workers.yaml`
- Modify: `.omo/standards/agent-cli-worker-collaboration.md`

**Interfaces:**
- Consumes adapter CLI from Task 1.
- Produces admitted worker `codex` with explicit capability and task-declared write scope.

- [x] **Step 1: Add registry contract test**

Extend adapter tests to load the real registry and assert `codex` is admitted only with the exact
bounded adapter command; other candidate workers stay disabled/declared.

- [x] **Step 2: Run the new test RED**

Expected: current `codex` declaration is disabled/declared and has no transport.

- [x] **Step 3: Promote only Codex**

Set `enabled: true`, `admission_state: admitted`, add exact adapter transport,
`require_explicit_capabilities: true`, L1 and `task_declared_only`; keep forbidden domains. Add a
Codex profile section explaining that `--approve-for-me` is automatic review, not bypass.

- [x] **Step 4: Run focused registry and OMO admission regressions**

```bash
uv run --with pytest --with pyyaml python -m pytest tests/unit/gac/test_codex_worker_adapter.py tests/unit/gac/test_agent_pool_observe.py -q
cd projects/omo && uv run python -m pytest tests/test_omo_worker_admission_gate.py tests/test_omo_worker_core.py -q
```

Expected: all commands exit 0.

### Task 3: Real Orca-supervised smoke and closeout

**Files:**
- Modify: `docs/plans/3y-bet-ledger.yaml`
- Create: `.omo/_knowledge/retros/BET-Y1Q2-T1-17.md`

**Interfaces:**
- Consumes adapter and admitted registry.
- Produces privacy-safe receipt digest and Orca Run/Task/Dispatch evidence.

- [x] **Step 1: Run real adapter smoke**

Run from this independent clone with a receipt path under `/private/tmp`. Prompt must forbid tools
and writes and require exactly `CODEX_UNATTENDED_SMOKE_OK:BET-Y1Q2-T1-17`. Verify exit 0, marker,
receipt schema/digest, zero manual approval, and no unexpected repository delta.

- [x] **Step 2: Run supervised Orca task**

Create an Orca Run and Task, attach one terminal, track one Dispatch, execute the bounded adapter,
then send exactly one explicit `worker_done`. Query task/dispatch state; release the worker after
the completion Delivery is acknowledged.

- [x] **Step 3: Independent verification**

Reviewer directly measures argv, registry admission, test output, receipt, current clone diff and
Orca task/dispatch. Any false-ready, missing cleanup, raw output leak or non-independent workspace
is BLOCK.

- [ ] **Step 4: Close and persist**

Update ledger to done only after all gates pass, write the five-question retro, run bet/workflow
verify, commit, tag, push, open/merge PR, then remove the Orca setup and independent clone.
