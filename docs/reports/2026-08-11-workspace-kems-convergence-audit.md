---
lifecycle: history
owner: governance-team
last_updated: 2026-08-11
snapshot-kind: derived-report
implementation-status: mixed
canonical-source: /Users/xiamingxing/Documents/@学习进化/_knowledge/10-systems/基建架构/10-Workspace-KEMS整体架构分析-2026-08-11.md
canonical-sha256: fecc039202fd93ddde73b7f48bef6eb30c70def682d1d87ad715598b4aab768f
baseline-root-commit: a4b08255e8a918a1b52dd32226d36c64db4f2c2e
type: ephemeral
---

# Workspace × KEMS 架构收敛审计（2026-08-11）

> 本文件是 Documents 私有 canonical 报告的 Workspace 派生审计快照，用于代码评审、治理追踪和长期取证。它不是 Documents 知识正文的第二 SSOT；发生差异时，以 frontmatter 中的 `canonical-source` 和 `canonical-sha256` 对应版本为准。

## 一句话结论

Workspace 与 Documents 的目标分层基本正确，正式 KEMS 链路也已具备可验证实现；当前需要解决的不是“再建一个 KEMS”，而是把方法源、L4 编译、知识运行时、任务治理四种职责彻底分名分权，并退役三个遗留或旁路实现。

## 1. 审计口径

状态标记：

| 标记 | 含义 |
|---|---|
| `[EXISTS]` | 已有代码或测试证据 |
| `[EXTEND]` | 归属正确，应在原组件内扩展 |
| `[BUILD]` | 有明确缺口，需要最小新增能力 |
| `[CONCEPT]` | 仅是目标或历史声明 |
| `[RETIRE]` | 与正式路径重复、失真或无消费者 |

事实优先级：运行代码/测试/Git 对象/机器注册表 > accepted ADR 与蓝图 > 项目说明 > 历史 KEMS 自述。

本审计区分：

1. 已批准的目标架构；
2. 已合并到 Git 对象的实现；
3. 当前进程和活跃检出真正加载的版本。

## 2. KEMS 的四个正式角色

| 角色 | 唯一职责 | 自然归属 | 裁决 |
|---|---|---|---|
| Method/Profile | 方法、策略、概念卡、领域 Profile | Documents KEMS | `[EXISTS]` 方法源，不再是执行器 |
| L4 Compiler/Harness | DomainManifest、路径策略、契约验证、健康检查、提案 | l4-kernel | `[EXISTS]` Phase 0 已实现 |
| KEMS Runtime | ingest、规范化、评估、图、promotion gate、恢复 | Kairon/KOS `kos.kems` | `[EXISTS]` 唯一 KEMS runtime |
| Task Governance | 状态、审批、证据、派发、执行回执 | OMO + Workflow Mesh + Runtime | `[EXISTS]` 唯一治理/执行链 |

禁止通过一个新的“超级 KEMS 服务”重新吞并上述职责。

## 3. 当前架构

```text
                         canonical human-readable knowledge
                         ┌───────────────────────────────┐
                         │ Documents                     │
                         │ domains + KEMS Method/Profile │
                         └──────────────┬────────────────┘
                                        │ source/profile/evidence refs
                                        v
┌──────────────┐   API/draft    ┌──────────────┐   approval/state   ┌─────────────┐
│ Cockpit      ├───────────────>│ OMO          ├───────────────────>│ Workflow    │
│ KEMS routes  │                │ task SSOT    │                    │ Mesh        │
└──────┬───────┘                └──────┬───────┘                    └──────┬──────┘
       │ ingest/eval/graph             │ evidence/receipt                  │ execution
       v                               │                                   v
┌──────────────────────┐               │                         ┌────────────────┐
│ Kairon / KOS         │<──────────────┘                         │ Runtime        │
│ kos.kems runtime     │                                         │ preflight/reach│
└──────────┬───────────┘                                         └────────────────┘
           │ derived index/evaluation/context
           v
┌──────────────────────┐
│ MOS / KOS / gbrain   │── citation/context ──> Documents canonical objects
└──────────────────────┘

Legacy/side islands:
  [RETIRE] tools/kems + omostation.py
  [RETIRE] projects/domain-kems
  [RETIRE] l4-kernel legacy DocumentKemsPlugin no-op actions
```

