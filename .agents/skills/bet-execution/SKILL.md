---
name: bet-execution
description: "认领并执行三年规划台账（3Y-BET-LEDGER）里的 bet。当你要开始一项工程/治理任务、需要知道现在该做什么、或被要求「领一个 bet」时使用。Triggers on: bet, 台账, ledger, BET-Y1Q1, bet-ledger, 认领任务, claim bet, 三年规划, 我该做什么, what should I work on, 下一步做什么。"
---

# Bet Execution — 台账认领与执行

台账把三年规划拆成了可并行认领的 bet。本技能告诉你怎么领、怎么做、怎么收尾。

**SSOT**: `docs/plans/3y-bet-ledger.yaml`
**人类视图**: `docs/plans/3Y-BET-LEDGER.md`
**完整指令**: `docs/plans/AGENT-BRIEF.md`（第一次执行前必须通读）
**战略依据**: `docs/STRATEGY-3YEAR-PLAN-2026H2-2029.md`
**审计依据**: `docs/reports/2026-08-06-deep-review-proactive-agent-and-scenario-orchestration.md`

---

## 0. 先知道三件事

**① 这个仓库有多个 agent 并行，你的文件会被别人删掉。**
写完一个文件立刻 `git add`。详见 skill `git-discipline`。

**② 主要矛盾是表面积超限，不是能力不够。**
Y1 唯一硬目标是让系统变小。所以每个 bet 收尾都要回答"我让系统变大还是变小了"。
推论：不要顺手新增文件、规则、脚本、ADR、文档。

**③ 最常见的失败模式是"声明 ≠ 事实"。**
不要用文件存在、schema 通过、模拟 harness 代替真实完成。

---

## 1. 领一个 bet

```bash
# 看现在能领什么（按窗口排序，优先做靠前的）
uv run --with pyyaml python bin/plan/bet-ledger.py status

# 挑一个不带 ★ 的（★ 需人类到场，你领不了），检查能否认领
uv run --with pyyaml python bin/plan/bet-ledger.py claim-check <BET-ID>
```

`claim-check` 检查四件事——状态可认领、依赖已 done、无冲突轨道在跑、未超并行上限（4）——
通过则**直接打印后续所有命令**，照抄执行即可。

不通过就换一个 bet，不要强行开工。

### 看清楚这个 bet 要什么

```bash
uv run --with pyyaml python bin/plan/bet-ledger.py show <BET-ID>
```

重点看四个字段：

| 字段 | 含义 |
|---|---|
| `goal` | 一句话目标 |
| `non_goals` | **硬边界，不是建议**。想做里面的事 → 另开 bet |
| `done_when` | 验收条件，逐条都要能被 `verify` 里的命令验证 |
| `circuit_breaker` | 超 appetite × 1.5 时怎么降级。到点就执行，不要硬扛 |
| `evidence` | 若有，是这个 bet 的立项实测依据，读完再动手 |

---

## 2. 开工

```bash
# ① 隔离工作树（强制，防止和其他 agent 互删）
bash bin/gac/gac-worktree.sh claim <bet-id 小写>

# ② 起 workflow（ADR-0203 红线：先 start 再改文件）
uv run --with pyyaml python bin/agent-workflow.py start <workflow-id> \
  --profile <agent-profile> --objective "<BET-ID> <标题>"

# ③ claim 每一个写面
uv run --with pyyaml python bin/agent-workflow.py claim <run-id> --path <每个 write_surface>
```

`workflow-id` 与 `agent-profile` 在 `claim-check` 的输出里，也在 bet 的 `workflow` 字段
和轨道的 `agent_profile_hint` 里。

### 执行期纪律

- 只改 `write_surfaces` 列出的路径。改别的 = 越权（D3）。
- **每写完一个文件立刻 `git add`**（D0）。
- 发现计划与事实不符 → 记下来，进复盘 Q3。不要默默按计划做完假装没事。
- 采集不到的指标标"未接入"，不要用代理量、估算值、合成数据填充（D1）。
- 若 `done_when` 有条目无法验证，这本身是一个发现，写进 Q3，不要自行放宽标准。

---

## 3. 收尾

