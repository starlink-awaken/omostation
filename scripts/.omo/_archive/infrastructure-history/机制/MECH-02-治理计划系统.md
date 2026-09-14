# MECH-02: 治理计划系统

> **来源**: `.omo/GOVERNANCE_PLAN.md`
> **状态**: ✅ 验证通过 12+ Phases（Phase 1-13），6 个债务缺口全部修复
> **层映射**: X1 治理 — 战略执行

---

## 一、定义

治理计划系统定义了 **多人多 Agent 协作执行工程治理** 的完整组织、通信和执行框架。

### 解决的问题

- 30+ 项目 / 225K LOC 的代码库，如何系统化治理
- 多 Agent（atlas/sisyphus/prometheus/hermes）如何分工协作
- 结构完整性（造了）vs 产品可用性（用了）的失衡纠偏

## 二、角色体系

这是整个系统中定义的 Agent 治理角色，独立于具体的 AI 模型：

| 等级 | 代号 | 角色 | 职责 | 产出 |
|------|------|------|------|------|
| **P10** | `atlas` | 架构师 | 定义方向、审批计划、仲裁争议 | `GOVERNANCE_PLAN.md`、Phase 边界 |
| **P9** | `sisyphus` | 技术负责人 | 拆解任务、写 Task Prompt、管理 P8 团队、验收 | Task Prompts、`TASK_POOL.md` |
| **P8** | `prometheus` | 高级工程师 | 执行 Wave 级任务、方案+编码+验证 | 代码变更、测试、文档 |
| **P7** | `epimetheus` | 工程师 | 在 P8 下执行子任务 | 自包含的代码贡献 |

### 通信协议

```
P10 → P9: GOVERNANCE_PLAN.md + Phase 边界定义
P9 → P8:  Task Prompt（六要素：目标/范围/验收/依赖/输出/角色）
P8 → P9:  [P8-COMPLETION] + 变更清单
P7 → P8:  [P7-COMPLETION] + 三问自审查
```

## 三、分解层级

```
阶段边界 (Phase)      — P10 定义, ~1-2 周
  ├── 迭代 (Sprint)   — P9 拆分, ~2-5 天
  │    ├── Wave A     — P8 独立执行, ~1 天
  │    │    ├── Task 1 — 具体文件变更, ~1 小时
  │    │    └── Task 2 — 具体文件变更, ~1 小时
  │    ├── Wave B     — P8 独立执行（与 Wave A 并行）
  │    └── ...
   └── ...

###  Sprint 类型（按层级分类）

```
I0 Sprint: 集成织物层迭代
  专注: Agora 路由优化、ops 能力扩展、MCP 协议升级
  不包含: 业务逻辑、领域知识
```

### Wave = 可独立执行的并行工作单元

| 属性 | 要求 |
|------|------|
| 执行者 | 1 个 P8（或 1 P8 + 1~2 P7） |
| 验收标准 | 必须明确定义 |
| 产出 | 可回顾（不只是 stdout） |
| 执行时间 | < 1 小时（否则拆更细） |

### Task = 最小可验证单元

| 属性 | 要求 |
|------|------|
| 粒度 | 具体的文件变更 + 测试 |
| 跟踪 | 关联 TASK_POOL 中的 task_id |
| 同步 | 完成后立即更新 STATE.md |

## 四、治理原则（固化）

1. **能力冻结** — 不写开新链路以外的新代码
2. **闭环优先** — 每条链路必须: 输入 → 处理 → 输出 → 保存 → 可回顾
3. **30 秒可用** — `workspace demo` 是门禁
4. **废弃即标记** — 30 天无人调用 → `@deprecated`

## 五、状态管理

### 共享状态文件

```
.omo/
├── GOVERNANCE_PLAN.md    ← 战略层（只读，P10 写）
├── TASK_POOL.md          ← 共享任务池（所有 agent 读写）
├── STATE.md              ← 状态追踪（自动更新）
├── boulder.json          ← Work tracking
├── plans/                ← Phase 级 plan 文件
└── AUDIT.md              ← 综合审计
```

### 状态流转

```
backlog → ready → in_progress → review → done
                                    ↓ (fail)
                                 in_progress
```

### 跨 session 共享

- `TASK_POOL.md` 是唯一的任务真相源
- 每个 session 启动时读 TASK_POOL.md → 找 ready 任务
- 每完成一个任务更新 TASK_POOL.md + STATE.md
- 会话结束时写 session_id 到 STATE.md

## 六、九维健康评分模型

治理中使用的全局健康评估方法：

| 维度 | 含义 | 测量方式 |
|------|------|---------|
| D1 愿景达成度 | 架构是否落地 | 对照 4+1+3 |
| D2 场景覆盖度 | 用户旅程覆盖 | E2E 测试 |
| D3 故事完整度 | 端到端可用 | `workspace demo` |
| D4 功能成熟度 | 测试覆盖 | 测试通过率 |
| D5 架构成熟度 | 降级/多实例/容错 | 混沌测试 |
| D6 熵增情况 | 保鲜机制 | cron 运行率 |
| D7 安全质量 | 门禁 enforce | 权限通过率 |
| D8 债务情况 | 技术债务 | 待修复条目 |
| D9 成本资源 | Token/模型路由 | usage.db |
