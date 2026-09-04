---
lifecycle: entry
owner: governance-team
last_updated: 2026-08-18
last_updated: 2026-09-03
type: ssot
---
# ADR-0192: 领域智能体事实萃取、长程显存自愈与全域自动化治理巡检体系

- **Status**: Accepted
- **Date**: 2026-08-17
- **Author**: Architecture & Governance Team
- **Deciders**: Chief Architect, Virtual Board (B.D.S.K.)
- **Consulted**: ECOS, Runtime, omlxc, AetherForge, Cockpit
- **Informed**: All Agents, All Domain Maintainers

---

## 1. 上下文与背景 (Context)

在 ADR-0190（MOF 动态约束体系）与 ADR-0191（双平面边界治理）落地之后，系统确立了 `Documents`（内容与事实面）与 `Workspace`（工程与计算面）的物理隔离。但在长效运维与垂直业务场景中，存在以下 4 大核心诉求：

1. **多客户端 IDE 挂载一致性 (Client Config Drift)**：Claude Desktop、Zed、Cursor、Codex、ChatGPT 的 Documents MCP 挂载配置需从单一真源 `documents-domain-projects.yaml` 自动化一键生成与校验。
2. **长程智能体显存预算自愈 (Long-running Agent OOM Risk)**：在多轮高密度 Agent 会话中（>30 轮），上下文膨胀导致显存超载，需在 L4/L7 数据面引入 0ms 前缀预热与滑动窗口蒸馏（ContextCompactor）。
3. **领域智能体事实标准化 (Domain Fact SSOT & SLA)**：卫健委信息化项目与国转中心成果转化等关键事实需具备统一的 YAML Schema 规范，并建立 14 天保鲜周期门禁。
4. **全域周期性巡检与防逃逸 (Automated Governance Hygiene)**：需有一键式全景治理巡检总控引擎，定期生成周度治理大盘报告，防止规则与状态漂移。

---

## 2. 架构决策 (Decision)

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                       ADR-0192 领域智能体事实萃取与全域自动化治理巡检全景                  │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
                                              │
              ┌───────────────────────────────┼───────────────────────────────┐
              ▼                               ▼                               ▼
  [1. 领域事实真源 Schema]       [2. 算力织网长程自愈]           [3. 周度自动化治理巡检]
  - _entities/facts/*.yaml       - omlxc fabric warm (0ms TTFT)   - weekly-hygiene-patrol.py
  - 卫健委/国转中心元模型        - VRAM Headroom (>85% 预警)      - 六大支柱交叉校验
  - 14 天保鲜周期 SLA            - ContextCompactor 蒸馏保留近程  - 自动生成周度治理大盘报告
  - FactInspector 结构化验证     - 跨轮次会话无损自愈             - make hygiene-patrol / strict
```

### 2.1 领域事实元模型规范 (Domain Truth Fact Specification)
所有领域业务事实（`Documents/@工作文档/卫健委` 与 `Documents/@工作文档/国转中心`）必须使用结构化 YAML 登记在 `_entities/facts/*.yaml`：

```yaml
schema_version: v1.0
entity_id: FACT-WJ-2026-001
domain: work-weijian
name: 基层医疗卫生信息系统互联互通工程
owner: 信息化推进处
updated_at: '2026-08-17'
lifecycle_stage: IMPLEMENTATION  # INITIATION | PLANNING | IMPLEMENTATION | PILOT | OPERATIONAL | EVALUATION | ARCHIVED
facts:
  project_code: WJ-2026-HLHT-01
  budget_million_cny: 8.60
  # 结构化业务指标...
```

- **保鲜 SLA 门禁 (E-DOC-004)**：`updated_at` 超过 14 天未更新的事实实体将在巡检中标记 `STALE_WARNING`，并在严格模式下拦截流水线。

### 2.2 长程会话显存自愈与前缀预热 (Compute Fabric Self-Healing)
- **0ms TTFT 前缀预热**：通过 `omlxc fabric warm` 将 BDSK 虚拟董事会、OpenCode 智能体与 SGF 约束前缀锁入 L1/L2 语义缓存。
- **Headroom 准入与滑动蒸馏**：`VRAMBudgetEstimator` 实时评估剩余统一内存，当达到安全预算水位（>85%）时返回 `compaction_advised=True`，触发 `ContextCompactor.compact_messages`，保留 System Prompt 与最近轮次，将历史蒸馏为结构化摘要，保障长程智能体永不中断。

### 2.3 全域六支柱自动化治理巡检 (Weekly Hygiene Patrol Engine)
巡检引擎 `bin/ssot/weekly-hygiene-patrol.py` / `ecos-constraint patrol` 覆盖六大支柱：
1. **MOF SSOT Rules Drift Gate**: 检查规则编译与元模型一致性。
2. **Documents Dual-Plane Cleanliness**: 检查是否存在可执行脚本与依赖目录污染。
3. **Domain Truth Facts Schema & Freshness**: 检查事实实体结构与 14 天保鲜期。
4. **Multi-Client Documents Configuration Sync**: 校验 Claude/Zed/Codex/ZCode 挂载配置。
5. **omlxc Compute Fabric Health**: 检查私有算力中枢服务与套接字探活。
6. **Agent Skills YAML Frontmatter Gate**: 检查智能体资产规范。

---

## 3. 影响与收益 (Consequences & Benefits)

1. **业务与代码彻底解耦**：卫健委与国转中心的业务事实沉淀为标准 YAML 真源，人类与 Agent 共同维护单一事实。
2. **长程智能体无损运行**：多智能体复杂推演在 `omlxc` 数据面保护下，告别 OOM 崩溃与冷启动延迟。
3. **全域零配置漂移**：多端 IDE 与治理巡检自动化，任何违规与漂移均在周度大盘中无所遁形。
4. **开箱即用命令群**：
   - `ecos-constraint facts validate [path]`
   - `ecos-constraint facts template --domain <weijian|transfer|generic>`
   - `ecos-constraint documents sync-clients [--mode {install,check,render}]`
   - `ecos-constraint patrol [--output <report>]`
   - `make hygiene-patrol` / `make hygiene-patrol-strict`

---

*ADR-0192 Accepted — System Governance & Architecture Council*
