---
title: 织星 / eCOS v6 深度 Review — 主动 Agent 心智模型与业务场景编排
type: review
owner: 夏明星
created: 2026-08-06
lifecycle: report
review-state: evidence-based-audit
note: >
  本文是评审报告，不是 SSOT。所有事实断言均标注取证命令或文件路径，可复核。
  ⚠️ 本文前两版为 untracked 文件，均在并发 agent 的工作树清理中被删除（2026-08-06 当天两次）。
  这本身是本文 F5 的实例，已固化为台账 D0 铁律：未 git add 的产物不算交付。
related:
  - docs/STRATEGY-3YEAR-PLAN-2026H2-2029.md
  - docs/plans/3Y-BET-LEDGER.md
---

# 织星 / eCOS v6 深度 Review

## 0. 结论先行

1. **架构层已经过关，战略层已经写对，问题全部在"输入面"和"结果面"。** 系统有完整的协议、治理、执行、记忆骨架。但它至今没有一个真实世界的持续输入源，也没有一个业务侧可验收的输出。它是一个高度完备的空转发动机。

2. **今天不存在"主动 Agent"，存在的是一个反射弧。** `scenewatcher.py` 全文 137 行，核心方法 `evaluate_confidence` 做的事是：拿 `node_output` → 交给 `ModelRouter` → 按 `confidence < 0.8` 返回 `pass / escalate / human_veto`。无状态、无记忆、无世界模型；`decision_log` 是进程内 list，进程死即消失，docstring 声称的"决策日志入 `bos://memory/mos/*`"在代码里没有对应实现。

3. **今天不存在"场景迭代"，存在的是模板克隆。** `docs/scene-cards/v2/` 下三张卡是同一个结构：6 个 node、线性 DAG、"取数 → 生成 → 检查 → 检查 → 检查 → 分发"，全部 `lifecycle: proposal_only` + `activation: forbidden`。

**主要矛盾是：系统的度量、场景和 Agent 全部指向系统自己。**

---

## 1. 现实差距审计（可复核实证）

### F1 · X3「工作交付」指标测量的是治理配置文件的 mtime

`BRIEF.md`："工作交付 本月 2026-08: 4 / 上月 2026-07: 0（软阈 8）… 环比 0→4, Δ+4. 持续追赶中。"

实际计算逻辑（`bin/mof/generate-brief.py::count_deliveries_by_month` L234-286）：

```python
for p in spaces.rglob("*.yaml"):
    if not _is_delivery_card(p, keywords):   # keywords = ["delivery", "deliverable"]
        continue                              # 判据 = 文件正文里出现 "delivery" 字样
    mtime = datetime.fromtimestamp(p.stat().st_mtime, ...)
    if mtime.year == cur_y and mtime.month == cur_m:
        current_count += 1                    # 判据 = 文件本月被 touch 过
```

命中的 4 个文件：

```bash
grep -rl "delivery\|deliverable" spaces/ --include=*.yaml
# spaces/system-space-cross-root-rule-registry.yaml
# spaces/system-space-rollout-policy.yaml
# spaces/runtime-space-rollout-policy.yaml
# spaces/runtime-space-cross-root-rule-registry.yaml
```

这 4 个是 runtime-space / system-space 的跨根规则注册表与灰度策略配置，与卫健委公文、国转中心中试平台、知识创作无任何关系。

"本月工作交付 4" 的真实含义是"本月有 4 个治理策略 YAML 被改动过"。**必须废除，不是调阈值。**

### F2 · 能力轨的 221 个「场景」是与业务无关的合成夹具

`ls .omo/_delivery/collab-scenarios/ | wc -l` → 222。

抽样：`ADV101-account-abstraction-drain` / `ADV103-validator-equivocation-coverup` / `ADV105-liquidity-migration-trap` / `ADV107-cross-chain-msg-replay` / `ADV109-oracle-latency-exploit` / `ADV113-shared-sequencer-dos` / `ADV115-private-mempool-leak` / `ADV119-threshold-sig-share-theft` / `ADV125-clock-sync-poison` —— 一整套区块链基础设施红队场景。

单个场景是黑板写冲突夹具：

```yaml
inject:
  - {type: write_conflict, role: attacker, target: api_path, value: "/admin/users/delete"}
expected: {behavior: broken_access_admin_detected, silent_loss: 0}
```

它们在测一个多角色黑板协调内核（`silent_loss: 0` 硬红线达成是真实工程成果），但自出题自答，98.6% 通过率不构成能力证据，且不覆盖任何真实业务领域。

能力轨 221 : 产能轨 30 ≈ **7:1**，系统 87% 的验证注意力花在自造题上。

### F3 · 真实任务台账是空的

