---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史设计/历史/评审/图表批量归档, 当前活跃设计以 design/INDEX.md + PANORAMA.md 为准"
---
# Phase 6 细化方案 — 依赖自动维护 + 视图

> **文档编号**: 27 | **前序**: #26 Phase 5 复盘
> **定位**: Phase 6 的细化执行计划（24-AAMF-v2 的第 6 阶段）
> **当前治理状态**: 12 CLI, 26 节点, 34 治理日志, 24 约束

---

## 一、Phase 6 整体目标

### 一句话

**从"手动维护"到"自动闭环"—— sniff 发现差异 → 自动修复 → 可视化决策。Phase 6 填的是抗熵层的运行时维护缺口 + 价值层的可视化缺口。**

### 三支柱

```
Phase 6
├── 依赖自动维护 (X2 抗熵层)
│   ├── 6.1 sniff-deps --auto-fix        — 连续 3 次 observation → update-node
│   ├── 6.2 依赖时效性检查               — 冷 dep 标记 + 降级 SOFT
│   └── 6.7 自评价 Level 2              — 治理有效性量化
│
├── 可视化 (X3 价值层)
│   ├── 6.3 C4 Context                    — 系统边界图
│   ├── 6.4 C4 Container                  — 节点拓扑图增强
│   ├── 6.5 Archimate                     — 三层分层图
│   └── 6.6 健康仪表盘 HTML              — 交互式仪表盘
│
└── 集成
    └── cron 链扩展 + drift-check 增强
```

### 与现有治理体系的关系

```
现有体系:                                           Phase 6 追加:
arcnode-sniff-deps --reconcile        ─────────→    --auto-fix (闭环)
  ↓ observation                                     依赖时效检查 (7d/30d)
arcnode-evolve --self-report          ─────────→    自评价 Level 2 (治理有效性评分)
arcnode-graph --html                  ─────────→    --format c4 / --format archimate
arcnode-evolve --dashboard            ─────────→    交互式 HTML 仪表盘
```

---

## 二、6.1 sniff-deps --auto-fix

### 现状

`arcnode-sniff-deps --reconcile` 已能 sniff 运行时差异并写入 observation 日志。但 observation 仅记录不修复。

### 闭环逻辑

```
第一次 sniff → observation (置信度=1)
第二次 sniff → observation (置信度=2)
第三次 sniff → observation (置信度=3) → AUTO-FIX TRIGGERED
                                         ↓
                                   arcnode-sniff-deps --auto-fix
                                         ↓
                                   调用 agora-update-node 追加缺失依赖
                                         ↓
                                   写入治理日志: action=auto-fix-deps
```

### 具体实现

```python
# 扩展 arcnode-sniff-deps（新增 --auto-fix 标志）

def auto_fix(data: dict) -> int:
    """处理 observation 队列，置信度≥3 的自动修复。
    
    1. 从 governance log 统计每个 (node_id, description) 的 observation 次数
    2. 置信度 ≥ 3 → 触发自动修复
    3. 调用 agora-update-node 追加缺失依赖
    4. 写入 governance log: action=auto-fix-deps
    5. 返回修复数量
    """
    
# 触发规则:
# - undeclared connection 连续 3 次观察 → 调用 agora-update-node 追加 dependency
# - HARD dep offline 连续 3 次 → 写入 observation 但不 auto-fix（需要人工确认真实原因）
```

### 门禁

| 条件 | 动作 |
|------|------|
| undeclared 置信度 ≥ 3 | auto-fix (追加 dependency) |
| undeclared 置信度 < 3 | 等待下次 sniff |
| HARD offline 置信度 ≥ 3 | 观察不修复（标记为架构债务） |
| HARD offline 置信度 < 3 | 等待下次 sniff |

### 产出

- `arcnode-sniff-deps` 新增 `--auto-fix` 标志
- 修改现有 `--reconcile` 逻辑，支持 auto-fix 调用 `agora-update-node`

---

## 三、6.2 依赖时效性检查

### 问题

声明了 `depends_on` 但运行时从未连接过的依赖 → 配置噪声。

