# OMO 体系扩展架构设计 (v1.0)

> 战略 × 战术 × 执行三层面，整合 5+3+1 架构
> 2026-06-06 | 状态: design-locked

---

## 一、战略层: OMO 在 5+3+1 中的定位

### 1.1 当前矛盾

OMO 治理体系在 5+3+1 中属于 **L2 内核三平面的治理平面**，但实际上：

```
架构定义:    L2 Kernel = OMO(治理) | kairon(引擎) | gbrain(记忆)
实际现状:    OMO 项目(60文件/12,765 LOC) 在 projects/omo/ 独立存在
            与 kairon(引擎) 和 gbrain(记忆) 之间通过 I0(Agora) 通信
            但 OMO 的 CLI 工具无法感知 kairon/agora/gbrain 的运行状态
```

**核心矛盾**: OMO 是"治理操作系统"，但它的输入全靠手动（撰写 YAML/文档），无法自动从系统运行时获取状态。

### 1.2 战略方向

```
OMO v5 愿景: 从"文件治理系统" → "运行时治理操作系统"
                                    ↓
                ┌───────────────────────────────────┐
                │   OMO Governance OS               │
                │                                    │
                │   ← I0(Agora) → 感知运行时状态      │
                │   ← L1(Matrix) → 获取服务健康数据   │
                │   ← L4(Self) → 接收人类指令/意图    │
                │                                    │
                │   输出 → _truth/ (事实面)            │
                │   输出 → _delivery/ (交付面)         │
                │   输出 → X1/X2/X3 治理策略           │
                └───────────────────────────────────┘
```

### 1.3 三层治理模型

| 层 | 角色 | 当前状态 | 目标 |
|----|------|---------|------|
| **战略** | 方向、目标、原则 | 手动 goals/current.yaml | OMO 自动跟踪 Phase 进展 |
| **战术** | 计划、决策、标准 | 手动 standards/ + _knowledge/ | OMO CLI 辅助决策记录 |
| **执行** | 任务、验证、交付 | debt 自动化 + 其余手动 | 全平面 CLI 覆盖 |

---

## 二、战术层: OMO × 5+3+1 分层扩展方案

### 2.1 L0 — 协议治理

当前: `projects/runtime/protocols/L0-registry.yaml` — 16 协议纯手动维护

扩展:
```
omo protocol list                   → 已有 (runtime CLI)
omo protocol validate               → 已有 (runtime CLI)
omo protocol register <name> ...    → 新增: 注册协议到 L0 注册表
omo protocol check-dead             → 新增: 检测 60 天未更新的协议
```

整合路径: `omo protocol *` 命令代理到 `runtime protocol *`，但同时在 OMO 治理面记录协议变更到 `_truth/registry/`。

### 2.2 L1 — 运行时刻治理

当前: `projects/runtime/src/runtime/` — 服务矩阵/健康扫描独立运行

扩展:
```
omo runtime status                  → 新增: 聚合 runtime 健康数据到 OMO 状态
omo runtime matrix list             → 代理到 runtime matrix list
omo runtime audit                   → 新增: 将 KEI 审计摘要写入 _delivery/
```

整合路径: OMO 通过 I0(Agora) 查询 runtime Matrix 状态，将健康评分写入 `_truth/registry/system-health.yaml`。

### 2.3 L2 — 内核融合治理

当前: 三平面各自独立，OMO 只管理自己的 .omo/ 目录

扩展:
```
omo kernel status                   → 新增: 聚合三平面健康度
omo kernel sync                     → 新增: 同步 OMO 治理决策到 kairon/gbrain
omo kernel drift                    → 新增: 检测三平面之间的状态偏差
```

整合路径: 通过 I0(Agora) 的 `tools/call` 统一接口，查询 kairon 和 gbrain 的健康状态，与 OMO 治理状态对比。

### 2.4 L3 — 入口治理

当前: 多入口无统一治理

扩展:
```
omo entry list                      → 新增: 列出所有已注册入口 (Hermes/Claude/Codex/ACP)
omo entry authorize                 → 新增: 授权/撤销入口能力
omo entry log                       → 新增: 查看各入口近期活动
```

整合路径: 在 `_truth/registry/entry-registry.yaml` 维护入口注册表。

### 2.5 L4 — 自我层整合

当前: `~/Documents/` 个人文档体系与 `.omo/` 治理体系完全分离

扩展:
```
omo self sync                       → 新增: 将 CARDS 追踪同步到 .omo/tasks/
omo self dashboard                  → 新增: 将 L4 驾驶舱状态同步到 OMO 健康评分
omo self archive                    → 新增: 归档 L4 已完成项到 _delivery/
```

整合路径: 双向同步 → `~/Documents/驾驶舱/CARDS/` ←→ `.omo/tasks/active/`。

### 2.6 I0 — 集成织层治理

当前: Agora 运行在 kairon 内，其服务发现/路由状态 OMO 无法感知

扩展:
```
omo i0 status                       → 新增: 查询 Agora 注册的 19 个服务状态
omo i0 route list                   → 新增: 查看 Agora 路由表
omo i0 audit                        → 新增: 检查跨层通信合规性 (是否绕过 Agora)
```

整合路径: OMO 调用 Agora MCP 工具 (`register_service`, `check_health` 等) 获取运行态数据。