```bash
ls .omo/tasks/active/    # 空
ls .omo/tasks/done/      # 0
ls .omo/tasks/planned/   # 2 个，都是 needs-human
```

`.omo/state/system.yaml`：`active_agents: 0`、`active_tasks: 0`、`health_score: 96`。

**健康分 96 与"零活跃任务、零活跃 Agent"同时成立**，说明健康分测的是治理面自洽度，不是系统在做事。

### F4 · 目标 SSOT 已陈旧近 6 周，且全部 100% done

`.omo/goals/current.yaml`：`last-reviewed: 2026-06-24`，G27.1–G27.4 / P30.x 全部 `status: done`。

一个"当前目标"文件里没有任何未完成目标，等于系统当前**没有目标**。意图模型的 SSOT 是空的。

### F5 · 未纳入版本控制的交付物会静默消失（本次会话实测两次）

会话开始时存在、结束时已消失的文件：

| 文件 | 声称状态 | git 状态 |
|---|---|---|
| `bin/ssot/journey-runner.py`（601 行） | v10 α.4 ✅ 已交付 | **从未 tracked** |
| `bin/ssot/scene-card-lifecycle.py` | v8 A.1 ✅ 已交付 | **从未 tracked** |
| `bin/ssot/validate-scene-card-v2.py` | 已交付 | **从未 tracked** |
| `docs/scene-cards/v2/`（5 文件） | scene-card v2 全套 | **从未 tracked** |
| `Plans/v10-vision.md` 等 4 份 | v10 规划 SSOT | **从未 tracked** |

取证：`git log --diff-filter=A -- bin/ssot/journey-runner.py` 无输出。`git reflog` 显示同一天内 HEAD 连续变动 `847375f0 → 7d7ffdaa → 5dff6900 → 42f23676`，分支在 `main` / `work/governance-phase9` / `work/governance-phase9-dimension` / `work/governance-phase10` 之间切换 —— **另一个 agent 正在同一个共享主工作树上高频操作**，其清理动作连带删除了所有 untracked 文件，且因从未 git add，**无任何 blob 可恢复**。

**这是"声明已交付"最彻底的一种失效：不是文实不符，是产物根本不存在于任何可持久位置。** 同时它是 ADR-0371（PASW）想解决但覆盖不足的问题：PASW 只隔离了 gbrain/cockpit/agora 三个子模块的 gitlink，没有禁止 agent 在共享主树上直接工作。

补充：子模块指针三方漂移仍在（根仓记录 `048d9432`，本地检出 `4d5a36bb`）。

### F6 · 三张 scene-card 结构同构，且全部禁止激活

| scene | 节点 | 结构 | lifecycle | activation |
|---|---|---|---|---|
| document-review | 6 | 取数→生成→检查→检查→检查→分发 | proposal_only | forbidden |
| engineering-delivery | 6 | 取数→实施→测试→评估→…→合并 | proposal_only | forbidden |
| knowledge-ingest | 6 | 取数→摘要→分类→…→发布 | proposal_only | forbidden |

三个业务性质截然不同的领域被压成同一个 6 步线性 DAG。真实公文有并行会签、时限倒逼、版本回退；真实工程交付有 CI 反馈环；真实知识加工有增量补录、来源冲突 —— 都没有出现在 DAG 里。

卡在这里的不是技术，是一次人类拍板。

### F7 · 唯一外部事件源被 fabric 红线封死

`document-review.yaml`：`trigger_mode: event_driven`、`event_source: iris:apple_mail`。
`scenewatcher-design.md` §3：iris 轮询需 CDP 9222 + operator grant，"本设计**不实现真实轮询**"。

系统真正在跑的自主循环是 `omo_daemon.run_once`（30 分钟 tick）：`audit → history append → sync (dry-run) → Mesh watchdog (dry-run)` —— 全部是对 `.omo/` 自身状态的扫描。

**系统每 30 分钟主动检查一次自己，从不主动看外面一眼。**

---

## 2. 战略层：三份战略文档在打架

| 文档 | 跨度 | 主张 | 状态 |
|---|---|---|---|
| `STRATEGY-3YEAR-PANORAMA.md` v2.3 | 2026H2–2029 | 四条黄金旅程并行 | active, contract |
| `ARCHITECTURE-STRATEGY-CLOSEOUT-2026-08.md` v1.0 | 36 个月 | **单点突破**：先做决策收件箱 | active, contract |
| `Plans/v10-vision.md` | 6 个月 | α/β/γ/δ 四阶段 | 未纳入 git（已丢失） |

冲突：广度（四旅程并行 vs 单场景突破）、顺序（v10 把能力供给侧扩容排进主线，违反 closeout §11"不把工具数量当产品进展"）、治理地位（三个自称权威的战略源）。