## 4. SSOT 与边界

| 对象或动作 | 唯一权威 | 不可越界 |
|---|---|---|
| 人类可读知识正文 | Documents | KOS/索引不得成为不可恢复的正文 SSOT |
| KEMS 方法与 Profile | Documents KEMS | 不保存运行任务状态，不直接调 worker |
| L4 域约束 | Documents registry + l4-kernel | 不承担全文检索和任务执行 |
| 任务状态、审批、证据 | OMO | Cockpit/KEMS 不得旁路审批 |
| 执行图与 worker 派发 | Workflow Mesh | 不创建第二 workflow engine |
| ingest/eval/graph | Kairon/KOS `kos.kems` | promotion gate 不自动晋升 canonical |
| 生产前检查与 reach | Runtime | 不接收 raw private content，不隐式成功 |
| 统一记忆控制面 | MOS | 不替代 Documents、KOS、gbrain 或 OMO |
| 派生检索和图索引 | KOS/gbrain | 必须可重建并能返回 canonical citation |
| 身份与准入 | Spaces | 不承载知识正文或任务状态 |

## 5. 正式闭环

### 5.1 知识准入与 canonical promotion

```text
Inbox/Connector
  -> OMO governed Run
  -> Kairon/KOS source admission
  -> KEMS normalize/enrich/evaluate/annotate
  -> l4-kernel contract/path validation
  -> human or OMO policy approval
  -> Documents canonical write
  -> OMO event/evidence
  -> MOS/KOS/gbrain derived-index rebuild
```

### 5.2 检索与记忆

```text
Agent/Cockpit
  -> Agora/MOS intent routing
  -> KOS/gbrain retrieval
  -> citation + context pack
  -> Documents canonical object
  -> evidence-bound answer/task
```

### 5.3 L4 演化

```text
Documents DomainManifest
  -> l4-kernel compile + Harness
  -> DomainHealth/drift evidence
  -> EvolutionProposal
  -> OMO approval/state
  -> Workflow Mesh mutation
  -> Harness re-check
  -> accepted evidence or rollback
```

Phase 0 已完成 contracts、registry、path policy 和 Harness 基础。`EvolutionProposal + ContextPack + OMO` 属于下一阶段 `[EXTEND]`，不是当前已完成能力。

## 6. 已验证事实

### 6.1 L4 Phase 0 已合并

- root accepted commit：`a4b08255e8a918a1b52dd32226d36c64db4f2c2e`；
- ECOS pointer：`ec139d03a5adbde71d67e801fa5c556d168ee8fa`；
- l4-kernel pointer：`b90ceae81c01e34122d4896c480929255924b463`；
- isolated verification：79 个 Phase 0 核心测试和 3 个 Documents 集成/安全测试通过；
- registry CLI 可解析 12 个域及对应 archetype/authority policy。

但审计时共享 `/Users/xiamingxing/Workspace` 活跃检出为 `fix/closed-loop-cwd@2ad5b522...`，根树、l4 pointer 和实际 l4 HEAD 不一致，并存在大量无关未提交修改。

裁决：实现 `[EXISTS]`，无需重写；P0 是进程加载版本和 accepted checkout 对齐。禁止在共享脏检出上直接 reset 或强制切分支。

### 6.2 Kairon/KOS 是正式 KEMS runtime

`projects/knowledge/kairon/packages/kos/src/kos/kems/` 覆盖 immutable source manifest、hash/sensitivity/redaction、持久化 run/step、checkpoint、fail-closed runner、evaluation、OCR/model acceptance、adjudication、promotion gate、graph、health 和 recovery。

关键约束：raw source 保持在 KEMS 外；OMO adapter 只生成 planned payload；promotion gate 只能返回 `eligible_for_human_approval`，不能自动 promotion。

审计验证：Kairon/KOS KEMS 相关测试 98 个通过。

### 6.3 Cockpit → OMO → Workflow Mesh → Runtime 成立

- Cockpit 标明 `review_only`、`dispatch=omo_only`；
- OMO KEMS ingress 不做 worker assignment；
- Runtime preflight 会检查 transport、source inventory、evaluation、adjudication persistence、model acceptance、recovery 和 OMO approval；
- reach gateway 只接受 `vault://redacted/`，拒绝 raw content 和隐式成功。

