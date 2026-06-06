# MECH-05: 任务分解 Wave 模型

> **来源**: `.omo/GOVERNANCE_PLAN.md` + `TASK_POOL.md` + `boulder.json`
> **状态**: ✅ 验证通过 12+ Phases，251/268 tasks 完成，6 债务缺口修复
> **层映射**: X1 治理 — 任务执行方法论

---

## 一、定义

Wave 模型是从大任务到最小可验证单元的**系统化分解方法**，用于管理多 Agent 协作的大型工程治理项目。

### 解决的问题

- 225K LOC 的代码库从哪里开始治理
- 如何将大 Phase（1-2 周工作量）分解到可并行执行的单元
- 多 Agent 如何高效并行且不冲突

## 二、分解金字塔

```
策略层: Phase (P10 定义, 1-2 周)
  主题明确 → 可验证的阶段性产出
  ├── Phase 1: 基础设施清理
  ├── Phase 2: 核心链路闭环
  ├── Phase 3: 统一入口
  └── ...

战术层: Sprint (P9 拆分, 2-5 天)
  可执行的迭代单元
  ├── Sprint 1.1: 配置洁净
  └── Sprint 1.2: 基线建立

执行层: Wave (P8 独立执行, ~1 天)
  可独立并行的工作包
  ├── Wave A: Go services 清洗
   ├── Wave B: agora 配置洁净
   ├── Wave C: E2E 测试修复
   └── I0-Wave: 集成织物层任务
       包含: MCP 协议升级、运维工具扩展、服务路由优化
       I0-Wave 的 task prompt 应注明「I0 不承载业务逻辑」

原子层: Task (具体执行, ~1 小时)
  最小可验证变更
  ├── Task: 修复 agora-routes JSON schema
  └── Task: 更新 agora-routes 测试
```

## 三、Wave 标准

| 属性 | 标准 |
|------|------|
| 执行者 | 1 个 P8（或 1 P8 + 1~2 P7） |
| 验收标准 | 明确定义 |
| 依赖声明 | 前置 Wave / 无依赖 |
| 产出 | 代码变更 + 测试 + boulder 更新 |
| 时间 | < 1 小时（否则拆更细） |
| 并行性 | 可并行（Wave A/B/C 同时执行） |

## 四、Task Prompt 六要素

P9 给 P8 的每个 Task 必须包含：

```
1. 目标    — 做什么
2. 范围    — 哪些文件/不改哪些
3. 验收    — 如何判断完成（门禁）
4. 依赖    — 前置条件
5. 输出    — 期望的文件变更
6. 角色    — 执行者身份
```

## 五、执行流程

```
1. P10 定义 Phase 边界
     ↓
2. P9 拆分为 Sprint + Wave
     ↓
3. P9 为每个 Wave 写 Task Prompt（六要素）
     ↓
4. P8 接收 Task Prompt 并行执行
     ↓
5. P8 完成后发 [P8-COMPLETION] + 变更清单
     ↓
6. P9 验收 → 更新 TASK_POOL + STATE
     ↓
7. 同步到 boulder.json
```

## 六、结果数据

| Phase | Tasks | 状态 | 验证 |
|-------|-------|------|------|
| 1-8: 个人AI OS + 多Agent协作 | 121 | ✅ 100% | 单人多Agent完全可用 |
| 9: 多人多组织 | 12 | ✅ 100% | Identity/CapGrant |
| 10: 蜂群智能 | 25 | ✅ 100% | 递归架构/进化闭环 |
| 11: 递归Agora | 10 | 🟡 启动 | Wave 11.1 |
| 13+: 终极进化 | 10 | ⏳ | 10/10 pending |

## 七、关键学习

### LESSON-01: 子代理超时
**问题**: deep 类别的 task() 几乎全部在 45 分钟超时后中断
**修复**: 改用 quick 类别 + 详细到逐文件的 prompt（平均 1-5 分钟，成功率 ~90%）
**规则**: 跨项目的复杂适配器类任务 → 用 quick 不是 deep，prompt 包含具体文件名

### LESSON-02: Plan 同步必须即时
**问题**: 执行节奏快时忽略 plan 更新 → 系统续接钩子持续触发 20+ 次
**修复**: 每完成一个 Wave 立即更新 plan checkbox + boulder.json
**规则**: `todowrite` 和 plan 更新 = 代码变更的一部分

### LESSON-03: 验证不能信任声明
**问题**: 子代理多次报告"已完成"但实际未完成
**规则**: 每次 subagent 完成后必须 Read 文件确认 + 运行命令验证输出

### LESSON-04: 模型统一应逐步完成
**规则**: 从适配器映射 → 字段归一化 → MetaType 枚举 → Python 继承，每步独立验证
