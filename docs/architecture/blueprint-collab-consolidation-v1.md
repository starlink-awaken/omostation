---
lifecycle: contract
owner: governance-team
last_updated: 2026-08-15
related:
  - ./digital-twin-blueprint-v1.md
  - ./blueprint-multi-agent-execution-control-v1.md
  - ../operations/blueprint-agent-instruction-pack-v1.md
  - ../reports/2026-08-06-multi-agent-git-topology.md
  - ../superpowers/specs/2026-08-14-supervised-blueprint-control-loop-design.md
title: 多 Agent 协作固化方案 v1 — 蓝图执行推进总案
type: doc
---

# 多 Agent 协作固化方案 v1 — 蓝图执行推进总案

> 日期：2026-08-15
> 状态：grill-me 十问裁定固化（C×10）/ 三 PR 的 spec 源
> 上游：织星第二数字分身总体架构蓝图 v1 + 多 Agent 执行控制体系 v1
> 本文是蓝图推进的顶层执行方案：接手前任 agent 遗留（W1 代码已交付、G-1 未核验、蜂群未开），定义三条工作线、四个固化件、一个复盘和一个 D2 节拍。

## 0. 现状判定（接手盘点）

| 层面 | 状态 | 证据 |
|---|---|---|
| 蓝图三文档 | ✅ 已发布 merge | #1313（architecture）+ instruction-pack；上游 Documents 同源三份 |
| W1 supervised loop 代码 | ✅ 已交付 | #1437：blueprint_control.py（compile/dispatch/verify/rollback 全链） |
| 执行计划 | ✅ 41/41 全勾 | docs/superpowers/plans/2026-08-14-supervised-blueprint-control-loop.md |
| Orca 运行时 | ✅ ready | runtimeState: ready, graphState: ready |
| G-1 Swarm Readiness | ❌ 未正式核验 | SR-01 刚过（P74 0 silent）；SR-02~06 无证据包 |
| BET-Y1Q2-T1-18 | candidate（代码已交付未收口） | 曾因 Codex ACP 依赖 blocked，本方案 unblock |
| 拓扑改造 | 半成品双轨 | ~/agents/ 已有 4 独立 clone；但本周事故全在旧 worktree 路径 |

**一句话**：万事俱备，只欠 G-1 正式核验 + SR-06 双轮演练。G-1 不过，蜂群禁止开闸（控制体系 §18 红线）。

## 1. 十问裁定快照（决策记录）

| # | 分叉 | 裁定 |
|---|---|---|
| Q1 | 第一波切入结构 | **双线并行**：执行线（G-1+SR-06）× 设计线（spec+find/load），零写面冲突 |
| Q2 | SR-06 演练载体 | **双轮制**：先微型包 reject→rollback（验基础设施），后 T1-18 真活 accept |
| Q3 | spec 约束机制 | **自研固化 + 吸收外来理念**：spec registry + digest 绑定 + lint 强制；不引入 openspec/bmad 工具链 |
| Q4 | capability find/load | **生成器+生成物+反漂移门**（复用 gen-agent-redlines 模式）；find 统一，load 不动 |
| Q5 | worktree 清理 | **submit 内置 + janitor 兜底**：三条件安全检查（claim 已关 AND 心跳超时 AND PR 已 merge），默认 dry-run |
| Q6 | 执行拓扑 | **混合分流**：验证交付的活走成熟管道；验证控制体系的活必须走 Orca+supervised loop（执行者≠验收者） |
| Q7 | G-1 证据包形态 | **分层落账**：门判定走 audits 证据包（不立 bet）；SR-06 演练挂 T1-18；开门决定留 human_gate 签名位 |
| Q8 | 复盘线形态 | **差量复盘+决策备忘录**：引用 08-06 基线，产出 D2 铺开决策；覆盖 agent 暴毙交接缺失这个新病根 |
| Q9 | 方案文档审验 | **即审即动**：本文档即三 PR 的 spec 源（digest 绑定自举）；review 不阻塞开工 |
| Q10 | D2 铺开节奏 | **渐进+硬收口**：08-21~28 渐进周（新 claim 走 clone）→ 08-28 激活主仓封写 guard → D3 启动 |

## 2. 三线作战图

```text
执行线（串行, 需 Human 配合 ~10min）
  G-1 核验 SR-01~05 ──► SR-06a 微型包 reject→rollback ──► SR-06b T1-18 真活 accept
        │                                                        │
        ▼                                                        ▼
  audits/gate-g1-swarm-readiness-2026-08.md ◄── 证据回填 ◄── T1-18 收口 done
        │
        ▼ [human_gate 签名] ──► 蜂群合法开闸

设计线（3 PR 并行, subagent）
  PR-A spec 约束链: spec 模板 + lint 强制 + grill-me 收束产物约定
  PR-B capability 生成器: capability-sync 扫四源 + registry + CI 反漂移门
  PR-C worktree janitor: 三条件安全清理 + make 目标 + dry-run 默认

复盘线（错峰, 等执行线数据）
  docs/reports/2026-08-15-multi-repo-collab-retro-v2.md
  = 08-06 后事故差量 + T1-05 落地差距审计 + 暴毙交接病根 + D2 决策备忘
```