### 规则

| 场景 | 阈值 | 动作 |
|------|------|------|
| 声明的 HARD dep 连续 7 天无运行时连接 | 7 天 | 标记 "idle-hard-dep" → 写入 observation |
| 声明的 SOFT dep 连续 7 天无运行时连接 | 7 天 | 标记 "idle-soft-dep" → 写入 observation |
| 任何 dep 连续 30 天无连接 | 30 天 | 自动降级 SOFT→OPTIONAL |
| observation 持续 14 天未解决 | 14 天 | 升级为架构债务 |

### 实现方式

**新增独立脚本**: `arcnode-dep-aging` 或作为 `arcnode-sniff-deps --aging` 子模式

```bash
arcnode-dep-aging [--snapshot PATH] [--dry-run]
```

- 读取 `governance_log/runtime-deps.json` 的历史快照
- 对比上次 sniff 的端口连接记录 → 判断是否存在连接
- 标记空闲依赖 → 写入 observation / 降级

### 数据结构

```json
{
  "node_id": "agent-runtime",
  "dep_id": "agora",
  "level": "SOFT",
  "last_seen_connected": null,
  "idle_days": 14,
  "action": "idle-dep-warning"
}
```

### 依赖

- 需要治理日志中包含至少一次 sniff 快照（已有 `runtime-deps.json`）
- 需要 `arcnode-sniff-deps` 每次运行时记录时间戳

---

## 四、6.3-6.5 C4 + Archimate 视图

### 现状

`arcnode-graph` 已有 `--format html`（vis.js 交互图）和 `--format dot` / `--format mermaid`。

### C4 四层视图

```
C4 Context        → 系统边界图 (governance-system 与外部系统的关系)
C4 Container     → 容器图 (26 节点按 7 种 MetaType 分组)
C4 Component     → 组件图 (每个节点的 provides/depends_on 内部)
C4 Code          → 代码视图 (ARCH_NODE.yaml 声明级)
```

### Archimate 三层视图

```
Business Layer   → 治理流程 · 宪法修订 · 热插拔审批
Application Layer → validate/reason/drift-check/report CLI
Technology Layer  → ARCH_NODE.yaml · governance log · git
```

### 实现

**扩展 `arcnode-graph`**:

```bash
arcnode-graph --format c4       # 输出 C4 context 图 (HTML)
arcnode-graph --format c4 --level container   # C4 container 图
arcnode-graph --format c4 --level component   # C4 component 图
arcnode-graph --format archimate              # Archimate 三层图 (HTML)
```

### C4 Context 图设计

```html
<!-- 系统边界框 -->
System Boundary: "AAMF Architecture"

  Person: "Architect (Human)" ←→ governance-system
  System: "eCOS / Kronos / Minerva" ← external
  System: "Git / launchd / macOS" ← infra

governance-system (EVOLVER) 
  → 管理 26 节点
  → 依赖 agent-runtime (SOFT)
```

### C4 Container 图设计

```html
<!-- 按 MetaType 分组的容器图 -->
Container: "PROCESSOR" (8个)
  agent-runtime, kos, minerva, ecos, ...

Container: "SERVICE" (5个)
  agora, iris, agentmesh, forge, ...

Container: "EVOLVER" (1个)
  governance-system

<!-- 带依赖箭头 -->
agent-runtime → agora (SOFT)
gateway → agora (HARD)
```

### Archimate 图设计

```html
Business Layer:
  [Governance Flow] → [Constitution Amend] → [Hotswap Approval]
  ↑ 由 governance-system 驱动

Application Layer:
  [validate] → [reason] → [register] → [update]
  [drift-check] → [evolve] → [report] → [graph]
  ↑ 12 CLI 工具

Technology Layer:
  [ARCH_NODE.yaml] [governance.jsonl] [Git]
  [launchd] [Mac mini M4] [SSH to MBP]
  ↑ 基础设施层
```

---

## 五、6.6 健康仪表盘 HTML

### 现状

`arcnode-evolve --dashboard` 目前只输出 ⚠️ 提示。

