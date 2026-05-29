# WorkSpace 治理计划 — 总纲

> 制定: 2026-05-24 | 战略周期: 2026-05 ~ 2026-08
> 核心矛盾: 工程完备性 >> 产品完整性 → 造了没用上

---

## 战略层：核心判断

### 根本问题
系统有 225K+ LOC 代码（agentmesh 115K + Python 100K+），但**唯一跑通全链路的只有 agora**。最大的模块是用户从未碰过的，最小但核心的场景（研究闭环）却没有完成。

### 治理原则（固化在 CLAUDE.md）
1. **能力冻结** — 不写开新链路以外的新代码
2. **闭环优先** — 每条链路必须: 输入 → 处理 → 输出 → 保存 → 可回顾
3. **30 秒可用** — `workspace demo` 是门禁
4. **废弃即标记** — 30 天无人调用 → `@deprecated`

### 五阶段路线

```
Phase 1: 基础设施清理（5天） ✅ DONE
  目标: 配置0污染 + 配置管理自动化 + 测试基线建立

Phase 2-3: 核心链路闭环 + 统一入口（10天） ✅ DONE
  目标: 深度研究链路完整闭环 + workspace CLI 统一入口

Phase 4: 能力增强（滚动） ✅ DONE
  目标: 废弃清理、文档补齐、持续集成

Phase 5: Self-Collab-Consensus 架构落地（8天） ▶ 当前
  目标: 实现4+1+3架构的自我层(L4)、协作层(L3)、价值堆栈(X3)
  Wave: 5.1A Eidos Schema → 5.1B KOS EntityType → 5.2 Self Domain → 5.3 Collab → 5.4A Consensus → 5.4B Cron+E2E

Phase 6: 验证·复盘·迭代·纠偏（2天） ◀ 门禁
  目标: 9维健康门禁 + 复盘迭代 + 纠偏归档
  门禁: D1-D9全部达标才能关闭

Phase 7+: 待规划（根据Phase 6复盘结果决策）
```

---

## 战术层：角色定义

### Agent 角色体系

| 角色 | 代号 | 职责 | 产出 |
|------|------|------|------|
| **P10 架构师** | atlas | 定义方向、审批计划、仲裁争议 | `GOVERNANCE_PLAN.md`、phase 边界 |
| **P9 技术负责人** | sisyphus | 拆解任务、写 Task Prompt、管理 P8 团队、验收 | Task Prompts、`TASK_POOL.md` 更新 |
| **P8 高级工程师** | prometheus | 执行 Wave 级任务、方案设计+编码+验证 | 代码变更、测试、文档 |
| **P7 工程师** | epimetheus | 在 P8 下执行子任务 | 自包含的代码贡献 |

### 通信协议

```
P10 → P9: GOVERANCE_PLAN.md + phase 边界定义
P9 → P8: Task Prompt（六要素: 目标/范围/验收/依赖/输出/角色）
P8 → P9: [P8-COMPLETION] + 变更清单
P7 → P8: [P7-COMPLETION] + 三问自审查
```

---

## 执行层：阶段·Sprint·Wave·Task

### 阶段划分

```
Phase 1 ── Sprint 1.1 (2d) ── Sprint 1.2 (3d)
            Wave A             Wave A
            Wave B             Wave B
            Wave C

Phase 2 ── Sprint 2.1 (2d) ── Sprint 2.2 (3d)
Phase 3 ── Sprint 3.1 (2d) ── Sprint 3.2 (3d)
Phase 4 ── Sprint 4.1 (滚动)
```

### Wave = 可独立执行的并行工作单元

每个 Wave:
- 由 1 个 P8 独立执行（或 1 P8 + 1~2 P7）
- 有明确的验收标准
- 产出必须是"可回顾的"（不只是 stdout）
- 执行时间 < 1 小时（否则拆更细）

### Task = 最小可验证单元

每个 Task:
- 具体的文件变更 + 测试
- 关联 TASK_POOL 中的 task_id
- 完成后更新 STATE.md

---

## 共享状态管理

### 文件体系

```
.omo/
├── GOVERNANCE_PLAN.md     ← 本文档（战略层，只读）
├── TASK_POOL.md           ← 共享任务池（所有 agent 读写）
├── STATE.md               ← 状态追踪（自动化更新）
├── boulder.json           ← Work tracking（已存在，兼容）
├── plans/
│   ├── governance-phase1.md
│   ├── governance-phase2.md
│   ├── governance-phase3.md
│   └── governance-phase4.md
├── run-continuation/      ← 会话延续（已存在）
└── AUDIT.md               ← 综合审计（已存在）
```

### 状态流转

```
backlog → ready → in_progress → review → done
                                    ↓ (fail)
                                 in_progress
```

### 共享内存（cross-session）

- `TASK_POOL.md` 是唯一的任务真相源
- 每个会话启动时读 TASK_POOL.md → 找 ready 任务
- 每完成一个任务更新 TASK_POOL.md + STATE.md
- 会话结束时写 session_id 到 STATE.md

---

## 依赖管理

### 关键依赖链

```
Phase 1 ─────────────── Phase 2 ────────────── Phase 3
  ├ agora 配置洁净        ├ minerva 持久化        ├ workspace CLI
  ├ go-services 清洗      ├ research list         ├ workspace status
  ├ agora-routes 清洗     ├ research open         ├ workspace demo
  ├ 全项目 ruff 基线      ├ research ask          └ agentmesh 验证
  ├ E2E 测试修复          └ progress bar
  └ MetaOS/SSOT 判定
```

### 并行执行规则

- Wave A/B/C 可以并行（不同 P8）
- Wave 内的 Task 按依赖顺序串行
- P8 负责自己 Wave 的依赖管理
- P9 负责跨 Wave 的协调