## 3. 执行线设计

### 3.1 G-1 核验（SR-01~05 机器证据）

| SR | 判据 | 证据命令 |
|---|---|---|
| SR-01 | workflow status.ok=true, 无 stale/orphan lock | `make agent-workflow-compliance` |
| SR-02 | preflight PASS + 派工别名有路由 | `make agent-workflow-doctor` |
| SR-03 | Agora healthy + send/get/cancel 冒烟 | agora health 探针 |
| SR-04 | M2/Schema/Compiler 同 hash | compile_packet 复现性测试 |
| SR-05 | Verifier 只读 + 独立检查 + receipt | blueprint_control verify 路径测试 |

### 3.2 SR-06 双轮演练

- **轮 a（reject→rollback）**：R1 微型包（appetite 1h / max_changed_files=2），故意让 diff 超界 → 验证 EvidenceRecorded 拒绝 + 基线 hash 恢复证明。account 记 T1-18 evidence。
- **轮 b（accept）**：T1-18 真活（supervised loop dogfood 收口），完整 accept 路径。
- 生产路径：Orca 托管交互 Codex TUI，每次 provider approval 由 Human 点击（契约不变）。
- 老王角色：Strategic Director（编译 Packet）+ Program Controller（确定性工具）；Codex = Executor；blueprint_control.py = 裁决面。

## 4. 设计线三 PR 规格（digest 绑定源）

### PR-A spec 约束链

- spec 生命周期 `draft → accepted → superseded`（对齐 ADR 词汇），落 `docs/superpowers/specs/`（既有目录升级为一等公民）
- 台账 lint 新规：R1+ bet 必须有 `accepted_specifications` 绑定且 digest 校验通过（spec 变更 → bet 自动失效）
- spec 模板强制段：验收标准（吸收 bmad story 理念）+ 反指标（对齐蓝图 §20 禁止指标）
- grill-me 收束约定：拷问裁定表 = spec 的 decision log 段（本文档 §1 即首个样例）

### PR-B capability 生成器

- `bin/capability-sync.py` 扫四源：`~/.claude/skills/`（124）+ `Workspace/.agents/skills/`（~15）+ `orca skills list` + MCP configs
- 产出 `docs/generated/capability-registry.yaml`（name/description/触发方式/来源/场景标签）
- `make capability-sync` + CI gate：生成物 ≠ 实际扫描 → FAIL（反漂移）
- 查询入口 `capability-find --query`（读生成物，毫秒级，跨 agent 一致视图）
- load 层不动（Skill 工具 / MCP 协议 / orca 命令 / workflow CLI 各自照旧）

### PR-C worktree janitor

- `bin/gac/worktree-janitor.py`：清三条件 = claim 已 close（协调层无活跃 claim）AND 心跳超时/无主 AND PR 已 merge
- `make worktree-janitor`（默认 dry-run 报告）+ `--apply` 显式执行
- submit 侧扩展 `--merge-and-clean`（寿终正寝路径一键收）
- 模式 5（误删在用 worktree）从「靠自觉」变「机器判据」——协调层 T1-05A 数据的第一个生产消费者

## 5. 复盘线要点

见 §2 图。四个必答：

1. 08-06 报告五件事（P0 止血 ×2 / P1 根治 / P1 补齐 / P2 加固）各自落地率多少？
2. 本周三事故（worktree 被清 ×2 / stash 误弹 / 主仓分支被占）+ 4 worktree 泄漏按 E1-E6 归因，成本几小时？
3. 前任 agent 暴毙案例：交接机制缺失是独立于拓扑的第四类病根，D2 是否需要配套「agent 退役清单」？
4. D2 铺开决策（Q10 已裁）写入 M2 里程碑，janitor 数据回填双轨残留曲线。

## 6. D2 节拍（Q10 固化）

| 时点 | 动作 |
|---|---|
| 08-21 | T1-05A 窗口收口（human_gate + status 快照）→ D2 启动条件满足 |
| 08-21→08-28 | 渐进周：新 claim 引导走 clone；janitor 每日 dry-run 报双轨残留 |
| 08-28 | **硬收口**：激活 `agent-clone.py guard` 主仓封写（I1 不变量物化）→ D3 启动（删 D2/D3/D5 旧纪律，预计 -2000 行） |

## 7. 风险与红线

1. G-1 未过不开蜂群（控制体系 §18）；本方案任何 PR 不改变此门。
2. SR-06 双轮的 provider approval 永远由 Human 点击——授权放权不覆盖这一条（蓝图契约级）。
3. janitor 三条件缺一不清；dry-run 是默认不是可选项。
4. 方案文档 lifecycle=active 随实现滚动；重大裁定变更须留 changelog 并同步三 PR 的 spec digest。
5. 主仓当前有他 agent 在途（分支被占/子模块脏）——所有操作继续走 worktree 隔离，不碰主仓 HEAD。

## 8. Changelog

| 日期 | 变更 |
|---|---|
| 2026-08-15 | v1 初版：十问裁定固化 + 三线作战图 + 三 PR 规格 + D2 节拍 |