审计验证：Cockpit 20 个、OMO 2 个、Runtime 35 个 KEMS 相关测试通过。

## 7. 关键发现

### F-01 `[P0]` 活跃检出与 accepted Phase 0 漂移

影响：Git 对象里能力已完成，但常驻进程可能仍加载旧 l4-kernel，形成“测试过、运行时没有”的假确定性。

处置：服务启动输出 root/l4/kairon commit；使用 clean release worktree 和 version pin，不破坏共享脏检出。

### F-02 `[P0]` Documents KEMS 裁决正确，正文仍失真

Documents KEMS 已裁定为方法/Profile 源，但正文仍混用 v7.4/v7.5/v7.6、同一能力同时标待建和完成，并引用不存在的 executor/status/storage 文件。

处置：保留方法资产和 2026-08-10 裁决；runtime/executor 自述转历史，任何“已实现”必须链接代码和测试。

### F-03 `[P0]` l4-kernel 旧插件返回假成功

`projects/l4-kernel/src/l4_kernel/plugins.py` 的 index/search/categorize/entity/storage/sync/notify 动作没有实际行为，却返回 `status=ok`。

处置：返回结构化 `not_implemented`/`deprecated` 并 fail closed，或显式桥接正式端点。

### F-04 `[P1]` `projects/domain-kems` 是未注册旁路原型

该目录不在 `docs/project-registry.yaml`，无独立 pyproject、README、AGENTS、测试或 CI；pipeline 声称 `extract→fuse→index`，实际无 index，且直接写域 `_knowledge`。未发现正式外部消费者。

处置：将有价值的 domain controller/keywords 吸收到 Kairon domain adapters；消费者清零后退役，不注册第二 runtime。

### F-05 `[P0]` root `tools/kems` 已断裂

`tools/__init__.py` 引用错误模块位置；`tools/kems/kems_engine.py` 递归导入不存在的 `KEMEngine`；`omostation.py` 调用不存在的 `run_full_pipeline()`。import probe 失败。

处置：旧入口先 fail closed；若有真实用户，改为 Cockpit/OMO 的薄客户端并设置退役期限。

### F-06 `[P1]` 正式实现与文档错位

KOS 文档存在多个互相冲突的静态文档数，architecture 未描述已存在的 `kos.kems`；根 ARCHITECTURE 仍展示不可用旧 KEMEngine。

处置：数量从运行命令生成；能力和路由从 registry/code/test 生成，禁止手写快速漂移数字。

### F-07 `[P1]` 缺稳定真实业务闭环

平台具备 engineering dogfood、shadow evaluation 和门禁，但还缺长期场景同时证明真实标签、人工审批、canonical promotion、引用、outcome、撤回与恢复。

处置：优先跑“决策收件箱”30 天闭环，再扩到 90 天。

## 8. 目标收敛

```text
Documents canonical + versioned MethodProfile
        |
        v
ECOS/MOF schemas -> l4-kernel compile/Harness -> DomainHealth/Proposal
                                                    |
                                                    v
                                     OMO state/approval/evidence
                                                    |
                                                    v
                                      Workflow Mesh sole spine
                                         /                  \
                                        v                    v
                              Kairon/KOS kos.kems          Runtime
                              ingest/eval/graph/gate     execute/recover
                                        \                    /
                                         v                  v
                                      evidence + receipts
                                               |
                                               v
                                MOS/KOS/gbrain derived recall
```

| 组件 | 决策 | 最终形态 |
|---|---|---|
| Documents KEMS | `[EXTEND]` | 方法/Profile，增加 version/hash |
| l4-kernel | `[EXTEND]` | contracts/Harness/Health/Proposal |
| Kairon/KOS | `[EXTEND]` | 唯一 KEMS runtime |
| Cockpit | `[EXTEND]` | 单一人机入口，dispatch 进入 OMO |
| OMO | `[EXTEND]` | 唯一任务/审批/证据状态权威 |
| Workflow Mesh | `[EXTEND]` | 唯一执行脊柱 |
| MOS/KOS/gbrain | `[EXTEND]` | 可重建、citation-bound 派生层 |
| `projects/domain-kems` | `[RETIRE]` | 配置吸收后退役 |
| root `tools/kems` | `[RETIRE]` | 薄客户端或停止服务 |
| l4 no-op actions | `[RETIRE]` | fail closed 或显式转发 |

