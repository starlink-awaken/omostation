---
schema_version: retrospective/v1
type: retro
title: BET-Y1Q4-T8-13 Closeout Retro — P0 core command dry-run/JSON contract
bet_id: BET-Y1Q4-T8-13
status: archived
lifecycle: contract
owner: governance-team
created: 2026-09-05
last-reviewed: 2026-09-05
---

# BET-Y1Q4-T8-13 Closeout Retro

> **TL;DR**: PSC v1 已落地 9 个 P0 命令的 `--dry-run`/`--json`；本轮以 Spec + `tests/test_core_commands.py` 锁死契约，零命令改写。Child PR `#134` → root pointer bump → ledger `delivery_accepted`。

## Deliverables
- Cockpit child: `#134` (`agent/bet-y1q4-t8-13-cockpit`) — `tests/test_core_commands.py`（13 cases）
- Spec: `docs/superpowers/specs/2026-09-05-t8-13-p0-core-commands-contract-design.md`
- Closeout receipt: `docs/reports/2026-09-05-t8-13-p0-core-commands-closeout.md`
- Pointer: `projects/cockpit` → `42c429fb4792cdce172fab10b4f5ec2c508a627e`

## Q1
Appetite 3 days；本轮以最小增量关账（Spec binding + 统一契约测试 + pointer），约数小时。

## Q2
- 9 大命令均支持 `-o json` 与 `--dry-run`：PASS（`JSON_CAPABLE` + 契约矩阵）
- 格式一致性校验全部通过：PASS（ANSI-free `json.loads(stdout)`）
- 单测覆盖率达标：PASS — `pytest .../test_core_commands.py` → **13 passed**
- Verify 命令 exit 0：PASS

## Q3
1. `accepted_specifications` 缺失会在 `start --bet` 被 SPEC_BINDING 拦截 — 必须先写 Spec 再 start。
2. claim 需要 `affected-graph` 含 `workspace-root`；仅 `cockpit` 不够。
3. PASW：代码改在 `.subtrees/cockpit`，verify 路径仍是 `projects/cockpit` — 本地需 copy 或 bump 后再跑门禁命令。
4. PSC 已交付实现；本 BET 缺口是 **统一 verify 面**（`test_core_commands.py`），勿重写已绿命令。

## Q4
净增：契约测试、Spec/retro/report、ledger binding；命令文件零改动。modernized 分测可并存。

## Q5
后续可逐步让 9 命令改用 `cockpit.output.json_print`；telemetry/结构化日志交给 T8-14。关账两段：delivery（含 pointer）→ done+completion_evidence（squash 后如需 rebind `merged_reachable_commit`）。
