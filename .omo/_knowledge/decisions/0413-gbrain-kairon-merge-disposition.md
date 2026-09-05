---
id: ADR-0413
title: gbrain + kairon 归并为 knowledge — 决策补档
status: archived
lifecycle: spec
owner: governance-team
created: 2026-08-17
last-reviewed: 2026-08-18
deciders:
  - 夏明星 (最终确认 pending)
  - engineering-agent (起草, 依据既有授权链)
related:
  - .omo/_knowledge/decisions/0410-strategy-mainline-plan-supersedes-panorama.md
  - .omo/_knowledge/decisions/0412-model-driven-disposition.md
  - docs/STRATEGY-3YEAR-PLAN-2026H2-2029.md
  - docs/plans/2026-08-16-t6-01-knowledge-merge-spec.md
  - docs/plans/2026-08-16-t6-01-dedup-ledger.md
  - .omo/_knowledge/retros/BET-Y1Q3-T6-01.md
supersedes: []
session: strategy-convergence-r3
type: ssot
---

# ADR-0413: gbrain + kairon 归并为 knowledge — 决策补档

## 状态

**ACCEPTED** — 2026-08-17 夏明星会话批准（"ABCE 都批准"）。实施 #1600 已 merged，
台账 BET-Y1Q3-T6-01 同日置 done，回滚 tag pre-knowledge-merge-20260816 已推远端。

## WHY（为什么归并）

1. **知识层双头**：gbrain（bun/ts, Postgres RAG, 164K src）与 kairon
   （python/uv, 16 包引擎 monorepo, 118K src）同属 L2 引擎层，双头治理面
   （双 .omo、双文档骨架、双 registry 条目、双 CI path filter）持续产生
   指针漂移与维护重复 — STRATEGY-3YEAR-PLAN §1.3 诊断，2026-08 归并实施中
   实测证实（去重清单 ~9,433 行治理面重复）。
2. **交互已是进程边界**：MOS→gbrain 走 subprocess/HTTP（ADR-0372），异构栈
   间无 import 依赖 — 目录归一不改变任何调用路径。
3. **归并是最大一处减法**：三年规划 T6-SUBTRACT 主件，消除 submodule 指针
   漂移面（GaC drift 类事故的根源之一）。

## WHAT（决策内容）

**治理层归一 + 异构栈目录内包**：`projects/knowledge/{gbrain,kairon}` 单一
L2 registry 项目；`.gitmodules` 双条目移除；BOS 双声明源（bos-services.yaml +
resolver/services.py + mcp_gateway）全部改道。

### "不可逆"判断的再确认（grill 要求项）

原判"不可逆"基于 submodule 指针删除。实施后实测修正为：**可逆但有成本** —
回滚 tag `pre-knowledge-merge-20260816`（指向归并前 main b7530c27，本地已打）
checkout 即恢复双 submodule 结构；成本在于归并后双仓的增量 commit 需手工
replay。降级为"高成本可逆"不改变审慎要求，维持 human_gate。

### 实施证据（已发生的事实）

- #1600 merged（2026-08-16）：gbrain 1770/1770 + kairon 1328 文件内包，
  全仓引用重写 ~140 文件，双仓断测清偿 8 项
- test_loc 454,784 ≥ 基线 350,854（保护量守住）
- 治理面去重 9,475 ≈ 去重清单 9,433（numstat 前后差闭环）
- kairon 16 包测试 FAIL=0；gbrain bun test fail 持平基线（388 vs 389，零新增）
- evidence-smoke 100/100；四坑入册 AGENT-BRIEF §8.5

## REJECTED ALTERNATIVES

1. **代码互融（单语言栈）**：异构栈物理不可互融，强行统一 = 重写业务逻辑
   （T6-01 non_goal）。运行时边界本就是进程级。
2. **维持双子模块**：双头治理面重复持续，指针漂移面不减。
3. **暂缓（等 Y1Q3 窗口满再决策）**：实施已按用户授权链完成（2026-08-14
   grill 十问裁定 C / 2026-08-16 /plan 批次 6 批准 / "全面推进"指令），
   本 ADR 是补档而非预决策。

## CONSEQUENCES

**正向**：submodule 数 -2；治理面单点；BOS/CI/registry 路径单源。
**负向/成本**：
- 回滚成本升高（tag checkout + 手工 replay 归并后增量）
- 根仓 checkout 体积增大（~280K src 文件内联）
- 异构构建（bun + uv）在 knowledge/ 内并存，需各自 `uv sync`/`bun install`
  （CI workflow 已适配）

**触发条件备案**（若人类否决本 ADR）：执行回滚 tag 流程，knowledge/ 目录
删除，`.gitmodules` 恢复双条目，已合入 main 的归并 commit revert。