## 9. 路线与验收门

### P0：消除假能力和版本错配

1. 盘点服务/daemon/CLI 的 cwd、Python path 和加载 commit；
2. 固化 authority matrix；
3. no-op plugin 和 broken CLI fail closed；
4. 归档过期 KEMS executor/runtime 自述；
5. success receipt 强制携带 evidence 或真实 state transition。

验收：实际服务版本与 accepted commit 一致；任何无行为路径都不能返回 success。

### P1：打通 L4 演化和真实场景

1. Kairon run 绑定 `MethodProfile ref + version + hash`；
2. 打通 `DomainHealth → EvolutionProposal → OMO → Workflow Mesh → Harness recheck`；
3. 吸收并退役 `domain-kems`；
4. 运行 30 天决策收件箱或工程交付真实闭环；
5. 代码、registry、文档和测试入口一致。

验收：每个 run 能追溯 profile、source、OMO task、approval、receipt 和 canonical object。

### P2：恢复和长期抗熵

1. 完成 L4 recovery/rollback 门；
2. 证明派生索引可从 canonical + event log 重建；
3. 完成 promotion/retraction/index invalidation 一致性门禁；
4. 自动生成项目、路由、能力和动态计数；
5. 真实场景连续验证 90 天后再提高自治级别。

## 10. 架构健康度

九维等权审计总分 `66/100`。这是 Workspace × KEMS 集成架构分，不等同于运行健康页分数，也不替代 Phase 0 前的历史基线。

| 维度 | 分数 |
|---|---:|
| Vision | 85 |
| Scenarios | 60 |
| Architecture | 70 |
| Maturity | 78 |
| Entropy Control | 45 |
| Debt Control | 50 |
| Maintainability | 65 |
| Recoverability | 76 |
| Cost Efficiency | 65 |
| **综合** | **66** |

目标：P0 后 ≥72；P1 真实闭环后 ≥80；长期个人 A 阶段 ≥90。

## 11. 明确不做

- 不创建新的 KEMS Platform 仓库或第二 workflow engine；
- 不把 Documents Markdown executor 恢复成运行时权威；
- 不让 l4-kernel 承担索引、模型评估或 worker execution；
- 不让 Kairon/KOS 自动晋升 canonical knowledge；
- 不把 MOS 变成内容数据库或 OMO 替代品；
- 不在共享脏检出上 reset、checkout 或强制对子模块；
- 不因目录存在就给 `domain-kems` 补齐一套平台基础设施；
- 不把文件存在、函数可导入或 HTTP 200 当作能力完成。

## 12. 证据入口

- `ARCHITECTURE.md`
- `docs/project-registry.yaml`
- `.omo/_knowledge/decisions/0362-kems-runtime-health-and-recovery.md`
- `.omo/_knowledge/decisions/0364-kems-repeated-shadow-promotion-gate.md`
- `.omo/_knowledge/decisions/0365-architecture-strategy-closeout.md`
- `.omo/_knowledge/decisions/0372-memory-os-control-plane.md`
- `projects/knowledge/kairon/packages/kos/src/kos/kems/pipeline.py`
- `projects/knowledge/kairon/packages/kos/src/kos/kems/runner.py`
- `projects/knowledge/kairon/packages/kos/src/kos/kems/omo_adapter.py`
- `projects/cockpit/src/cockpit/web/api_kems.py`
- `projects/omo/src/omo/omo_ingress_kems.py`
- `projects/runtime/scripts/kems_production_preflight.py`
- `projects/domain-kems/src/domain_kems/kems_pipeline.py`
- `projects/l4-kernel/src/l4_kernel/plugins.py`

最终裁决：保留一个 KEMS runtime（Kairon/KOS）、一个任务权威（OMO）、一条执行脊柱（Workflow Mesh）、一个知识正文 SSOT（Documents）、一个 L4 编译/验证内核（l4-kernel）。其余同名实现必须成为薄适配器、历史材料或被退役。
