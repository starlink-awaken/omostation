---
lifecycle: plan
owner: governance-team
last_updated: 2026-08-18
type: ephemeral
---
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

### 1.4 子模块指针更新统一走秒级 bump-fast 与 Auto-PR，严禁执行全量 submodule update

- **严禁**：执行 `git submodule update --init --recursive`（耗时 >90s 且会长时间占用 D2 锁阻塞其他 agent）。
- **指针快进**：使用 `bash bin/gac/gac-worktree.sh bump-fast <submodule_path> [--sha <sha>|--latest-main]`（基于 cacheinfo，<1s 完成）。
- **发布自动化**：子模块打 Release Tag 或执行 `workflow_dispatch` 后，会自动调用主仓 Reusable Workflow 并在主仓发起 `auto-bump/*` PR，通过 CI 门禁后人工点击合并。全仓 19 个子仓均已预置 `OMOSTATION_BOT_TOKEN`。

### 1.5 开工前与收工后使用 `omo-status` / `omo-top` 检查全局状态与锁占用

- **秒级快照**：执行 `bin/omo-status`（或 `make omo-status`，<0.2s），快速自检 6 个 Agent 心跳、D2/D3 锁占用、19 子仓指针漂移与 BET 台账完成度。
- **全屏实时大盘**：执行 `bin/omo-top`（或 `make omo-top`），按 `1~4` 深入查看锁堆栈与 A2A 消息流。

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

#### T1-05 delivery-attempt 独立 clone

写入型 agent 的稳定身份是 `actor_id`；每一次交付另分配不可复用的
`delivery_attempt_id`。一个 actor 可以并行拥有多个 attempt，但每个 attempt 必须有
独立 clone、分支、manifest、provenance、readiness、changeset 和 PR head。不要手工
复制目录，也不要用长期 `--reference` 借用 `~/Workspace` 的对象库：源仓移动或 GC
会破坏借用仓。

```bash
python3 bin/gac/agent-clone.py create --agent-id <agent-id> \
  --delivery-attempt-id <attempt-id> --source <origin-url-or-path> \
  --destination "$HOME/agents/<agent-id>/attempts/<attempt-id>/ws" --json
python3 bin/gac/agent-clone.py manifest \
  --clone "$HOME/agents/<agent-id>/attempts/<attempt-id>/ws" \
  --output "$HOME/agents/<agent-id>/attempts/<attempt-id>/manifest.json" --json
python3 bin/gac/agent-clone.py verify \
  --clone "$HOME/agents/<agent-id>/attempts/<attempt-id>/ws" \
  --manifest "$HOME/agents/<agent-id>/attempts/<attempt-id>/manifest.json" --json
```

`create` 只接受不存在的目标路径，初始化根仓声明的全部子模块（不递归穿越
嵌套 Workspace 镜像），切换到 `agent/<actor>--<attempt>` 私有分支，并在成功后
写入 clone 私有 identity、启用 `.githooks`。这里使用 `--` 而不是
`agent/<actor>/<attempt>`：Git 不允许既有 `refs/heads/agent/<actor>` 与其子 ref
并存。actor/attempt 以 identity 字段为准，禁止从分支字符串反向推断。

冻结 manifest 是执行基线，不是第二份任务 SSOT。跨仓交付由 `changeset` 汇总
root 与子仓 SHA；它只生成候选收据，不会自行 push 或 merge。v1 identity 仅保留
读取、验证和退役兼容；所有新 writer attempt 必须使用 v2 attempt-qualified identity。

写入型 agent 必须设置 `AGENT_ID=<agent-id>` 并使用独立 clone。tracked hook
对所有 agent identity 自动启用严格门，拒绝没有独立 clone identity 的 linked
worktree；改写 `HOME` 不会降级准入。Orca 可注册和打开独立 clone，但 Orca 自己
创建的 linked worktree 只可作为人类迁移/检查环境，不能承接 agent 写入。
D2/D3/D5 仅在全员迁移和 72 小时零冲突证据成立后退役。

```bash
AGENT_ID=<agent-id> \
  python3 bin/gac/agent-clone.py guard \
  --workspace "$HOME/agents/<agent-id>/attempts/<attempt-id>/ws" \
  --require-clone --json
```

### 2.4 起 workflow（ADR-0203 红线：先 start 再改文件）

