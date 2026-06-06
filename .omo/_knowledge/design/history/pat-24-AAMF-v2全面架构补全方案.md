# AAMF v2 — 全面架构补全方案

> 文档编号: 24 | 前序: #23 Phase 3 复盘
> 定位: 从治理层到自我层的完整架构蓝图
> 原则: 模型驱动 · 本体论完整 · 渐进实现 · 可验证

---

## 一、现状 vs 蓝图

### 当前 AAMF 治理体系覆盖了什么

```
X1 治理层 ✅ (85%)
├── 宪法 + Schema (8 章, 18 约束)
├── 10 CLI 脚本 (validate/reason/graph/drift/sniff/report/register/update)
├── 25 节点注册 (6 类型全覆盖)
├── 28 条治理日志 (SHA256 链式校验)
├── cron 巡检链 (每日 5:00 + 周一 7:00→9:00→9:30)
└── git 版本控制
```

### 原始蓝图缺失了什么

| 层 | 定位 | 状态 | 核心能力 |
|----|------|------|---------|
| **S2 进化层** | 持续进化 | ❌ 空 | 熵趋势分析、自动修复、元模型扩展 |
| **X2 抗熵层** | 运行时韧性 | 🔶 半空 | 热插拔(空)、依赖自动维护(半)、跨机器拓扑(空) |
| **L4 自我层** | 系统自管理 | ❌ 空 | 自注册、自评价、自优化、自进化 |
| **X3 价值层** | 可视化决策 | ❌ 空 | C4 视图、Archimate、健康仪表盘、决策追溯 |

### 核心缺陷

**治理系统自身不受治理。** 现有的 AAMF 治理体系管理其他 24 个节点，但没有注册自身。这意味着：
- 治理体系的架构声明不存在（无 ARCH_NODE.yaml）
- 治理体系的依赖关系未定义（depends_on 缺如）
- 治理体系的健康度不可追踪

**这违反了架构的第一原则：管理系统的架构也必须受管理。**

---

## 二、本体论扩展

### 元模型（M2）扩展

当前: **6 MetaType × 6 MetaRelation** → 目标: **7 MetaType × 10 MetaRelation**

#### 新增 MetaType

| 类型 | 标识 | 定义 | 约束 |
|------|------|------|------|
| **EVOLVER** | 进化器 | 负责熵趋势分析、自动修复、元模型管理的系统组件 | 必须提供进化分析能力；必须有 EVALUATE 关系 |

EVOLVER 的 engine/actor 分类：**engine**（接受指令按指令执行，无自主目标）。

#### 新增 MetaRelation

| 关系 | 定义 | 合法类型对 | 约束 |
|------|------|-----------|------|
| **REPLACE** | 节点 A 替换节点 B（热插拔） | PROCESSOR→PROCESSOR, SERVICE→SERVICE, TOOL→TOOL, STORE→STORE, GATEWAY→GATEWAY, AGENT→AGENT | 同类型替换；接口旧⊆新；版本严格递增 |
| **EVOLVE** | 类型/节点 A 进化自类型/节点 B | MetaType→MetaType, EVOLVER→任何类型 | 进化必须保留向下兼容性 |
| **OBSERVE** | 治理系统观察被管节点 | EVOLVER→PROCESSOR/SERVICE/TOOL/STORE/GATEWAY/AGENT | 观察结果必须写入治理日志 |
| **EVALUATE** | 进化器评估节点健康度 | EVOLVER→PROCESSOR/SERVICE/TOOL/STORE/GATEWAY/AGENT | 评估必须基于客观指标 + LLM 语义分析 |

### 约束扩展

| 约束 | 类型 | 定义 | 代码化 |
|------|------|------|--------|
| **S7** | Schema | 所有节点必须有 lifecycle.manager 定义 | `arcnode-validate` |
| **S8** | Schema | 所有节点必须有 governance.audit_events | `arcnode-validate` |
| **T7** | Type | EVOLVER 必须提供 trend_analysis 能力 | `arcnode-validate --strict` |
| **R4** | Runtime | REPLACE 操作必须先验证 R2+R3+R10 | `agora hotswap` |
| **R5** | Runtime | OBSERVE 结果必须 7 天内处理或升级 | `arcnode-evolve` |
| **R6** | Runtime | EVALUATE 分数 < 0.3 必须触发告警 | `arcnode-evolve` |
| **G4** | Governance | governance-system 自身必须注册为 AGENT 节点 | self-register 脚本 |
| **G5** | Governance | 治理日志必须包含 governance-system 自身的操作 | `arcnode-evolve` |

