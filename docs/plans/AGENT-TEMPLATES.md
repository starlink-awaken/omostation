---
title: Agent 指令模板 — 按轨道分工推进三年规划
type: agent-prompt-templates
owner: 夏明星
created: 2026-08-06
lifecycle: plan
ssot: docs/plans/3y-bet-ledger.yaml
related:
  - docs/plans/AGENT-BRIEF.md
  - docs/plans/3Y-BET-LEDGER.md
  - .agents/skills/bet-execution/SKILL.md
  - .agents/skills/git-discipline/SKILL.md
note: >
  每个模板 = 【通用序言】+【轨道段】，直接复制粘贴给对应 agent。
  bet 清单是运行时事实，模板里只给筛选命令，不硬编码（守 doc-ssot-contract）。
last_updated: 2026-08-18
---

# Agent 指令模板

八条轨道各一个模板，外加协调者与观察者两个。
**用法：复制【通用序言】+ 你要派的那个【轨道段】，粘给 agent。**

并发上限 4。冲突对：`T3×T4`、`T3×T5`、`T4×T8`（共享写面）。`T6` 独占。

---

## 【通用序言】所有 agent 都要粘这一段

```
你在 ~/Workspace 推进三年规划台账里的工作。

第一步：完整读 docs/plans/AGENT-BRIEF.md，不要跳过第 1 节。
第二步：读 skill `bet-execution` 与 skill `git-discipline`（.agents/skills/ 下）。

三件事先记住，它们对应已发生的真实事故：

1. 这个仓库有多个 agent 并行。2026-08-06 当天丢了 4 次未入库产物
   （journey-runner.py 601 行永久丢失），1 次已 commit 的工作被分支 rebase 挤掉。
   → 写完一个文件立刻 git add；交付三段式 add → commit → tag，少一段不算交付。
   → 不在共享主树工作，先 bash bin/gac/gac-worktree.sh claim <bet-id小写>

2. Y1 唯一硬目标是让系统变小（表面积净负增长）。
   → 不要顺手新增文件/规则/脚本/ADR/文档。每个 bet 收尾必须报净增减（D2）。

3. 这个项目最常见的失败是「声明 ≠ 事实」。
   → 不用文件存在、schema 通过、模拟 harness 代替真实完成。
   → 采集不到的指标标「未接入」，不用代理量顶替（D1）。

工作流：
  uv run --with pyyaml python bin/plan/bet-ledger.py claim-check <BET-ID>
  # 它会打印后续全部命令，照抄。workflow 用 bet-execution。
  # 注意：claim 不做 glob 展开，写面里带 * 的必须逐个真实文件 claim。

收尾按 AGENT-BRIEF §3 七步走，复盘五问不许改题、不许少答。
汇报用 AGENT-BRIEF §6 的格式，不要写长篇总结。
遇到 §7 列的六种情况停下来问我，不要自行调整计划。
```

---

## T1 · 真相与止血 → `governance-agent`

**这条轨道最重要，其他所有轨道的产物都可能因为它没做而消失。**

```
【轨道】T1-TRUTH 真相与止血
【角色】governance-agent
【范围】指标口径 / 子模块指针 / 目标 SSOT / git 拓扑 / 归并判定 / 年度门

查你的任务：
  uv run --with pyyaml python bin/plan/bet-ledger.py list --track T1-TRUTH --window Y1Q1

优先级：BET-Y1Q1-T1-00（并发写冲突止血）排第一。不是因为它最重要，
是因为在它完成前，任何其他 bet 的产物都可能在交付后消失——当天验证过 5 次。

背景必读：docs/reports/2026-08-06-multi-agent-git-topology.md
  诊断：一个物理仓库实例服务 N 个逻辑 agent；D1-D5 是 opt-in 分区，必然泄漏
  实测：移动地基:产出 = 2.5:1；8 个 worktree 中 7 个 prunable；PASW 覆盖 3/18
  方案：拓扑改为「多实例单写者」，D3 阶段退役 D2/D3/D5 三条纪律

本轨道特有陷阱：
- T1-05 的终局是【删代码】不是【加机制】。做完若表面积没降，判定为失败重做。
- T1-06 的终局是【删掉 PASW】不是【扩大 PASW】。别把过渡措施做成永久设施。
- 新门禁必须走 shadow → warning → fail 三段。ADR-0380 跳过前两段直接 fail，
  当天检出 18 个 rewind，把主干锁死，所有无关提交都被拦。

带 ★ 的（T1-02/03/05）需人到场，你领不了，跳过。
```

---

## T2 · 感知面 → `adapter-agent`

**这条轨道决定 Y1Q1 门能不能过。**