**建议裁定**：以 closeout 为主线，3 年全景降为背景板，v10 的 γ/δ 冻结。

---

## 3. 架构层：结构对，形状错

```
【缺】感知面              【已有：完整中段】             【缺】结果面
真实外部信号              入口→路由→治理→Mesh            人类接受/修改/拒绝
0 条/周                   →执行→证据→记忆                0 条记录
```

- **感知面**：唯一绑定的 `iris:apple_mail` 卡在 CDP 9222，实际输入 0。
- **结果面**：三张卡都声明了 `outcome_metric`，无一有采集实现，无一有实测值。`verified` 与 `delivered` 之间缺的正是"人类是否接受、改了什么"。

补丁位置（不新增顶级项目）：感知面 → `iris` + `signal-sources.yaml` + `bos://perception/*`；结果面 → OMO `AdjudicationRecorded` + `.omo/_delivery/outcomes/` + Cockpit `/outcomes`。

---

## 4. 主动 Agent 的心智模型

### 4.1 现状定性

`scenewatcher.py` + `model_router.py` + `omo_agent_host.py` 合计 366 行，执行语义：

```
node_output ──→ ModelRouter.route() ──→ confidence < 0.8 ? human_veto : pass
```

无持久状态、无 MOS 写回、无历史依赖；`AgentHost.tick_all()` 是 for + try/except，Agent 间无通信、无共享上下文、无优先级。**这是刺激→响应，不是心智。**

### 4.2 心智模型的最小定义（四件套）

| 模型 | 必须能回答 | 反例（今天） |
|---|---|---|
| 世界模型 | 外面发生了什么？和上次比变了什么？ | 无外部输入 |
| 自我模型 | 我能做什么？上次做得怎样？还剩多少预算？ | 有能力清单，无历史表现 |
| 意图模型 | 谁想要什么？现在最重要的是哪件？ | goals 全 done、6 周未更新 |
| 因果模型 | 上次判断对了吗？人改了什么？ | 无 outcome 采集 |

### 4.3 落点映射：不新建，接现有

| 模型 | 承载 | 缺口 |
|---|---|---|
| 世界 | MOS `memory_types` + Neo4j | Neo4j `off_until_NEO4J_URI`；mem0 `stub_optional`；memtheta `partial_simulation`（logger-only）。**生产可用的只有 KOS FTS 与 gbrain** |
| 自我 | `bos-services.yaml` + `x3-role-metrics.yaml` | 无"某能力在某场景的历史准确率" |
| 意图 | `goals/current.yaml` + tasks | 内容空/陈旧 |
| 因果 | OMO 事件流 + evidence | 缺 outcome / adjudication 事件 |

**不需要新建基础设施。需要四件小事：把外部信号接进来、把目标写回去、把决策落盘、把人类反馈采集回来。**

### 4.4 MVMM 三张表

```yaml
world_snapshot:          # 世界模型
  scene_id, observed_at, source, facts[], delta_from_previous

capability_calibration:  # 自我模型
  capability, scene_id, invocations,
  human_accepted_as_is, human_edited, human_rejected,
  avg_edit_distance, calibration   # = accepted_as_is / invocations

decision_outcome:        # 因果模型（枢纽）
  decision_id, scene_id, node, model_used, action, confidence, cost_estimate,
  human_verdict,         # agreed | overridden | ignored  ← 结果面回填
  human_note, closed_at
```

**`decision_outcome` 是枢纽**：同时是评测集样本源、放权判据、漂移监控信号、跨场景学习的唯一输入。

### 4.5 自主性阶梯（放权由数据触发）

| 级别 | 行为 | 升级硬门 | 降级触发 |
|---|---|---|---|
| L0 观察 | 只记录 | 默认起点 | — |
| L1 建议 | 草案进收件箱 | 累计 ≥ 20 次 L0 观察 | — |
| L2 受审执行 | 低风险动作，可撤销 | `calibration ≥ 0.6` + 连续 30 次无 rejected + 有回滚路径 | 单次 rejected 或 calibration < 0.5 |
| L3 自动 | 白名单自动完成 | `calibration ≥ 0.85` + 连续 100 次 + 预算上限 + 影响可逆 | 任一 override |

### 4.6 "主动"的可操作定义

> Agent 在没有被要求的情况下，因为观察到世界状态变化，产出了一个人类认为值得看的东西。

指标：**主动产出被采纳率 = 采纳数 / 主动产出数**。它天然惩罚刷存在感。

---

## 5. 业务编排与场景迭代

### 5.1 场景必须先写「赌注声明」

```yaml
bet: "如果系统每周替我处理 3 份公文的格式与敏感项初检, 我每周省 2 小时, 且不增加外发风险。"
falsifier: "连续 4 周, 若人类修改率 > 70% 或出现 1 次敏感项漏检, 此赌注证伪, 场景退回或关停。"
```

