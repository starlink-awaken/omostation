---
category: workflows
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# Phase 17 Planning Gate — 架构分析与债务治理综合报告

> 日期: 2026-06-03
> 当前阶段: Phase 16 completed · Phase 17 planning gate
> 分析范围: 全 Workspace 架构健康、跨项目依赖、代码质量、债务治理

---

## 执行摘要

本报告基于对 `.omo/` 治理知识库和 `projects/` 代码基线的全量扫描，为 Phase 17 planning gate 提供架构准入评估和债务治理状态。

| 维度 | 评分 | 关键结论 |
|------|:----:|----------|
| 架构健康 | **C+** | 核心能力层优秀 (A)，产品表面层缺失 (F) |
| 依赖耦合 | **B+** | 历史硬耦合已消除，残余风险可控 |
| 代码质量 | **A-** | ruff 全绿，零测试包仅 2 个 |
| 债务治理 | **A** | 历史债务 9/9 closed，新风险 6 项已注册 |
| 文档一致性 | **D** | LAYER-INDEX 与实际状态多处不符 |

**Planning Gate 判定**: ✅ **Phase 17 可以启动**，但必须遵守本报告定义的 Wave 0 准入条件和 guardrails。

---

## 一、架构全景分析

### 1.1 4+1+3 架构健康度

基于 `.omo/diagrams/4-plus-1-3-architecture.md` 和 `LAYER-INDEX.md` 的逐层验证：

| 层 | 设计组件 | 实际状态 | 健康度 |
|----|----------|----------|:------:|
| P0 | hermes-webui, pallas, gstack, bos-skill-cli | **全部缺失或不活跃** | 🔴 F |
| I0 | Agora (7430/7431) | 代码完整，**服务未启动** | 🟡 C |
| L1 | eidos, SSOT, pipeline | 代码+测试完整，ruff 0 | 🟢 A |
| L2 | ontoderive, minerva, forge, kos, ... | 10 个子项目全部健康 | 🟢 A |
| L3 | KOS collab, phase-lock, PipelineTracer | 测试覆盖，证据存在 | 🟢 A- |
| L4 | KOS self, metacog | 代码存在，数据活跃度待确认 | 🟡 B |
| X1 | arcnode, CI, dashboard, Agora, Security | CI 完整，Agora 未运行 | 🟡 B+ |
| X2 | freshness, backup, zombie audit | 备份存在，无 freshness cron | 🟡 B |
| X3 | consensus, PipelineTracer, provenance | evidence 目录存在 | 🟡 B |

**核心发现**: 系统呈现 **"强壮内核 + 虚弱外壳"** 的特征。L1-L4 能力栈经过 Phase 9-16 的持续治理已达到生产级代码质量（ruff 全绿、测试覆盖），但 P0 产品交互层和 I0 服务网格在运行时层面未就绪。

### 1.2 LAYER-INDEX 状态漂移

LAYER-INDEX.md 作为架构状态的权威索引，存在 **4 处严重不符**：

| 条目 | 声称 | 实际 | 影响 |
|------|------|------|------|
| Agora | 🟢 运行中 | 端口未监听 | 高 — 影响路由决策 |
| SharedBrain | 🟢 19 organs | organs/ 已删除 | 高 — 影响分解认知 |
| D-Memory | 🟢 运行时记忆 | organs 已归档 | 中 — 影响架构理解 |
| D-Harvest | 🟢 delegated | organs 已归档 | 中 — 影响架构理解 |

**建议**: Phase 17 Wave 0 必须包含 LAYER-INDEX 全面更新。

---

## 二、跨项目依赖审计

### 2.1 历史债务消除确认

| 历史问题 | 来源 | 当前状态 | 验证方法 |
|----------|------|----------|----------|
| Agora → OntoDerive 硬耦合 (12 处) | ARCH-AUDIT-2026-05 | **已消除** | `grep -r "from engine" packages/agora/src/` → 0 匹配 |
| KOS 零消费者 | ARCH-REVIEW.md | **已消除** | 5 个活跃消费者确认 (eidos, agora, kronos, minerva×2) |
| 硬编码绝对路径 | ../design/INSIGHTS-AND-ROADMAP.md | **已消除** | `/Users/xiamingxing/` 在 packages 中 0 匹配 |
| ruff 大规模报错 | DEBT-ANALYSIS.md | **已消除** | 全量 0 errors |

