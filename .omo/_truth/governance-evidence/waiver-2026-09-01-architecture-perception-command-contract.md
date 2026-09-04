---
schema_version: governance-waiver-evidence/v1
owner: human-principal
lifecycle: history
created: 2026-09-01
last_updated: 2026-09-01
value_indicator_policy: false
title: Architecture perception managed command contract bootstrap waiver
type: doc
---

# Architecture Perception Managed Command Contract Bootstrap Waiver

## Principal response

```text
批准 architecture-perception command contract bootstrap 第7节原文。
```

The response approves Section 7 of
`/Users/xiamingxing/Documents/学习进化/基建架构/2026-09-01-architecture-perception-command-contract-bootstrap-proposal.md`
in full. The approved document SHA-256 is
`e97662e37e0cfe561fa67fc8f8cde0c26316f1fe39aaa8af86730d639f84243b`.

## Human authorization — approved Section 7, verbatim

> 本次 architecture-perception SKILL command contract 自举修复跳过 workflow start，允许使用 `AGCP_REQUIREMENT_ITERATION_GATE=0`；初始观察 root main 为 `1436639a4d3acc4076108f66486f0f0a18c6ac3f`，现状命令 `python3 bin/ssot/scene-card-lifecycle.py --validate --all` 在 provenance/readiness-ready clone 中因裸 `python3` 解析到 Xcode Python 3.9 而 `ImportError: cannot import name 'UTC'`，在 managed Python 中又因 current CLI 不接受 flag-first `--validate --all` 而 exit 2；`external-adapter-sync` 虽拥有 `.agents/skills/**`，但 global requirement gate要求已有 BET且当前 34 个 candidate无一覆盖 `.agents/skills/architecture-perception/SKILL.md`，故仅限一次三文件自举：`.agents/skills/architecture-perception/SKILL.md` 只将该行替换为 `uv run --with pyyaml python "bin/ssot/scene-card-lifecycle.py" validate --all`，新增 `tests/test_architecture_perception_skill_command.py` 先以旧 skill产生预期 RED、再锁定 managed command/current CLI help并 GREEN，以及 `.omo/_truth/governance-evidence/waiver-2026-09-01-architecture-perception-command-contract.md` 记录本句、fixed refs、RED/GREEN/manual execution、scope、rollback和 `value_indicator_policy=false`；不得修改其他 skill内容、scene card、`bin/ssot/scene-card-lifecycle.py`、workflow registry/policy/profile、BET/ledger、架构标准、规则预算、generated面、gitlink、runtime、用户配置、completion/value evidence或任何其他文件，不得新增 wrapper/script/dependency/dispatcher/truth plane。若执行时 root main已前进，仅在上述三路径未被并发修改、现状错误仍可精确复现、没有 open PR占用实现路径时允许 rebase到该 successor；任何 scope/RED/测试/GaC/required check/post-merge异常即停止或按新PR回滚。交付必须是一个三文件commit、annotated tag、唯一PR和exact-SHA post-merge验证，结果不绑定个人价值、不标记任何 BET done。

## Execution identity

- Workflow run: none; the principal explicitly authorized skipping workflow start for this exact self-bootstrap.
- Requirement gate override: `AGCP_REQUIREMENT_ITERATION_GATE=0`, limited to the exact three authorized paths and delivery commit.
- Agent profile: `blueprint-governance-skill-maintenance`.
- Delivery attempt: `architecture-perception-command-20260901-01`.
- Branch: `agent/blueprint-governance-skill-maintenance--architecture-perception-command-20260901-01`.
- Initial observed root main: `1436639a4d3acc4076108f66486f0f0a18c6ac3f`.
- First admitted successor: `377e561259cd8bdf62c5c39ff6523969f9fcb38d`.
- Final delivery base: `2f4eb7a5d8b909cfda8999da87092d4c88f967bf`.
- Both successor admissions proved all three authorized paths unchanged from
  the initial observation, the stale command present exactly once, the managed
  replacement absent, and no open PR occupying either implementation path.
  The task-owned three-path stash used for the final fast-forward was restored
  and dropped; no stash ref or hidden work remained.
- Skill blob before / after the one-line edit:
  `941e08956315b4e880c5590f4640316674fe32f9` /
  `602777eb94190a446871c90b41a60293ae49efce`.
