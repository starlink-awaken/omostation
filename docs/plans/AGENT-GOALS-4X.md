---
title: 四 Agent 并行持续推进 — Goal 模式指令
type: agent-goal-templates
owner: 夏明星
created: 2026-08-06
lifecycle: plan
ssot: docs/plans/3y-bet-ledger.yaml
related:
  - docs/plans/AGENT-TEMPLATES.md
  - docs/plans/AGENT-BRIEF.md
note: >
  与 AGENT-TEMPLATES.md 的区别：那份是「派一个 bet」的单次指令，
  本文是「给一条轨道一个长期目标，agent 自己循环取活」的 goal 模式。
last_updated: 2026-08-18
---

# 四 Agent 并行 — Goal 模式

**Task 模式**：我给你一个 bet，你做完汇报，结束。
**Goal 模式**：我给你一条轨道和一个目标，你自己循环取活，直到目标达成或被叫停。

---

## 0. 为什么是这四条轨道

并发上限 4；冲突对 `T3×T4`、`T3×T5`、`T4×T8`；`T6` 独占。
在 Y1Q1 窗口内，**唯一零冲突的四轨组合**是：

```
Agent-1  T1-TRUTH    governance-agent    Y1Q1 有 8 个 bet（最多）
Agent-2  T2-PERCEPT  adapter-agent       Y1Q1 有 2 个
Agent-3  T3-COGNI    engineering-agent   Y1Q1 有 2 个
Agent-4  T7-SCENE    docs-agent          Y1Q1 有 3 个
```

`T4-OUTCOME` 与 T3 冲突、`T8-SURFACE` 与 T4 冲突、`T5` 与 T3 冲突、`T6` 独占且 Y1Q1 无任务——
所以这四条是当前唯一能同时开满的组合。

**Agent-3 做完 T3 的 Y1Q1 两个 bet 后**，自然切到 T4（`T4-01` 本来就依赖 `T3-01`），
那时 T3 已停，不再冲突。这个切换写进了它的 goal 里。

---

## 【共同前缀】四个 agent 都粘这段

```
你在 ~/Workspace 以 Goal 模式持续推进三年规划台账。

═══ 一次性准备 ═══
读 docs/plans/AGENT-BRIEF.md（全文）
读 .agents/skills/bet-execution/SKILL.md 与 .agents/skills/git-discipline/SKILL.md

═══ 三条底线（对应已发生的真实事故）═══
1. 多 agent 并行。2026-08-06 当天丢了 4 次未入库产物（journey-runner.py 601 行永久
   丢失），1 次已 commit 的工作被分支 rebase 挤掉。
   → 写完一个文件立刻 git add；交付三段式 add → commit → tag，少一段不算交付
   → 绝不在共享主树工作，先 bash bin/gac/gac-worktree.sh claim <bet-id小写>
2. 减法必须逐项指名道姓，不接受百分比目标。test_loc 是保护量，下降即违规（D6）。
3. 「声明 ≠ 事实」是本项目最常见的失败。不用文件存在、schema 通过、模拟 harness
   代替真实完成；采集不到的指标标「未接入」。

═══ 循环协议（这是 Goal 模式的核心）═══
LOOP:
  1. uv run --with pyyaml python bin/plan/bet-ledger.py list --track <你的轨道> --claimable
  2. 若无可领 → 报告「本轨道当前无可认领项 + 阻塞原因」，进入待命，不要去别的轨道抢活
  3. 选窗口最靠前、不带 ★ 的一个 → claim-check → 照它打印的命令执行
  4. 做完走 AGENT-BRIEF §3 七步收尾（含 tag），写复盘五问
  5. 按 §6 格式汇报这一个 bet
  6. 回到 1

═══ 每完成 3 个 bet，额外做一次轨道级小结 ═══
  - 这三个 bet 的复盘 Q3（打假发现）里，有没有共同模式？
  - 台账里本轨道剩下的 bet，有没有因为新发现而需要改？
  - 表面积在本轨道净增减多少？（贴 surface 输出）

═══ 什么时候必须停 ═══
  - 遇到 ★ 标记的 bet（需人到场）
  - AGENT-BRIEF §7 的六种情况
  - 连续两个 bet 触发 circuit_breaker
  - 发现的问题影响到别的轨道
停下来问，不要自行调整计划。这个项目的教训是：agent 改计划的速度超过人核对的速度。
```

---

## Agent-1 · T1-TRUTH（governance-agent）

**这条轨道最重要——在它完成前，其他三条的产物都可能在交付后消失。**