```bash
uv run --with pyyaml python bin/agent-workflow.py start <workflow-id> \
  --profile <agent-profile> --bet <BET-ID> --objective "<BET-ID> <标题>"

# claim 前必须生成可复算 receipt（缺失、篡改、过期或覆盖不全都会拒绝）。
# 根仓文件（包括 docs/）必须显式加入 workspace-root；projects/<name>/ 路径加入对应项目名：
uv run --with pyyaml python bin/gac/affected-graph.py \
  --workspace-root . \
  --changed-projects workspace-root <涉及项目> \
  --output .omo/evidence/<session>/affected-graph-receipt.json --json
uv run --with pyyaml python bin/agent-workflow.py claim <run-id> \
  --path <每个写面> \
  --affected-receipt .omo/evidence/<session>/affected-graph-receipt.json
```

`workflow-id` 和 `agent-profile` 在 `claim-check` 的输出里，也在 bet 的 `workflow` 字段和轨道的 `agent_profile_hint` 里。

需求迭代 `start` 必须带 `--bet`（根仓 `bin/agent-workflow.py` 与 `omo.workflow.cli` 同一谓词；`bet_id` 写入 run）。`ok` closeout / `bet-ledger complete` 缺北极星指针、run 绑定或 retro 会 halt。冷启动看 `bootstrap`/`status` 的 `chain:` 行：active 显示最近 BET-ID，已关闭显示最近 `BET-ID (closed)`（按 run `updated_at`/`created_at`，不是文件名第一），从未绑定显示 `unbound`。执行器：`bin/plan/chain-bind-check.py`；红线：`redlines.yaml::vision-to-retro-chain`（digest：`make gen-agent-redlines`）。对照表：`docs/architecture/wave-gate-bet-map.md`。`bet-ledger verify --execute` 会把 verify 命令非 0 变成自己的非 0。

**⚠️ 三个实测过的坑（2026-08-14 T1-05A 修复轮补充）**：

1. **profile × workflow 权限矩阵是硬约束**——`start` 会拒绝无权跑该 workflow 的 profile（如
   engineering-agent 跑 governance-state-mutation）。不确定时先跑
   `bin/agent-workflow.py agents` 查权限矩阵，别照抄轨道 hint 就开工。
2. **`verify --file` 必须逐个 append**——`--file` 是 `action=append`，一次传多个路径会报
   unrecognized arguments。批量大 diff 直接用 `verify --from-diff`。
3. **verify 不带 run_id 时**，lifecycle 会把 argv 串拼进锁文件名——多文件场景直接撞
   `Errno 63 File name too long`。**带 run_id 或用 `--from-diff`**。
4. **跨 lane 的基础设施 bet**——`make gac-local-gate` 的 change-lane-check 若报 mixed
   lanes，先查 `.omo/_truth/registry/agent-workflows/_root.yaml` 里对应 diff check 的
   `allowed_lanes` 是否覆盖你的
   lane 组合（ADR-0129 §11.3.2: workflow 显式授权优先于硬编码隔离）；修复通道是补
   check 的 `allowed_lanes`，不是手动 env 伪造。

**⚠️ 三个失败模式（2026-08-24 T10 验收会话，golden-rules: BASE-TREE-SNAPSHOT / SCHEMA-VALIDATOR-FIRST / TIME-FIRST-TRIAGE）**：

1. **API 推送必须用完整 base_tree**——GitHub Git Data API 的 tree 是**完整快照不是 patch**。
   `base_tree=None` + 只列变更 blobs = `.github/workflows/` 整个被删 → CI 0 runs
   （PR #2126 曾因此 debug 一整轮）。**用 `bin/gac/gh-api-push.sh` 一键推送**
   （内置 base_tree=父完整树 + 推后验证 workflows 存在），别手搓 gh api。
2. **填 schema 数据先读 validator**——`bet-ledger complete` 的 completion_evidence
   有三类必踩坑：diff 用 `receipt://`|`repo://`（不能用 `git://`）；merged_reachable_commit
   用 `git://origin/main@<40hex>` 且先 `git merge-base --is-ancestor` 验证可达；
   value.ACCEPTED 必须 attestation（ref+sha256）+ 声明 `overall_state: outcome_accepted`。
   先读 `bin/plan/bet-ledger.py` 的 `COMPLETION_DIRECT_EVIDENCE` / `_validate_evidence_reference`
   再填，别报错驱动式试。
