# SYSTEM-INDEX.md — Workspace 全景导航

> **维护规则**
> - owner: governance-team
> - trigger: 重大架构变更、新项目加入、工具链变更
> - method: 人工维护框架结构，具体内容指向各索引
> - validation: 所有指针路径必须存在（doc-ssot-lint 扩展检测）
> - status: active
> - created_at: 2026-07-14

---

## 快速开始

1. 读本文 → 了解全局结构
2. 读目标项目 `AGENTS.md` → 了解操作规则
3. 查 `INDEX-TOOLS.md` → 找可用工具
4. 查 `INDEX-KNOWLEDGE.md` → 查历史决策

---

## 层模型

见 `ARCHITECTURE.md` §2 和 `docs/project-registry.yaml::layers`。

当前架构为 **5+4+1+1 分层**：
- L0: 协议层
- L1: 运行时层
- L2: 引擎层
- L3: 入口层
- L4: 自我层
- I0: 织层
- M0: 横切框架
- X: 横切扩展

---

## SSOT 导航

| 需要什么 | 去哪里读 | 维度 |
|----------|---------|------|
| 项目元数据 | `docs/project-registry.yaml` | 事实层 |
| 运行时状态 | `.omo/state/system.yaml` | 事实层 |
| 架构契约 | `ARCHITECTURE.md` | 架构层 |
| 端口分配 | `protocols/port-registry.yaml` | 边界层 |
| 治理规则 | `.omo/_truth/registry/governance-checks.yaml` | 事实层 |
| ADR 决策 | `.omo/_knowledge/decisions/INDEX.md` | 知识层 |
| BOS 服务 | `projects/agora/etc/bos-services.yaml` | 边界层 |
| L0 约束 | `projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml` | 协议层 |
| MOF 能力 | `.omo/_truth/registry/mof-capabilities.yaml` | 事实层 |

---

## 分类索引

→ [项目索引](INDEX-PROJECTS.md) — 项目按层/栈/状态分类（见 `docs/project-registry.yaml`）

→ [工具索引](INDEX-TOOLS.md) — bin/ + scripts/ + .agents/skills 统一目录

→ [知识索引](INDEX-KNOWLEDGE.md) — ADR + 审计 + 模式 + 总结交叉索引

→ [Agent 能力索引](INDEX-AGENTS.md) — 当前 agent 配置 + 技能清单

→ [Closeout 记录](closeout/) — 各轮关闭记录和复盘（详见 `docs/closeout/`）

→ [操作 SOP](operations/) — 运维手册、清单、模板（详见 `docs/operations/`）

→ [架构设计](architecture/) — 方案设计文档（详见 `docs/architecture/`）

→ [ISA 分析](isa/) — 接口/服务/架构图（详见 `docs/isa/`）

→ [设计方案](proposals/) — 设计提案和历史方案（详见 `docs/proposals/`）

→ [本地计算集群](local-compute/) — omlx 集群架构（详见 `docs/local-compute/`）

---

## 文档维护生命周期

### 索引维护责任矩阵

| 事件 | 影响的索引 | 更新方式 | 优先级 |
|------|-----------|---------|--------|
| 新项目加入 | INDEX-PROJECTS | 脚本重新生成 | P1 |
| 项目归档 | INDEX-PROJECTS | 脚本重新生成 | P1 |
| 新增 bin/ 工具 | INDEX-TOOLS | 脚本重新生成 | P2 |
| 新增 ADR | INDEX-KNOWLEDGE | 脚本重新生成 | P2 |
| 新增审计 | INDEX-KNOWLEDGE | 脚本重新生成 | P2 |
| 新增 skill | INDEX-AGENTS | 脚本重新生成 | P2 |
| Agent CLI 升级 | INDEX-AGENTS | 脚本重新生成 | P3 |
| 架构层变更 | SYSTEM-INDEX | 人工更新 | P1 |

### 阅读指南

#### 新 Agent 进入 Workspace

```
第 1 步: 读 SYSTEM-INDEX.md（了解全局）
第 2 步: 读目标项目 AGENTS.md（了解操作规则）
第 3 步: 按需查 INDEX-TOOLS.md（找工具）
第 4 步: 按需查 INDEX-KNOWLEDGE.md（查历史决策）
```

#### 查找特定信息

| 我想找什么 | 去哪里 |
|-----------|--------|
| 某个项目在哪个层 | INDEX-PROJECTS.md → 按层分类 |
| 某个工具怎么用 | INDEX-TOOLS.md → 按用途分类 |
| 某个主题有哪些决策 | INDEX-KNOWLEDGE.md → 按主题索引 |
| 当前 agent 有哪些技能 | INDEX-AGENTS.md → 技能分布 |
| 端口号是多少 | protocols/port-registry.yaml（不经过索引） |
| 当前 Phase 是多少 | .omo/state/system.yaml（不经过索引） |

---

## 项目文档矩阵

| 文档 | 事实层 | 架构层 | 操作层 | 边界层 | 入口层 |
|------|:------:|:------:|:------:|:------:|:------:|
| project-registry.yaml | **OWN** | — | — | — | — |
| system.yaml | **OWN** | — | — | — | — |
| ARCHITECTURE.md | ref | **OWN** | — | — | — |
| AGENTS.md | ref | ref | **OWN** | — | — |
| CLAUDE.md | ref | ref | **OWN** | — | — |
| BOUNDARY.md | ref | ref | — | **OWN** | — |
| CALLCHAIN.md | ref | ref | — | ref | — |
| README.md | ref | ref | ref | — | **OWN** |
| LAYER-INDEX.md | ref | **OWN** | — | — | — |
| PANORAMA.md | ref | **OWN** | — | ref | — |

---

## 工具分类导航

| 域 | 主要工具 | 位置 |
|----|---------|------|
| GaC 治理即代码 | gac-validate, gac-drift, gac-local-gate | bin/gac/ |
| ADR 治理 | adr-coverage, adr-drift-check | bin/adr/ |
| SSOT 守护 | doc-ssot-lint, ssot-guardian | bin/ssot/ |
| MOF 工具 | mof-enforce, mof-reason | bin/mof/ |
| Agent 工作流 | agent-workflow.py | bin/ |

详见 `INDEX-TOOLS.md` 获取完整工具目录。

---

## 知识资产分类

| 类型 | 位置 |
|------|------|
| ADR 决策 | `.omo/_knowledge/decisions/`（见 `INDEX.md` 索引） |
| 审计报告 | `.omo/_knowledge/audits/` |
| 模式总结 | `.omo/_knowledge/patterns/` |
| 管理文档 | `.omo/_knowledge/management/` |

详见 `INDEX-KNOWLEDGE.md` 获取完整知识索引。

---

## 关联文档

→ [ARCHITECTURE.md](../ARCHITECTURE.md) — 架构契约
→ [AGENTS.md](../AGENTS.md) — Agent 操作指南
→ [CLAUDE.md](../CLAUDE.md) — 会话上下文加载
→ [README.md](../README.md) — 项目快速开始
→ [doc-ssot-contract.md](../.omo/standards/doc-ssot-contract.md) — 文档正交契约
→ [layer-contract.yaml](layer-contract.yaml) — 分层依赖规则
→ [生成的索引](generated/) — `project-layer-index.md`, `agent-gac-rules.md` 等自动生成的文档
→ [近期报告](closeout/) — 2026-07-15 各轮 closeout 记录
→ [操作 SOP](operations/) — 运维手册、模板、清单