```
【轨道】T1-TRUTH 真相与止血
【角色】governance-agent
【Goal】让「系统说的」和「系统实际是的」重新对齐，并让并发写不再丢产物。
       达成标志：连续 7 天没有交付物丢失事件，且 goals/current.yaml 不再是空的。

【执行顺序】严格按此，不要跳
  1. BET-Y1Q1-T1-00  并发写冲突止血 ← 第一个，其他一切的前提
  2. BET-Y1Q1-T1-07  git 入口收口 shim
  3. BET-Y1Q1-T1-04  未入库产物普查 + D0 门禁
  4. BET-Y1Q1-T1-01  废除 X3 mtime 交付指标
  （T1-02 / T1-03 / T1-05 带 ★，跳过，报告给人）
  5. BET-Y1Q1-T1-06  子模块隔离（依赖 T1-02，可能被卡）

【必读】docs/reports/2026-08-06-multi-agent-git-topology.md
  诊断：一个物理仓库实例服务 N 个逻辑 agent；D1-D5 是 opt-in 分区，必然泄漏
  实测：移动地基:产出 = 2.5:1；8 个 worktree 中 7 个 prunable；PASW 覆盖 3/18

【本轨道特有陷阱】
  · T1-05 的终局是【删代码】不是【加机制】。做完表面积没降 = 失败重做
  · T1-06 的终局是【删掉 PASW】不是【扩大 PASW】。别把过渡措施做成永久设施
  · 新门禁必须走 shadow → warning → fail 三段。ADR-0380 跳过前两段直接 fail，
    当天检出 18 个 rewind 把主干锁死
  · 你自己就在共享树上工作 —— 做 T1-00 时格外注意别把别人的东西删了
```

---

## Agent-2 · T2-PERCEPT（adapter-agent）

**这条轨道决定 Y1Q1 门能不能过。**

```
【轨道】T2-PERCEPT 感知面
【角色】adapter-agent
【PASW】需要（触及 agora）
【Goal】让系统第一次看到仓库以外的东西。
       达成标志：连续 7 天每天有去重后的真实外部信号落盘，断连时显示 unreachable。

【执行顺序】
  1. BET-Y1Q1-T2-01  signal-sources 注册表与感知面契约 ← 不卡红线，先做完
  2. BET-Y1Q1-T2-02  iris apple_mail 真实轮询 ← 带 ★，需 operator 到场开 CDP 9222
     做不了就报告并待命；T2-01 的成果先摆在那等着接

【为什么要紧】
  系统现在每 30 分钟主动检查一次自己（omo_daemon tick 扫 .omo/），从不看外面一眼。
  Y1Q1 门的唯一验收问题：「过去一周系统看到了多少条来自真实工作的信号？」必须 > 0。
  现在的答案是 0。

【本轨道特有纪律】
  · 信号源不可达必须显示 unreachable，禁止显示为「本周 0 条信号」
    —— 用「没有」冒充「没接通」，是 F1 类自欺的同型陷阱
  · 每条 Signal 必须有幂等键，重复投递不产生重复 Journey
  · 感知面只读，不产生任何业务副作用
  · 接第二个源时若要写 if-else 特判 → 抽象有问题，先修抽象再接

【T2-01 做完后若 T2-02 仍卡住】
  报告并待命。不要为了「有事做」去改抽象或加功能 —— 那是供给侧扩容。
```

---

## Agent-3 · T3-COGNI（engineering-agent）

**这条轨道是「主动 Agent」的全部实质。**

```
【轨道】T3-COGNI 认知面 / 心智模型，做完后接 T4-OUTCOME
【角色】engineering-agent
【冲突】T3 与 T4/T5 共享 projects/omo。你做 T3 时别人不做 T4/T5；
        你转 T4 时必须先确认 T3 的 bet 全部 done
【Goal】让 Agent 从反射弧变成有持久状态的心智。
       达成标志：进程重启后能查到历史决策，且决策与人类裁决成对落盘。

【执行顺序】
  1. BET-Y1Q1-T3-01  MOS agent_belief 三表 schema 与写入路径
  2. BET-Y1Q1-T3-02  SceneWatcher 决策日志真写 MOS
  3. ↓ T3 的 Y1Q1 清空后，切到 T4（T4-01 本就依赖 T3-01，此时不再冲突）
     BET-Y1Q1-T4-01  AdjudicationRecorded 事件与裁决存储
     注意：T4 需要 PASW（触及 cockpit）

【现状定性】读 docs/reports/2026-08-06-deep-review-*.md §4
  scenewatcher.py + model_router.py + omo_agent_host.py 合计 366 行，
  执行语义是 node_output → 阈值 0.8 → pass/escalate/human_veto。
  无持久状态、无 MOS 写回、无历史依赖。这是反射弧，不是心智。

【关键设计约束】
  · 不新建基础设施。四件套的物理承载基本都在（MOS memory_types / bos-services /
    goals / OMO 事件流），缺的是投影和写回
  · decision_outcome 是枢纽表：评测集样本源 + 放权判据 + 漂移监控 +
    跨场景学习的唯一输入。没有它 Y2 无从谈起
  · MOS 适配器真实成熟度：Neo4j off_until_NEO4J_URI / mem0 stub_optional /
    memtheta partial_simulation（logger-only）。生产可用的只有 KOS FTS 与 gbrain。
    别把 partial_simulation 当已接通

【T3-02 有个具体的文实不符要修】
  scenewatcher.py 三处 docstring 声称「决策日志入 bos://memory/mos/*」，
  代码里没有任何 MOS 调用。
```