3. **CI 失败先算时间戳再归因**——`system_health.yaml` 的 `last_scan` 超 48h SLA 会让
   CI meta-doctor fail（曾因 age 恰好跨 48h 边界误判"环境性"）。先 `date`+换算 age，
   心跳状态过期是**可修的状态**，刷新 last_scan 即治本；只有"时间戳算过+反证找过+与
   改动无关已证"才能标 blocked/环境性。

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

### 3.1 诊断三步法（T9-01 ④ — 两次误诊换来的，强制）

下结论前必须按序走完三步，缺一步就是诊断不重现（模式 2）：

1. **先看时间戳/版本** — 日志、报错、plist 的 mtime 是不是「现在」？2026-08-15 事故：err 日志里 Xcode Python 路径是 08-08 旧残留，被当当前问题写进汇报。
2. **再看反驳证据** — 找一条能推翻你假设的证据。plist 内容已是对的？进程其实活着？只有支持性证据没有反驳性证据 = 还没诊断完。
3. **最后才下结论** — 结论必须同时兼容两类证据。「现象吻合 ≠ 因果成立」。

### 3.2 测试隔离规则（T9-01 ③ — bump-fast 污染真实指针事故）

| 测试类型 | 在哪跑 |
|---|---|
| 只读测试（status/lint/dry-run） | worktree 里随便跑 |
| **写操作测试**（改指针/改 state/发请求） | **必须 temp repo / temp dir**，禁止在真实 repo 或主仓跑 |

判断标准：这条命令会不会改仓库状态？会 → temp 环境。2026-08-14 事故：bump-fast 计时测试在真实 repo 跑 `--latest-main`，改了 omlxc 指针留下 registry 不一致。

### 3.3 状态变更与提交同树（T9-01 ① — PR #1518 丢变更事故）

改了 status / 台账 / 任何受治理字段后：**当场 `git add + git commit` 到当前 worktree 分支**，然后才允许开新 worktree。verify 的 `diff_baseline` 检查会拦「claim 基线之后冒出来且未被 claim 覆盖的变更」——被拦到就说明你要么漏 claim，要么在别的树改了东西。

### 3.4 Agent 停工交接（E7 — 2026-08-15 补充）

**Agent 停工前必须填写退役交接清单**（E7 根治，防止孤儿资源遗留）。

#### 强制触发条件（任一满足即填写）

- 任务被人类终止 / 预算耗尽暴毙
- 工作流 verify 失败且决定放弃
- Bet 完成，需要释放所有资源
- 切换到另一个 Agent 身份（如 engineering-agent → governance-agent）

#### 填写步骤

1. **使用模板**：`docs/operations/agent-retirement-handoff-template.md`
2. **填写内容**：
   - 在途 worktree 清单（路径/分支/状态）
   - 在途 Orca worker 清单（terminal handle/用途/是否可回收）
   - 活跃 claim / workflow run 清单
   - 未推送 commit 位置
3. **提交方式**：
   - 作为附件粘贴到 workflow closeout 的 `--evidence`
   - 或在 PR body 中粘贴（若 workflow 未启用）

#### 接手人协议

- **第一步**：运行模板 §5 的五组命令，盘点遗留资源
- **孤儿 worker 回收**：超 48h 未活动的 Orca worker 可直接回收
- **活跃任务转交**：在途 claim / workflow run 必须显式转交或 close

#### 豁免条件（仅以下情况可跳过）

- 纯只读任务（无任何 worktree / worker / claim）
- 人类明确书面豁免（在 workflow evidence 中标注）

> **违例后果**：停工前未填写 → 后续审计追溯时记入「治理违约」，对应 bet 不予 done。

### 3.5 治理演进工作必须先登记治理 bet（G8 — 2026-08-24 补充）

**触发**：任何"改进治理机制本身"的工作 —— 治理文档 / GaC 规则 / 检查器 / scorecard
升级 / SSOT 口径对齐，且非 observer-audit 只读任务。

**规则**（防止 S1/S5/CONV-3 三次 blocked 复发）：

1. **先登记治理 bet**：在 `docs/plans/3y-bet-ledger.yaml` 登记一个 `T10-MATURITY` 或
   governance 类 bet（如 T10-07/08/09/10），或复用现有治理 bet
