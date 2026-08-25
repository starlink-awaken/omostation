---
title: 织星 Y1 中段蓝图迭代 — 价值闭环与表面积回收
status: active
lifecycle: plan
owner: 夏明星
created: 2026-08-25
last-reviewed: 2026-08-25
type: phase-blueprint
horizon: Y1-remain (post Y1Q3 close → Y1 年度门)
supersedes:
  - docs/plans/two-week-integration-and-forward-plan.md
does_not_supersede:
  - docs/STRATEGY-3YEAR-PLAN-2026H2-2029.md
  - docs/plans/3y-bet-ledger.yaml
  - .omo/_knowledge/decisions/0410-strategy-mainline-plan-supersedes-panorama.md
related:
  - docs/architecture/project-strategy-v1.md
  - docs/reports/2026-08-20-blueprint-strategy-retrospective.md
  - docs/reports/2026-08-22-bet-ledger-snapshot.md
  - docs/reports/2026-08-24-resident-system-deep-review.md
note: >
  本文是阶段契约，不是第二套三年规划。愿景/证伪条件只引用 Plan。
  运行时规模读 `python3 bin/plan/bet-ledger.py surface` 与
  `python3 bin/plan/bet-ledger.py status`，不在正文追更。
---

# 织星 Y1 中段蓝图迭代 — 价值闭环与表面积回收

## 0. 一句话判断

**Y1Q3 台账已经关账，但 Y1 并没有成功。** 系统在 30 天里把中段建得更厚、把治理建得更会自己打分，两端（真实外部信号 → 主人愿意署名的产出）仍然空。下一阶段不是 AGE-v2 Phase 8，也不是再刷成熟度，而是：**冻结平台扩张，选定一条主人真实价值环并每周走通，同时把无消费者的中段资产按名单回收。**

| 维度 | 判定 | 证据口径 |
|---|---|---|
| 愿景 | `VALID` 未改 | Plan §0.3，ADR-0410 |
| 台账进度 | `PROVEN` 且 `MISLEADING` | 138/140 done，2 条 Y3 业务冻结 |
| Y1 减法 | `FAILED so far` | src +27%，bin +116% vs 2026-08 基线 |
| 感知面 | `NOT_PROVEN` | PersonalSignal 全流 2 条；9 张场景卡仍 shadow |
| 结果面 | `PARTIAL` | 有 attestation / dogfood 样本，无连续主人采纳周 |
| 认知面 | `PARTIAL` | MOS / sediment 管道在，产出多为模板 |
| 执行脊柱 | `PROVEN` | workflow / clone / gate / resident / AGE-v2 均有代码 |
| 下一阶段 | **价值闭环 + 净减法** | 本文 §5–§7 |

不推翻三年规划。不新写北极星。不把「成熟度 9.0」当成愿景达成。

---

## 1. 愿景锚点（只引用，不改写）

SSOT：[`docs/STRATEGY-3YEAR-PLAN-2026H2-2029.md`](../STRATEGY-3YEAR-PLAN-2026H2-2029.md)（ADR-0410）。

> 织星是夏明星一个人的业务操作系统。它的唯一职责是：把外部进来的信号，变成他愿意署名发出去的东西，并且记住他每次改了什么。

| 锚 | 内容 | 对下一阶段的约束 |
|---|---|---|
| 证伪条件 | 2027-12-31 前未能连续 12 周每周 ≥ 3 条被本人采纳的建议 | 下一阶段必须开始数「周」，不是数 PR |
| Y1 主轴 | 收敛与接通：表面积净负（逐项冗余清零）+ 感知/结果两端 + 一个真实闭环 | 平台扩张默认拒绝 |
| 形状 | 四面一脊：感知 → 认知 → 执行脊柱 → 结果，回流学习 | 只加厚脊柱 = 继续做错形状 |
| 四年功能 | F1 收件 / F2 旅程 / F3 记忆 / F4 治理做减法 | F1 未激活则其余无法验证 |
| 原主战场 | 公文场景 | **2026-08-19 业务冻结**，不可假装还在打 |
| 不可逆点 | gbrain+kairon 归并 | 已做（ADR-0413 / T6-01），下一阶段不再重开归并 |

执行台账仍是 [`docs/plans/3y-bet-ledger.yaml`](3y-bet-ledger.yaml)。本文**不**往台账里批量塞新 bet；需要新 bet 时最多开 3–5 条，且每条必须绑一条可证伪的主人行为。

---

## 2. 近一个月实际发生了什么

本地 `origin/main` 是浅克隆，只能直接看到 8/24–8/25 的 146 个 commit。完整节奏以 GitHub PR + 报告面为准（2026-07-25 → 2026-08-25）。

