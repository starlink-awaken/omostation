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

### 1. c2g 自治盲区 (P0, 推进中)

**现状**: c2g 五原语 (brainstorm/draft/bet/radar/gc) 天然匹配 GaC 元治理循环. 但:
- brainstorm 已修真 (memory: product-walkthrough-focus)
- **draft→bet 路径断** (draft 产出无法顺畅转 bet)
- 全场景门户盲区 (公文/家庭/健康非一等公民)

**推进步骤**:
1. 探查 c2g cli brainstorm/draft/bet 命令现状
2. 定位 draft→bet 断点 (schema/流程/入口)
3. 修复 draft→bet 路径
4. (扩展) 全场景门户 (公文/家庭/健康 一等公民)

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

### 4. BOS 鸿沟 (P1)

**现状** (bos-decl-exec-gap): 102 URI 声明 alive 但 resolve 全失败. 静态 42 vs 动态 102 (60 假阳性). evidence-smoke 基线 53.0.

**推进**: evidence-smoke 量化 + 逐个 resolve 修复.

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
