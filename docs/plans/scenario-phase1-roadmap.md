---
lifecycle: plan
owner: system-owner
last_updated: 2026-08-07
type: ephemeral
---

# Scenario Phase 1: 场景验证期方案与实施路线图

> 创建: 2026-08-07 | 状态: draft | 所有者: 系统所有者
> 基于: ARCHITECTURE-STRATEGY-CLOSEOUT-2026-08.md, VISION-ROADMAP.md

## 1. 核心目标

**在 4 周内完成一个真实业务场景的五段闭环：输入 → 判断 → 执行 → 交付 → 复用**。

当前系统处于 **M4 平台就绪 / P0 场景待验证** 阶段。核心运行链已经完备，但缺少三个决定性事实：
1. 一个持续发生、低风险、可重复的真实业务消费场景
2. 一份来自真实业务过程的稳定标注评测集
3. 一次由人或 OMO 明确批准的生产启用决策

## 2. 场景选择

### 2.1 首场景: 资料/邮件/待办到决策收件箱 (P0)

| 维度 | 说明 |
|------|------|
| 输入 | 邮件、OA 通知、文件、消息、待办事项 |
| 处理 | 结构化抽取、优先级排序、关联已有知识 |
| 输出 | 结构化事项清单、优先排序、待确认问题 |
| 自动化边界 | 只抽取和建议，不自动发送或承诺 |
| 入口 | cockpit CLI + cockpit-ui 决策收件箱视图 |
| 风险 | 低 — 输出可人工复核，无自动执行 |

### 2.2 场景价值

```
场景价值 = 发生频率 × 单次节省时间 × 可复用性 × 可验证性 × 风险可控度
         = 每天 × 30min × 高(可复用) × 高(可人工复核) × 高(只建议不执行)
```

## 3. 方案架构

### 3.1 系统交互流程

```
用户输入 (邮件/文件/消息)
    ↓
kronos fetch (5层抓取引擎) → 原始内容
    ↓
kairon pipeline (内容抽取/结构化) → 结构化事项
    ↓
kos index (知识关联/上下文补充) → 增强事项
    ↓
OMO task (事项注册/优先级排序) → 待确认清单
    ↓
cockpit-ui (决策收件箱视图) → 用户确认
    ↓
用户反馈 (确认/修改/拒绝) → 复盘改进
```

### 3.2 组件职责

| 组件 | 职责 | 变更范围 |
|------|------|---------|
| cockpit | 场景卡管理、旅程时间线、证据面板 | 新增 API + CLI |
| cockpit-ui | 决策收件箱视图、事项卡片、确认交互 | 新增视图组件 |
| ecos | 场景绑定契约、旅程定义 | 新增契约 + 模板 |
| omo | 事项任务生命周期、HITL 审批流 | 新增审批流程 |
| agora | 场景路由、外部连接绑定 | 新增路由规则 |
| kronos | 内容抓取(已就绪) | 无变更 |
| kairon | 内容结构化(已就绪) | 无变更 |

## 4. 里程碑规划

### 4.1 时间线

```
Week 1 (08-07 ~ 08-13)     Week 2 (08-14 ~ 08-20)     Week 3 (08-21 ~ 08-27)     Week 4 (08-28 ~ 09-03)
──────────────────────────┼──────────────────────────┼──────────────────────────┼──────────────────────────
场景卡 MVP                决策收件箱视图              HITL 流程 + 证据面板      试点启动 + 复盘
                                                                                            
M1: 场景卡 API             M2: 收件箱交互             M3: 审批闭环               M4: 4周试点
```

### 4.2 里程碑详情

#### M1: 场景卡 MVP (Week 1, 08-13)

| 交付物 | 项目 | 描述 |
|--------|------|------|
| 场景卡数据模型 | ecos | scene_id, journey_id, intent_id 契约 |
| 场景卡 CRUD API | cockpit | 创建/查看/列表场景旅程 |
| 场景卡 CLI | cockpit | `cockpit scene create/list/status` |
| 场景绑定契约 | ecos | 外部资源→场景绑定模板 |

**验证**: cockpit 可创建场景旅程，查看时间线

#### M2: 决策收件箱视图 (Week 2, 08-20)

| 交付物 | 项目 | 描述 |
|--------|------|------|
| 事项数据模型 | omo | 事项→任务映射，优先级字段 |
| 事项摄取管线 | cockpit | 邮件/文件→结构化事项API |
| 决策收件箱视图 | cockpit-ui | 事项列表、优先级排序、知识关联 |
| 事项 CLI | cockpit | `cockpit inbox list/status/process` |

**验证**: 用户可查看事项列表，确认优先级

#### M3: HITL 审批 + 证据面板 (Week 3, 08-27)

| 交付物 | 项目 | 描述 |
|--------|------|------|
| HITL 审批流 | omo | 事项→ Task → 审批 → 关闭 |
| 证据面板 API | cockpit | 事项来源、处理依据、处理结果 |
| 证据面板视图 | cockpit-ui | 证据链展示 |
| 审批 CLI | cockpit | `cockpit approval list/approve/reject` |

**验证**: 用户可审批事项，查看完整证据链

#### M4: 试点启动 + 复盘 (Week 4, 09-03)

| 交付物 | 项目 | 描述 |
|--------|------|------|
| 真实输入接入 | cockpit | 邮件/OA 自动导入 |
| 结果复盘 CLI | cockpit | 每周复盘，统计节省时间/误报率 |
| 复盘视图 | cockpit-ui | 趋势图表、准确率统计 |
| 试点报告 | docs | 4 周试点总结 |