### 2.1 四幕

| 幕 | 窗口 | 主题 | 代表产物 | 对愿景的净效果 |
|---|---|---|---|---|
| **A 立宪** | 7/25–8/15 | 承认表面积超限，写下三年规划与台账纪律 | Plan、BET ledger、ADR-0410、swarm 拓扑、文档平面、T6-01 知识层归并 | **正确**：第一次有可证伪愿景 |
| **B 打假** | 8/16–8/22 | 发现「119 bet done 但价值 0」 | 8/20 蓝图复盘、T4-01 价值轴、T7-01 dogfood、attestation、instruction binding | **正确**：把 E4 抬成完成语义 |
| **C 关账** | 8/21–8/22 | 所有可推进 bet 置 done，Y3 两条业务冻结 | 8/22 台账快照 121/123 | **半对**：关的是台账，不是 Y1 |
| **D 中段爆炸** | 8/22–8/25 | 成熟度 T10、resident、BCOS、AGE-v2 Phase 5–7、AST/SEMA | 4 天合并约 200 个 PR；ADR-0423..0426 | **偏离**：继续加厚中段 |

8/24 的两周前向计划（`two-week-integration-and-forward-plan.md`）把下一周定义成「认领 12 条 T10」。那些 bet 在 48 小时内被打完。**Phase α 已过期。** 它的后继不是 Phase β 的更多工具，而是本文。

### 2.2 这一个月真正留下的强资产

这些是下一阶段**必须复用、禁止重造**的东西：

1. **治理脊柱**：agent-workflow、独立 clone、claim/verify/closeout、GaC gate、gitlink ancestry。
2. **完成语义工具**：WorkPacket / CompletionManifest / attestation verifier / completion_evidence 三轴。
3. **知识层目录归一**：`projects/knowledge/{gbrain,kairon}`（ADR-0413）。异构栈仍在，双头治理面已收。
4. **常驻与总线**：resident 五角色、Agora 2.0 `:7432`、cockpit 入口收敛方向。
5. **价值测量管线**：north_star meter、attest-review、weekly-review、dogfood observer。
6. **减法机制（有工具、未兑现）**：subtraction quota、anti-corrosion、script registry、zero-call archive 口径。

### 2.3 这一个月同时做大的偏差

1. **体积**：相对 2026-08 基线，`src_loc` +27%、`bin_scripts` +116%（310 → 670）、ADR +42、`projects/` 自 8/1 净值约 +56 万行。Y1 唯一硬目标是变小。
2. **完成语义通胀**：Y1Q2–Y3 大量 bet 在数周内标 done。8/20 复盘已经写过「台账全绿、Human Outcome 0」；8/22 之后用 T10/成熟度把「系统更成熟」再次写成完成。
3. **场景 0 触发**：九维战略 v1（8/24）记录 9 张场景卡全部 `shadow`、0 samples。主战场公文/中试已冻结。
4. **resident 空转**：8/24 复盘 — sediment 405 条全是模板；PersonalSignal 2 条；ExecutionRequested 1 条；health=recovered 与 idle 9h 并存。
5. **AGE-v2 / Phase 5–7**：Agent Cell、cartridge、LSP、in-memory bus、AST merge、SEMA 结晶，全部是中段能力。没有一条直接增加「主人本周采纳了 3 条建议」。
6. **入口过载**：bin 670 + 多套评分（scorecard / compass_radar / UHS / north_star v2/v3）。F2「cockpit 唯一入口」仍是愿望。

---

## 3. 愿景对照：声明 vs 事实

按 Plan 的四面一脊验收，不用成熟度分数代替。

| Plan 要求 | 声明状态 | 当前事实 | 阶段判定 |
|---|---|---|---|
| 感知面接通 | T2 轨道 done | 信号源注册存在；真实外部流入接近 0 | `NOT_PROVEN` |
| 结果面建立 | T4-01 / T7-01 done | 有 dogfood 裁决与签名工具；无连续主人周 | `PARTIAL` |
| 一个真实闭环 | Y1 成功标志 | 没有一条场景离开 shadow | `NOT_PROVEN` |
| 知识层双头清零 | T6-01 done | 目录归一已做；检索栈仍两套实现 | `PARTIAL`（治理面过，能力面未过） |
| 无消费者模块 / 零调用脚本清零 | T6 / T10-01 | 脚本登记了，没有按零调用归档压下去 | `NOT_PROVEN` |
| GaC ≤80 / bin ≤180 | F4 减法 | 规则略增，bin 翻倍 | `FAILED so far` |
| 公文 shadow→assisted | Y1 场景矩阵 | 业务冻结，保持 blocked | `DEFERRED`（合法） |
| 工程 dogfood 作数据发生器 | 不计价值指标 | 它是目前唯一有流量的环 | **下一阶段改判为临时主环** |
| Agent 有状态心智 | T3 done | decision_outcome / sediment 缺真实回流 | `NOT_PROVEN` |
| 放权由 calibration 触发 | Y1Q4-T3-01 done | 无连续样本，阶梯无数据可爬 | `NOT_PROVEN` |

