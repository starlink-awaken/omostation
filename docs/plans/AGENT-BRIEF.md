# AGENT-BRIEF — 三年规划台账执行指令

> 给任何一个准备认领 bet 的 agent。**读完本文再动手，不要跳过第 1 节。**
>
> 台账 SSOT：`docs/plans/3y-bet-ledger.yaml`
> 人类视图：`docs/plans/3Y-BET-LEDGER.md`
> CLI：`python3 bin/plan/bet-ledger.py --help`
> 战略依据：`docs/STRATEGY-3YEAR-PLAN-2026H2-2029.md`
> 审计依据：`docs/reports/2026-08-06-deep-review-proactive-agent-and-scenario-orchestration.md`

---

## 1. 你必须先知道的三件事

### 1.1 这个仓库正在被多个 agent 同时改，你的文件会被别人删掉

2026-08-06 实测：一小时内 HEAD 变了四次，分支在 `main` / `work/governance-phase9` / `work/governance-phase9-dimension` / `work/governance-phase10` 之间切换，**所有未 `git add` 的文件被连带清理，且因从未入库，无任何 blob 可恢复**。

已知因此永久丢失的"已交付"产物：`bin/ssot/journey-runner.py`（601 行）、`bin/ssot/scene-card-lifecycle.py`、`bin/ssot/validate-scene-card-v2.py`、`docs/scene-cards/v2/`（5 文件）、`Plans/v10-*.md`（4 份）。

> **所以：写完一个文件，立刻 `git add`。不要等到 commit，不要等到收尾。**
> `git clean` 不会删已暂存的文件。这是唯一有效的防护。

### 1.2 这个项目的主要矛盾是"表面积超限"，不是"能力不够"

实测：98.2 万行代码 / 4537 文件 / 18 项目、344 份 ADR（8 月前 6 天新增 85 份）、134 条 GaC 规则、309 个 bin 脚本、53 份标准。

**Y1 的唯一硬目标是让系统变小。** 所以你交付的每一个 bet 都要回答："我让系统变大还是变小了？"

> 推论：**不要顺手新增文件、规则、脚本、ADR、文档。** 需要新增就必须在复盘里记账，且大概率要配一个对应的删除。

### 1.3 这个项目历史上最常见的失败模式是"声明 ≠ 事实"

三类真实案例，你要避免成为第四类：

- **代理指标冒充真实指标**：X3「工作交付 4/8」实际是在数 `spaces/` 下含 "delivery" 字样的 YAML 的文件修改时间。
- **自出题自答冒充能力证据**：221 个"协作场景"是自造的区块链红队夹具，98.6% 通过率与真实业务无关。
- **docstring 声称已做而代码未做**：`scenewatcher.py` 三处声称"决策日志入 `bos://memory/mos/*`"，代码里没有任何 MOS 调用。

---

## 2. 认领流程（照抄命令）

### 2.1 看有什么可领

```bash
python3 bin/plan/bet-ledger.py status
```

优先领**窗口靠前**的（Y1Q1 > Y1Q2 > …）。带 ★ 的需要人到场，你领不了，跳过。

### 2.2 检查能不能领

```bash
python3 bin/plan/bet-ledger.py claim-check <BET-ID>
```

它会检查四件事——状态可认领、依赖已 done、无冲突轨道在跑、未超并行上限（4）——并**直接打印后续所有命令**。检查不过就换一个 bet，不要强行开工。

### 2.3 开隔离工作树（强制，防止和其他 agent 互删）

```bash
bash bin/gac/gac-worktree.sh claim <bet-id 小写>
```

**不要在共享主工作树上直接改文件。** 如果 bet 的 `pasw_required: true`，子模块改动必须在 `.subtrees/<sub>/` 内完成（ADR-0371，涉及 gbrain / cockpit / agora）。

### 2.4 起 workflow（ADR-0203 红线：先 start 再改文件）

```bash
uv run --with pyyaml python bin/agent-workflow.py start <workflow-id> \
  --profile <agent-profile> --objective "<BET-ID> <标题>"

uv run --with pyyaml python bin/agent-workflow.py claim <run-id> --path <每个写面>
```

`workflow-id` 和 `agent-profile` 在 `claim-check` 的输出里，也在 bet 的 `workflow` 字段和轨道的 `agent_profile_hint` 里。

---

## 3. 执行期纪律

| 做 | 不做 |
|---|---|
| 只改 `write_surfaces` 列出的路径 | 改别的路径（= 越权，D3） |
| 严格遵守 `non_goals` | 把 `non_goals` 当建议；想做就另开 bet |
| 每写完一个文件立刻 `git add` | 攒着最后一起 add |
| 超 appetite × 1.5 立刻走 `circuit_breaker` | 硬扛、加班、扩范围 |
| 发现计划与事实不符 → 记下来，进复盘 Q3 | 默默按计划做完假装没事 |
| 采集不到的指标标"未接入" | 用代理量、估算值、合成数据填充（D1） |

