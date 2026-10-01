---
schema: md/v1
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-10-01
type: report
bet_id: BET-Y2Q4-T10-217
title: BET-Y2Q4-T10-217 closeout — bin/ 侧根写手挂 state_root，三个仓根 env 私有别名退役
---

# BET-Y2Q4-T10-217 closeout — ADR-0456 B5 残留（根侧写手）

契约：`docs/superpowers/specs/2026-09-30-bet-217-root-side-writers-state-root.md`（v1.0.0，
`status: accepted`，`lifecycle: contract`，digest `sha256:046312f6ea322cf7890c6743020acddbcbd906fbf303ec4687fdf5b57692006a`，
合并后冻结，改一字即破坏台账 binding）。
交付：`bin/gac/evidence-smoke.py`、`bin/gac/task-inventory.py`、`bin/mof/generate-brief.py`、
`bin/ssot/generate-docs-index.py` 四个根侧模块 + 两个路径断言测试 + 台账/spec 两条记录。
run：交付 `20260930T131106Z-project-code-change-a4e5ad95`，回填 `20261001T005127Z-project-doc-change-6a707287`。
PR：**#4591**，3 commit（`03b5ef7d118` governance_code+docs+docs_data / `9b37e1d3af5` code / `9d69f19e4bc` docs_data），
squash 合并为 `ff6e45a7479242e655373314d53d9bdc05e7800d`，CI 22 pass / 0 fail，L3 deep review 0 findings。
复盘：`.omo/_knowledge/retros/BET-Y2Q4-T10-217.md`

## 1 本轮的唯一硬规则：写者可独走，读者须随写者

spec §0.5 把这一轮的判据压成一句话：**写面可以单独改挂 `state_root()`；读面只有在它的写者已经改挂之后
才允许跟着走** —— 否则读者静默读到另一棵树的旧数据，而没有任何测试会红。所以 §2 的每一条 MOVED
都配一条 KEPT，配不成对的项就整条留在检出侧。

台账 verify 第 2 条把这条规则做成了机器判据（在声明 profile 的子进程里逐常量比对前缀），本轮复跑读数：

```
MOVED   <state>/.omo/_delivery/evidence-smoke            (evidence-smoke.py:110 OUTPUT_DIR)
MOVED   <state>/runtime/task-inventory/snapshots         (task-inventory.py:39 SNAP_DIR)
MOVED   <state>/runtime/task-inventory/drifts.jsonl      (task-inventory.py:40 DRIFTS)
MOVED   <state>/.omo/state/system.yaml                   (generate-brief.py:18 SYSTEM_YAML)
KEPT    <checkout>                                       (三处 WORKSPACE = code_root())
KEPT    <checkout>/.omo/_knowledge/governance-history.jsonl   (evidence-smoke.py:111)
KEPT    <checkout>/.omo/_knowledge/omo-events.jsonl          (evidence-smoke.py:112)
KEPT    <checkout>/.omo/state/task-registry.yaml         (task-inventory.py:36 REGISTRY)
KEPT    <checkout>/BRIEF.md                              (generate-brief.py:19 BRIEF_MD)
```

四项 KEPT 各自的理由都不是"没来得及"：

| KEPT 项 | 实测理由 |
|---|---|
| 两个 `*.jsonl` | `git ls-files` 两条均在跟踪集合里，与 `.omo/state/system.yaml` 同属"生成态未摘库"cohort（另立，见 §4）。摘库前先搬读者＝把跟踪文件的写入挪进 gitignore 区，diff 会凭空消失。 |
| `REGISTRY` | 全仓（`bin` + `projects/omo/src` + `projects/runtime` + `crontab.new` + `.github`）**查不到写者**，只有两个读者（`task-inventory.py:36`、`panorama-collect.py:3198`）。没有写者的读面改根，等于把读者指向一个不存在的目录。 |
| `BRIEF_MD` | 它是 git 跟踪的人类读物，摘库属 §4 那批；本轮只保证显式 `OMOSTATION_BRIEF_OUTPUT` 不再把根一起拖走（测试 `test_explicit_output_is_used_without_dragging_the_root`）。 |
| 三处 `WORKSPACE` | 读面（`.omo/_truth/registry/**`、`collab-dualtrack.yaml`）按 ADR-0456 归 code root，逐条由测试钉住。 |