---

## 三、S2 进化引擎设计

### 核心指标：架构熵

```
e(node) = (src_missing * 3 + port_down * 2 + health_fail * 1 + gov_missing * 2) / 8

整体熵: E(system) = avg(e(node)) for all registered nodes

ΔE/Δt = 熵变化率 (每周)
```

### 进化触发阈值

| E 范围 | 状态 | 动作 |
|--------|------|------|
| < 0.1 | 健康 | 记录基线，无动作 |
| 0.1–0.3 | 注意 | 写入 observation，建议 review |
| 0.3–0.6 | 警告 | 触发进化引擎根因分析 |
| ≥ 0.6 | 危机 | 自动冻结新注册，升级人工 |

| ΔE/Δt | 意义 | 动作 |
|--------|------|------|
| > 0.05/周 | 熵增趋势 | 进化引擎分析根因，建议宪法修订 |
| < -0.05/周 | 熵减趋势 | 记录成功模式到 governance log |

### 观察置信度积累

```
auto_fix_threshold = 3    # 连续 3 次 observation → auto-fix
confidence_decay = 7d     # 7 天无新 observation → 置信度归零
escalation_delay = 14d    # 14 天未解决 → 升级为架构债务
```

### 架构组件

```
arcnode-evolve (EVOLVER 类型节点)
├── 输入: drift-check 快照 / sniff-deps 观察 / governance log
├── 处理:
│   ├── entropy_analyzer    — 熵趋势计算
│   ├── pattern_detector    — 模式识别
│   ├── fix_recommender     — 修复建议生成
│   └── meta_model_advisor  — 元模型扩展建议
└── 输出: governance log observation / auto-fix / proposal
```

### 脚本设计

```bash
arcnode-evolve [--entropy] [--trend] [--auto-fix] [--proposal]
  --entropy:    输出当前架构熵值 + 各节点熵
  --trend:      输出 ΔE/Δt 熵趋势 (周)
  --auto-fix:   处理 observation 队列 (置信度≥3 的 auto-fix)
  --proposal:   输出元模型扩展/宪法修订建议
  --self-report:输出治理体系自身健康度
```

---

## 四、热插拔机制设计

### 节点状态机

```
ACTIVE ──→ DRAINING ──→ STANDBY ──→ VERIFYING ──→ ACTIVE (new)
  │                                           │
  └──→ DECOMMISSIONED (old node) ←────────────┘
  
  状态: 
  - ACTIVE: 正常工作状态 (95% 时间)
  - DRAINING: 停止接受新请求, 等待 in-flight 完成
  - STANDBY: 旧进程暂停, 新进程已启动
  - VERIFYING: 运行 R2+R3+R10 验证
  - DECOMMISSIONED: 旧节点标记为已废弃
```

### 协议步骤

```
Step 1: 标记目标节点为 "replacing"
  → governance log entry: action="hotswap", status="draining"
  
Step 2: 通知 HARD 依赖方
  → 写入 governance log: "node X is draining, expect downtime"
  
Step 3: 排空 (drain)
  → 等待 lifecycle.startup_duration_sec + 超时
  → 超时未完成 → 回滚到 ACTIVE
  
Step 4: 启动新进程
  → lifecycle.manager == launchd: launchctl bootstrap
  → lifecycle.manager == manual: 输出脚本等待人工执行
  
Step 5: 验证 (R2 + R3 + R10)
  → R3: 旧 provides ⊆ 新 provides
  → R2: 新节点 HARD 依赖可达
  → R10: 新节点 health_check OK
  
Step 6: 切换路由
  → 更新 ARCH_NODE.yaml (旧→新版本)
  → 通知依赖方重连
  
Step 7: 清理旧节点
  → lifecycle.manager == launchd: launchctl bootout
  → 旧节点 ARCH_NODE.yaml 标记 lifecycle.status = "decommissioned"
  → governance log entry: action="hotswap", status="completed"
```