2. **用 bet 绑定 run**：`start <workflow> --bet <治理-bet-id>`，不要走无 bet 的 waiver run
3. **closeout 走治理 bet 闭环**：治理演进由 bet 承载 vision→run→retro 链，无需业务 bet
   （chain-bind-check 对治理 workflow + 治理 bet 豁免业务 bet 绑定）

**豁免**：仅 observer-audit（只读审计）可无 bet；业务功能改动必须绑定业务 bet。

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
- ❌ `git clean` / `git reset --hard` / `git stash -u`（会删别的 agent 的未入库文件；agent 环境 PATH shim 已强制收口，T1-07）
- ❌ raw `git --no-verify`（**逃生口只有 `bin/gac/swarm-git` 一个入口**，T1-07 PATH shim + swarm-git 强制拦截 `--no-verify` 与高危操作）
- ❌ 修改 `.omo/goals/current.yaml`（仅人类可改）
- ❌ 直接写 `.omo/` 或 `spaces/`（走 OMO CLI / MCP / 已注册 broker）
- ❌ 新增顶级项目、新增顶级入口、新增治理维度
- ❌ 用文件存在、schema 通过、模拟 harness 代替真实完成
- ❌ 把 Agent 数量 / 工具数量 / 场景数量 / 测试数量写进进展叙述
- ❌ 领 ★ 标记的 bet（需人到场）

---

## 8.5 L3 归并操作规程（T6-01 实证，2026-08-16 四坑入册）

大规模内包（submodule → 目录内包）必须按此清单执行，缺一步都是返工：

### 8.5.1 搬运完整性双校验（gitignore 黑洞坑）

- `git archive` 搬运后，**必须** `git ls-files <新路径>` vs `git ls-tree -r <子仓> HEAD` 对比
  ——磁盘 `find` 对比全绿 ≠ git 索引完整（`.gitignore` 泛目录规则如 `kos/`、`skills/`
  以任意深度匹配，曾吞 342 个源码文件，唯一暴露口是 CI capability drift）
- 嵌套 `.gitmodules` 条目、运行时 db（`*.sqlite`/`*.db`）、`.omc/` 会话、graphify-out
  一律不入仓（tree 有 ≠ 该进）

### 8.5.2 子模块指针纪律（add -A 吸指针坑）

- **禁止**在 bump-pointer 后再 `git add -A` / `git add projects/<sub>`——会把 checkout
  旧 HEAD stage 进去，覆盖 update-index 的新值（曾致修复 3 轮「修了又报」）
- 正确顺序：子仓 `.subtrees/<sub>` commit → push 走 main → `git update-index
  --cacheinfo 160000,$(git -C .subtrees/<sub> rev-parse HEAD),projects/<sub>` →
  **commit 前必验** `git ls-tree HEAD projects/<sub>` == subtree HEAD
- 指针要过 pre-push 的 pointer-drift gate，子仓修复必须**先合进子仓 main**（PR squash
  或直推），side-branch 指针必被 DIVERGED 拦

### 8.5.3 路径改写三查（sed 自指坑）

批量 sed 后必须复核三类自指文件：①spec/文档里描述「旧→新」的映射文字
②`.githooks/`、CI workflow 里的路径常量与 PASW 列表 ③`.gitmodules` 条目本体。
拼接式路径（`Path / "projects" / "kairon"`）sed 字面量改不到，**找常量 SSOT 根**
（如 `omo_paths.KAIRON_DIR`）一处修全修。

### 8.5.4 双声明源与表面积证据

- BOS 有**双声明源**：`etc/bos-services.yaml` + `resolver/services.py`（POC_SERVICES）
  + `mcp_gateway.py`（KNOWN_BACKENDS）——改一个漏两个，evidence-smoke 是验收口
- surface 前后对比用 **numstat 两 commit 差值**（worktree 子模块 checkout 完整度会污染
  绝对值）；test_loc 是保护量，workflow 先跑基线再动手

---

## 9. 遇到这些情况停下来问人

- `claim-check` 不过，但你认为应该能领
- `done_when` 有条目无法验证
- 需要改 `write_surfaces` 之外的路径
- 需要新增文件/规则/脚本，且找不到对应可删项
- 发现台账本身有错（依赖搞反、appetite 明显不合理、目标已过时）
- 触发 `circuit_breaker` 且降级方案也做不到

**停下来问，比按自己的理解改计划要好。** 这个项目的历史教训是：agent 自行调整计划的速度，超过了人类核对的速度。