## 2 未声明 profile 时对运行态零效应——用字节等式证明，不是用"应该没影响"

verify 第 3 条把 `origin/main` 的四个模块 checkout 到 tmp 目录，与 HEAD 版本在同一 env（显式
`env -u` 四个别名）下各起一个进程打印 12 个路径常量，归一化后逐字节比对：

```
IDENTICAL <ROOT> | <ROOT>/.omo/_delivery/evidence-smoke | <ROOT>/.omo/_knowledge/governance-history.jsonl
| <ROOT>/.omo/_knowledge/omo-events.jsonl | <ROOT> | <ROOT>/.omo/state/task-registry.yaml
| <ROOT>/runtime/task-inventory/snapshots | <ROOT>/runtime/task-inventory/drifts.jsonl
| <ROOT> | <ROOT>/.omo/state/system.yaml | <ROOT>/BRIEF.md | <ROOT>
```

这条同时是回滚判据：profile 未声明时 `state_root() == code_root()`，两棵树同一个值，
所以 B4b 的 plist/cron 改道不必等这一轮，也不受这一轮影响。

verify 第 4 条 `ALIAS-SURVIVORS-3` 记录三个私有别名的剩余 env 读点：`agent-presence.py:23`、
`agent-tick-daemon.py:36`、`agent-tick-daemon.py:55`。判据刻意用 `environ.get("…")|getenv("…")` 式
grep 而不是裸串 grep：实测 `bin/gac/meta-doctor.py:50` 是
`re.compile(r"\$OMO_WORKSPACE_ROOT|…")` —— 一条匹配字面量的正则，不是 env 读方；
`bin/gac/documents-zcode-config.py:196` 与 `bin/gac/documents-claude-desktop-config.py:167`
各有一行 `"WORKSPACE_ROOT": str(contract.workspace_root)`，是配置键的**写方**。裸串 grep 会把
这三处算进来假红（本轮实测：`OMO_WORKSPACE_ROOT` 在 `bin/**/*.py` 去 `_archive/` 后共 2 行，
env 读点 1 行）。

## 3 六条 verify 的全部复跑读数（回填 worktree，HEAD = `ff6e45a74`）

台账 `verify` 的 6 条命令在本 worktree 用 `subprocess.run(shell=True)` 逐条重跑（与
`bet-ledger.py:_run_verify_cmd` 同一执行面），**6/6 exit 0**：

| # | 命令 | 读数 |
|---|---|---|
| 1 | 三 file pytest | `16 passed in 0.09s`（9 + 5 + 2） |
| 2 | 声明 profile 的 MOVED/KEPT 比对 | MOVED 恰 4、KEPT 恰 7（§1） |
| 3 | HEAD vs `origin/main` 常量字节等式 | `IDENTICAL` + 12 常量（§2） |
| 4 | 三别名 env 读点 | `ALIAS-SURVIVORS-3` |
| 5 | 生成态不随本轮走 | 交付分支上打印恰 8 条路径、`.omo/state/**` 与 `BRIEF.md` 零命中；合并后同命令在 main 为空（分支 delta 已成 commit），持久等价读数 `git show --name-only ff6e45a74` = **8 files** |
| 6 | `make gac-local-gate` | `GaC local gate: PASS (68 checks executed, 1 SOFT WARN)`，另 6 条 known-unavailable 跳过 |

第 5 条在交付阶段不只是一条判据，它拦下了一次真实污染：跑门禁期间 hook 把
`.omo/state/system.yaml` 的 `health_score_evidence_generated_at` 改脏（实测 `100.0`，来源
`bin/gac/evidence-smoke.py`），`git checkout --` 剔除后把这类污染写进判据 —— 即 `AGENTS.md` §7
"生成态随交付动作漂移"那条坑（#4346/#4359）在这一轮的结构化堵法。回填阶段这条污染**又发生一次**
（`closeout` 交付 run 时同一行被改写），同法剔除 —— 判据第 5 条两次都保持 exit 0。

文档治理侧：本 receipt 与 retro `git add` 后跑
`bin/ssot/doc-governance-check.py --no-new-warnings --scope tracked` =
**PASS（4530 files，145 warnings）**，告警数与 T10-216 轮末值相同、受检文件 +2，
即两份新文档没有带入新告警。

## 4 本轮量出来、但按 non-goals 留在门外的三件事