### 降级链

```
auto (launchd) → semi-auto (systemd/supervisor) → manual (通知+脚本)
```

### CLI

```bash
agora hotswap <node-id> [--new-yaml PATH] [--force] [--dry-run]
  --dry-run: 只验证不执行 (检查 R2+R3, 输出步骤)
  --force:   跳过 R3 兼容性检查 (紧急热修复)
```

---

## 五、运行时依赖自动维护

### 闭环逻辑

```
sniff-deps → observation (连续 3 次) → auto-fix → governance log
                                        │
                                  未满 3 次 → 等待下次 sniff
```

### 触发规则

| 场景 | 阈值 | 动作 |
|------|------|------|
| sniff 发现未声明连接 | 连续 3 次 | 自动注册 dependency → `agora-update-node` |
| 声明的 HARD dep 连续 7 天无连接 | 7 天 | 标记为 "idle-hard-dep" → 写入 observation |
| 声明的 dep 连续 30 天无连接 | 30 天 | 自动降级 SOFT → 通知 review |
| 同一个 observation 持续 14 天未解决 | 14 天 | 升级为架构债务 |

### 实现

扩展 `arcnode-sniff-deps --reconcile --auto-fix`：
```
--auto-fix: 连续 3 次 observation → 自动调用 agora-update-node
```



---

## 六、自注册：governance-system 节点

### ARCH_NODE.yaml

```yaml
architecture_node:
  id: "governance-system"
  name: "AAMF Governance System — 架构治理系统自身"
  meta_type: EVOLVER
  version: "1.0.0"
  meta:
    description: "管理所有架构节点的治理系统。自身也受同一宪法约束。"
    tags: ["governance", "self-reference", "evolution", "meta"]
    source: "~/.hermes/architecture/"
    source_type: "python+yaml"
  provides:
    - id: "governance.validate"
    - id: "governance.drift-check"
    - id: "governance.evolve"
    - id: "governance.hotswap"
    - id: "governance.report"
    - id: "governance.constitution"
  depends_on:
    - id: "agent-runtime"    # LLM Reasoner 依赖
      dependency: SOFT
    - id: "kos"              # 知识检索（可选）
      dependency: OPTIONAL
  lifecycle:
    manager: "manual"
    health_check: "/dev/null"  # 治理系统无 HTTP 端点
  governance:
    audit_events: true
```

### 约束

- governance-system 受 S1-S8, T1-T7, R1-R6, G1-G5 全部约束
- governance-system 的变更必须在 governance log 中记录
- governance-system 的 drift-check 自身必须有健康检查

---

## 七、L4 自我层设计

### 三层自指能力

```
Level 1 — 自描述 (Phase 4)
  能力: 生成自身架构报告、依赖图包含自身节点
  验证: arcnode report 中包含 "governance-system"

Level 2 — 自评价 (Phase 6)
  能力: 评估自身治理有效性 (约束违反率、熵趋势、observation 处理速度)
  验证: arcnode-evolve --self-report 输出健康度评分

Level 3 — 自进化 (Phase 7)
  能力: 元模型变更提议、宪法修订建议
  验证: 进化引擎提议 → 人类确认 → 宪法自动修订
```

### 自我评估指标

| 指标 | 定义 | 健康范围 |
|------|------|---------|
| 约束违反率 | 活跃约束违反数 / 总约束数 | < 10% |
| 观察处理速度 | 已解决的 observation / 总 observation | > 80% |
| 熵趋势 | ΔE/Δt | < 0.02/周 |
| 治理延迟 | 从 detection 到 log 的平均时间 | < 1 分钟 |
| 宪法时效性 | 最后修订距今 | < 90 天 |

---

## 八、X3 价值堆栈：可视化

### C4 多视角视图