赌注可证伪，场景才可迭代。现在的卡只能"通过校验"，不能"被证伪"。

### 5.2 迭代三维度（每次只动一个，观察两周）

| 维度 | 动作 | 公文场景实例 |
|---|---|---|
| 输入宽度 | 1 类 → N 类 | 借调群邮件 → +OA → +纸质扫描 |
| 自主等级 | L0 → L1 → L2（按 4.5 硬门） | 只标注 → 出草案 → 自动格式修正 |
| 动作范围 | 只读 → 建议 → 写 → 发 | 检查 → 生成草案 → 改稿 → 直发（**永不到**） |

### 5.3 生命周期五档（替换断崖式两档）

```
draft → shadow → assisted → supervised → routine
       (只观察,  (出建议,   (可执行,     (白名单
        无副作用) 不进流程)  人类事前批)   自动)
```

**`shadow` 档是解锁一切的关键**：不产生业务副作用，因此不需要业务拍板，能立刻让三张卡开始吃真实数据。

### 5.4 三锚点角色不同，不该平行推进

- **公文 / 决策收件箱 — 主战场**。第一版砍到 3 node：`fetch → format_check → inbox`。不生成草案、不做敏感判断、不分发。理由：规则可判、错了代价小、一眼能验收，最快拿到 calibration 数据。
  **DAG 缺陷必须修正**：现有 `sensitive_check --escalate--> dispatch`，敏感升级后仍指向分发，语义危险。应改为 `escalate → human_hold`（显式 waiting 节点，仅人工放行可到 dispatch）。
- **工程交付 dogfood — 数据发生器**。PR 评审意见即天然 `human_verdict`，两周可攒数百条校准样本，零业务风险。**产出永不计入 X3 价值指标。**
- **知识入库与创作 — 存量变现**。KOS 5193 篇 + 创作 674 篇是唯一真实存量。指标只一条：**召回被引用率**（召回 N 条，成稿引用 M 条）。

### 5.5 编排层真实短板：缺"等待"和"往返"

`journey-runner` 的拓扑排序只走 `always` 边，其余边（`pass`/`fail`/`escalate`/`verified`）执行语义未定义。缺失三件真实业务日常：

1. **长时等待**：人工审批挂 3 天，需 durable timer，不能靠进程活着。
2. **往返修订**：回退边已声明但无次数上限与升级路径。
3. **并行会签**：`journey.type: linear`，无 fork/join。

三项都属于 Workflow Mesh 已有状态机（`waiting_approval` 已定义）的落地问题，不是新概念。**应列为编排层 P0，优先于任何新场景。**

---

## 6. 愿景收窄

> **织星是夏明星一个人的业务操作系统。它的唯一职责是：把外部进来的信号，变成他愿意署名发出去的东西，并且记住他每次改了什么。**

三个定语各砍一片：「一个人的」砍多租户与通用产品化；「愿意署名发出去」砍一切无人类交付出口的自动化；「记住改了什么」把学习锚定在人类修订差异上。

---

## 7. 指标重构

**废除**：X3 工作交付（mtime）、能力轨通过率、健康分作为进展信号、角色完成率、项目/能力/工具/测试/ADR 计数。

**换成**：有效工作旅程完成率（北极星）、主动产出被采纳率、人类修订率、每周真实外部信号数、capability_calibration 分布、召回被引用率、单条建议平均成本、`/inbox` 打开频率。

**纪律：采集不到的指标显示"未接入"，禁止用代理量顶替。**

---

## 附录 · 事实来源

| 断言 | 取证 |
|---|---|
| F1 交付指标逻辑 | `bin/mof/generate-brief.py` L234-286 |
| F1 spaces 命中 | `grep -rl "delivery\|deliverable" spaces/ --include=*.yaml` |
| F2 场景数与内容 | `ls .omo/_delivery/collab-scenarios/`（222），抽样 ADV101/103/105/171 |
| F3 任务台账 | `ls .omo/tasks/{active,done,planned}/`；`.omo/state/system.yaml` |
| F4 目标陈旧 | `.omo/goals/current.yaml` L5 |
| F5 未入库丢失 | `git log --diff-filter=A -- bin/ssot/journey-runner.py`（无输出）；`git reflog` |
| F6 scene-card 同构 | `docs/scene-cards/v2/*.yaml`（已丢失，内容见本文） |
| F7 daemon tick | `projects/omo/src/omo/omo_daemon.py` L1-7, L42 |
| MOS 适配器成熟度 | `.omo/_truth/registry/memory-os.yaml::adapters` |
| 体量实测 | 见 `docs/STRATEGY-3YEAR-PLAN-2026H2-2029.md` §1.1 |
