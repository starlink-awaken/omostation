---
schema: md/v1
status: completed
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-27
type: report
bet_id: BET-Y2Q4-T10-209
title: BET-Y2Q4-T10-209 交付运行态 worktree 归集 — closeout receipt
created: '2026-09-27'
run_id: 20260927T125149Z-project-code-change-8dfb04f4
---

# BET-Y2Q4-T10-209 closeout receipt — 交付运行态 worktree 归集（canonical 锚 + symlink 桥 + release rescue）

> 本文件是 ledger `completion_evidence` 指向的 receipt。done_when 复测在**合并后的 main**
> （`65611d5ba`，worktree `agent/governance-agent/run-anchor-close`，2026-09-27T19:58Z）上重跑，
> 非复述交付期数字。契约：`docs/superpowers/specs/2026-09-27-delivery-state-worktree-anchor-design.md`
> （`spec_version 1.0.0`，digest `sha256:5204a90d…`）。复盘：`.omo/_knowledge/retros/BET-Y2Q4-T10-209.md`。
> 交付 PR **#4468**（squash 合并 2026-09-27T19:40:59Z，merge commit `65611d5ba`，21 files +1048/−50）。

## 1 · 交付链终验（交付波）

| 检查 | 结果 |
|------|------|
| PR CI（#4468） | 全绿；唯一非 pass = 4 个 policy-skipping（披露项，符合预期） |
| `make gac-local-gate`（commit 后） | **PASS — 68 checks ALL GREEN** @ `f8502e179` |
| gate 树等价 | `git rev-parse 65611d5ba^{tree}` == `f8502e179^{tree}` == `997cd166…` ⇒ 该 gate 结果对合并树成立 |
| 根测试套件 | **1783 passed / 3 failed / 1 error**；3 failed = main 既有基线（`test_codex_worker_adapter` / `test_panorama_agent_brief` / `test_repo_root_profile`），1 error = `test_phase8_unified_ecosystem` root venv 缺 `rich`（main 既有） |
| 内核全量（projects/omo @ pin `53a4b4c`，合并未动 pin） | **2862 passed** |
| `bet-ledger.py lint` | **OK — 495 bets, 16 tracks, no errors** |

## 2 · done_when 逐条复测（合并后 main，命令 + 实测）

1. **内核 anchor 落位 + 生产分支接线** — `ls -la projects/omo/src/omo/workflow/delivery_anchor.py` 存在（6951 B）；
   `grep -n ensure_delivery_anchor projects/omo/src/omo/workflow/core.py` → `:16`（relative import）、
   `:41`（绝对 import fallback）、`:457`（`_runner_path` 相对分支生产调用）。**PASS**
2. **自愈 symlink 桥** — 本 worktree 为合并后新 claim，`ls -la .omo/_delivery` 实测
   `agent-workflows -> /Users/xiamingxing/Workspace/.omo/_delivery/agent-workflows`（lrwx，创建于 claim 时段自愈），
   `readlink` 指 canonical；run yaml `Path.resolve()` 落 canonical
   （`.omo/_delivery/agent-workflows/runs/20260927T125149Z-…yaml`）。内核 placement/migration 测试见 §3。**PASS**
3. **release/merge/TTL 三处 merge-rescue** — `grep -n "merge-rescue" bin/gac/gac-worktree.sh` →
   helper `:207` + 调用点 `:807`（release）、`:899`（merge）、`:1282`（TTL）；`bash -n` OK；
   同会话早前对 `ws-run-anchor` 的真实 `release` 以 RC=0 跑通（/tmp/ws-anchor-release.log，worktree/分支/claim 三查全净）。**PASS**
4. **契约文档** — `bin/lib/repo_root.py:18` docstring 第四条判据（worktree remove 只 unlink 不跟随）；
   ADR-0456 addendum `:283-300` 含 symlink 桥、第二道防线、**禁止 `rm -rf <link>/` 尾斜杠**禁令。**PASS**
5. **测试** — `uv run pytest tests/unit/test_delivery_anchor_contract.py -q` → **10 passed**；
   `projects/omo` `pytest tests/test_delivery_anchor.py tests/test_workflow_workspace_isolation.py -q` → **20 passed**；
   既有全量（根 1783 / 内核 2862）见 §1，同一树同一 pin。**PASS**

## 3 · 运行态证据（operational）

- **live_canary**：合并后新 worktree 的 claim 全链（start → claim ×3 → 状态写读）全程经 canonical run 记录完成；
  未再出现 #4435 类 worktree-local run 落盘。
- **fresh_receipt**：本文件；**replay**：retro `BET-Y2Q4-T10-209.md`；**cleanup**：第一波 worktree
  `ws-run-anchor` 已 release（PASW 子树同清），三查 `git worktree list` / `git branch --list` / claim 文件全空。

## 4 · 本波状态修复（披露，均运行态不进 git）

1. **`work_packet_hash` 陈旧修复**：重编号（208→209）改了 run 的 `work_packet` 内容但未重算 declared hash，
   claim 报 `WORK_PACKET_HASH_MISMATCH`。实测 packet 内容与 `prepare_bet_execution` 重投影**逐字节一致**
   （measured == rebuilt == `6b0f3d9e…`），仅 declared 过期 → 重算回写。
2. **`write_surfaces` +2**：closeout 产物（receipt / retro）入面，与 T10-207 先例一致；
   packet 随 ledger 重投影同步（`826f7bfd…`）。两处均为 `.omo/_delivery/*`（gitignored）运行态。

## 5 · 回滚

- 交付整体：squash revert `65611d5ba` 一步还原 21 文件（内核/桥/兜底/契约/测试）。
- 本波收尾：第二 PR（receipt + retro + 台账）独立 revert。
- 运行态（run yaml / packet / claim 锁）不随 git 回滚，按 `.omo/_delivery` 生命周期治理。