```
arcnode-graph --format c4

├── Context: 系统边界图 (governance-system 与外部系统关系)
├── Container: 容器图 (25 节点按类型分组)
├── Component: 组件图 (每个节点的 provides/depends_on 内部)
└── Code: 代码视图 (ARCH_NODE.yaml 声明级)
```

### Archimate 分层视图

```
Business Layer: 治理流程 · 宪法修订流程 · 热插拔审批
Application Layer: validate/reason/drift-check/report CLI
Technology Layer: ARCH_NODE.yaml · governance log · git
```

### 健康仪表盘

```bash
arcnode-evolve --dashboard
```
输出 HTML 仪表盘，包含：
- 架构熵趋势折线图 (周粒度)
- 节点健康度热力图 (行=节点, 列=漂移维度)
- 约束违反率饼图
- observation 处理速度柱状图
- 决策追溯时间线

---

## 九、实施 Roadmap

### Phase 4: 进化引擎 + 自注册 (2 周)

| ID | 任务 | 工时 | 前置 | 产出 |
|----|------|------|------|------|
| 4.1 | government-system 自注册 | 4h | — | ARCH_NODE + governance log |
| 4.2 | 元模型扩展 (EVOLVER/REPLACE/EVOLVE/OBSERVE/EVALUATE) | 4h | 4.1 | meta_types.md + constraints.md 修订 |
| 4.3 | 宪法修订 (S7-S8/T7/R4-R6/G4-G5 追加) | 4h | 4.2 | CONSTITUTION.md v2 |
| 4.4 | arcnode-evolve --entropy | 6h | 4.1 | 熵计算 + 趋势追踪 |
| 4.5 | arcnode-evolve --auto-fix | 6h | 4.4 | 观察置信度积累 + auto-fix |
| 4.6 | arcnode-evolve --self-report | 4h | 4.1 | 自评价报告 |
| 4.7 | evolution cron (每日 6:00) | 1h | 4.5 | 进化引擎每日运行 |
| 4.8 | Phase 4 复盘 + 红队 | 3h | 4.1-4.7 | #25 文档 |

### Phase 5: 热插拔 (2 周)

| ID | 任务 | 工时 | 前置 | 产出 |
|----|------|------|------|------|
| 5.1 | 节点状态机实现 | 6h | 4.2 | status 变更流水线 |
| 5.2 | drain 机制 | 4h | 5.1 | 排空 + 超时回滚 |
| 5.3 | launchd 热插拔集成 | 4h | 5.1 | launchctl bootstrap/bootout |
| 5.4 | manual 降级（通知脚本） | 3h | 5.1 | 热插拔 → 人工执行脚本 |
| 5.5 | `agora hotswap` CLI | 4h | 5.2-5.4 | 完整命令 + dry-run |
| 5.6 | 热插拔测试 (模拟+真实) | 4h | 5.5 | 测试套件 |
| 5.7 | hotswap governance log | 2h | 5.5 | 日志 + SHA256 |
| 5.8 | Phase 5 复盘 | 2h | 5.1-5.7 | #26 文档 |

### Phase 6: 依赖自动维护 + 视图 (2 周)

| ID | 任务 | 工时 | 前置 | 产出 |
|----|------|------|------|------|
| 6.1 | sniff-deps auto-fix | 4h | 4.5 | 3 次 observation → update-node |
| 6.2 | 依赖时效性检查 | 4h | 6.1 | 冷 dep 标记 + 降级 |
| 6.3 | C4 Context 视图 | 4h | — | 系统边界图 HTML |
| 6.4 | C4 Container 视图 | 4h | 6.3 | 节点拓扑图增强 |
| 6.5 | Archimate 视图 | 4h | 6.4 | 三层分层图 |
| 6.6 | 健康仪表盘 HTML | 6h | 6.5 | 交互式仪表盘 |
| 6.7 | 自评价 Level 2 | 4h | 4.6 | 治理有效性评分 |
| 6.8 | Phase 6 复盘 | 2h | 6.1-6.7 | #27 文档 |

### Phase 7: L4 自我层 (3 周)

