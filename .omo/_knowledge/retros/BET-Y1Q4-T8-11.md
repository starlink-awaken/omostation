---
schema_version: retrospective/v1
type: retro
title: BET-Y1Q4-T8-11 Closeout Retro — Orthogonal domains + dual-track router
bet_id: BET-Y1Q4-T8-11
status: archived
lifecycle: contract
owner: governance-team
created: 2026-09-04
last-reviewed: 2026-09-05
---

# BET-Y1Q4-T8-11 Closeout Retro

> **TL;DR**: PSC v1 已交付 `ORTHOGONAL_DOMAINS` 8 域树 + 双轨透明预处理路由器；本轮仅做台账 closeout（`candidate`→`done` + `delivery_accepted`），不 bump cockpit gitlink。

## Deliverables
- Cockpit child: PSC v1 `#130` (`16a9d65`) — `_subcommands.py` + `test_command_hierarchy.py`
- Root mainline pointer carrying PSC: `#3099` / later tips (current cockpit ptr includes delivery)
- Closeout: design binding + retro archive + ledger completion matrix

## Q1
Appetite 2 days；实现已在 PSC v1 同日落地。本轮 closeout 约 1h（binding 补齐 + evidence 入账）。

## Q2
- 8 大正交领域树在 help 中清晰展现：PASS（hierarchy tests）
- 双轨无感知路由器透明拦截并映射旧命令：PASS（`cockpit <cmd>` ↔ `cockpit <domain> <cmd>`）
- 单测全部通过：PASS（`test_command_hierarchy.py` 4 passed）

## Q3
1. BET 长期停在 `candidate` 且仅有 `done_at` note，缺 `accepted_specifications` → `start --bet` 被 SPEC_BINDING 拦截；closeout 须先补 canonical Spec。
2. `write_surfaces` initially 只有 cockpit 路径，关账改 ledger/retro 前必须扩写面，否则 claim 被 scope 拒绝。
3. PASW：交付已在 submodule main 可达时，根仓 closeout 不必再 bump cockpit pointer。

## Q4
Closeout 净增：+1 Spec、retro 归档、ledger done matrix。GaC/脚本配额 0；不改 cockpit 运行时代码。

## Q5
同类 PSC 批量 BET（T8-12..）关账前先检查 binding + write_surfaces 是否覆盖 ledger/retro；两段 commit：先用 main tip 占位 `merged_reachable_commit`，再用 delivery commit 自绑定。