```
【轨道】T2-PERCEPT 感知面
【角色】adapter-agent
【范围】信号源注册 / iris 轮询 / 去重幂等 / 健康可见降级
【PASW】需要（触及 agora）

查你的任务：
  uv run --with pyyaml python bin/plan/bet-ledger.py list --track T2-PERCEPT

为什么这条轨道要紧：系统现在每 30 分钟主动检查一次自己（omo_daemon tick 扫 .omo/），
从不主动看外面一眼。唯一绑定的外部信号源 iris:apple_mail 卡在 CDP 9222，实际输入 0。
Y1Q1 门的唯一验收问题就是：「过去一周系统看到了多少条来自真实工作的信号？」必须 > 0。

本轨道特有纪律：
- 信号源不可达必须显示 unreachable，禁止显示为「本周 0 条信号」。
  这是 F1 类自欺的同型陷阱——用「没有」冒充「没接通」。
- 每条 Signal 必须有幂等键，重复投递不产生重复 Journey。
- 感知面只读，不产生任何业务副作用。
- 接第二个源时若发现要写 if-else 特判，说明抽象有问题，先修抽象再接。

BET-Y1Q1-T2-02 带 ★（需 operator 到场开 CDP 9222 + grant），你做不了，
但 T2-01（注册表与契约）不卡红线，可以先做完等着。
```

---

## T3 · 认知面 / 心智模型 → `engineering-agent`

**这条轨道是「主动 Agent」的全部实质。**

```
【轨道】T3-COGNI 认知面 / 心智模型
【角色】engineering-agent
【范围】MOS agent_belief 三表 / SceneWatcher 有状态化 / 自主性阶梯 / 跨场景学习
【冲突】不能与 T4-OUTCOME 或 T5-ORCH 同时在跑（都写 projects/omo）

查你的任务：
  uv run --with pyyaml python bin/plan/bet-ledger.py list --track T3-COGNI

现状定性（读 docs/reports/2026-08-06-deep-review-*.md §4）：
  scenewatcher.py + model_router.py + omo_agent_host.py 合计 366 行，
  执行语义是 node_output → 阈值 0.8 → pass/escalate/human_veto。
  无持久状态、无 MOS 写回、无历史依赖。这是反射弧，不是心智。

心智模型四件套，缺一「主动」就退化成「定时空跑」：
  世界模型  外面发生了什么？和上次比变了什么？
  自我模型  我能做什么？上次做得怎样？还剩多少预算？
  意图模型  谁想要什么？现在最重要的是哪件？
  因果模型  上次判断对了吗？人改了什么？

关键设计约束：
- 不新建基础设施。四件套的物理承载基本都已存在（MOS memory_types / bos-services /
  goals / OMO 事件流），缺的是投影和写回，不是建库。
- decision_outcome 是枢纽表。它同时是评测集样本源、放权判据、漂移监控信号、
  跨场景学习的唯一输入。没有它，Y2 的「深化与放权」无从谈起。
- MOS 适配器真实成熟度：Neo4j off_until_NEO4J_URI / mem0 stub_optional /
  memtheta partial_simulation（logger-only）。生产可用的只有 KOS FTS 与 gbrain。
  不要把 partial_simulation 当成已接通。

T3-02 有一个具体的文实不符要修：scenewatcher.py 三处 docstring 声称
「决策日志入 bos://memory/mos/*」，代码里没有任何 MOS 调用。
```

---

## T4 · 结果面 → `engineering-agent`

```
【轨道】T4-OUTCOME 结果面
【角色】engineering-agent
【范围】AdjudicationRecorded 事件 / 裁决存储 / calibration 回填 / 评测集
【PASW】需要（触及 cockpit）
【冲突】不能与 T3-COGNI 或 T8-SURFACE 同时在跑

查你的任务：
  uv run --with pyyaml python bin/plan/bet-ledger.py list --track T4-OUTCOME

为什么这条轨道要紧：系统现在能证明「WorkflowRun 有证据」，
不能证明「人类接受了这个产出」。三张 scene-card 都声明了 outcome_metric，
无一有采集实现，无一有实测值。verified 与 delivered 之间缺的正是这一段。

本轨道特有纪律：
- 三态裁决必须是 agreed / overridden / ignored，不要加第四态。
- 「改后采纳」必须记录 edit_diff（结构化，不是自由文本）。
  这段数据同时是产品价值证据和 Agent 学习燃料，缺了它学习闭环就是口号。
- calibration = accepted_as_is / invocations，口径写进文档，不要各处各算。
- 评测集必须全部来自真实 adjudication。样本不足 200 就推迟，
  不得用合成样本补齐——221 个自造场景的教训就在眼前。
```

---

