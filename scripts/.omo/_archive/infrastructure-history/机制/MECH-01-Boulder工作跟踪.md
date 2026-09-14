# MECH-01: Boulder 工作跟踪系统

> **来源**: `.omo/boulder.json`
> **状态**: ✅ 稳定，schema v2，跨 13+ 工作流验证
> **层映射**: X1 治理 — 执行跟踪

---

## 一、定义

Boulder 是跨 session 的**工作跟踪系统**，通过 `boulder.json` 文件追踪每次开发工作的完整生命周期。

### 解决的问题

- 系统断连后如何恢复上一次的工作
- 多 agent 如何共享状态（谁来执行、执行到什么阶段）
- 如何跨 session 保持上下文不丢失

## 二、架构

```
boulder.json (唯一状态源)
├── schema_version        — 格式版本 (当前 v2)
├── active_work_id        — 当前活跃 work 的 UUID
├── active_plan           — 对应的 plan 文件路径
├── works: {              — 所有 work 的历史记录
│     {work_id}: {
│       active_plan       — plan 文件
│       plan_name         — plan 标识名
│       status            — completed / active / failed
│       session_ids[]     — 参与的所有 session ID 链
│       agent             — 执行 agent 代号
│       task_sessions: {  — task 级粒度
│         {task_key}: {
│           session_id    — 具体 session
│           agent         — 执行 agent
│           category      — task 类型 (deep/quick)
│           status        — running/completed
│         }
│       }
│       phases: {         — Phase/Sprint/Wave 结构
│         {phase_id}: {
│           name, status
│           sprints: { {sprint_id}: {name, status} }
│         }
│       }
│       ended_at          — 结束时间
│     }
│   }
```

## 三、核心规则

### R1: 活跃 work 唯一性

同一时间只有 `active_work_id` 指向的 work 是活跃的。新 work 开始前旧 work 必须 completed。

### R2: session_id 链

每次恢复一个 work 时，将当前 session_id append 到 `session_ids[]`。形成完整的执行历史链（部分 work 跨越 13+ 个 session）。

### R3: 状态同步

```
完成变更 → 更新 boulder.json → 更新 STATE.md → 提交
```

每完成一个 task 就同步，不批量。否则系统续接钩子将持续触发。

### R4: agent 归属

每个 work 记录 `agent` 字段（atlas/laowang/sisyphus/hermes），明确执行者身份。task 级 agent 也可以不同（比如 P9 拆 Task, P8 执行）。

## 四、文件清单

| 文件 | 角色 | 备注 |
|------|------|------|
| `.omo/boulder.json` | 唯一状态源 | schema v2，自动更新 |
| `.omo/STATE.md` | 人类可读摘要 | 从 boulder.json 手动同步 |
| `.omo/GOVERNANCE_PLAN.md` | 治理总纲 | 战略层定义 |
| `.omo/TASK_POOL.md` | 共享任务池 | 所有 agent 读写 |

## 五、使用模式

```
# 开始新 work
boulder 启动 → 设 active_work_id → 关联 plan → 写 session_id

# 续接 work
读 boulder.json → 取 active_work_id → 读 plan → 继续执行

# 完成 work
设 status=completed → 设 ended_at → 清 active_work_id

# 查看历史
boulder.json.works 列出所有已完成 work
```