| ID | 任务 | 工时 | 前置 | 产出 |
|----|------|------|------|------|
| 7.1 | 元模型变更控制流程 | 6h | 6.7 | 版本化元模型 |
| 7.2 | 宪法修订自动化 | 6h | 7.1 | proposal→approve→amend 流水线 |
| 7.3 | 架构模式识别 | 8h | 4.4 | 从历史数据学习模式 |
| 7.4 | 自进化验证 | 6h | 7.2-7.3 | 端到端测试 |
| 7.5 | 终极自指测试 | 4h | 7.4 | governance-system 替换自身 |
| 7.6 | 最终复盘 | 4h | 7.5 | 完整架构报告 + 文档 |

---

## 十、验收标准

### Phase 4 验收

```bash
arcnode validate ~/.hermes/architecture/arch_nodes/governance-system.yaml --strict
→ PASS (S1-S8, T1-T7, G1-G5)

arcnode-evolve --entropy
→ E(system) = 0.12, 3 节点有漂移

arcnode-evolve --auto-fix --dry-run
→ 0 auto-fix ready (confidence < 3)

arcnode-evolve --self-report
→ 治理体系健康度: 92% (约束违反率 2/18)
```

### Phase 5 验收

```bash
agora hotswap agent-runtime --dry-run
→ 步骤 1-7 输出, 无实际执行

agora hotswap agent-runtime --new-yaml arch_nodes/agent-runtime-v2.yaml
→ ✅ 替换完成 (验证 R2+R3+R10)
```

### Phase 6 验收

```bash
arcnode-sniff-deps --reconcile --auto-fix
→ 0 observation → auto-fix (0 置信度 > 3)

arcnode-graph --format c4
→ 4 视图文件 (context/container/component/code)

arcnode-evolve --dashboard
→ HTML 仪表盘 (熵趋势/健康热力图/约束率/处理速度)
```

### Phase 7 验收

```bash
arcnode-evolve --self-report
→ 健康度: 95%, 指标 > 全部健康范围

# 终极验证: 治理系统替换自身
agora hotswap governance-system --new-yaml arch_nodes/governance-system-v2.yaml
→ ✅ 自指闭环完成
```

---

## 十一、关键设计决策

| # | 决策 | 选项 | 选择 |
|---|------|------|------|
| 1 | EVOLVER 的 engine/actor | engine / actor | **engine** — 进化器接受指令，不做自主决策 |
| 2 | 自注册的 meta_type | AGENT / EVOLVER / SERVICE | **EVOLVER** — 新建类型明确语义 |
| 3 | 热插拔的 drain 方式 | 超时自动 / 手动确认 / in-flight 计数 | **超时自动** — 超时后回滚，避免死锁 |
| 4 | auto-fix 的触发阈值 | 1次 / 3次 / 5次 | **3 次** — 平衡响应速度和错误率 |
| 5 | 宪法修订的门禁 | 人工确认 / LLM 自动 / 委员会投票 | **LLM 提议 + 人工确认** — Phase 7 可升级 |
| 6 | C4 视图 vs Archimate | 二选一 / 两个都做 | **都做** — C4 技术层, Archimate 治理层 |
| 7 | governance-system 的 lifecycle | manual / ephemeral | **manual** — 治理体系不应自动重启 |

---

## 十二、总结

### 从 Phase 0 到 Phase 7 的完整旅程

```
Phase 0: 审计发现           → 5 个核心问题
Phase 1: 宪法落盘           → 8 章宪法 + 18 约束
Phase 2: 21 节点注册        → 7 步注册流水线
Phase 3: 可视化+报告        → 依赖图 + drift + 周报
────────────────────────────────────────────
Phase 4: 进化引擎+自注册     → 治理系统自我管理
Phase 5: 热插拔              → 节点替换不断服
Phase 6: 自动维护+视图       → 闭环基础设施
Phase 7: L4 自我层           → 系统自我进化
```

### 一句话

**从"管理别人的系统"到"管理系统还能管理自己"——补全的不是功能，是元层级的一致性。**

---

> **文档位置**: `~/Documents/学习进化/基建架构/24-AAMF-v2-全面架构补全方案.md`
> **前序**: #23 Phase 3 复盘
> **当前 Phase**: Phase 3 ✅ → 待确认 Phase 4 启动