---

## Agent-4 · T7-SCENE（docs-agent）

**这条轨道有全台账最高杠杆的一步。**

```
【轨道】T7-SCENE 场景
【角色】docs-agent
【Goal】让三张 scene-card 从「等一次人类拍板」变成「不需要拍板也能开始吃真实数据」。
       达成标志：三张卡都在 shadow 档，公文场景连续 4 周每周 ≥ 3 条真实输入。

【执行顺序】
  1. BET-Y1Q1-T7-01  scene-card 五档生命周期 schema ← 最高杠杆，先做
  2. BET-Y1Q1-T7-02  v10 失落产物重建并入库
     （journey-runner.py 601 行 / scene-card-lifecycle.py / validator，
      从未 git add，工作树清理后无 blob 可恢复 —— 只能重建）
  3. BET-Y1Q1-T7-03  公文场景砍到 3 node 并进 shadow ← 依赖 T2-02，可能被卡

【为什么 T7-01 是最高杠杆】
  三张卡现在全部 proposal_only + activation forbidden，卡在「等一次业务拍板」。
  shadow 档不产生业务副作用 → 不需要拍板 → 三张卡立刻能开始跑真实数据。
  一个 3 天的 schema 改动，解锁三个场景。

【本轨道特有纪律】
  · 场景卡必须写 bet + falsifier。可证伪才可迭代；现在的卡只能「通过校验」，
    不能「被证伪」
  · 迭代三维度：输入宽度 / 自主等级 / 动作范围。每次只动一个，动完观察两周。
    三个同时动 = 无法归因
  · 公文场景第一版必须砍到 3 node（fetch → format_check → inbox）。
    不生成草案、不做敏感判断、不分发 —— 这是最快拿到 calibration 数据的路径
  · 必修的 DAG 缺陷：document-review 里 sensitive_check --escalate--> dispatch，
    敏感升级后仍指向分发，语义危险。应改为 escalate → human_hold（显式 waiting 节点）
  · 若新场景 DAG 又长成 6 步线性克隆 → 抽象有问题，先修抽象再建卡
```

---

## 协调者（你）的循环

```bash
# 每天开工
uv run --with pyyaml python bin/plan/bet-ledger.py status      # 谁能领、进度、★ 项

# 每天收工
uv run --with pyyaml python bin/plan/bet-ledger.py retro-due   # 缺复盘的
uv run --with pyyaml python bin/plan/bet-ledger.py surface     # test_loc 保护量

# 每周五
uv run --with pyyaml python bin/plan/bet-to-task.py --check    # task 卡漂移
```

**四个 agent 里只有你能解的三个 ★**（按优先级）：

1. `BET-Y1Q1-T1-03` 口述 3 条真实未完成目标——`goals/current.yaml` 现在全是 done、6 周没更新，意图模型的 SSOT 是空的
2. `BET-Y1Q1-T1-02` 确认哪个分支/指针是权威
3. **`BET-Y1Q1-T2-02` 到场打通 iris（CDP 9222 + grant）**——感知面 0→1 的唯一钥匙，也是 Y1Q1 门的唯一验收问题

**第 3 件不做，Agent-2 会一直待命，Agent-4 的 T7-03 也会卡住。**

---

## 停机条件（四个 agent 全停）

- `bet-ledger.py surface` 报 `test_loc` 下降（有害减法）
- 一天内出现 ≥ 2 次交付物丢失
- 主干被门禁锁死超过 2 小时
- 任一 agent 报告「发现台账本身有错」且影响 ≥ 2 条轨道
