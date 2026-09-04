---
id: BET-Y1Q3-T6-04
type: retro
status: archived
date: 2026-08-18
bet_id: BET-Y1Q3-T6-04
north_star_ref: docs/STRATEGY-3YEAR-PLAN-2026H2-2029.md
repo: omostation-gbrain
merged_prs:
  - 8
  - 9
  - 10
gbrain_merge_commits:
  - 42d02bdd
  - 9e4a9f19
  - afef89e8
scope:
  - gbrain src
lifecycle: history
owner: governance-team
last_updated: 2026-08-18
title: "BET-Y1Q3-T6-04 Retro: gbrain god-module SRP 拆分"
---

# BET-Y1Q3-T6-04 Retro: gbrain god-module SRP 拆分

## Q1 目标回顾
把 gbrain 4 个 >2800L 的 god-module 文件拆分为职责清晰的多个文件，让 omo lint god-module 回归全绿：doctor.ts (4659L) + postgres-engine.ts (4514L) + pglite-engine.ts (4509L) + ai/gateway.ts (2895L)，全部 ≤1500L。

## Q2 实际结果
4 个 god-module 全部拆分完成并合入 gbrain main：

| 文件 | 拆分前 | 拆分后 | PR |
|---|---|---|---|
| doctor.ts | 4659 | 1272 | #8 |
| ai/gateway.ts | 2895 | 1080 | #9 |
| postgres-engine.ts | 4514 | 787 | #10 |
| pglite-engine.ts | 4509 | 701 | #10 |

**doctor.ts** 拆成 6 文件: doctor.ts(骨架) + doctor-checks + doctor-types + doctor-remediate + doctor-db-conn-checks + doctor-db-data-checks。

**ai/gateway.ts** 拆成 3 文件: gateway.ts(配置/认证/状态) + gateway-embed + gateway-chat。共享状态通过 gateway.ts 访问器(_getConfig/_getModelCache 等)跨模块共享, 避免循环 import。

**postgres-engine.ts** 拆成 4 文件: 主类(787L) + pages(1092) + links(1325) + takes(1352)。

**pglite-engine.ts** 拆成 5 文件: 主类(701L) + pages(1092) + links(840) + facts(555) + takes(1368)。

engine 两个文件用 mixin 模式: 方法通过 `Object.assign(Engine.prototype, methods)` 注入, `interface Engine extends BrainEngine {}` 合并声明保持类型正确。

## Q3 目标偏差
- engine 拆分原计划用类 mixin(继承), 实际采用 Object.assign 方法注入更简单, 无需改变类层次。
- 拆分成 3-6 个文件而非单一 mixin 文件, 每个 ≤1500L 满足 god-module 阈值。
- gbrain 是孤儿仓库(独立 remote omostation-gbrain), 不涉及主仓指针 bump。

## Q4 机制沉淀
- **source-grep 测试适配**: 拆分后测试对源文件的内容断言需拼接全部 mixin 文件。新增 test/helpers/doctor-sources.ts 供 doctor 测试复用; postgres-engine.test.ts / connection-resilience.test.ts 也改为拼接。**source-grep 是拆分的高频破坏点**。
- **私有方法提取**: 类私有方法(`private async _searchKeywordCJK` 等)的签名带 `private` 前缀, 提取脚本正则需兼容; 拆分后私有方法转普通方法, 通过 `this` 调用。
- **mixin 类型**: `Record<string, any>` 对象方法里 `this` 是 any, 需给方法签名加 `this: EngineLike` 注解, 否则方法体内 `this.db.query<T>()` 报 "Untyped function calls"。
- **泛型方法丢失**: `async executeRaw<T>(...)` 泛型签名不被简单正则识别, 需单独处理; executeRaw 类方法易被吞, 拆分后须检查。
- **接口提取边界**: 类后接口(FactRowSqlShape)提取时须精确配平, 否则缺闭合 `}`。
- **方法间逗号**: Object.assign 注入对象的方法间需逗号, 提取脚本须 `,\n`.join。
- **CI 环境**: gbrain CI test(4) 的 whoknows cwd 测试为 pre-existing 环境失败, 非拆分引入, 不阻塞合并(main 无 required checks)。