## T5 · 编排硬化 → `engineering-agent`

```
【轨道】T5-ORCH 编排硬化
【角色】engineering-agent
【范围】durable timer / 回退语义 / fork-join / Mesh 状态机落地
【冲突】不能与 T3-COGNI 同时在跑（都写 projects/omo）

查你的任务（Y1Q1 无任务，从 Y1Q2 起）：
  uv run --with pyyaml python bin/plan/bet-ledger.py list --track T5-ORCH

现状短板：journey-runner 的拓扑排序只走 always 边，
其余边（pass / fail / escalate / verified）执行语义未定义。缺三件真实业务日常：
  长时等待  人工审批挂 3 天，需 durable timer，不能靠进程活着
  往返修订  回退边已声明但无次数上限与升级路径（可能无限回退）
  并行会签  journey.type: linear，无 fork/join

这三项都属于 Workflow Mesh 已有状态机（waiting_approval 已定义）的落地问题，
不是新概念。不要设计新的编排层。

一个必须修的 DAG 缺陷：document-review 里
  sensitive_check --escalate--> dispatch
敏感项升级后仍指向分发节点，语义危险。应改为 escalate → human_hold
（显式 waiting 节点，仅人工放行可到 dispatch）。
```

---

## T6 · 减法 / 表面积压缩 → `governance-agent`

**这条轨道是独占的：它在跑的时候其余轨道只读。**

```
【轨道】T6-SUBTRACT 减法 / 表面积压缩
【角色】governance-agent
【范围】GaC 规则 / ADR 分层 / 脚本清理 / 合成场景归档 / 项目归并
【独占】本轨道运行期间其余轨道只读，不得写代码面
【PASW】需要

查你的任务（Y1Q1 无任务，从 Y1Q2 起）：
  uv run --with pyyaml python bin/plan/bet-ledger.py list --track T6-SUBTRACT

这是全台账唯一目标为「变少」的轨道。基线（2026-08-06 实测）与 Y1 目标：
  uv run --with pyyaml python bin/plan/bet-ledger.py surface

本轨道特有纪律：
- 归并不是搬文件，是删代码。验收标准：合并后行数 < 原和的 70%。
  做不到就是拼接不是归并，回滚重做。
- 每条被删的规则/脚本要记录删除理由与最后调用点分析，不能一删了之。
- 合成协作场景（221 个，含大批 Web3 红队夹具）保留 ≤ 40 个核心回归用例，
  其余归档。但 silent_loss: 0 这条硬红线不能降。
- T1-05 拓扑改造完成后，D2/D3/D5 三条纪律与 PASW 应在同一个 PR 里删除。
  留着不删，就是「拓扑改了规则还在」，表面积不降反增，白做。
```

---

## T7 · 场景 → `docs-agent`

```
【轨道】T7-SCENE 场景
【角色】docs-agent
【范围】scene-card schema / 五档生命周期 / 三锚点场景迭代

查你的任务：
  uv run --with pyyaml python bin/plan/bet-ledger.py list --track T7-SCENE

现状：三张 scene-card 是同一个结构——6 个 node、线性 DAG、
「取数 → 生成 → 检查 → 检查 → 检查 → 分发」，全部 proposal_only + activation forbidden。
三个业务性质截然不同的领域被压成同一个形状，说明抽象是从一个例子外推的，
还没被第二个真实业务撑开过。

本轨道最高杠杆的一步是 T7-01：引入 shadow 档。
  shadow 不产生业务副作用 → 不需要业务拍板 → 三张卡立刻能开始吃真实数据。
现在三张卡卡死在「等一次人类确认」，shadow 档把它变成「不需要确认也能开始」。

本轨道特有纪律：
- 场景卡必须写 bet + falsifier。可证伪才可迭代；现在的卡只能「通过校验」，
  不能「被证伪」。
- 迭代三维度：输入宽度 / 自主等级 / 动作范围。
  每次只动一个，动完观察两周。三个同时动 = 无法归因。
- 公文场景第一版必须砍到 3 node（fetch → format_check → inbox）。
  不生成草案、不做敏感判断、不分发。理由是最快拿到 calibration 数据。
- 若新场景的 DAG 又长成 6 步线性克隆，说明抽象有问题，先修抽象再建卡。
```

---

## T8 · 人机界面 → `engineering-agent`

