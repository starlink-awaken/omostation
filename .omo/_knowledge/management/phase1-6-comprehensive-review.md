# Phase 1-6 全面 Review 报告

> 日期: 2026-05-31 | 状态: 最终稿
> 范围: OMO 系统 Phase 1 至 Phase 6 的全面审阅
> 评估维度: 整体架构、应用场景、功能模块、使用方式、核心流程

---

## 目录

1. [整体架构演进](#一整体架构演进)
2. [应用场景覆盖](#二应用场景覆盖)
3. [功能模块交付](#三功能模块交付)
4. [使用方式演变](#四使用方式演变)
5. [核心流程定义](#五核心流程定义)
6. [全阶段汇总表](#六全阶段汇总表)
7. [跨阶段缺陷与改进建议](#七跨阶段缺陷与改进建议)

---

## 一、整体架构演进

### Phase 1：基础设施补完 —— 从"能跑"到"协同跑"

**起点态**: 5 个独立项目（kairon、SharedBrain、agentmesh、gbrain、ops）各自运行，Agora service mesh 已有但连通性未验证，MCP 协议不统一，无集成测试。

**目标态**: 4 个核心系统全部就位并开始协同工作。

```
用户入口 (wksp CLI / Agora Dashboard)
         │
    Agora Service Mesh (100+ MCP tools)
   ┌─────┼─────┬─────┬─────┐
   │     │     │     │     │
SharedBrain  kairon  agentmesh  gbrain  ops
(合规控制)  (知识栈)  (运行时)  (记忆)  (运维)
```

**架构交付**:
- Agora 服务网格全面连通性验证（MCP 标准化 + 动态路径注册）
- LiteLLM 作为 LLM 路由层接入 agentmesh
- sharedbrain-bridge 包实现 SharedBrain ↔ kairon 的 EU 计价/免疫/同步
- memU TypeScript 引擎替代原计划 Rust 实现（兼容性 > 60% 阈值后决策 GO）

**架构特征**: 星形拓扑，Agora 为中心枢纽。项目边界清晰但耦合松散，治理信息分散。

---

### Phase 2：知识能力深化 —— 从"通路"到"能力"

**起点态**: 基础设施通路已建立，但知识层缺乏结构化存储、搜索、和协作安全保障。

**目标态**: 知识操作栈完善，具备死锁检测/恢复、搜索（BFS/DFS/语义）、Obsidian 双向同步、信任评分、EU 追踪。

**架构新增**:
- **L1 契约层 (5包)** — core-models、eidos、family-models、work-models、media-models
- **L2 能力层 (10包)** — kronos、minerva、sophia、ontoderive、ssot、codeanalyze、eu-pricing、token-juicer、memory-tree、bf-search
- **L3 协作层 (8包)** — forge、kos、iris、cross-domain、kems-runtime、trust-layer、skill-router
- **L4 元层 (8包)** — agent-runtime、metaos、ecos、cron-service、wksp、family-os、kos-health、device-orchestrator

**架构特征**: 四层包结构（L1-L4）正式确立。kairon 从 19 包扩展至 ~30 包。治理机制第一次接到运行时（provider plane、LiteLLM route seam、agent runtime wiring 真实打通）。

---

### Phase 3：自我进化闭环 —— 从"能力"到"闭环验证"

**起点态**: 能力包已存在但各自为战，LLM 调用方式碎片化（不同仓库使用不同 provider/env 配置），无统一验收标准。

**目标态**: 统一 LLM contract、落地 capability slice、自动化验收。

**架构交付**:
- `LLM_PROVIDER / LLM_BASE_URL / LLM_API_KEY / LLM_MODEL` 四统一 contract
- Capability slice：KOS / Minerva / MetaOS / Iris / gbrain 五个系统的关键能力串接
- `scripts/phase3_acceptance.py` — 可重复执行的完成态验证脚本

**架构特征**: 第一次实现跨仓库协议统一。`scripts/phase3_acceptance.py` 定义了 218 测试/6 套件的验收基线。OMO 从"文档仓库"进化为"治理执行 + 验收"操作台。

**健康评分**: 88/100

---

### Phase 4：Worker Ops 生产化 —— 从"试点"到"默认底座"

**起点态**: Worker 协作机制存在但偏手工，dispatch 频次低、checkpoint 产物浅、协同流程依赖手工组织。

**目标态**: Worker dispatch 自动化、checkpointed reclaim、consistency auto-gate 落地。

**架构交付**:
- `scripts/omo worker dispatch` — 自动生成 dispatch/prompt/review/reclaim 文件
- `scripts/omo worker status` — 汇总 active dispatch、worker、checkpoint 数量
- `scripts/omo worker reclaim` — 标记前序 dispatch 为 reclaimed
- `scripts/sync_omo_state.py` — 自动 divergence flags 检测
- Wave 2: lifecycle gate hardening + divergence triage + worker utilization baseline + handoff index

**架构特征**: `.omo` 治理机制从"描述计划"正式升级为"回写真实状态、任务、证据"。四平面架构概念萌芽（control/truth/knowledge/delivery 职责开始分化）。

**健康评分**: 90/100

---

### Phase 5：治理正式化 —— 四平面架构 + 着陆模型冻结

**起点态**: 工作机制存在但缺乏正式架构模型，计划/执行/复盘的模式已形成但未固化。

**目标态**: 四平面架构形式化、着陆模型冻结、governed worker execution。

**架构交付**:
1. **四平面架构** — `_control/`（控制面/驾驶舱）、`_truth/`（事实面/SSOT）、`_knowledge/`（知识面/手册库）、`_delivery/`（交付面/货架）
2. **着陆模型冻结** — task-center ownership、secrets（secret_ref model）、proposals（proposal model）、Hermes convergence（Direction A）
3. **Packet 模式** — plan + task + evidence + retrospective 的波浪工作模式制度化
4. **Skill Federation 概念** — 跨 worker 技能联合执行机制设计

**架构特征**: 四平面架构从概念变为正式约束。`.omo` 目录结构重构（`_control/`、`_truth/`、`_knowledge/`、`_delivery/` 作为导航壳 + 约束层）。治理层不再与运行时执行混为一谈。

---

### Phase 6：运行时实现 —— 从"冻结设计"到"真实运行时"

**起点态**: 四平面架构已完成设计冻结，但 checkpoint/lease/watchdog、discovery registry、skill federation 还是设计文档。

**目标态**: 把 Phase 5 冻结的 durable/governance/discovery/templates/skill 转成真实运行时。

**架构交付**:
1. **Wave 1 — 运行时核心**：
   - proposal-governed truth mutation runtime（提案治理的真实变更运行时）
   - checkpoint / lease / watchdog durability path（检查点/租约/看门狗持久化路径）
   - divergence scope 收紧到当前阶段活动工作
2. **Wave 2 — 发现 + 模板**：
   - blueprint discovery registry（蓝图发现注册表）
   - governed template instantiation into valid task packets（受治理的模板实例化）
3. **Wave 3 — 技能联合**：
   - skill manifest truth records（技能清单事实记录）
   - governed skill-to-task bridge（受治理的技能到任务桥接）

**最终架构**:

```
                    ┌────────────────────────┐
                    │       控制面 _control/   │
                    │  (驾驶舱 · 状态 · 门禁)   │
                    └──────┬─────────┬───────┘
                           │         │
                    ┌──────▼──┐  ┌──▼──────────┐
                    │ 事实面    │  │  知识面       │
                    │ _truth/  │  │ _knowledge/  │
                    │ (SSOT)   │  │ (设计/过程/     │
                    │          │  │  管理/使用/参考)│
                    └──────┬──┘  └──┬──────────┘
                           │         │
                    ┌──────▼─────────▼──────────┐
                    │       交付面 _delivery/     │
                    │  (运行记录 · 证据 · 产出)   │
                    └────────────────────────────┘
```

**健康评分**: 90/100 | **任务完成**: 85/87

---

## 二、应用场景覆盖

### Phase 1 覆盖场景

| 场景 | 描述 | 状态 |
|------|------|------|
| 系统集成验证 | 全链路 MCP 连通性（Agora ↔ SharedBrain ↔ kairon ↔ gbrain） | ✅ E2E 11/11 PASS |
| 记忆引擎 | gbrain 高性能记忆（memU TypeScript 引擎） | ✅ 27/27 测试 |
| LLM 路由 | LiteLLM 部署 + agentmesh 适配器 | ✅ 性能基线 P50 14.8ms |
| 基础设施弹性 | Docker 4/4 Healthy、故障注入 5/5 PASS | ✅ |
| 合规控制面接入 | SharedBrain EU 计价/免疫/身份/自愈 | ✅ 4/4 organ delegated |

### Phase 2 覆盖场景

| 场景 | 描述 | 状态 |
|------|------|------|
| 知识查询与存储 | KOS 查询/存储 + Consistency Check + 桥文件同步 | ✅ M2.0 |
| 死锁检测与恢复 | wait-for graph + timeout detection + victim selection | ✅ 60 测试 |
| 多策略搜索 | BFS/DFS/Semantic 三种搜索策略 + 缓存层 | ✅ 44 测试 |
| Obsidian 笔记同步 | Frontmatter 抽取 + 双向同步 | ✅ 51 测试 |
| 信任与安全 | Trust Graph Layer、Agent Registry (Ed25519 签名)、Agent Sandbox | ✅ |
| 成本追踪 | EU Pricing、Agora EU Middleware、agentmesh/gbrain EU Tracker | ✅ |
| 任务优先级调度 | Priority Queue、L2 Controller | ✅ |
| 免疫审计 | Pipeline Immune Audit Stage | ✅ 8 测试 |

### Phase 3 覆盖场景

| 场景 | 描述 | 状态 |
|------|------|------|
| LLM 协议统一 | 跨仓库统一 LLM_PROVIDER/BASE_URL/API_KEY/MODEL | ✅ |
| 知识编排 | KnowledgeClosedLoop（缓存→研究→保存→审计） | ✅ |
| 跨域研究 | Minerva cross-domain research | ✅ 3 测试 |
| Capability 路由 | KOS skill router | ✅ 3 测试 |
| wksp orchestration | 工作区编排 32 项测试 | ✅ |
| 记忆恢复 | gbrain memory & recovery | ✅ 175 测试 |
| 自动化验收 | phase3_acceptance.py 脚本化验收 | ✅ 218/218 |

### Phase 4 覆盖场景

| 场景 | 描述 | 状态 |
|------|------|------|
| Worker dispatch 自动化 | 自动生成 dispatch/prompt/review/reclaim 文件 | ✅ |
| Checkpointed reclaim | 带检查点和部分产物的 worker 恢复演练 | ✅ |
| Consistency gate | state/system.yaml 与 tasks 数量自动对账 | ✅ |
| Lifecycle gate | task active→done 的正式 promotion 条件 | ✅ |
| Divergence triage | 差异信号分级/归属/处置 | ✅ |
| Worker utilization | 周期性 worker 使用率基线 | ✅ |
| Handoff index | task/dispatch 证据链统一索引 | ✅ |

### Phase 5 覆盖场景

| 场景 | 描述 | 状态 |
|------|------|------|
| 治理正式化 | 四平面架构形式定义与约束 | ✅ |
| 着陆模型冻结 | task-center ownership / secrets / proposals / Hermes | ✅ |
| 波浪工作模式 | plan + task + evidence + retrospective 标准化 | ✅ |
| 技能联合设计 | skill federation 概念框架 | ✅ |
| 入口门禁 | 阶段切换的正式 entry gate | ✅ |

### Phase 6 覆盖场景

| 场景 | 描述 | 状态 |
|------|------|------|
| 提案治理运行时 | proposal-governed truth mutation | ✅ |
| 持久化路径 | checkpoint / lease / watchdog | ✅ |
| 蓝图发现 | blueprint discovery registry | ✅ |
| 模板实例化 | governed template → task packets | ✅ |
| 技能清单 | skill manifest truth records | ✅ |
| 技能→任务桥接 | governed skill-to-task bridge | ✅ |

---

## 三、功能模块交付

### Phase 1 交付清单

| 模块 | 类型 | 规模 |
|------|------|------|
| MCP 标准化修复 | 基础设施 | 2 个核心修复 (format_version + 动态路径) |
| sharedbrain-bridge 包 | 新交付 | 6 文件, uv pip install |
| memU 引擎 (TypeScript) | 新交付 | src/core/memu-engine.ts (866 行) |
| LiteLLM 适配器 | 新交付 | agentmesh litellm.ts |
| Docker 集成环境 | 基础设施 | 4/4 Healthy |
| E2E 测试套件 | 测试 | test-e2e-phase1.py (11 项) |
| 故障注入测试 | 测试 | test-fault-injection.py (5 场景) |
| 性能基线测试 | 测试 | test-perf-baseline.py (3 端点) |

### Phase 2 交付清单

| 模块 | 类型 | 规模 |
|------|------|------|
| KOS 知识操作栈 | 功能模块 | KOSSaveStage + KnowledgeClosedLoop + MCP tool |
| Deadlock Detector | 功能模块 | deadlock_detector.py (334 行) + 60 测试 |
| BFTS 搜索 | 功能模块 | bfs_search.py (334 行) + 44 测试 |
| Obsidian Connector | 功能模块 | obsidian.py + 51 测试 |
| Trust Graph Layer | 功能模块 | 信任评分层 |
| TokenJuicer | 功能模块 | 压缩层 |
| Model Garden | 功能模块 | 模型花园清单 |
| KEMS Runtime | 功能模块 | KEMS 运行时 |
| Agent Registry | 功能模块 | Ed25519 签名 + backup registry |
| Priority Queue | 功能模块 | 优先级任务调度器 |
| L2 Controller | 功能模块 | L2 级别任务控制器 |
| EU 追踪 (3 项目) | 功能模块 | agora + agentmesh + gbrain (15 测试) |
| Immune Audit Stage | 功能模块 | Pipeline 免疫审计 (8 测试) |

### Phase 3 交付清单

| 模块 | 类型 | 规模 |
|------|------|------|
| LLM Contract 统一 | 协议标准化 | 4 env var (PROVIDER/BASE_URL/API_KEY/MODEL) |
| Capability Slice | 集成 | 5 系统串接 (KOS/Minerva/MetaOS/Iris/gbrain) |
| Acceptance Runner | 工具 | scripts/phase3_acceptance.py |
| wksp CLI 增强 | 工具 | product-health 子命令修复 |
| Acceptance Report | 文档 | phase3-acceptance-report.md |

### Phase 4 交付清单

| 模块 | 类型 | 规模 |
|------|------|------|
| worker dispatch 脚本 | 工具 | scripts/omo worker dispatch |
| worker status 脚本 | 工具 | scripts/omo worker status |
| worker reclaim 脚本 | 工具 | scripts/omo worker reclaim |
| sync_omo_state.py | 工具 | 状态同步 + divergence flags |
| omo_metrics.py | 工具 | worker utilization baseline |
| omo_handoff_index.py | 工具 | handoff evidence 索引 |
| 测试套件 | 测试 | test_omo_automation.py |

### Phase 5 交付清单

| 模块 | 类型 | 规模 |
|------|------|------|
| 四平面架构 | 架构定义 | DOC-ARCH.md + 4 个 INDEX.md |
| 着陆模型 | 设计 | phase5-entry-architecture.md |
| Packet 模式 | 流程标准化 | plan + task + evidence + retrospective |
| Hermes 收敛策略 | 设计 | hermes-convergence-strategy.md (Direction A) |
| secret_ref 模型 | 设计 | secrets 引用模型 |
| proposal 模型 | 设计 | 提案治理模型 |
| 各 Wave 复盘 | 文档 | Wave 0-3 复盘报告 |

### Phase 6 交付清单

| 模块 | 类型 | 规模 |
|------|------|------|
| Proposal-governed runtime | 运行时 | truth mutation 治理 |
| Checkpoint/Lease/Watchdog | 运行时 | 持久化路径 |
| Blueprint discovery registry | 模块 | 蓝图发现注册表 |
| Template instantiation | 模块 | 模板→task packet 治理 |
| Skill manifest truth records | 模块 | 技能清单 SSOT |
| Skill-to-task bridge | 模块 | 受治理的技能桥接 |
| 治理测试 | 测试 | test_omo_governance.py |
| 发现测试 | 测试 | test_omo_discovery.py |
| 技能测试 | 测试 | test_omo_skill.py |

---

## 四、使用方式演变

### Phase 1：CLI 为主，MCP 为辅

```
使用入口: wksp CLI (4 命令: status/sync/eu/audit)
         + Agora Dashboard (Web UI)
         + LiteLLM (API 路由)
交互方式: 命令行 + HTTP API
自动化:   Docker Compose 管理容器生命周期
用户画像: 开发者/SRE
```

### Phase 2：CLI + MCP + Hermes 三通道

```
使用入口: wksp CLI → 扩展命令集
         + Agora 100+ MCP tools → IDE/Agent 调用
         + Hermes Agent (WeChat/IM/CLI/WebUI) — 初步接入
交互方式: 命令行 + MCP 协议 + 自然语言
自动化:   死锁自动检测/恢复、EU 自动追踪
用户画像: 开发者 + AI Agent
```

### Phase 3：验收脚本化

```
使用入口: wksp CLI → product-health 命令
         + phase3_acceptance.py → 一键验收
         + MCP tools → 知识闭环/研究/路由
交互方式: CLI + 自动化脚本 + MCP
自动化:   LLM 统一 contract 消除跨仓库配置碎片
用户画像: 开发者 + AI Agent + CI/CD
```

### Phase 4：Worker Ops 操作台

```
使用入口: scripts/omo worker dispatch|status|reclaim
         + scripts/sync_omo_state.py
         + scripts/omo_metrics.py (基线报告)
         + scripts/omo_handoff_index.py (证据链)
交互方式: CLI + 自动化脚本 + 周期性报告
自动化:   dispatch 自动生成、consistency gate 自动检测
用户画像: 开发者 + Agent Coordinator
```

### Phase 5：四平面导航

```
使用入口: _control/INDEX.md (驾驶舱) → 状态/门禁/目标
         + _truth/INDEX.md (SSOT 索引)
         + _knowledge/ (设计/过程/管理/使用)
         + _delivery/ (证据/运行记录)
         + Packet 模式: plan → task → evidence → retrospective
交互方式: 文档导航 + CLI + MCP + Hermes (多通道并行)
自动化:   entry gate 条件检查
用户画像: 开发者 + Agent Coordinator + 治理审计
```

### Phase 6：运行时一体化

```
使用入口: proposal → truth mutation (提案治理)
         + blueprint registry (蓝图发现)
         + template → task packet (模板实例化)
         + skill manifest → skill-to-task bridge (技能联合)
         + .omo/tests/ 全套治理测试
交互方式: CLI/脚本 + MCP + 自动治理
自动化:   checkpoint/lease/watchdog 自动维护
         divergence 自动检测与 flag
用户画像: 开发者 + AI Agent + 系统自身 (自运维)
```

### 演变总结

```
Phase 1:  CLI ─── MCP ─── (Web UI)
Phase 2:  CLI ─── MCP ─── Hermes ─── (CI)
Phase 3:  CLI ─── MCP ─── Hermes ─── CI (验收自动化)
Phase 4:  CLI ─── MCP ─── Hermes ─── CI ─── Worker Ops
Phase 5:  CLI ─── MCP ─── Hermes ─── CI ─── Worker Ops ─── 治理平台
Phase 6:  CLI ─── MCP ─── Hermes ─── CI ─── Worker Ops ─── 治理平台 ─── 自运维

通道演进: 单通道 → 双通道 → 三通道 → 多通道并行 → 平台化 → 自运维
```

---

## 五、核心流程定义

### 5.1 Task Lifecycle（跨 6 阶段)

```
Phase 1-2:  需求 → 实现 → 测试 → 文档    (线性)
Phase 3:    需求 → 实现 → 测试 → acceptance → 复盘 (加入验收)
Phase 4:    需求 → task YAML → dispatch → worker → reclaim → review → done (加入 Worker)
Phase 5:    plan → tasks → evidence → retrospective  (Packet 模式制度化)
Phase 6:    proposal → truth mutation → checkpoint → watchdog (提案治理运行时)
```

最终形态（Phase 6）：

```
goals/ → plans/ → tasks/active/ → worker dispatch → execution
    ↑                                                    ↓
    └───────── state/system.yaml ← sync_omo_state.py ← evidence/
                        ↓
              CONSISTENCY-CHECK.md / divergence flags
```

### 5.2 Worker Dispatch（Phase 4-6）

```
1. Coordinator 识别可分发任务
2. scripts/omo worker dispatch → 生成 checkpoint + dispatch YAML
3. External worker 接收 prompt → 执行 → 产出 evidence
4. 首次 worker 在 lease 窗口内留下 checkpoint
5. 如中断 → scripts/omo worker reclaim → successor 从 checkpoint 续跑
6. Worker 交付 → review → 证据归档
7. sync_omo_state.py 回写 task → done
```

### 5.3 Governance Pipeline（Phase 5-6）

```
proposal (提案)
    │
    ▼
proposal-governed truth mutation (治理的真实变更)
    │
    ├── checkpoint (检查点) ← 可回退
    ├── lease (租约) ← 时间窗口
    └── watchdog (看门狗) ← 异常检测
    │
    ▼
divergence triage (差异治理)
    ├── severity (严重度)
    ├── owner (责任人)
    └── disposition (处置策略)
    │
    ▼
四平面写入
    ├── _control/ → state/system.yaml 更新
    ├── _truth/ → SSOT 更新
    ├── _delivery/ → evidence 归档
    └── _knowledge/ → 复盘/设计文档更新
```

### 5.4 Skill Federation（Phase 5 概念 → Phase 6 运行时）

```
skill manifest (技能清单 SSOT)
    │
    ▼
blueprint discovery (蓝图发现注册表)
    │
    ▼
governed template instantiation (受治理的模板实例化)
    │
    ▼
skill-to-task bridge (技能→任务桥接)
    │
    ▼
worker dispatch → execution → evidence
```

### 5.5 核心流程演变对比

| 流程 | Phase 1 | Phase 2 | Phase 3 | Phase 4 | Phase 5 | Phase 6 |
|------|---------|---------|---------|---------|---------|---------|
| Task Lifecycle | 线性 | 线性+测试 | +验收 | +Worker | +Packets | +Runtime |
| Worker Dispatch | — | Pilot | — | 自动化 | 制度化 | 默认底座 |
| Governance | 无 | 机制萌芽 | 工具化 | gate | 四平面 | runtime |
| Verification | 手动 | 半自动 | 自动acceptance | auto-gate | 门禁+测试 | 全套测试 |
| Evidence | 无 | 无 | 无 | handoff index | 交付面 | 运行时证据 |

---

## 六、全阶段汇总表

### 6.1 总体状态

| 指标 | Phase 1 | Phase 2 | Phase 3 | Phase 4 | Phase 5 | Phase 6 |
|------|:-------:|:-------:|:-------:|:-------:|:-------:|:-------:|
| **健康评分** | 75 | 80 | 88 | 90 | 90 | 90 |
| **任务完成** | 21/21 | 20+/20+ | 218 test | Wave 1+2 | 4 Waves | 85/87 |
| **持续时间** | 1天 | 1天 | 1天 | 1天 | 1天 | 1天 |
| **新增包/模块** | 4+ | 20+ | 5+ | 6+ | 5+ | 6+ |

> 注：短期集中交付模式（每阶段约 1 天）导致时间维度不反映真实工作量。实际工作量以任务数和新模块数为准。

### 6.2 维度对照

| 维度 | Phase 1 | Phase 2 | Phase 3 | Phase 4 | Phase 5 | Phase 6 |
|------|:-------:|:-------:|:-------:|:-------:|:-------:|:-------:|
| **整体架构** | 星形拓扑 | 四层包结构 | 跨仓库统一 | Ops 底座 | 四平面正式 | 运行时实现 |
| **应用场景** | 连通性/记忆 | 知识/搜索/安全 | 闭环验证 | Worker协作 | 治理/标准 | 运行时自洽 |
| **功能模块** | 基础设施 | 知识栈/安全 | 验收/工具 | Ops 脚本 | 治理/设计 | 运行时/桥接 |
| **使用方式** | CLI+MCP | +Hermes | +CI | +Worker | +治理平台 | +自运维 |
| **核心流程** | 线性 | +测试 | +验收 | +Dispatch | +Packets | +Runtime |

### 6.3 架构复杂度演进

```
架构层级:                                         Phase
                                             1  2  3  4  5  6
  项目级: kairon/SharedBrain/agentmesh/gbrain  ✅ ✅ ✅ ✅ ✅ ✅
  Mesh级: Agora service mesh                    ✅ ✅ ✅ ✅ ✅ ✅
  治理级: goals/state/tasks/standards            ─ ─ ✅ ✅ ✅ ✅
  运营级: worker dispatch/reclaim                ─ ─ ─ ✅ ✅ ✅
  治理正式级: 四平面架构                          ─ ─ ─ ─ ✅ ✅
  运行时级: proposal/checkpoint/skill            ─ ─ ─ ─ ─ ✅
```

### 6.4 健康评分趋势

```
90 ┤                                          ● ● ●
88 ┤                                     ●
80 ┤                               ●
75 ┤                    ●
   └───────────────────────────────────────────
     Phase 1  Phase 2  Phase 3  Phase 4  Phase 5  Phase 6
```

评分提升主要驱动因素：
- Phase 1→2: 测试覆盖大幅增加（从 27 到 1000+）
- Phase 2→3: 验收自动化 + LLM 统一
- Phase 3→4: Worker Ops 生产化 + consistency gate
- Phase 4→6: 治理固化 + 运行时实现，维持在 90

---

## 七、跨阶段缺陷与改进建议

### 7.1 已识别跨阶段缺陷

| # | 缺陷 | 涉及阶段 | 严重度 | 当前状态 |
|---|------|---------|:------:|:--------:|
| D1 | KOS 对 gbrain SQLite 紧耦合 | Phase 2-6 | 中 | 未修复（Phase 3 已记录为风险） |
| D2 | E2E 测试需运行中服务集群 | Phase 2-6 | 高 | 未完全解决（仍依赖外部服务） |
| D3 | eu-pricing 无独立测试 | Phase 2-6 | 低 | 通过 agora 间接覆盖 |
| D4 | 跨仓库治理同步不一致 | Phase 2-6 | 中 | 部分推进（43 仓库未全部对齐） |
| D5 | 2 个 blocked connector specs | Phase 3-6 | 中 | 外部阻塞（Apple/WeChat） |
| D6 | Hermes 调度面 179 条断链 | Phase 1-6 | 中 | 待收敛（Phase 5 Direction A） |
| D7 | 1 个 orphaned task | Phase 6 | 中 | state/system.yaml 已记录 divergence |

### 7.2 改进建议

| 优先级 | 建议 | 预期收益 | 目标阶段 |
|:------:|------|---------|:-------:|
| P0 | KOS 存储抽象层：解耦 gbrain SQLite 依赖，支持多后端 | 消除架构紧耦合风险 | Phase 7 |
| P0 | CI 测试环境：搭建 Agora + SharedBrain + gbrain 的 CI 测试集群 | E2E 测试可脱离本地运行 | Phase 7 |
| P1 | Hermes 调度面收敛：按 Direction A 方案融合 cron-service | 消除 179 条断链、统一调度 | Phase 7 |
| P1 | 跨仓库治理同步：统一 43 仓库的 AGENTS.md 和 CI 配置 | 降低维护成本、提高一致性 | Phase 7 |
| P2 | 性能回归门禁：在 CI 中引入 P95 阈值检查 | 防止性能退化 | Phase 7 |
| P2 | eu-pricing 独立测试套件：添加专用测试目录 | 提升 EU 计价可靠性 | Phase 7 |
| P2 | Hermes 记忆/技能层集成：利用 Hermes 的 layered memory 和 self-improving skills | 补充 OMO 在持久记忆方面的短板 | Phase ∞ |

### 7.3 值得保持的模式

| 模式 | 描述 | 首次出现 | 持续使用 |
|------|------|:--------:|:--------:|
| 先验证再推进 | 每个 phase 启动前有 Go/No-Go 判断 | Phase 1 | Phase 1-6 |
| 渐进式交付 | 不做大而散的扩张，优先做最小闭环 | Phase 2 | Phase 2-6 |
| Packet 模式 | plan + task + evidence + retrospective | Phase 5 | Phase 5-6 |
| 四平面写入约束 | 新增内容先判平面，再写入底层位置 | Phase 5 | Phase 5-6 |
| 跨阶段验收 | 以验收报告为 phase 完成的唯一证据 | Phase 3 | Phase 3-6 |
| SSOT 不漂移 | 同一事实不在多处重复写 | Phase 2 | Phase 2-6 |

### 7.4 健康建议

1. **不要急于 Phase 7**：系统当前 health 90/100，2 个 blocked tasks + 1 个 orphaned task。建议在启动 Phase 7 前先清理技术债务（尤其是 D1 和 D2）。
2. **四平面维护优先于扩张**：架构已趋于稳定，后续扩展应在现有四平面约束下进行，避免再次回到"目录更大、机制更松"的状态。
3. **自动化优先于手动治理**：Phase 6 的 checkpoint/lease/watchdog 提供了良好的自运维基础，后续应继续将手动治理流程自动化。
4. **Hermes 收敛按计划推进**：Direction A 的 Priority 0（修复断链）和 Priority 1（收敛调度）应在 Phase 7 优先执行。

---

*报告生成: 2026-05-31 | 基于 Phase 1-6 全部复盘报告、计划文件、架构文档和系统状态*
*数据来源: state/system.yaml, evolution-roadmap-4phases.md, ../design/MASTER-BLUEPRINT.md, DOC-ARCH.md, 各 Phase 复盘/关闭报告*