**结论**：中段 `PROVEN`，两端 `NOT_PROVEN`，减法 `FAILED so far`。再交付中段能力，只会让对照表更难看。

---

## 4. 三个必须接受的结构性事实

### 4.1 台账空了 ≠ Y1 做完了

`bet-ledger.py status`：140 条里 138 done、2 blocked、0 candidate。这只说明「按当前台账没有可领的工程项」。Plan 的 Y1 成功标志是冗余清零 + 两端接通 + 一个真实闭环。这三件里只完成了部分归并（知识层目录、omo-debt/c2g、family-hub 暂停），其余两件失败或未证。

把「无 candidate」读成「可以开始 Y2 放权」，是 8/20 复盘里同一类错误的复现。

### 4.2 主战场没了，必须显式换主环

Plan 把公文定为 Y1 主战场，中试为 Y3 扩展。2026-08-19 用户不再借调国转中心，两条冻结合法，**不要解冻**。

空出来的不是「没事做」，是「主环未选定」。继续用治理 dogfood 冒充价值，会再次把 T4-01 做成自指闭环。

### 4.3 成熟度与 AGE-v2 是资产，不是下一阶段的目标

T10 把 scorecard 做到可报 9.0，AGE-v2 把 Cell / cartridge / LSP / bus 铺上。它们的正确角色是：**已建成的脊柱，进入冻结期**。下一阶段只允许为「主人环走不通」或「减法门禁缺口」而改它们，不允许以「Phase 8 / 成熟度 9.5」立项。

---

## 5. 下一阶段定义

### 5.1 名称与窗口

**阶段名**：Y1-Remain / 价值闭环与表面积回收（简称 **VL-1**）

**窗口**：从本文采纳日起，到 Y1 年度门（Plan 的 Y1Q4-T1-01 语义：逐项冗余对账，不是再开功能清单）。日历上对应 2026H2 剩余时间。不把 Y2「深化与放权」提前。

**前一阶段（已结束）**：Y1Q3 台账关账 + T10 成熟度冲刺 + AGE-v2 Phase 5–7。允许作为资产入库，禁止作为惯势延续。

### 5.2 成功 / 失败 / 不做

**VL-1 成功（三条全要）**：

1. **周环**：连续 4 周，每周 ≥ 3 条被本人采纳的建议或署名产出（对齐愿景证伪条件的「开始计数」）。来源必须是主人真实输入，不能是治理自审。
2. **净减**：bin 脚本相对本文采纳日净减少（零调用归档 + 入口收敛到 cockpit）；不得新增 GaC required 规则除非同时删 1 条 required；不得新增独立项目/平台层。
3. **一端变实**：9 张场景卡中 **恰好 1 张** 离开 shadow 进入 assisted（有 ≥3 条主人 useful sample）。其余保持 shadow 或归档，禁止并行激活。

**VL-1 失败（任一即部分失败）**：

- 4 周后主人周环仍为 0，但 PR / ADR / 脚本继续增长。
- 再出现 AGE-v2 Phase 8、新评分体系、新编排引擎、新「操作系统」叙事。
- 把冻结的公文/中试重新标 done 或用合成样本升档。

**明确不做**：

- 不解冻国转中心场景（除非主人书面发起）。
- 不启动 Y2 L2/L3 放权（没有 calibration 数据）。
- 不重开 gbrain×kairon 代码互融。
- 不把 aetherforge 并入 runtime 当作本阶段主线（Y1Q4-T6-01 可排期，但排在主人环之后）。
- 不新增第二套战略文档。愿景仍是 Plan。

### 5.3 主环选择（阶段契约）

公文不能打。工程交付在 Plan 里「不计价值」，但它是目前唯一有真实流量的环。VL-1 **临时改判**：

> **主环 = 个人工作收件箱：把本周外部/自身信号变成 3 条主人署名产出，并记下改了什么。**

落地落在已有表面上，不新建项目：

```
信号（邮件/聊天/周报素材/工程待决）
    → cockpit decide / inbox          [EXISTS，未激活]
    → 一条最小旅程（取 → 问题清单 → 草稿或结论）
    → attest-review / weekly-review   [EXISTS]
    → north_star 记「采纳/改后采纳/忽略」 [EXISTS，缺主人习惯]
    → MOS decision_outcome 回填       [EXISTS，缺真实回流]
```

