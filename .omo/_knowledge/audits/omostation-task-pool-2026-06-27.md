---
status: active
lifecycle: tracking
owner: laowang
last-reviewed: 2026-06-27
---

# omostation 任务池 (2026-06-27)

> GaC 达生产级稳态后, 4 个 omostation 任务持续跟踪推进. 来源: memory 锚点.

## 任务清单

| # | 任务 | 域 | 优先级 | 状态 | 来源 memory |
|---|------|-----|:------:|:----:|------------|
| **1** | c2g 自治盲区 (brainstorm→draft→bet 路径) | c2g | P0 | 🟡 推进中 | product-walkthrough-focus |
| **2** | omo 5 任务 (P0 鸿沟/反馈 + P1 GodModule/并发锁/产品门户) | omo | P0-P1 | ⬜ 待推进 | systematic-issues-tasks |
| **3** | mypy 清理 (minerva 175 / eidos 217 / ontoderive 470) | kairon | P1 | ⬜ 待推进 | kairon-mypy-cleanup-progress |
| **4** | BOS 鸿沟 (102 URI 声明/执行, 60 假阳性) | agora | P1 | ⬜ 待推进 | bos-decl-exec-gap |

## 任务详情

### 1. c2g 自治盲区 (P0, draft→bet 已通验证, 剩全场景门户)

**draft→bet 路径验证 (2026-06-27)**: ✅ **已通** (memory `product-walkthrough-focus` 过时更新)
- brainstorm 真生成 Pitch (非 mock, cli.py:58-73)
- bet 接受 Pitch → `_import_pitch` (Upstream 验证 CR-STRATEGY-01 + LLM 提取 + 物化)
- **LLM 容错**: httpx ConnectError → `except Exception` (llm.py:144) → `_mock_extract` fallback (行 148)
- 物化: local adapter `.c2g_data/`, ecos adapter 需 omo (goals/planned)

**结论**: draft→bet 路径代码通 + LLM 容错通. memory "断" 过时 (现已修: brainstorm 真生成 + LLM except mock).

**剩余**: 全场景门户盲区 (公文/家庭/健康非一等公民) — 产品层 (c2g 原语支持多场景), 非路径断.

### 2. omo 5 任务 (P0-P1)

**任务锚点** (systematic-issues-tasks):
- 9B363829 (P0 鸿沟)
- 26348641 (P0 反馈闭环)
- F7114ABA (P1 God Module)
- 94BB9C70 (P1 并发锁)
- 6B868907 (P1 产品门户)

**推进**: 逐个 omo task 评估 + 推进 (P0 优先).

### 3. mypy 清理 (P1)

**现状** (kairon-mypy-cleanup-progress): kos 清零 / iris 61→11 / baseline 873. 剩:
- minerva 175 errors
- eidos 217 errors
- ontoderive 470 + iris 架构债 11

**范式**: MYPYPATH=src 真相 + 增量清零 (kos 范式).

### 4. BOS 鸿沟 (P1, ✅ 已修复 2026-06-27)

**现状验证** (evidence-smoke 2026-06-27): resolve 率 **100% (100/100, 鸿沟 0)**.
- memory `bos-decl-exec-gap` (102 URI resolve 全失败) **过时** — 现已全 resolve.
- 任务 9B363829 (P0 BOS 鸿沟 resolve 21.6%→≥90%) **已达成** (100%).
- transport: stdio 44 / mcp_stdio 37 / internal 19.

**结论**: BOS 鸿沟闭环 (前面工作或并发 agent 修复). memory 待更新.

## 推进计划

依次推进 (c2g → omo → mypy → BOS), 每任务分阶段:
1. **c2g** (当前): 探查 draft→bet 断点 + 修复
2. omo: 5 任务 P0 优先
3. mypy: 增量清零 (minerva → eidos → ontoderive)
4. BOS: resolve 修复 (60 假阳性优先)

## 状态更新

- **2026-06-27**: 任务池建立. c2g 推进中 (探查阶段).

---

*omostation 任务池 v1 · 2026-06-27 · GaC 稳态后持续跟踪*
