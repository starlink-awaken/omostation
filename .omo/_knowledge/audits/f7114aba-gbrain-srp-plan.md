---
status: active
lifecycle: planning
owner: laowang
last-reviewed: 2026-06-28
related-task: F7114ABA
---

# F7114ABA gbrain God Module SRP 拆分计划

> check-god-module error 文件 (>1500L) 拆分路线图. engine.ts 范式已建立, 剩 8 文件留 srp-refactor 专项 wave.

## 范式总结: engine.ts 类型提取 (已完成 ✅)

**commit**: gbrain `6b27c9df` (2026-06-27)

**为何 engine.ts 可快速低风险拆**:
- 32 个 engine 专属类型集中在 45-534 行 (500L 连续类型区)
- BrainEngine interface 是纯声明 (无实现逻辑)
- `export * from engine-types` 向后兼容, 消费者 import 不变
- typecheck 是唯一验证 (干净 = 拆分正确)

**结果**: engine.ts 1563→1060 (<1500 达标), error 10→9.

## 剩 8 文件评估 (按风险/优先级排序)

| 文件 | 行数 | 类型数 | 切入点 | 风险 | 优先级 |
|------|------|:------:|--------|:----:|:------:|
| **cli.ts** | 1735 | 1 | 命令 dispatch 表 → 按域拆子路由 (像 cockpit status.py) | 中 | P2 |
| **commands/sync.ts** | 1609 | 2 | performSync 编排 vs pure helpers 分离 (core/sync.ts 已是 pure) | 中 | P2 |
| **cycle.ts** | 1707 | 7 | 类型区(56-254, ~200L)提取不够达标; 需 phase wrappers 拆到 cycle/phases/ | 中高 | P3 |
| **serve-http.ts** | 1756 | 3 | OAuth/admin/SSE/MCP 四职责 → 子模块 (oauth/server-sse/mcp-dispatch) | 高 | P3 |
| **gateway.ts** | 2895 | 14 | 类型分散 + 模块状态耦合 (_config/_modelCache/_embedTransport); 子模块: rerank/voyage-compat/dims | 高 | P3 |
| **migrate.ts** | 4333 | 1 | MIGRATIONS 数组 + runner; 按 migration 版本段拆 (v1-30/v31-60/v61+) | 高 | P4 |
| **postgres-engine.ts** | 4514 | 0 | BrainEngine 实现; 与 pglite-engine 平行逻辑 (DRY 提取 engine-shared) | 极高 | P4 |
| **pglite-engine.ts** | 4509 | 0 | 同上 (双引擎平行实现) | 极高 | P4 |
| **doctor.ts** | 4825 | 2 | 健康检查聚合; 按 check 域拆 (sync-freshness/skill-brain-first/supervisor/...) | 极高 | P4 |

## 关键观察

### 1. engine.ts 范式不直接适用剩 8 文件
剩 8 文件类型数 0-14 (远低于 engine.ts 的 32), 且类型**分散**非连续区. 无法用"纯类型提取"一步达标.

### 2. postgres-engine + pglite-engine DRY 潜力最大
两个文件几乎同大 (4514/4509), 是 BrainEngine 双实现, 大量平行 SQL 逻辑 (addLinksBatch/searchKeyword/searchVector). 提取共享 SQL 构建器/纯助手到 `engine-shared.ts` 可同时降两个文件. 但需逐方法对比两引擎差异 (postgres 用 unnest+JOIN, pglite 用手动 $N), 工作量大.

### 3. 高耦合模块状态 (gateway.ts)
gateway.ts 模块级状态 (_config/_modelCache/_extendedModels/_embedTransport/_chatTransport/_shrinkState) 跨函数共享. 提取子模块需先状态对象化 (gateway-state.ts), 否则循环依赖.

### 4. 已有拆分惯例 (cycle.ts)
cycle.ts 已拆出 cycle/ 子目录 (14 模块: anomaly/auto-think/base-phase/budget-meter/calibration-profile/drift/emotional-weight/extract-facts/extract-takes/grade-takes/patterns/phantom-redirect/propose-takes/recompute-emotional-weight). 剩余 1707 行 = 类型(200L) + phase wrappers(~830L) + runCycle(~670L). phase wrappers 是下一步拆分点 (薄包装 → cycle/phases/).

## srp wave 建议

**Wave 1 (低风险, P2)**: cli.ts + commands/sync.ts
- 命令 dispatch 拆分有成熟模式 (cockpit status.py 范式)
- core/sync.ts 已是 pure, commands/sync.ts 编排层可薄化

**Wave 2 (中风险, P3)**: cycle.ts + gateway.ts + serve-http.ts
- cycle.ts phase wrappers → cycle/phases/
- gateway.ts 状态对象化 → 子模块
- serve-http.ts 职责拆分

**Wave 3 (高风险, P4)**: migrate.ts + postgres-engine + pglite-engine + doctor.ts
- 双引擎 DRY 提取 (最大收益但需逐方法对比)
- migrate.ts 按版本段拆
- doctor.ts 按 check 域拆

## 验证标准 (每文件拆分后)

1. `bun run typecheck` 干净 (无新错误)
2. `bun test` 相关测试绿
3. check-god-module 该文件 < 1500L
4. 向后兼容 (public exports 不变, 消费者 import 不破坏)
5. `bun run verify` CI gate 绿

## 约束

- **不盲目拆**: 每文件先评估切入点, 低风险才动 (CR-ENG-LOOP-HONESTY)
- **每步验证**: 类型提取→typecheck; 函数提取→typecheck+test; 不累积未验证改动 (CR-ENG-SRP-INCREMENTAL-01)
- **向后兼容优先**: public exports 保持, 内部重组不破坏消费者
- **核心文件谨慎**: postgres-engine/pglite-engine/doctor 是运行时核心, 拆分需充分测试覆盖

---

*F7114ABA gbrain SRP 拆分计划 v1 · 2026-06-28 · engine.ts 范式已建立, 8 文件留 srp wave*