### 2.7 X1 / X2 / X3 — 跨切面治理

当前: X1-X3 是概念定义，在 `_truth/` 中有 YAML 定义但无运行时

| 横切面 | 当前 | 扩展 |
|--------|------|------|
| **X1 治理安全** | `x1-governance-policies.yaml` 存在 | `omo x1 policy add/list/check` |
| **X2 抗熵** | `x2-lifecycle-rules.yaml` 存在 | `omo x2 freshness scan/report/heal` |
| **X3 价值栈** | `x3-value-stack.yaml` 存在 | `omo x3 cost estimate/allocate/track` |

---

## 三、执行层: 分 Phase 实施路线图

### Phase 29: OMO CLI 核心扩展 (1-2 周)

**目标**: 让 `omo` 命令覆盖 debt 之外的第一个平面

```
输出:
  omo goal list        — 读取 goals/current.yaml
  omo goal status      — 显示 Phase 目标完成百分比
  omo knowledge list   — 列出 _knowledge/ 下所有文档
  omo delivery list    — 列出 _delivery/ 下所有交付物
  omo standard list    — 列出 standards/ 下所有标准
  omo state show       — 显示 system.yaml 关键指标
```

实现方式: 每个命令都是读取对应 YAML/Markdown 目录的轻量封装。**不需要修改任何 .omo/ 文件结构**。

### Phase 30: OMO × Runtime 桥接 (2-3 周)

**目标**: OMO 能感知运行时状态

```
输出:
  omo runtime sync               — KEI 审计摘要 → _delivery/
  omo state refresh               — 从 Matrix 更新服务健康 → system_health.yaml
  omo x2 freshness scan           — 扫描所有服务 freshness
```

实现方式: `projects/omo/` 添加 `omo_runtime.py` 模块，通过 `httpx` 调用 Agora MCP / runtime CLI。

### Phase 31: OMO × I0(Agora) 整合 (2-3 周)

**目标**: OMO 通过 Agora 感知全系统

```
输出:
  omo i0 status                   — Agora 注册服务列表
  omo i0 route list               — Agora 路由表
  omo kernel status               — 三平面健康聚合
  omo x1 policy check             — 治理策略合规检查
```

### Phase 32: 全平面工具体系 (2-3 周)

**目标**: 所有平面都有 CLI 入口

```
输出:
  omo protocol register           — L0 协议注册
  omo entry list                  — L3 入口注册表
  omo self sync                   — L4 → OMO 同步
  omo x3 cost estimate            — X3 成本估算
```

---

## 四、架构原则

### 4.1 增量扩展，不动现有结构

- **不修改现有 .omo/ 文件结构** — 只在现有目录上添加读取/写入功能
- **不重构 projects/omo/ 现有的 60 个文件** — 新增模块按 `omo_{plane}.py` 方式添加
- **不改变 debt 工具链** — debt 已是 15 子命令的成熟系统

### 4.2 CLI 优先，Web 其次

```
第一优先:  omo <plane> <action>     — CLI 命令
第二优先:  omo <plane> --json      — JSON 输出供其他工具消费
第三优先:  omo dashboard --serve   — Web 仪表板
```

### 4.3 三层状态模型

```
观测层 (observe):    omo <plane> list/status/show
决策层 (decide):     omo <plane> authorize/approve/register
执行层 (execute):    omo <plane> dispatch/sync/archive
```

每个平面至少实现"观测层"，可选实现"决策层"和"执行层"。

---

## 五、长远战略图景

### 12 个月后的 OMO

```
OMO v5 作为真正的"治理操作系统":

  人类设计师
      │  (制定目标、审核决策)
      ▼
  ┌─────────────────────────────────────┐
  │  OMO Governance OS                  │
  │                                     │
  │  ┌─────────┐  ┌─────────┐  ┌─────┐ │
  │  │ 战略引擎 │  │ 战术引擎 │  │执行  │ │
  │  │ (Phase) │  │(决策)   │  │引擎  │ │
  │  └────┬────┘  └────┬────┘  └──┬──┘ │
  │       │            │          │     │
  │       └─────┬──────┴──────────┘     │
  │             │                       │
  │       ┌─────▼──────┐                │
  │       │  I0(Agora) │  ← 运行时感知  │
  │       └─────┬──────┘                │
  │             │                       │
  │   ┌─────────┼─────────┐             │
  │   ▼         ▼         ▼             │
  │  OMO      kairon    gbrain          │
  │  治理面    引擎面     记忆面         │
  └─────────────────────────────────────┘
      │  (输出: 审计报告、Phase 验收、债务报告)
      ▼
  归档到 _delivery/
```

### 关键里程碑

| 里程碑 | 时间 | 标志 |
|--------|------|------|
| M1: OMO CLI 全平面覆盖 | ~2 weeks | `omo * list/status` 覆盖全部 10 个子系统 |
| M2: OMO × Runtime 桥接 | ~4 weeks | OMO 无需手动写 health_score |
| M3: OMO × Agora 整合 | ~6 weeks | OMO 能感知全系统 32 服务状态 |
| M4: 全平面工具体系 | ~8 weeks | 所有平面有"观测-决策-执行"三层 |
| M5: AI 辅助治理 | ~12 weeks | OMO 自动生成 Phase 建议/债务预警 |