1. **`task-inventory` 的整条数据面是空的。** `crontab.new:90` 声明每天 09:35 跑它，实测
   `crontab -l | grep -c task-inventory` = **0**（未安装，与 G8 的 morning-brief 同类复发）；
   `runtime/task-inventory/` 既无 `snapshots/` 也无 `drifts.jsonl`；它读的
   `.omo/state/task-registry.yaml` untracked、无写者、且在 `~/Workspace` 与两个 state root 下
   **都不存在**；`load_registry()`(`:61-69`) 用 `except Exception` 把缺文件压成 `[]` 后继续。
   ⇒ 本轮把 SNAP_DIR/DRIFTS 改挂 state root 在结构上是对的，但今天零运行流量；
   "改根"不能替代"这条链本来就没在跑"。
2. **`agent-presence` 的协调面：初稿写的"两份准入清单自相矛盾"是类别错误，改判如下。**
   它写的 `runtime/agents/*.json` 确有仓外读者 `bin/gac/ci-local-fast.py:539`（实测该行
   `presence = WORKSPACE / "runtime" / "agents"`，紧邻的 `:540` 是
   `if not presence.is_dir(): return` —— fail-open，目录不存在就静默跳过在场检测）。
   但我原先拿来对数的 `allowed_runtime_roots` **不是目录白名单**：全仓唯一读者是
   `projects/omo/src/omo/omo_rollout.py:38`，校验对象是 rollout envelope **自己声明的**
   `rollout_context.runtime_residue_paths`（`:37`），经 `_is_allowed_runtime_path`（`:22-24`）
   前缀匹配后产出 `disallowed_runtime_paths`（`:40`）参与 `decision` —— 它是"单次 rollout 的
   残留准入"，不扫文件系统，因而与 stamp-policy 的 runtime 孤儿审计**不是同一个谓词的两个声明**。
   真实缺口在 stamp-policy 一侧，一次探针即可复现：在检出里放 `runtime/agents/probe-scratch.json`
   后 `bin/gac/omo-runtime-stamp-policy.py --json` 报 `ok: false` +
   `orphan_paths: [{path: runtime/agents/probe-scratch.json, size: 30}]`（探针随即删除，
   `git status --short` 只剩回填 receipt 一条）。三条通道对 `runtime/agents` 全部零命中 ——
   `ALLOW_PATHS`（`:34-45`，其中 `:38` 恰收 `runtime/coordination/handoffs/**`）无该条、
   `.gitignore` 无该条（`runtime/**` 侧只忽略 `*.log` / `*.jsonl` / `*.pid` / `runtime/data/` 等，
   `:60-72`）、projection registry 的 17 条不含它。⇒ `agent-presence.py register` 只要真跑一次，
   第一次落盘就把 `gac-gate` 变红。
   再看这条链今天有没有流量：本机 **7 个检出**（主仓 + 6 worktree，`git worktree list | wc -l`）
   里 `runtime/agents` **零存在**；`runtime/coordination/handoffs/` 每个检出只有 1 个文件，就是
   tracked fixture `test-run-001.json`（`run_id: test-run-001`、`agent_id: sisyphus`）—— 那也就是
   初稿"git 跟踪目录"那句话的全部实质；除自身 registry 条目
   `bin/_registry/scripts/governance/agent-presence.yaml` 与文档叙述外**零调用者**；
   `crontab -l | /usr/bin/grep -c agent-presence` = **0**；`.githooks` 零引用。
   ⇒ #101 的前置不是"先定边界再改根"，而是两件按序的事：先决定这条**注册在案却从未被调用**的链
   要不要活，若要活就再给 `runtime/agents` 一个合法准入（projection registry 或 `.gitignore`），
   写者与读者（`ci-local-fast.py:539`）同移。这是"注册即事实"的第三次同类复发
   （§4.1 task-inventory、会话任务 #97 morning-brief）。
3. **三个 jsonl/生成态 cohort 未摘库**（`governance-history.jsonl`、`omo-events.jsonl`、
   `system.yaml`）。摘库属 ADR-0129 的收尾（#98），本轮只保证不改它们的根。

## 5 本轮写错并被自己的测量改掉的三处

- verify 第 3 条初稿把整串 `python3 -c "…"` 赋给 `P` 再喂给 `-c`，程序文本被当源码解析，
  `SyntaxError: invalid syntax`。修法是 `P` 只装 python 程序；这条已写进该判据的 `expect`，
  因为下次重写判据的人仍会踩。