**验证**: 连续 4 周有真实输入，形成可审计事项清单

## 5. 技术方案详述

### 5.1 场景卡数据模型 (ecos)

```yaml
scene:
  id: scene-{uuid}
  name: 场景名称
  description: 场景描述
  status: active | paused | archived
  created_at: timestamp
  journeys:
    - id: journey-{uuid}
      name: 旅程名称
      status: proposed | running | completed | failed
      intents:
        - id: intent-{uuid}
          source: email | file | message | manual
          content: 原始输入
          processed: 结构化事项
          status: pending | approved | rejected | done
          evidence:
            - source: 来源
              action: 处理动作
              result: 处理结果
              timestamp: timestamp
```

### 5.2 事项→任务映射 (omo)

```yaml
inbox_item:
  id: item-{uuid}
  scene_id: scene-{uuid}
  journey_id: journey-{uuid}
  source: email | file | message | manual
  raw_content: 原始内容
  structured:
    title: 事项标题
    description: 事项描述
    priority: P0 | P1 | P2 | P3
    category: 分类
    deadline: 截止时间
    related_knowledge: [知识引用]
  status: pending | task_created | approved | rejected | done
  task_id: 关联 OMO Task ID
  created_at: timestamp
  processed_at: timestamp
```

### 5.3 审批流 (omo)

```
inbox_item.status: pending
    ↓
cockpit approval list → 用户查看待审批事项
    ↓
用户操作: approve | reject | modify
    ↓
approve → omo task create → item.status = task_created
reject  → item.status = rejected (记录原因)
modify  → 更新结构化字段 → 重新提交
    ↓
evidence 记录: 来源、操作、结果、时间戳
```

## 6. 实施任务分解

### 6.1 Week 1 任务

| 任务 | 文件 | 预估 |
|------|------|:----:|
| T1.1 场景卡数据模型定义 | ecos/src/ecos/ssot/... | 1d |
| T1.2 场景卡 CRUD API | cockpit/src/cockpit/api/scene.py | 1d |
| T1.3 场景卡 CLI 命令 | cockpit/src/cockpit/cli/scene.py | 1d |
| T1.4 场景绑定契约 | ecos/src/ecos/ssot/... | 1d |

### 6.2 Week 2 任务

| 任务 | 文件 | 预估 |
|------|------|:----:|
| T2.1 事项数据模型定义 | omo/src/omo/... | 1d |
| T2.2 事项摄取管线 API | cockpit/src/cockpit/api/inbox.py | 2d |
| T2.3 决策收件箱视图 | cockpit-ui/src/views/Inbox/ | 2d |
| T2.4 事项 CLI 命令 | cockpit/src/cockpit/cli/inbox.py | 1d |

### 6.3 Week 3 任务

| 任务 | 文件 | 预估 |
|------|------|:----:|
| T3.1 HITL 审批流 | omo/src/omo/approval/ | 2d |
| T3.2 证据面板 API | cockpit/src/cockpit/api/evidence.py | 1d |
| T3.3 证据面板视图 | cockpit-ui/src/views/Evidence/ | 2d |
| T3.4 审批 CLI 命令 | cockpit/src/cockpit/cli/approval.py | 1d |

### 6.4 Week 4 任务

| 任务 | 文件 | 预估 |
|------|------|:----:|
| T4.1 真实输入接入 | cockpit/src/cockpit/ingest/ | 2d |
| T4.2 结果复盘 CLI | cockpit/src/cockpit/cli/review.py | 1d |
| T4.3 复盘视图 | cockpit-ui/src/views/Review/ | 1d |
| T4.4 试点报告 | docs/plans/scenario-pilot-report.md | 1d |

## 7. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|:----:|:----:|:----:|------|
| cockpit-ui 视图开发滞后 | 中 | 中 | 优先 CLI 交互，UI 后续迭代 |
| 邮件/OA 接入权限 | 中 | 高 | 先手动导入，再自动化 |
| 结构化抽取质量 | 中 | 中 | 人工复核兜底，持续改进 |
| omo 审批流复杂度 | 低 | 中 | 先简化审批，再完善 |
| 用户参与度不足 | 低 | 高 | 从系统所有者自身工作流开始 |

## 8. 验收标准

### 8.1 M1 验收

- [x] cockpit scene create/list/status 命令可用
- [x] 场景卡数据模型通过 schema 校验
- [x] gac-local-gate 通过

### 8.2 M2 验收

- [x] cockpit inbox list/status/process 命令可用
- [x] 事项可自动结构化抽取
- [x] 决策收件箱视图可展示事项列表
- [x] gac-local-gate 通过

### 8.3 M3 验收

- [x] cockpit approval list/approve/reject 命令可用
- [x] 审批通过后自动创建 OMO Task
- [x] 证据面板可展示完整证据链
- [x] gac-local-gate 通过

### 8.4 M4 验收

- [ ] 连续 4 周有真实输入 *(待真实运行采集 — 引擎已就绪, 连接器支持 MBOX/目录/JSONL 自动导入)*
- [x] 每周形成可审计事项清单 *(review 引擎: 每周复盘 + 可审计统计)*
- [ ] 用户确认部分建议 *(运行期人工行为, 引擎已就绪)*
- [x] 每条建议可回链来源和处理结果 *(intent + evidence 链)*
- [x] 系统可统计节省时间和误报率 *(review 引擎: 时间节省/准确率/误报率)*