### 2.2 当前依赖拓扑

```
P0 (缺失)
  ↓
I0 (Agora — 代码就绪，运行时缺失)
  ↓ MCP 协议
L1 (契约层: eidos, SSOT, pipeline — 健康)
  ↓
L2 (能力层: 10 子项目 — 健康)
  ← KOS 被 5 个包消费 ✅
  ← sharedbrain-standalone: 0 消费者 ⚠️
  ← sharedbrain-bridge: 0 外部消费者 🟡
L3 (协作层: agentmesh — 健康)
  ← gbrain 依赖 agentmesh (设计预期)
L4 (自我层: sharedbrain-standalone — 孤立)
```

### 2.3 残余耦合风险

- **sharedbrain-standalone**: 分解后的残留包，零测试、零消费者。若其包含 SharedBrain 核心运行时逻辑，则存在"隐式依赖"风险（其他包通过动态加载而非显式 import 使用）。
- **sharedbrain-bridge**: 设计目的是双向桥接，但 SharedBrain 已分解为文档仓库，bridge 的实际用途需重新评估。

---

## 三、代码质量基线

### 3.1 量化指标

| 指标 | Phase 16 基线 | 评价 |
|------|---------------|------|
| ruff errors (33 包) | **0** | 🟢 优秀 |
| 测试覆盖 | 31/33 包有测试 | 🟢 良好 |
| 零测试包 | 2 (sharedbrain-standalone, wksp) | 🟡 可接受 |
| 硬编码绝对路径 | **0** | 🟢 优秀 |
| sys.path.insert (运行时) | 4 处 (metaos) | 🟡 需清理 |
| except ImportError (运行时) | ~49 处 (5 个核心包) | 🟡 长期债务 |

### 3.2 与历史审计的对比

相比 2026-05-21 的 `DEBT-ANALYSIS.md`：

| 包 | 历史 ruff | 当前 ruff | 改善 |
|----|:---------:|:---------:|:----:|
| kos | 5,263 | 0 | ✅ 清零 |
| ontoderive | 1,307 | 0 | ✅ 清零 |
| minerva | 955 | 0 | ✅ 清零 |
| sophia | 121 | 0 | ✅ 清零 |

**结论**: Phase 9-16 的代码质量治理取得了**质变级**改善。

---

## 四、SharedBrain 分解验证

### 4.1 关闭有效性判定

债务项 **SB_DECOMPOSITION** (closed 2026-06-03) 的关闭声明：

| 声明 | 验证结果 |
|------|----------|
| All 19 D_ organs extracted to kairon packages | ✅  git 删除记录确认，_archived/SharedBrain-code/ 归档完整 |
| sharedbrain-core library completed | 🟡  `sharedbrain-standalone` 存在但零测试；无明确 core 包名 |
| README and AGENTS.md updated | ✅  已更新，但路径指针有误 |
| 107K → 115 .py cleanup complete | ✅  实际 115 个 Python 文件 |

**判定**: 关闭有效。核心工作已完成。剩余为文档收尾（路径指针修正、验证清单更新）。

### 4.2 文档不一致

- `DECOMPOSITION.md` 和 `README.md` 指向 `SharedBrain/_archived/SharedBrain-code/`，实际在 `projects/_archived/SharedBrain-code/`
- DECOMPOSITION.md 验证清单 Wave 0-4 全部未勾选，但 Wave 0 和部分 Wave 1 实际已完成

**建议**: 文档修正作为独立 cleanup 任务，不重新打开 SB_DECOMPOSITION。

---

## 五、Phase 17 Planning Gate 风险评估

### 5.1 残余风险注册

基于本次分析，已注册 6 项残余风险（lifecycle_state: `watching`）：

| ID | 维度 | 描述 | 严重度 | 是否阻塞 |
|----|------|------|--------|:--------:|
| R1 | product | P0 产品交互层缺失 | **high** | 约束范围 |
| R2 | architecture | Agora 服务未运行 | medium | Wave 0 前置 |
| R3 | documentation | LAYER-INDEX 状态漂移 | medium | Wave 0 交付 |
| R4 | technical | 运行时适配器模式债务 | medium | 否 |
| R5 | technical | metaos sys.path.insert | medium | 否 |
| R6 | code_test | sharedbrain-standalone 零测试 | medium | 否 |

