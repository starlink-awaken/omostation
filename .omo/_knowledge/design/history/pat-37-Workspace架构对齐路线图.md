# 全面规划：Workspace CLI × 4+1+3 架构对齐路线图

> 编制日期: 2026-05-26
> 当前基线: 28.5/100 🔴
> 下一目标: 80/100 🟢
> 文档位置: `~/Documents/学习进化/基建架构/37-全面规划-Workspace×架构对齐路线图.md`

---

## 目录

1. [现状总览](#1-现状总览)
2. [根因分析](#2-根因分析)
3. [差距深度分析](#3-差距深度分析)
4. [战略方向](#4-战略方向)
5. [战术路径](#5-战术路径)
6. [执行方案（4 Phase）](#6-执行方案4-phase)
7. [可落地性验证](#7-可落地性验证)
8. [风险与缓解](#8-风险与缓解)
9. [附录：产品健康度计算框架](#9-附录产品健康度计算框架)

---

## 1. 现状总览

### 1.1 现有资产

| 资产类别 | 数量 | 状态 |
|---------|------|------|
| **架构文档** | 41 篇文档 (34编号+6宪法+1README) | 🟢 完备 |
| **治理体系 (AAMF)** | 27 节点 / 26 约束 / 15 CLI / 33 SHA256日志 | 🟢 75/100 |
| **治理 Cron** | 8 道任务 | 🟢 运行中 |
| **workspace CLI** | 8 命令 / 18 research子命令 / 2249行 cli.py | 🟡 v0.1.0 |
| **测试** | 54 测试 / 0.13s / 全绿 | 🟢 |
| **4+1+3 架构覆盖** | L4 10% / L3 15% / L2 35% / L1 75% / X1 25% / X2 10% / X3 10% | 🔴 28.5% |

### 1.2 当前产品健康度基线

```
Product Health Score = 架构对齐度(28.5%) × 用户旅程完整度(80%) × 产品原则满足率(60%)
                     = 13.7% 🔴
```

三重衰减后分数低是正常的——**看趋势，不看绝对值**。目标是在4个Phase内提升5倍。

---

## 2. 根因分析

### 2.1 根因链 1：架构设计缺失 — 产品界面层在 4+1+3 中没有位置

```
产品初始构想(5/23) → 快速迭代 → 4+1+3 作为系统架构定稿
→ 产品入口(workspace CLI) 是事后追加 → 不属于任何层
→ 造成 P0 vs 4+1+3 天然不对齐
```

**事实**：4+1+3 是开发者眼中的系统架构（"系统由什么组成"），
workspace CLI 是用户眼中的产品界面（"用户从哪进入"）。
两者不是替代关系，但缺少一个**桥接层**。

### 2.2 根因链 2：执行路径偏差 — 治理工作自然"吃掉"产品投入

```
治理工作有明确边界(节点/约束/日志/基线分数)
→ 可完全自主完成(不需要用户决策)
→ 反馈即时(测试通过/分数上升)
→ 自然吸引 90% 投入

产品工作需要用户体验设计决策
→ 需要更高认知投入
→ 用户确认延迟
→ 被治理工作"挤出" → 仅10%投入
```

**事实**：3天里治理做了 Phase 1-11，产品只做了 Phase 1-4。

### 2.3 根因链 3：反馈回路缺失 — 产品没有"测试套件"

```
治理有即时反馈: calibrate → 75/100 → 明确"有效"
产品缺少验证: status 显示什么? 用户觉得好用吗? → 没有量化指标
→ 产品缺陷累积无感知 → 直到目标纠偏审计才发现28.5%
```

### 2.4 根因总结

| # | 根因 | 类型 | 修复策略 |
|---|------|------|---------|
| 1 | 4+1+3 缺少 P0(产品界面层) | 设计问题 | 架构中显式定义 P0 层 |
| 2 | 治理工作的"低反馈路径"吸引度 | 执行问题 | 30/70 资源约束 + 产品门禁 |
| 3 | 产品缺少量化健康度指标 | 反馈问题 | 建立产品健康度计算和监控 |

---

## 3. 差距深度分析

### 3.1 逐层条件满足度

| 层 | 当前分数 | 目标分数 | 差距 | 核心缺失 |
|----|---------|---------|------|---------|
| **L4 自我层** | 10% | 70% | **60pp** | 身份/愿景/原则在 CLI 中无体现 |
| **L3 协作层** | 15% | 60% | **45pp** | 单用户/无 Agent 标记/无共享平面 |
| **L2 能力层** | 35% | 80% | **45pp** | 片段式 MCP/无统一调用 |
| **L1 契约层** | 75% | 90% | **15pp** | 缺 identity/event 导出 |
| **X1 治理** | 25% | 70% | **45pp** | 缺身份/授权/免疫模型 |
| **X2 抗熵** | 10% | 60% | **50pp** | 无保鲜/无自动回收 |
| **X3 价值堆栈** | 10% | 60% | **50pp** | 无半衰期/无引用链 |

**关键发现**：L1 契约层是唯一接近目标（75→90）的层。
其他层全在 10-35%，需系统提升。

### 3.2 用户旅程 vs 架构层映射

```
用户操作              → 需要哪层       → 当前状态
workspace demo        → P0(引导)       → ✅ 存在
workspace research    → L2(MCP能力)    → 🟡 自实现SQLite
workspace status      → P0(工作台)     → ✅ Phase 2改造
workspace daily       → P0(简报)       → ✅ Phase 3改造
workspace help        → P0(地图)       → ✅ Phase 4新增
workspace profile     → L4(身份)       → ❌ 不存在
workspace contracts   → L1(契约)       → ✅ 但缺identity
workspace governance  → X1(审计)       → ✅ 委派arcnode-*
保鲜/自动归档         → X2(抗熵)       → ❌ 不存在
热力图/半衰期          → X3(价值堆栈)   → ❌ 不存在
```

### 3.3 技术债务

| 债务 | 位置 | 影响 |
|------|------|------|
| workspace CLI 直接操作 SQLite | `storage.py` | 🔴 无法热插拔、无法复用 |
| 治理 arcnode-* 独立脚本 | `~/.hermes/scripts/` | 🟡 已委派但未统一 |
| 治理基线存储在文件系统而非 MCP | `calibration/` | 🟡 不可被 Agora 发现 |
| research engine 有3级降级但无统一调用 | `cli.py:200-415` | 🟡 冗余代码 |

---

## 4. 战略方向

### 4.1 核心命题

> **如何在不暴露 4+1+3 复杂度的情况下，让 workspace CLI 用户自动获得每一层的能力？**

### 4.2 三大战略支柱

```
┌─────────────────────────────────────────────────────────────┐
│  支柱1: P0 层定义 — 产品界面层                              │
│  4+1+3 + P0                                                │
│  P0翻译层: L4→Profile / L3→Agent标记 / L2→MCP调用         │
│           L1→Contracts / X1→Governance / X2→保鲜 / X3→热力图│
├─────────────────────────────────────────────────────────────┤
│  支柱2: 产品治理闭环                                        │
│  产品健康度 = 架构对齐×旅程完整×原则满足                    │
│  每次Phase完成自动基线检测                                  │
│  ≥70%产品投入强制执行                                       │
├─────────────────────────────────────────────────────────────┤
│  支柱3: 统一MCP调用路径                                     │
│  workspace CLI → Agora MCP → Backend服务                    │
│  不再直接操作SQLite                                         │
│  治理数据通过 Agora 注册，不独立存储                        │
└─────────────────────────────────────────────────────────────┘
```

### 4.3 P0 层在 4+1+3 中的定位

P0 不是第5层——它是一个**横切界面层**，将 L4-L1 + X1-X3 翻译为用户可理解的操作：

```
P0: 产品界面层
┌────────────────────────────────────────────────┐
│ workspace CLI                                  │
│ profile | research | import | status | daily   │
│ contracts | governance | help | demo           │
└────────────────┬───────────────┬───────────────┘
         ↓调用         ↓委派          ↓加载
     L2能力层    X1治理脚本      L1契约Schema
     L4身份       X2保鲜策略     L3协作事件
                   X3价值计算
```

---

## 5. 战术路径

### 5.1 各层修复策略

| 层 | 修复策略 | 优先度 | 工作量估时 |
|----|---------|--------|-----------|
| **P0 定义** | 架构文档更新 + workspace profile | P0 | 2h |
| **L4 自我** | workspace profile + PERSONA.yaml 加载 | P1 | 1h |
| **L2 统一** | research backend → Agora MCP 调用 | P1 | 3h |
| **L1 补全** | contracts export --identity/--event | P1 | 1h |
| **X2 基**础 | daily 保鲜提示 + 自动归档策略 | P2 | 1.5h |
| **L3 基础** | research --agent 标记 | P2 | 1h |
| **X3 基础** | half-life 计算 + heatmap | P3 | 2h |
| **产品健康度** | product-health 脚本 + 基线 | P0 | 1h |

### 5.2 30/70 资源分配

```
每个 Phase 的资源分配:
├── 产品(≥70%): P0/L4/L2/L1 → workspace CLI 新功能
├── 治理(≤30%): X1/X2/X3 → 仅在 Phase 计划内按需接入
```

---

## 6. 执行方案（4 Phase）

### 6.1 Phase A — 产品界面层落地 ⭐ 当前阶段

**目标**: 28.5% → 45% 架构对齐度 / 产品健康度 13.7% → 27%

**时间估时**: 4-6 小时（约 1 次会话）

**交付清单**:

| # | 任务 | 文件 | 估时 |
|---|------|------|------|
| A1 | 更新架构文档: 在 09-* 和 README 中定义 P0 层 | `09-*.md` | 20min |
| A2 | 创建 workspace profile 命令 + PERSONA.yaml | `cli.py` + `~/.workspace/persona.yaml` | 40min |
| A3 | 创建 product-health 计算脚本 | `~/.hermes/scripts/product-health` | 30min |
| A4 | research backend → Agora MCP 调用（第一步: 只读） | `storage.py` / `cli.py` | 90min |
| A5 | 产品健康度首次基线采集 | 自动 | 10min |
| A6 | 54 tests + product-health 验证 | `pytest` | 10min |

**Phase A 验收门禁**:

```bash
workspace profile                   # 应显示当前身份/角色
workspace product-health            # 应输出分数 ≥ 27%
workspace research --list           # 应还能正常使用(backend迁移后)
pytest -q                           # 54 passed
```

**回滚路径**:
- `git revert 41974fb` 回退到 Phase 1-4 完成状态
- 删除 `~/.workspace/persona.yaml` 回退 profile
- 恢复 `storage.py` 到 SQLite 直连版

---

### 6.2 Phase B — 契约补全 + 抗熵基础

**目标**: 45% → 60% / 产品健康度 27% → 43%

**时间估时**: 3-4 小时

**交付清单**:

| # | 任务 | 文件 | 估时 |
|---|------|------|------|
| B1 | contracts export --identity (IdentityEnvelope) | `cli.py` | 30min |
| B2 | contracts export --event (EventEnvelope) | `cli.py` | 30min |
| B3 | daily 增加保鲜提示（3天未操作研究显示"🧊"警告） | `cli.py:cmd_daily` | 20min |
| B4 | status 工作台增加"待归档"标记 | `_render_workbench` | 20min |
| B5 | 自动归档 cron 策略（可配置天数阈值） | `~/.hermes/scripts/auto-archive` | 30min |
| B6 | 产品健康度第二阶段基线 | 自动 | 10min |

**Phase B 验收门禁**:

```bash
workspace contracts export --identity 1   # 输出 IdentityEnvelope JSON
workspace contracts export --event 1      # 输出 EventEnvelope JSON
workspace daily                           # 旧研究显示保鲜警告
pytest -q                                 # 54+ passed
product-health                            # 分数 ≥ 43%
```

---

### 6.3 Phase C — 协作基础 + 价值堆栈

**目标**: 60% → 70% / 产品健康度 43% → 60%

**时间估时**: 4-5 小时

**交付清单**:

| # | 任务 | 文件 | 估时 |
|---|------|------|------|
| C1 | research --agent <name> 标记处理 Agent | `cli.py` + `storage.py` | 30min |
| C2 | research --heatmap 热力图（按活跃度/追问/发布） | `cli.py` | 40min |
| C3 | 半衰期计算（最后活跃时间+追问频率→衰减曲线） | `storage.py` | 40min |
| C4 | Agora MCP 注册 workspace CLI 操作 | `agora/registry/` | 60min |
| C5 | workspace research --agent 在 dossier/timeline 中显示 | `cli.py` | 20min |
| C6 | 产品健康度第三阶段基线 | 自动 | 10min |

**Phase C 验收门禁**:

```bash
workspace research --tag 1 --agent name   # 显示标记
workspace research --heatmap              # 显示热力图
workspace research --dossier 1            # 显示 Agent 信息
Agora MCP tools | grep workspace          # Agora 可发现 workspace 操作
pytest -q                                 # 全绿
product-health                            # 分数 ≥ 60%
```

---

### 6.4 Phase D — 自动化闭环 + 产品治理成熟

**目标**: 70% → 80% / 产品健康度 60% → 75%

**时间估时**: 4-5 小时

**交付清单**:

| # | 任务 | 文件 | 估时 |
|---|------|------|------|
| D1 | 研究自动保鲜 cron（按半衰期阈值自动提醒） | `cronjob` | 30min |
| D2 | 产品健康度自动监控（每日 cron + 微信推送） | `cronjob` + `~/.hermes/scripts/` | 40min |
| D3 | 治理-产品双基线对比（governance calibrate vs product-health） | `~/.hermes/scripts/` | 30min |
| D4 | 全链路 E2E 验证 test | `tests/test_e2e_journey.py` | 60min |
| D5 | 产品健康度最终基线 | 自动 | 10min |
| D6 | 更新所有架构文档对齐 P0 层定义 | 多文档 | 30min |

**Phase D 验收门禁**:

```bash
# 全链路 E2E
workspace import ~/Desktop/test.md          ✅
workspace research --list                   ✅ 显示新记录
workspace research --open 1                 ✅ 显示全文
workspace research --ask 1 "追问"           ✅
workspace research --publish 1 --style brief ✅
workspace research --dossier 1              ✅ 关系网络
workspace research --timeline 1             ✅ 时间线
workspace research --archive 1              ✅

# 监控
product-health                              # 分数 ≥ 75%
governance calibrate --check                # 治理分数稳定

pytest -q                                   # 全绿
```

---

## 7. 可落地性验证

### 7.1 每个 Phase 的可执行要素

| 要素 | Phase A | Phase B | Phase C | Phase D |
|------|---------|---------|---------|---------|
| 具体文件改动 | ✅ 已列出 | ✅ 已列出 | ✅ 已列出 | ✅ 已列出 |
| 验证命令 | ✅ 有验收门禁 | ✅ | ✅ | ✅ |
| 基线提升公式 | ✅ 45%目标 | ✅ 60% | ✅ 70% | ✅ 80% |
| 回滚路径 | ✅ git revert | ✅ 逐个回滚 | ✅ | ✅ |
| 工作量估时 | 4-6h | 3-4h | 4-5h | 4-5h |
| 产品投入占比 | ≥70% | ≥70% | ≥70% | ≥70% |

### 7.2 产品健康度计算脚本

创建 `~/.hermes/scripts/product-health`（Phase A 任务 A3），
该脚本自动计算:

```python
product_health = (
    arch_alignment_score  # 来自36-审计的逐层打分
    * journey_completeness  # E2E链路完成度: 实现的旅程/总旅程
    * principle_satisfaction  # 5条产品原则满足率(AGENTS.md检查)
)
```

输出格式:
```
Product Health Score: 27% 🟡
├── 架构对齐度: 45% (目标: 80%)
├── 用户旅程完整度: 85% (目标: 95%)
├── 产品原则满足率: 70% (目标: 95%)
└── 对比上次: +13% ↑
```

### 7.3 守门员规则

| 规则 | 内容 |
|------|------|
| **产品门禁** | 每次 Phase 开始前必须回答"这Phase服务哪条产品原则?" |
| **30/70 约束** | 每个 Phase 结束后检查: 产品投入 ≥ 70% |
| **基线门禁** | 每个 Phase 结束后 product-health 必须提升 |
| **测试门禁** | pytest 必须全绿才能推进下一Phase |
| **回滚门禁** | 每个 Phase 必须有回滚路径文档 |

---

## 8. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| Agora MCP 迁移影响现有功能 | 中 | 🔴 | Phase A 第一步只做只读，先并行再切换 |
| 产品健康度分数受三重衰减影响长期低 | 高 | 🟡 | 文档声明"看趋势不看绝对值"，每Phase目标提升15pp |
| 治理工作再次挤出产品投入 | 中 | 🔴 | 30/70 约束 + 产品门禁 + 每次Phase开始前拒绝治理任务 |
| workspace CLI 只有一个开发者 | 低 | 🟡 | 估时保守(4-6h/Phase)，确保一次会话完成 |
| 架构文档 vs 实际代码再次漂移 | 中 | 🟡 | Phase D 专门安排文档对齐任务 |

---

## 9. 附录：产品健康度计算框架

### 9.1 架构对齐度计算（7 维度加权）

| 维度 | 权重 | Phase A目标 | Phase D目标 | 测量方法 |
|------|------|------------|------------|---------|
| P0 产品界面层 | 15% | 60% | 90% | 命令覆盖率 |
| L4 自我层 | 10% | 40% | 70% | profile 存在性 |
| L3 协作层 | 10% | 20% | 60% | agent 标记 |
| L2 能力层 | 20% | 60% | 80% | MCP 调用路径 |
| L1 契约层 | 15% | 80% | 90% | contracts 完备性 |
| X1 治理安全 | 10% | 40% | 70% | governance 接入 |
| X2 抗熵 | 10% | 30% | 60% | 保鲜/回收 |
| X3 价值堆栈 | 10% | 20% | 60% | 半衰期计算 |

### 9.2 用户旅程完整度

| 旅程段 | 当前 | Phase A | Phase D |
|--------|------|---------|---------|
| import→research→open | ✅ | ✅ | ✅ |
| →ask→publish | ✅ | ✅ | ✅ |
| →dossier→timeline | ✅ | ✅ | ✅ |
| →archive→restore | ✅ | ✅ | ✅ |
| →profile/identify | ❌ | ✅ | ✅ |
| →heatmap/half-life | ❌ | ❌ | ✅ |

### 9.3 产品原则满足率（5 条检查）

| 原则 | 当前 | Phase A | Phase D |
|------|------|---------|---------|
| 结果优先 | 80% | 85% | 95% |
| 一条路径 | 60% | 70% | 95% |
| 旅程完整 | 70% | 80% | 95% |
| 渐进披露 | 50% | 60% | 95% |
| 系统有记忆 | 50% | 55% | 95% |

---

> **当前阶段: Phase A 待启动**
> 如需推进，回复"启动 Phase A" 或 "先做 A1" 等具体指令。