### 仪表盘设计

```html
Dashboard Layout:
┌──────────────────────────────────────────────────┐
│  架构健康仪表盘 · 2026-05-28                      │
├─────────────────┬────────────────────────────────┤
│ 架构熵趋势       │ 节点健康度热力图                 │
│ (折线图, 周粒度) │ (行=节点, 列=漂移维度)          │
├─────────────────┼────────────────────────────────┤
│ 约束违反率       │ Observation 处理速度            │
│ (饼图)           │ (柱状图)                        │
├─────────────────┼────────────────────────────────┤
│ 决策追溯时间线                                     │
│ (历史治理事件, 按时间轴展示)                       │
└──────────────────────────────────────────────────┘
```

### 数据源

| 面板 | 数据源 |
|------|--------|
| 熵趋势 | `governance_log/entropy-trend.json` |
| 健康热力图 | `last-drift.json` + `runtime-deps.json` |
| 约束违反率 | governance log 扫描 (status ≠ PASS) |
| 观察处理速度 | governance log (observation vs auto-fix 比例) |
| 决策追溯 | governance log (action, ts, hash) |

### 技术方案

使用 Plotly.js（CDN 加载）生成交互式图表，不需要后端服务。纯 HTML 文件，浏览器直接打开。

```python
def generate_dashboard() -> str:
    """生成 HTML 仪表盘。"""
    # 1. 读取 entropy-trend.json → 熵折线图
    # 2. 读取 last-drift.json → 热力图
    # 3. 扫描 governance log → 约束饼图 + 处理速度 + 时间线
    # 4. 渲染为单页 HTML（Plotly.js CDN）
```

### 输出

```bash
arcnode-evolve --dashboard

# 输出:
✅ Dashboard saved to ~/.hermes/architecture/governance_log/dashboard.html
```

---

## 六、6.7 自评价 Level 2

### 现状

`arcnode-evolve --self-report` 已输出基于熵的健康度评分，但指标较浅。

### Level 2 新增指标

| 指标 | 定义 | 公式 | 健康范围 | 数据源 |
|------|------|------|---------|--------|
| **约束违反率** | 活跃约束违反数 / 总约束数 | `violations / 24` | < 10% | governance log |
| **观察处理速度** | 已解决的 observation / 总 observation | `resolved / total` | > 80% | governance log |
| **治理时效性** | 从 detection 到 log 的平均时间 | avg(log.ts - detect.ts) | < 1 分钟 | governance log |
| **往返时间** | observation → auto-fix 的平均天数 | avg(fix.ts - first_obs.ts) | < 7 天 | governance log |
| **宪法时效性** | 最后修订距今 | now - last_constitution_update | < 90 天 | git log |
| **GIT 同步年龄** | 最后 git commit 距今 | now - last_git_commit | < 7 天 | git log |

### 修改范围

扩展 `arcnode-evolve` 的 `self_report()` 函数：
- 新增 `_calc_constraint_rate()` — 扫描 governance log
- 新增 `_calc_observation_speed()` — 统计 resolved / total
- 新增 `_calc_gov_lag()` — 时间差计算
- 新增 `_calc_turnaround()` — auto-fix 往返时间
- 新增 `_calc_constitution_age()` — git log 分析
- 更新评分公式

---

## 七、cron 链扩展

### 当前（Phase 5 结束）

```
每日 5:00 drift-check       ← 四维漂移 + 嗅探
每日 6:00 evolve            ← 熵趋势 + auto-fix + 自报告
周一 7:00 graph             ← 依赖图更新
周一 9:00 resolve           ← unresolved 队列
周一 9:30 report            ← 完整周报
```

### Phase 6 后

```
每日 5:00 drift-check             ← 四维漂移 + 嗅探
每日 6:00 evolve + self-report    ← 熵趋势 + auto-fix + 自评价 L2
每日 6:05 sniff --auto-fix        ← 依赖自动修复 ← NEW
每日 6:10 dep-aging               ← 依赖时效性检查 ← NEW

周一 7:00 graph + c4              ← C4/Archimate 图更新 ← NEW
周一 9:00 resolve                 ← unresolved 队列
周一 9:30 report + dashboard      ← 周报 + 仪表盘 ← NEW
```