### 5.2 阻塞分析

**不构成完全阻塞**：
- Phase 16 closeout 已接受 fixture-backed 证据作为产品表面收敛的证明
- 代码质量和架构耦合度已达到健康水平
- 历史债务全部关闭

**构成范围约束**：
- Phase 17 的 "live pilot" 必须有真实 CLI/API 入口，不能再次仅用 fixture
- Agora 启动必须作为 Wave 0 硬性前置条件
- LAYER-INDEX 更新必须作为 Wave 0 交付物

---

## 六、Guardrails 摘要

### 6.1 Wave 0 准入条件（go/no-go）

```
□ Agora 服务启动（7430/7431 监听验证）
□ P0 入口定义（至少一个 CLI/API capture/search 入口）
□ LAYER-INDEX 状态更新（与实际对齐）
□ gbrain local brain 可运行验证
□ 风险 R1-R6 已注册到 debt registry
```

### 6.2 执行范围边界

| 允许 | 禁止 |
|------|------|
| 一个 gbrain capture/search CLI/API pilot | 第二个 pilot 或并行 pilot |
| fixture → live 渐进验证 | 跳过 fixture 直接声称 live |
| 现有包内部重构 | 新增 kairon workspace 包 |
| Agora 启动和路由配置 | 新增 MCP 协议或路由规则 |
| P0 CLI 入口 | WebUI 重写或全新前端 |

### 6.3 Stop 条件

若以下任一情况发生，触发 immediate stop：
- P0 入口在 Wave 1 后仍无用户可见输出
- Agora 启动后 24h 内再次崩溃
- 数据泄漏（capture/search 越过 user data boundary）
- 对 gbrain schema 的不可逆变更无 rollback 脚本
- Phase 17 引入新的运行时适配器模式代码

---

## 七、交付物清单

| 文件 | 位置 | 平面 |
|------|------|------|
| 架构健康快照 | `.omo/_knowledge/management/architecture-health-snapshot-phase16-post.md` | 知识面 |
| 依赖审计报告 | `.omo/_knowledge/management/dependency-audit-post-phase16.md` | 知识面 |
| 代码质量基线 | `.omo/_knowledge/management/code-quality-baseline-phase16.md` | 知识面 |
| SB 分解关闭验证 | `.omo/_knowledge/management/sharedbrain-decomposition-closeout-verification.md` | 知识面 |
| Phase 17 风险评估 | `.omo/_knowledge/management/phase17-planning-gate-risk-assessment.md` | 知识面 |
| 残余风险注册 (R1-R6) | `.omo/debt/items/R{1-6}_*.yaml` | 事实面 |
| 债务注册表更新 | `.omo/debt/registry.yaml` | 事实面 |
| 债务仪表盘更新 | `.omo/debt/dashboard/current.yaml` | 事实面 |
| Planning Gate Guardrails | `.omo/_knowledge/design/phase17-planning-gate-guardrails.md` | 知识面 |
| **本综合报告** | `.omo/_knowledge/management/phase17-planning-gate-architecture-debt-report.md` | 知识面 |

---

## 八、建议的下一步行动

### 立即（当日）
1. 审批本报告和 guardrails
2. 确认 Phase 17 Wave 0 任务清单

### 本周
3. 启动 Agora 服务并验证端口监听
4. 更新 LAYER-INDEX.md（修正 4 处不一致）
5. 定义 capture/search CLI 入口规格

### 本月
6. 修正 DECOMPOSITION.md 和 README.md 路径指针
7. 评估 sharedbrain-standalone 去留或补充测试
8. 试点适配器模式重构（engine-core 或 agora）

---

*报告生成: 2026-06-03*
*分析输入: state/system.yaml, goals/current.yaml, LAYER-INDEX.md, 4+1+3 architecture, ../design/MASTER-BLUEPRINT.md, 33 包代码基线*
*验证命令: `lsof -i :7430`, `ruff check packages/ --statistics`, `git log --diff-filter=D`, `find packages/*/tests -name "*.py"`*