- 台账 `verify` 初稿缺，`bet-ledger.py lint` 直接 `ERROR BET-Y2Q4-T10-217: 缺字段 verify`；
  补 6 条时又连撞两处 YAML 结构事实：`- id:` 起始块 `yaml.safe_load` 返回 **list**（要 `[0]`），
  且 T10-217 是 `bets:` 序列的**最后一个**条目 —— 条目边界是第一个 column-0 行（`campaigns:`），
  不是下一个 `- id:`，按后者切片会把顶层键吃进块里报 `expected <block end>`。
- **§4.2 初稿的"两份清单互斥"。** 它在交付 PR #4591 合并前就进了台账 `non_goals` 与 spec §2，
  回填阶段按判据 1 逐行去核 `allowed_runtime_roots` 的读者时才发现那是 envelope 级残留准入
  （`omo_rollout.py:37-40` 的对象来自 envelope 自己声明的 `runtime_residue_paths`），
  我拿两个不同谓词的**条目**对了一次差就写成"矛盾"。改判后本节以探针读数为准。
  判据补一条：**要说"两份声明矛盾"，先证明它们校验同一个对象**（同一批路径、同一方向的动作），
  否则只是两句话看起来不一致。本轮的三处里前两处是"跑一次就知道"，第三处是"读一次读者就知道"——
  都属同一类错误：把没验过的机制写进契约。

## 6 回填阶段撞出来的协调面读数（第三次独立实证）

`gac-local-gate` 报 `change-lane-check: FAIL mixed lanes=code,docs,docs_data,governance_code`，
读 `bin/change-lane-check.py` 后确认 `code` 与任何 lane 不同乘 —— 三个 commit 的拆法由此确定，
而不是凭印象。回填阶段两条：

1. 首轮 run `20261001T004900Z-…` 的 `claim` 报
   `WORK_PACKET_SCOPE_MISMATCH: … is outside [8 个代码交付面]`。packet 的 `scope.write_surfaces`
   **由台账条目派生**，而 T10-217 条目当初只登记了代码面，两个回填产物（本 receipt + retro）
   从未在内 —— 按 T10-216 先例（它的 `write_surfaces` 就含 report 与 retro）补两行后新 run 放行。
   台账 `verify` 参与 packet 哈希，所以这只能是"新 run"，不是"改旧 run"。
2. 补完 scope 后 `claim docs/plans/3y-bet-ledger.yaml` 报
   `A2A Path Lock Collision … in run 20260930T131106Z-project-code-change-a4e5ad95` ——
   交付 run 的锁跨 worktree 挡住回填 run，这是"协调面全机共享"的第三次独立实证
   （前两次于 T10-216 §1）。而 `closeout` 交付 run 又先报 `missing_retro`：
   **retro 必须在交付 run closeout 之前落盘**，尽管它记的是交付轮的复盘。

## 7 交付边界

未启停任何服务、未改 plist/cron/registry、未动 `projects/omo/**` 与 `.gitignore`、
未摘任何跟踪状态、未删任何并发会话的锁。`OMO_WORKSPACE_ROOT` 在 `bin/` 只剩 2 处
（1 处 env 读 + 1 处字面量正则），`OMOSTATION_WORKSPACE_ROOT` 的脚本侧读点归零。
ADR-0456 的 `status` 翻转与 id 重号仍属 principal（claim 打印的下一个空闲编号是 ADR-0461）。

本回填 PR 还多做了两件，都限定在已登记面内：

1. **改判两处已合并文本**（spec §2 非目标第 ② 条、台账 T10-217 `non_goals` 第 1 条）——
   它们随 #4591 进了 main，内容就是 §5 第三处那个类别错误。决定本身（不移 `agent-presence.py`）
   不变，只把理由换成可复现读数。spec 属 `lifecycle: contract` 且被台账按 `content_digest` 绑定，
   所以本 PR 同时重算 spec 与本 receipt、retro 三份 sha256 并回写绑定值；
2. **一次瞬时探针**：在 worktree 里建 `runtime/agents/probe-scratch.json` 供
   `omo-runtime-stamp-policy.py` 判定后立刻删除（读数见 §4.2）。产物未提交、
   `runtime/` 下 `git status` 干净。写代码面零变更 —— 本 PR 的 diff 只含 4 个文档路径。