场景卡只升 **一张**。候选按「主人本周是否真会打开」排序，不按架构完整性：

| 优先级 | 场景 | 理由 |
|---|---|---|
| **1（默认）** | `knowledge-curation` 或「周回顾→署名笔记」 | 最接近愿景「记住改了什么」；不依赖国转中心 |
| 2 | `engineering-delivery-dogfood` | 已有样本与 observer；风险是再次自指治理 |
| 3 | `unified-inbox` | F1 正统入口；若主人拒绝每日打开则降级 |
| 禁用 | `document-review` / 中试 | 业务冻结 |
| 禁用 | 同时激活 ≥2 张 | 重演表面积 |

**默认选 1。** 若主人明确说「我就用工程 dogfood 当主环」，改选 2，并在 weekly-review 里把「治理自审」样本标 `out_of_value`（沿用 Plan：工程数据发生器 ≠ 北极星）。

---

## 6. 三条轨道（不是十二条 bet）

只允许三条并行。超过就停。每条轨道的工具优先 EXTEND 现有 cockpit / attest-review / anti-corrosion，禁止新 bin。

### Track A — 主人环（P0，本阶段唯一价值轨道）

| 项 | 内容 |
|---|---|
| 目标 | 连续 4 周，每周 3 条采纳；1 张场景卡 assisted |
| 写面 | `docs/scene-cards/**`、cockpit decide/inbox、attest-review、MOS outcome |
| 验收 | 主人能在 15 分钟内走完一次：inbox 里有条目 → 裁决 → 署名产出可回放 |
| 非目标 | 自动放权、多场景、新 UI 框架 |
| 人的动作 | 周一打开 inbox，周日 attest。没有这个习惯，轨道失败，agent 不能用 PR 补 |

### Track B — 表面积回收（P0，Y1 硬目标补课）

| 项 | 内容 |
|---|---|
| 目标 | bin 净减；零调用脚本归档；cockpit 成为人类默认入口 |
| 方法 | 用已有 `anti-corrosion-check` / script registry / subtraction quota，**执行归档**而不是再写检测器 |
| 验收 | `bet-ledger.py surface` 的 `bin_scripts` 相对 VL-1 起点下降；新增脚本必须删或归档等量 |
| 保护量 | `test_loc` 不得下降；不删 advisory 规则充数 |
| 非目标 | 「再登记一遍」；新的 registry 生成器 |

优先回收对象（指名，不设百分比）：

1. 零调用 / 无消费者 bin（script registry 已能列）。
2. 重复评分入口：对外只保留 `maturity-scorecard`（成熟度）+ `north_star`（价值）+ `omo-status`（运行）。其余降为内部实现。
3. 空转平台层：SEMA 自动结晶、AST merge driver、daemon 50-agent 压测 — **冻结**，无主人环证据前不得再扩展。
4. 休眠项目：family-hub / observability 维持暂停，不复活。

### Track C — 平台冻结与承重判定（P1，防守轨道）

对 AGE-v2 / resident / BCOS / AST-SEMA 做一次 **承重判定**，只出一张表，不写新架构：

| 组件 | 判定 | VL-1 动作 |
|---|---|---|
| ecos / omo / agora / runtime / cockpit | 承重 | 只修主人环阻塞 |
| knowledge (gbrain+kairon) | 承重，能力仍双栈 | 不互融；只保证召回可走通主环 |
| aetherforge / omlxc | 半承重 | 主环不依赖本地大模型 |
| AGE-v2 Cell / cartridge / LSP | 实验层 | **冻结** |
| resident 五角色 | 管道在、价值无 | 只修「事件源接入主人环」；禁止新角色 |
| BCOS evolution engine | 自指风险 | 冻结自我进化提案自动落地 |
| metaos / model-driven / l4-kernel | 待验证 | 本阶段不碰 |

Track C 的完成物是一页判定表 + 冻结名单进 GaC（已有 quota 即可，不新增规则类型）。

---

## 7. 波次

### W0 · 7 天 · 停损与选定

```
☐ 主人确认主环（默认知识策展/周回顾；备选工程 dogfood）
☐ 冻结名单生效：AGE-v2 / SEMA / 新评分 / 新编排 不得立项
☐ 记录 VL-1 表面积起点（跑一次 `bet-ledger.py surface`，日期入库）
☐ cockpit decide 或等价 inbox 能放入 1 条真实条目（不是治理自测）
☐ 本波次 PR 净增 bin = 0
```

