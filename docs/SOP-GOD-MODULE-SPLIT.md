---
status: draft
lifecycle: sop
owner: governance-team
last-reviewed: 2026-07-07
related:
  - ../../../.omo/_knowledge/decisions/STRAT-P76-strategic-roadmap.md
  - ../../../.omo/_knowledge/audits/2026-07-02-system-comprehensive-audit.md
  - ../../../.omo/_knowledge/patterns/p71-baseline-recovery-pattern.md
  - CR-X1-GOD-MODULE-LIMIT (governance-checks)
---

# SOP: God-Module 渐进拆分

> **触发**: `bin/check-god-module.py --strict` 报告 > 1500L 文件失败。
> **范围**: P76 Phase 1 Step 1.5 交付物。
> **目标**: 把 7 个 > 1500L god module (gbrain 重灾区) 通过 5 阶段渐进拆解,**不冻结 gbrain 开发**。

## 1. 当前 God Module 清单 (实测 2026-07-07)

按 `wc -l` 实测, `projects/gbrain/src/core/` 下:

| 排名 | 文件 | 行数 | 状态 |
|:---:|------|---:|:---:|
| 1 | `postgres-engine.ts` | **4514** | 🔴 P0 |
| 2 | `pglite-engine.ts` | **4509** | 🔴 P0 |
| 3 | `core/ai/gateway.ts` | **2895** | 🟡 P1 |
| 4 | `migrate/migrations-early.ts` | **1341** | 🟢 接近阈值 |
| 5 | `core/search/hybrid.ts` | **1302** | 🟢 接近阈值 |

> 真实数字从源码实测 (符合 ISC-27 "不硬编码" 原则)。

## 2. 五阶段渐进拆分 (P76 复用)

### Phase 0 · 边界划定 (1-2 天)

```
行动:
  - 在 god module 顶部加 `@module-boundary: <logical-name>` 注释
  - 用 `ts-morph` 或 `grep` 分析导入关系, 画"外部消费者矩阵"
输出:
  - <god-module>.BOUNDARY.md (列出每个区块的：输入 / 输出 / 调用者)
```

### Phase 1 · 块级抽取 (3-5 天/文件)

```
规则:
  - 单次抽取 < 500L 区块, 不动接口
  - 抽取后立即跑 `bun test`, 不许引入新测试失败
  - 新文件命名: `<god-module>/<concern>.ts`
工具:
  - `bin/check-god-module.py --relaxed` (允许短暂 >1500L 但 ≤2000L)
```

### Phase 2 · 接口抽象 (5-7 天/文件)

```
目标:
  - god module 变成"组装层" (facade), 内部细节全部下沉
  - 暴露纯函数 + 注入式依赖, 便于 mock
验证:
  - 所有 call site 接口不变 (by function signature)
  - test coverage 不降
```

### Phase 3 · 跨仓可移植性 (按需)

```
触发条件:
  - god module 内容已开始被 omo / cockpit 直接 import
行动:
  - 抽到独立 `@gbrain/<concern>` 包
  - 走 projects/gbrain monorepo workspace split
约束:
  - 必须在 P72 closed-loop 协议下, 每独立包一个 PR
```

### Phase 4 · 守门固死 (1 天)

```
最终验收:
  - `bin/check-god-module.py --strict` 全绿
  - CI 强制 (不能让 god module 重新膨胀)
  - 写 ADR-0156 god-module-split-record.md
```

## 3. 关键约束 (反 cargo cult)

| 不该做 | 替代 |
|--------|------|
| 直接整体重写 (常见诱惑) | 必须走 5 阶段, 不允许跳 |
| 抽接口但留 god module 原状 | interface 抽出 = 必须立即下沉 |
| 拆开后立即改名 | 同名迁移, 保留 IDE history |
| 不测就拆 | 每个抽取必须单独 commit + test |

## 4. 进度跟踪

```
月度检查: ./bin/check-god-module.py
每个拆分完成的指标:
  - 文件数 / 行数 下降率
  - call site 减少率
  - test coverage 持平或上升
```

## 5. 与现有规则的对齐

| 规则 | 关系 |
|------|------|
| `CR-X1-GOD-MODULE-LIMIT` | 拦新 > 1500L 文件 (已立, 2026-07-02 audit 加) |
| `TASK-F7114ABA` | 旧 planned task, 内容已整合到此 SOP |
| `bin/check-god-module.py --strict` | 自动检测工具, CI 集成入口 |

## 6. 验证清单

- [ ] Phase 0 边界文档 (1 篇/文件)
- [ ] Phase 1 块级抽取 (≥ 2 文件)
- [ ] Phase 2 接口抽象 (按需)
- [ ] Phase 4 守门固死 (CI 强制)
- [ ] ADR-0156 god-module-split-record.md

---

*最后更新: 2026-07-07 · P76 Phase 1 Step 1.5 · 沿用 P71 baseline recovery 5 阶段流程*
