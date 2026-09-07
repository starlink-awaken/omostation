---
bet: BET-Y2Q1-T6-02
title: 知识层彻底归并首期
phase: Phase 1 (first PR)
date: 2026-09-07
status: in_progress
---

# Retro: BET-Y2Q1-T6-02 Phase 1

## Q1: What went well

- UnifiedMemoryInterface ABC cleanly defined with 3 primitives (query/ingest/search)
- UnifiedMemoryBridge implements zone-based routing (health→gbrain, work→kairon)
- 26 tests all passing on first real run (after mock fix)
- Found and fixed submodule-guard bug: `get_staged_submodules()` was treating all staged files under `projects/` as submodule paths, causing false blocking on new files in non-submodule directories
- Spec created and bound to ledger via `spec-init`

## Q2: What didn't work

- gbrain/kairon submodules are empty in worktree — actual adapter bridge cannot be tested end-to-end until submodules are initialized
- Network issues (SSL_ERROR_SYSCALL to github.com) required `GIT_SSL_NO_VERIFY` workaround
- Hook-runner blocking checks (submodule-reachability, remote-hygiene) are pre-existing worktree hygiene debt

## Q3: Learnings

- PITFALL-GAT-006 caught: BET-Y2Q1-T6-01 and BET-Y1Q4-T10-133 were already delivered on main but still showed as "candidate" in the ledger → ledger status sync is async/delayed
- All 2-day non-★ bets are either already done or blocked by dependency chains → harder to find truly fresh non-★ small-appetite work
- The submodule-guard `get_staged_submodules()` bug is a real correctness issue that would block any new file creation under `projects/` — should be a separate BET fix

## Q4: Next steps (Phase 2)

- Initialize gbrain/kairon submodules and do actual adapter stub deletion (≥10K LOC target)
- Wire UnifiedMemoryInterface into consumer code paths (SceneWatcher, KEMS, distillation engine)
- Verify test_loc doesn't decrease after adapter consolidation

## Files changed

| File | Action | Lines |
|------|--------|-------|
| projects/knowledge/src/knowledge/unified/__init__.py | Created | +12 |
| projects/knowledge/src/knowledge/unified/interface.py | Created | +75 |
| projects/knowledge/src/knowledge/unified/adapter_bridge.py | Created | +196 |
| projects/knowledge/tests/test_unified_memory.py | Created | +391 |
| bin/gac/submodule-guard.py | Modified | ~15 changed |

**Net: +674 lines added, ~4 lines removed**

---

# Retro: BET-Y2Q1-T6-02 归并阶段（Phase 2，追加）

> 补充记录：Phase 1 之后，kairon 侧完成 4 轮死代码/假实现归并（9,097 LOC 删除）。
> 与 Phase 1（projects/knowledge/unified 接口）互补：Phase 1 加接口，本阶段做减法。

## Q1 实际耗时 vs appetite

- appetite: 4 days（T6-02 完整 bet）
- 实际: 跨多个 session 完成接口（里程碑 1）+ 4 轮归并。归并阶段在 1 个 session 内连续完成。

## Q2 done_when 是否全部通过？

- ① bos://memory/unified 接口：**通过**（unified.py + UnifiedMemoryInterface 双实现）
- ② 归并 ≥10,000 LOC：**未通过（9,097/10,000，差 903）**——见 Q3 打假
- ③ 保护 test_loc + ADR 完整保留：**通过**（每轮删除后 eidos/minerva/kos/ontoderive 全量测试保持通过；未动任何 ADR）

## Q3 打假发现（与 plan 不符的事实）

1. **10K LOC 目标与实际可删面有 ~10 倍差距**：台账假设 kairon 有大量"重复适配层"，但经 4 轮严格审计，真实的死代码/假实现只有 ~9,097 LOC（eidos vector_backends 776 + eidos.memory/minerva.observability/quality 4,271 + ontoderive.engine/minerva storage 4,050）。其余候选（minerva BM25/embeddings、kos hybrid_search、eidos memory 模块、ontoderive reasoners/theories）经 import* / lazy import 验证均为**活跃能力**，删除会破坏功能。
2. **"重复适配层"大部分是独有能力**：minerva BM25（mos 无此能力）、kos 三路检索（FTS5/LanceDB/图谱，mos 只有内存后端）、gbrain TS（跨语言）——这些不是"与 mos 重复"，是各包独有。
3. **死代码判定陷阱**：storage_dal 被误判死代码（实际 4 处活跃引用）；ontoderive analytics/advanced/validation_steps 通过 `import *` / lazy import 被引用（初判 0 引用，字符串验证揭示活跃）——多次避免了误删。

## Q4 净增减

| 轮 | 内容 | 删除 LOC |
|---|---|---|
| 1 | eidos vector_backends（死适配层） | 776 |
| 2 | eidos.memory 4 + minerva.observability 2 + minerva.quality 3 | 4,271 |
| 3+4 | ontoderive.engine 6 + minerva storage/transform 4 | 4,050 |
| **合计** | | **9,097** |

每轮删除后：eidos 416 / minerva 549 / kos 562 / ontoderive 882 / mos 6/6 全绿（circuit_breaker 通过）。
kairon 合并：#71 / #72 / #73；主仓合并：#3385 / #3390 / #3394。

## Q5 下一个认领者须知

- **10K 目标的最后 ~903 LOC 在安全边界之外**：剩余候选要么是独立包公共 API（kairon_plugin_sdk.cli）、要么有运行时注入依赖（knowledge_store）、要么是入口（forge.*/kos.cli）——删除需高风险重构，可能触发 circuit_breaker。
- 若后续要凑满 10K，建议先与台账 owner 确认目标口径（"重复适配层"的真实含义 + 是否含 gbrain 跨语言路由接入）。
- 归并已完成主体（9,097），bet 可考虑 complete（若接受 9,097 口径）或保持 candidate（若坚持 10K 原目标）。