门禁：没有主人确认主环，W1 不得开始。

### W1 · 14 天 · 走通一次

```
☐ 主人亲手走完主环 1 次（15 分钟剧本）
☐ 当周 ≥ 3 条裁决（采纳/改后采纳/忽略），写入 attest-review
☐ 场景卡仍为 shadow，但 sample 从 0 变成 ≥3
☐ resident/sediment 若被触发，产出不得再是空模板（空则标 NOT_PROVEN，不标 done）
☐ bin 开始净减（至少归档第一批零调用脚本）
```

门禁：没有主人亲手走通，任何「场景升档」PR 拒绝。

### W2 · 30 天 · 习惯门

```
☐ 连续 4 周每周 ≥ 3 条（不足则阶段失败，不延长功能清单）
☐ 1 张场景卡 shadow → assisted
☐ bin_scripts 相对 W0 起点明显下降（以 surface 为准，不在本文写死目标整数）
☐ AGE-v2 / resident / BCOS 无新 Phase
☐ Y1 冗余清单（双栈检索、零调用脚本、休眠项目）逐项状态更新
```

### W3 · 季度 · Y1 年度门预演

只做 Plan §2.2 的可持有性对账：

- 已识别冗余是否清零（指名项，不是行数百分比）。
- 保护量是否守住（`test_loc`、ADR 总数不靠删除历史充数）。
- 周环是否已开始（为 2027-12-31 证伪条件积累周数）。

过不了就收窄 Y1，不进入 Y2。

---

## 8. 红队（阶段设计自检）

| # | 攻击 | 回应 |
|---|---|---|
| 1 | 这是又一份战略，制造双主线 | 愿景 SSOT 仍是 Plan；本文只覆盖 Y1 剩余阶段；8/24 两周计划被本文替代 |
| 2 | 再开 12 条 T10 式 bet | 禁止。最多 3–5 条，且必须有主人行为验收 |
| 3 | 用工程 PR 数充当「每周 3 条建议」 | 治理自审样本标 `out_of_value`；主环默认不是 dogfood |
| 4 | 没有主人习惯，agent 会自己把 inbox 填满 | W0/W1 门禁是主人亲手走通；填满自审条目算失败 |
| 5 | 减法又去删测试 / advisory 规则 | 保护量写死；只归档零调用与重复入口 |
| 6 | AGE-v2 不继续会烂掉 | 冻结 ≠ 删除。无主人环证据前扩展是更大的腐烂 |
| 7 | 公文解冻后怎么办 | 保持 blocked；解冻走 `blocked_reentry_policy`，不走本文 |
| 8 | 知识层仍双栈，T6-01 是否假完成 | 承认 PARTIAL；VL-1 不重做互融，只要求主环召回可走 |
| 9 | cockpit 收编 670 个 bin 会变成新巨石 | 收编是「发现层」不是搬代码；实现可留 bin，人类默认只见 cockpit |
| 10 | 4 周太短 | 愿景证伪以周计。4 周还走不通，说明主环选错或系统不是为这个人服务的 |

---

## 9. 与既有文档的关系

| 文档 | 关系 |
|---|---|
| `STRATEGY-3YEAR-PLAN-2026H2-2029.md` | 愿景 SSOT，**不被替代** |
| `3y-bet-ledger.yaml` | 执行台账 SSOT。VL-1 需要新 bet 时改 YAML，不改人类视图 |
| `project-strategy-v1.md` | 九维诊断仍有效（场景 0 触发、入口过载）。其「12 个月放权」推迟到 VL-1 习惯门之后 |
| `two-week-integration-and-forward-plan.md` | **被本文替代**。Phase α（T10）已完成；Phase β/γ 的「再加工具」取消 |
| `2026-08-20-blueprint-strategy-retrospective.md` | 诊断仍成立（E4 未证）。T4-01 之后的爆炸没有推翻它 |
| ADR-0424 / 0425 / 0426 | 入库为冻结资产，不是 VL-1 工作项 |

---

## 10. 需要主人拍板的三件事

1. **主环选哪张场景卡？** 默认 `knowledge-curation` / 周回顾；备选工程 dogfood。选完 W0 才算开始。
2. **是否接受平台冻结？** 包括 AGE-v2 不再开 Phase、不新写评分器、不新写编排引擎。拒绝冻结 = 拒绝 VL-1，等于选择继续加厚中段。
3. **周一 inbox + 周日 attest 是否愿意做 4 周？** 不愿意，则不要让 agent 把本阶段标成可交付。

拍板前，agent 不应把本文标为台账 done，也不应派生 12 条新 bet。