```bash
# ① D0 优先：先入库再验证
git add <所有 deliverable>

# ② 台账验收（同时跑 D0 检查）
uv run --with pyyaml python bin/plan/bet-ledger.py verify <BET-ID> --execute

# ③ 表面积记账（D2）
uv run --with pyyaml python bin/plan/bet-ledger.py surface

# ④ workflow 验证与关闭
uv run --with pyyaml python bin/agent-workflow.py verify <run-id> --from-diff --execute
make agent-workflow-closeout RUN_ID=<run-id>

# ⑤ 门禁
make gac-local-gate && make ssot-guardian

# ⑥ 写复盘（D5：无 retro 不得置 done）
#    .omo/_knowledge/retros/<BET-ID>.md

# ⑦ 钉死 + 提交
git tag -a "bet/<BET-ID>-$(date -u +%Y%m%dT%H%M%SZ)" -m "<BET-ID> deliverable"
bash bin/gac/gac-worktree.sh submit <bet-id 小写>
```

**第 ⑦ 步的 tag 不是可选项。** commit 只是暂时安全——共享分支被 rebase 时
提交会脱离历史、内容从工作树消失（2026-08-06 实测发生）。tag 的 ref 不随分支重写消失。

---

## 4. 六条铁律（closeout 必检）

| 编号 | 铁律 | 检查 |
|---|---|---|
| **D0** | 交付物在 `git add` + `tag` 之前不算交付 | `git ls-files --error-unmatch <file>` |
| **D1** | 采集不到的指标显示"未接入"，禁止代理量顶替 | review 抽查 |
| **D2** | closeout 必须报告净增减（行/文件/规则/ADR/脚本） | `bet-ledger.py surface` |
| **D3** | 先 claim 后写，未 claim 的写面视为越权 | `bet-ledger.py claim-check` |
| **D4** | 走 ADR-0203 workflow，先 start 再改文件 | `agent-workflow.py start` |
| **D5** | 无 retro 不得置 done | `bet-ledger.py retro-due` |

---

## 5. 复盘模板（`.omo/_knowledge/retros/<BET-ID>.md`）

五问固定，因为要跨 bet 比较。**不要改问题，不要少答。**

```markdown
# <BET-ID> 复盘

## Q1 实际耗时 vs appetite？超出比例？
## Q2 done_when 是否全部通过？哪条没过，为什么？
## Q3 过程中发现的与 plan 不符的事实（打假）？
## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）
## Q5 下一个认领本 track 的 agent 需要知道什么？
```

**Q3 空着通常说明没认真找。** 台账是基于 2026-08-06 快照写的，执行时一定有偏差。
**Q4 是 Y1 主目标的下沉。** 若净增，必须说明为什么必要、配套删了什么。

---

## 6. 汇报格式

```
BET-ID: <id>
状态: done / blocked / failed
耗时: <实际> vs <appetite>
done_when: <n>/<total> 通过（未过的逐条说明）
表面积净变化: 代码 <±行> / 文件 <±n> / 规则 <±n> / ADR <±n> / 脚本 <±n>
D0 入库: <已 git add 的文件清单> + tag
打假发现: <Q3 摘要，一到三条>
需要人拍板的: <若有>
复盘: .omo/_knowledge/retros/<BET-ID>.md
```

不要写长篇总结。

---

## 7. 停下来问人的六种情况

1. `claim-check` 不过，但你认为应该能领
2. `done_when` 有条目无法验证
3. 需要改 `write_surfaces` 之外的路径
4. 需要新增文件/规则/脚本，且找不到对应可删项
5. 发现台账本身有错（依赖搞反、appetite 不合理、目标已过时）
6. 触发 `circuit_breaker` 且降级方案也做不到

**停下来问，比按自己的理解改计划要好。**
这个项目的历史教训是：agent 自行调整计划的速度，超过了人类核对的速度。

---

## 8. 改台账

- **改 `3y-bet-ledger.yaml`，不改 `3Y-BET-LEDGER.md`**（后者是视图）
- 改完跑 `bet-ledger.py lint`
- 新增 bet 必须给全：`goal` / `non_goals` / `done_when` / `verify` / `write_surfaces` / `circuit_breaker`
- **新增 bet 前先问：这是不是在增加表面积？** 是的话必须配一个对应的减法 bet
- 注意 YAML 陷阱：列表项里未加引号的冒号会被解析成 dict，静默丢失语义。lint 会查这个。