- Focused test blob before commit:
  `e7851215abdeab4b855deb73830d2dd94c7a6d58`.

## Exact scope

This self-bootstrap changes exactly:

1. `.agents/skills/architecture-perception/SKILL.md`: replace the single stale
   naked-Python, flag-first command with the repository-managed current CLI
   command;
2. `tests/test_architecture_perception_skill_command.py`: lock the exact skill
   text and execute the real `validate --help` parser contract;
3. this waiver evidence.

No scene card, validator implementation, workflow policy/profile/registry,
BET/ledger, architecture standard, budget, generated surface, gitlink, runtime,
user configuration, completion evidence, value evidence, wrapper, script,
dependency, dispatcher, or truth plane is changed.

## RED, GREEN, and manual execution evidence

- RED command:
  `PYTHONDONTWRITEBYTECODE=1 uv run --with pyyaml pytest tests/test_architecture_perception_skill_command.py -q`
- RED result: `1 failed, 1 passed`. The only failure was
  `test_skill_uses_managed_current_scene_validation_command`, because the
  expected command count was zero. The real current CLI help test passed.
- Skill semantic diff: exactly one deletion and one addition
  (`git diff --numstat` reported `1 1` for the skill).
- GREEN command: the same focused pytest command.
- GREEN result: `2 passed in 0.25s`.
- Manual command:
  `uv run --with pyyaml python "bin/ssot/scene-card-lifecycle.py" validate --all`
- Manual result: expected exit `1`; semantic validation reached
  `[FAIL] admin-classify: tier=unknown` and the existing scene findings.
  Neither `ImportError` nor `unrecognized arguments` occurred.
- Temporary manual-execution stdout/stderr files were deleted and their absence
  was re-proved; no runtime state was retained.
- Focused test, all 32 Agent skill validations, and agent-workflow lint passed.
- The first file-scoped GaC invocation correctly rejected the three files as
  mixed `other`, `code`, and `governance_state` lanes. Section 7 explicitly
  authorizes one commit containing these exact three files. The registered
  `change-lane-check.py --allow-lane` contract accepted only those three lanes;
  the unchanged full file-scoped GaC was then rerun with the equivalent
  process-local `AGENT_WORKFLOW_ALLOWED_LANES=other,code,governance_state`.
  This was an assertion of the principal-approved commit shape, not
  `--advisory`, and did not modify workflow policy, profile, gate code, or
  repository state.
- File-scoped GaC result: `ok=true`, 56 checks, zero hard failures, and
  `change-lane-check` passed. Current-main soft warnings remained visible:
  `governance-semantic-gate` reported pre-existing ADR coverage
  (`duplicate_numbers=2`, `frontmatter_issues=2`,
  `files_not_in_index=2`) plus one unknown governance-evolution package;
  `command-discovery` reported the existing “其他” group at 47 commands.
  None of those unrelated surfaces is changed or represented as repaired.
- `git diff --check` passed.

## Independent review

- Orca Run / Task / Dispatch:
  `run_9f849953cd02` /
  `task_a2c1faa6a0f4` /
  `ctx_5853405e5823`.
- Review mode: strict read-only; the reviewer made no file, Git, GitHub,
  workflow, lock, or runtime mutation.
- Review outcome: `PASS`. It independently rechecked the exact three paths,
  one-line skill diff, managed command text, real `validate --help` parser
  contract, verbatim Section 7 authorization, scope boundaries, three explicit
  lanes without advisory semantics, and focused pytest (`2 passed`).
- Reviewer residual risk: historical RED, manual execution, and GaC evidence is
  retained as bounded waiver narrative rather than raw logs. The base/current
  blobs and current gate semantics were independently found internally
  consistent with that narrative.
- The settled worker terminal was released with an inspectable archive and its
  delivery `delivery_066ee6844b23` was acknowledged.

## Rollback and residual debt

Before merge, any scope, focused-test, GaC, required-check, or independent-review
failure closes the unique PR without widening this change. After merge, a failure
caused by these three files requires a separate revert PR. A rollback must not
repair scene cards, validator code, workflow policy, BET truth, or rule budgets.

The semantic scene findings remain visible, pre-existing debt. This command
contract bootstrap neither accepts nor repairs them. It is value-exempt,
`value_indicator_policy=false`, does not prove principal-bound value, and does
not mark any BET done.