### 说明

- `dep-aging` 在 `sniff` 之后 5 分钟运行，确保数据新鲜
- `graph + c4` 在周一 7:00 更新所有图类型
- `dashboard` 在报告后重新生成，包含最新数据

---

## 八、任务分解

### 优先级排序

| 优先级 | ID | 任务 | 工时 | 前置 | 价值 |
|--------|----|------|------|------|------|
| **P0** | 6.1 | sniff-deps --auto-fix | 4h | — | 依赖闭环核心 |
| **P0** | 6.6 | 健康仪表盘 HTML | 6h | — | 决策可视化核心 |
| **P1** | 6.7 | 自评价 Level 2 | 4h | 6.6 | 治理量化 |
| **P1** | 6.2 | 依赖时效性检查 | 4h | 6.1 | 配置噪声清理 |
| **P2** | 6.3 | C4 Context 视图 | 3h | — | 可视化 |
| **P2** | 6.4 | C4 Container 视图 | 3h | 6.3 | 可视化 |
| **P2** | 6.5 | Archimate 视图 | 3h | 6.4 | 可视化 |

### 执行顺序

```
Step 1: 6.6 健康仪表盘 (最直观的产出, 先看到效果)
Step 2: 6.1 sniff-deps --auto-fix (依赖闭环)
Step 3: 6.2 依赖时效性检查 (冷清理)
Step 4: 6.7 自评价 Level 2 (量化治理)
Step 5: 6.3 C4 Context (第一步可视化)
Step 6: 6.4 C4 Container (深化)
Step 7: 6.5 Archimate (完善)
Step 8: 复盘文档落盘
```

---

## 九、验收标准

### 6.1 sniff-deps --auto-fix

```bash
# 模拟 3 次 sniff → auto-fix 触发
arcnode-sniff-deps --reconcile --auto-fix
→ 0 auto-fixes (第一次, 置信度不够)

# 模拟再多跑 2 次...
arcnode-sniff-deps --reconcile --auto-fix
→ 1 auto-fix: node-X → added dependency on node-Y
```

### 6.2 依赖时效性检查

```bash
arcnode-dep-aging --dry-run
→ 3 deps marked idle (7d+), 1 eligible for SOFT downgrade (30d+)
```

### 6.3-6.5 C4 + Archimate

```bash
arcnode-graph --format c4 --level context
→ 生成 ARCHITECTURE_C4_CONTEXT.html (系统边界图)

arcnode-graph --format c4 --level container
→ 生成 ARCHITECTURE_C4_CONTAINER.html (容器拓扑图)

arcnode-graph --format archimate
→ 生成 ARCHITECTURE_ARCHIMATE.html (三层分层图)
```

### 6.6 健康仪表盘

```bash
arcnode-evolve --dashboard
→ arch_root/governance_log/dashboard.html (交互式 HTML)
→ 包含: 熵折线图 + 健康热力图 + 约束饼图 + 处理速度 + 时间线
```

### 6.7 自评价 Level 2

```bash
arcnode-evolve --self-report
→ 包含: 约束违反率 < 10%, 观察处理速度 > 80%, 治理时效 < 1m, 往返时间 < 7d
```

---

## 十、风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| sniff --auto-fix 误修复 | 低 | 中 | 连续 3 次 observation 才触发（已实现） |
| 仪表盘 HTML 过大 | 中 | 低 | 分页加载，每个面板独立 chart div |
| C4 视图太抽象 | 中 | 低 | 保持现有 HTML 交互式，C4 作为额外 format |
| archimate 三层不直观 | 低 | 低 | 用不同背景色区分三层 |

---

> **文档位置**: `~/Documents/学习进化/基建架构/27-Phase6-细化方案.md`
> **前序**: #26 Phase 5 复盘
> **下一步**: 确认后从 Step 1 (6.6 健康仪表盘) 开始执行