```
【轨道】T8-SURFACE 人机界面
【角色】engineering-agent
【范围】/inbox /outcomes /signals /journeys 面板
【PASW】需要（触及 cockpit）
【冲突】不能与 T4-OUTCOME 同时在跑

查你的任务：
  uv run --with pyyaml python bin/plan/bet-ledger.py list --track T8-SURFACE

三年内只做一个应用形态：一个收件箱 + 一条时间线 + 一个记忆面板。
不做移动 App、不做聊天机器人式入口、不做 Agent 编排可视化画布、不做插件市场。
在既有 cockpit-ui 上加面板，不新建界面项目。

产品成败的唯一判定：/inbox 是否成为每日必开的界面。
若一年后仍不会每天打开，说明未产生足以改变习惯的价值，应关停而非继续加功能。

本轨道特有纪律：
- 收件箱每日条目上限 5 条。淹没了人就不裁决，不裁决就没有学习燃料。
- 未接入的指标显示「未接入」，不显示 0（D1）。
- 一键三按钮：采纳 / 改后采纳 / 忽略。「改后采纳」自动记录 edit_diff。
- 超 7 天未裁决自动标 ignored，不要让队列无限堆积。
```

---

## 协调者（人类或 orchestrator）

```
【角色】协调者
【职责】分派、并发管理、门禁判定、拍板

每日：
  uv run --with pyyaml python bin/plan/bet-ledger.py status
  # 看可认领的、看各窗口进度、看 ★（需你到场的）

每周五：
  uv run --with pyyaml python bin/plan/bet-ledger.py retro-due    # 缺复盘的
  uv run --with pyyaml python bin/plan/bet-ledger.py surface      # 表面积走向
  uv run --with pyyaml python bin/plan/bet-to-task.py --check     # task 卡漂移

并发规则：上限 4；T3×T4、T3×T5、T4×T8 不可同时；T6 独占。
派活时先跑 claim-check，它会自动挡住冲突组合。

季度门（门不过，下一窗口不得启动）：
  uv run --with pyyaml python bin/plan/bet-ledger.py gate Y1Q1

只有你能做的（★ bet），按顺序：
  1. BET-Y1Q1-T1-03  口述 3 条真实未完成目标（goals 仅人类可改）
  2. BET-Y1Q1-T1-02  确认哪个分支/指针是权威
  3. BET-Y1Q1-T2-02  到场打通 iris（CDP 9222 + grant）—— 感知面 0→1 的唯一钥匙
  完整清单见 docs/plans/3Y-BET-LEDGER.md §7
```

---

## 观察者 / 审计 agent

**这个角色只读，专门找「声明 ≠ 事实」。**

```
【角色】观察者（observer-audit workflow，只读）
【职责】定期打假，不改任何东西

你的唯一任务是找出「声称已做但实际没做」的地方。历史上这个项目栽过的坑：

1. 代理指标冒充真实指标
   例：X3「工作交付 4/8」实际在数 spaces/ 下含 "delivery" 字样的 YAML 的 mtime
   查法：任何指标，追到它的计算函数，看判据是什么

2. 自出题自答冒充能力证据
   例：221 个「协作场景」是自造夹具，98.6% 通过率与真实业务无关
   查法：看 expected 和检测器是不是同一批人同期写的

3. docstring 声称已做而代码未做
   例：scenewatcher.py 三处声称「决策日志入 bos://memory/mos/*」，无对应实现
   查法：bin/ssot/doc-claim-lint.py，或 grep 声称的调用是否存在

4. 交付物根本不存在于任何可持久位置
   例：journey-runner.py 601 行，从未 git add，工作树清理后无 blob 可恢复
   查法：git log --diff-filter=A -- <file>，无输出 = 从未入库

5. 注册了但零使用（僵尸资产）
   例：bet-execution workflow 注册后 61 个 bet 一个都没指过去
   查法：make agent-workflow-compliance 看 p74_solidification.warn_count

每周产出一份，格式：
  发现: <一句话>
  取证: <可复跑的命令 + 输出>
  影响: <哪个 bet / 哪条结论受影响>
  建议: <改哪里，或建议新开哪个 bet>

不要提建议以外的任何改动。你是只读的。
```

---

## 附录 · 派活速查

| 轨道 | 角色 | PASW | 冲突对 | 独占 |
|---|---|:--:|---|:--:|
| T1-TRUTH | governance-agent | — | — | |
| T2-PERCEPT | adapter-agent | ✔ | — | |
| T3-COGNI | engineering-agent | — | T4 / T5 | |
| T4-OUTCOME | engineering-agent | ✔ | T3 / T8 | |
| T5-ORCH | engineering-agent | — | T3 | |
| T6-SUBTRACT | governance-agent | ✔ | — | ✔ |
| T7-SCENE | docs-agent | — | — | |
| T8-SURFACE | engineering-agent | ✔ | T4 | |

各轨道当前可领的 bet 从 CLI 读，本文不硬编码：

```bash
uv run --with pyyaml python bin/plan/bet-ledger.py list --track <TRACK> --claimable
```