**特别提醒**：`done_when` 里每一条都要能被 `verify` 里的命令验证。如果你发现某条 `done_when` 无法验证，这本身是一个发现，写进复盘 Q3，不要自行放宽标准。

---

## 4. 收尾流程（照抄命令）

```bash
# ① D0 优先：先入库，再验证
git add <所有 deliverable>

# ② 台账验收（同时跑 D0 检查）
python3 bin/plan/bet-ledger.py verify <BET-ID> --execute

# ③ 表面积记账（D2）
python3 bin/plan/bet-ledger.py surface

# ④ workflow 验证与关闭
uv run --with pyyaml python bin/agent-workflow.py verify <run-id> --from-diff --execute
make agent-workflow-closeout RUN_ID=<run-id>

# ⑤ 门禁
make gac-local-gate
make ssot-guardian

# ⑥ 写复盘（D5：无 retro 不得置 done）
#    .omo/_knowledge/retros/<BET-ID>.md

# ⑦ 提交与释放
bash bin/gac/gac-worktree.sh submit <bet-id 小写>
```

**不要 commit 到 main、不要 push、不要 merge，除非人类明确确认。**

---

## 5. 六条铁律（closeout 必检）

| 编号 | 铁律 | 检查 |
|---|---|---|
| **D0** | 任何交付物在 `git add` 之前不算交付 | `git ls-files --error-unmatch <file>` |
| **D1** | 采集不到的指标显示"未接入"，禁止代理量顶替 | review 抽查 |
| **D2** | closeout 必须报告净增减（行/文件/规则/ADR/脚本） | `bet-ledger.py surface` |
| **D3** | 先 claim 后写，未 claim 的写面视为越权 | `bet-ledger.py claim-check` |
| **D4** | 走 ADR-0203 workflow，先 start 再改文件 | `agent-workflow.py start` |
| **D5** | 无 retro 不得置 done | `bet-ledger.py retro-due` |
| **D6** | 指标设立前必须回答「最便宜的达标路径是什么」，若那条路径有害则指标不成立 | 设指标时人工反问；已知有害路径写进 non_goals |

---

## 6. 复盘模板（强制，`.omo/_knowledge/retros/<BET-ID>.md`）

五问是固定的，因为要跨 bet 比较。**不要改问题，不要少答。**

```markdown
# <BET-ID> 复盘

## Q1 实际耗时 vs appetite？超出比例？
（appetite: X；实际: Y；超出 Z%。若超 1.5× 说明为什么没触发 circuit_breaker）

## Q2 done_when 是否全部通过？哪条没过，为什么？
（逐条列，通过打 ✅，没过写原因，不要模糊化）

## Q3 过程中发现的与 plan 不符的事实（打假）？
（这一栏空着通常说明没认真找。计划是我基于 2026-08-06 的快照写的，
  执行时一定会发现偏差。写下来比装作没有更有价值）

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？
（贴 `python3 bin/plan/bet-ledger.py surface` 的输出。
  若净增，说明为什么必要，以及配套删了什么）

## Q5 下一个认领本 track 的 agent 需要知道什么？
（踩过的坑、没做完的尾巴、隐含依赖、环境要求）
```

---

## 7. 向人类汇报的格式

完成后用这个格式回报，**不要写长篇总结**：

```
BET-ID: <id>
状态: done / blocked / failed
耗时: <实际> vs <appetite>
done_when: <n>/<total> 通过（未过的逐条说明）
表面积净变化: 代码 <±行> / 文件 <±n> / 规则 <±n> / ADR <±n> / 脚本 <±n>
D0 入库: <已 git add 的文件清单>
打假发现: <Q3 摘要，一到三条>
需要人拍板的: <若有>
复盘: .omo/_knowledge/retros/<BET-ID>.md
```

---

## 8. 明确禁止

- ❌ 在共享主工作树上直接改文件（用 `gac-worktree.sh claim`）
- ❌ `git commit` / `push` / `merge` 到 main（除非人类明确确认）
- ❌ `git clean` / `git reset --hard` / `git stash -u`（会删别的 agent 的未入库文件）
- ❌ 修改 `.omo/goals/current.yaml`（仅人类可改）
- ❌ 直接写 `.omo/` 或 `spaces/`（走 OMO CLI / MCP / 已注册 broker）
- ❌ 新增顶级项目、新增顶级入口、新增治理维度
- ❌ 用文件存在、schema 通过、模拟 harness 代替真实完成
- ❌ 把 Agent 数量 / 工具数量 / 场景数量 / 测试数量写进进展叙述
- ❌ 领 ★ 标记的 bet（需人到场）

---

## 9. 遇到这些情况停下来问人

- `claim-check` 不过，但你认为应该能领
- `done_when` 有条目无法验证
- 需要改 `write_surfaces` 之外的路径
- 需要新增文件/规则/脚本，且找不到对应可删项
- 发现台账本身有错（依赖搞反、appetite 明显不合理、目标已过时）
- 触发 `circuit_breaker` 且降级方案也做不到

**停下来问，比按自己的理解改计划要好。** 这个项目的历史教训是：agent 自行调整计划的速度，超过了人类核对的速度。
