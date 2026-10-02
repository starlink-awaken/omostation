---
schema_version: specification/v1
spec_version: 1.0.0
title: BET-Y2Q4-T10-221 — 写面收敛轮的运行后果固化进 agent 感知面（投影兜底的仓库事实 / 判定装置自证 / 交付机制）
bet_id: BET-Y2Q4-T10-221
status: accepted
lifecycle: contract
last-reviewed: 2026-10-02
owner: governance-team
---

# 写面收敛轮的运行后果固化进 agent 感知面

> ADR-0456 决策 4（plan B5）收尾轮 T10-219 + T10-220 交付后，把**只有做的时候才知道**的事实
> 写进后续 agent 读得到、门禁查得到的文字。本 BET **纯文档**：不改 `.py`、不改 registry、
> 不翻 ADR-0456 的 status。

## 1 问题（本轮实测，非推断）

T10-220 把 system.yaml 的写者与读者收敛到 `state_root()`（已合并 `origin/main@ece7a6048`、
omo `1eda1fde7`），T10-219 把"谁写哪个键"变成门禁（#4571）。两轮的**代码后果**已经进了
台账和 receipt，但它们的**判定装置性质**和**仓库事实**没有进感知面，而这正是下一个人会踩的
东西。本轮在 `ws-t10-221-perception` 基线（`978aadf02`）上重新实测，得到五类。

### 1.1 「已提交的 legacy 兜底」不是这份仓库的性质

`runtime-projections.yaml` 声明的 17 条投影路径里，**只有 1 条在 `origin/main` 上被跟踪**，
而那条是 `.omo/_truth/registry/memory-os.yaml` —— 它是权限面（registry），不是生成态。
其余 8 条 canonical + 8 条 legacy 生成态**全部既未跟踪又被 gitignore**，包括测试断言要兜回去的
`.omo/state/health.yaml`（`.gitignore:411`，`:409-410` 的注释自己写明"readers take canonical
and report absence as not-generated"）。

后果分三条，都是可判定的：

- `projection_read()`（`bin/lib/repo_root.py:182`）的 legacy 分支返回的是**路径**，不是内容
  （`:199` 判 `is_file()`、`:201` 回退），其 docstring `:193` 已说"也可能是根本没生成过的"。
  一个**干净检出**（fresh clone、CI）两面都没有；兜底只有在"这个检出曾经跑过写者"时才存在。
- 于是 `tests/unit/test_repo_root_profile.py:146` 的断言（`:150` 期望
  `REPO/.omo/state/health.yaml`）**按构造不可满足** —— 它把"仓库里有一份提交的旧文件"当既有事实，
  而那正是 gitignore 禁止的。实测：该用例在本基线 FAILED。
- 同文件对面的 `tests/unit/test_projection_reader_resolution.py:42` 之所以 PASS，是因为它的
  fixture **自己造出** legacy 文件。这是测兜底的唯一合法形状：**先物化，再断言**。

同一条判据也解释了两根命名的不对称：`state_file_read()`（`:204`）没有 canonical/legacy 两个
名字（docstring `:207-209`），它是同一相对路径的两份副本；而 `system.yaml` 之所以还在跟踪里，
是 `.gitignore:294` 的一条显式反选（`!.omo/state/system.yaml`），**不是**疏漏。所以检出里那份
从 T10-220 起就是**设计上的陈旧快照**，读者不得当作现值。

### 1.2 写路径必须在调用时刻解析，模块常量会冻结 env

四个写者都改成了 `_system_yaml()` 这样的调用时刻解析缝：`bin/compass_radar.py:1138`（调用点
`:1414`）、`bin/gac/harness-omo-bridge.py:39`（`:190`）、`bin/gac/self-evolution-loop.py:35`
（`:245`）、`bin/gac/evidence-smoke.py:212`（`:235`）。原因是模块常量在 **import 时**求值，
profile 在 import 之后声明就被冻结在旧根上 —— 而**没有任何测试会红**（同 AGENTS.md 已有的
`compass_radar.py:482` 不传 `env=` 那条沉默契约）。新写者若把路径写成模块级常量，就是这个形状。

缝的另一半是**不许写半份镜像**：`bin/gac/harness-omo-bridge.py:193` 在 state 根那份不存在时
**跳过**（注释 `:191-192` 写明"凭空写一份只有 harness 键的镜像会让 `state_file_read` 的读者
读到缺字段的新状态"）。这不是保守，是 `state_file_read` 能整文件偏向 state 根的前提 ——
写者若允许部分镜像，整文件优先就是错的读法。

### 1.3 扫源码的判定装置必须先自证，且要按源码顺序展平

两条装置性质，写下来是为了下一个人不必重新发现：

- `/`-链要**按源码顺序**递归展平（`tests/unit/test_system_yaml_write_plane.py:254-256`
  `_path_segments`）。用栈弹出序拼接会把 `a / b / c` 读成别的次序，于是同一个字面量能绕过检测。
- 任何这类检测器都要拿**合成违规样本自证**：`projects/omo/tests/test_omo_system_yaml_state_root.py:99`
  `test_detector_itself_catches_a_known_offender`。空绿的代价不是"少查一项"，是**一条判据在写者
  没改完时就变绿**。
- 检测器的边界是**显式**的：`tests/unit/test_system_yaml_write_plane.py:240`
  `CHECKOUT_PINNED_ALLOWLIST`（8 条检出侧残留，`:293` 断言集合相等、`:296` 断言每条理由指向真实
  文件）。允许清单被测试钉住，才不会被下一次"顺手加一条"稀释成无清单。

### 1.4 两个门禁的真实语义与它们的自否证方式

- `bin/ssot/script-registry.py validate()`（`:115`）把 id 收进 **set**（`:119`、`:124`）⇒
  重复 id 静默折叠；`missing = git ls-tree HEAD 的 bin 全部脚本 − registered`（`:133`、`:147`）
  ⇒ "把一个 id 改指到活副本"会让旧脚本从 registered 消失、当场报 `Missing registrations: 1`，
  **判据自己否证自己**。validate 也不校验 schema（57 条 `maturity` 取值在枚举外无告警）。
- `bin/gac/omo-state-write-guard.py` 的归属检查是 `present == declared` **双向**（`:156`，
  两类违规 `:181` undeclared-key / `:189` ghost-declaration，计数 `:256`）⇒ **只声明已经存在的键**。
  声明一个 HEAD 上不写的键会当场造出幽灵声明，把上一轮的绿判据变红（本轮 `worktree_dirty_count`
  即因此不声明）。
- `R-GOV-2` 结构上不可能变红：`check_score_convergence()`（`bin/gac/governance-convergence-lint.py:159`）
  在 `:161` 初始化 `errors`、`:176` 原样返回，中间只 `warnings.append`（`:168`、`:173`）。
  所以拆掉 compass_radar 的跨键复制是**安全动作**，不需要先立 known-debt。
- CI 的 pytest 面是**显式文件白名单**（`.github/workflows/governance-check.yml:118-127`，
  七条具体文件 + `-q`），**不含 `tests/unit/**`** ⇒ §1.1 那个红的用例本地跑得到、CI 看不见。
  新增 `tests/unit` 判据时，"CI 绿"不构成证据。

### 1.5 台账与交付机制（本轮踩实的四条）

1. `bet-ledger.py complete` 要求 `engineering.merged_reachable_commit` **本地可达**（`bin/plan/bet-ledger.py:1682`）
   ⇒ squash-merge 之后必须先 `git fetch origin main` 再 complete，否则
   `COMPLETION_GIT_REF_NOT_REACHABLE` 会连带报 `OVERALL_STATE_MISMATCH: derived='blocked'`，
   看着像 evidence 写错，其实是对象库没取。
2. `WORK_PACKET_SOURCE_DRIFT`（`bin/plan/bet-ledger.py:2336`）只 gate **claim**；`status` /
   `done_at` / `completion_evidence` 不在 packet 投影里，retro 与 receipt 路径实测可未 claim 提交。
   `refresh-packet`（`bin/agent-workflow.py:1031` → `_refresh_packet_run` `:814` →
   `_assert_packet_sources_at_ref` `:738`）要求检出里 ledger/spec 字节 == `origin/main`
   （`:772`），所以**新建 BET 首轮用不上它**。
3. GitHub 对 squash-merge 自动删除 head 分支；往同名分支再 push 会把**整条旧 stack** 复活。
   二次交付必须从当前 `origin/main` 起新分支 + cherry-pick，并用
   `git diff --name-status origin/main..HEAD` 查 `D` 行（PITFALL-COO-005 的同族）。
4. 本地门禁与 closeout 的 hook 会脏 `.omo/state/system.yaml`（纯时间戳）与
   `.omo/tasks/registry/INDEX.md`（`Updated:`）⇒ 交付前 `git checkout --` 这两处，别把生成态搭在
   功能 PR 上（AGENTS.md §7 已记过这条纪律，本处只补"具体是哪两个文件"）。

## 2 交付

在两个感知面上落字，不新增代码：

- `AGENTS.md` §7 Common Pitfalls —— 新增条目，覆盖 §1.1（兜底的仓库事实 + 测兜底的合法形状）、
  §1.2（import 冻结 + 不许半份镜像）、§1.4（三个门禁的真实语义与自否证）、§1.5（四条机制）。
  每条给可复制判据，每个 `path:NN` 指针在本检出实测可解析。
- `.omo/_knowledge/decisions/0456-dev-runtime-profile-root.md` —— 追加一节带日期的执行期实测
  （与既有 §7「B1 执行期实测出的两个例外」和第 273 行之后的 Addendum 同体例），记录两根命名
  不对称（`projection_read` 双名 vs `state_file_read` 单名两副本）与 `!.omo/state/system.yaml`
  这条反选的后果。

## 3 非目标

- **不翻 ADR-0456 的 status**（`PROPOSED → ACCEPTED` 属 principal 决定），也不处理 `id: ADR-0456`
  的重号（另有 `ADR-0456-governance-downshift-closeout-grading.md`）。
- **不修** §1.1 那个红的用例，也不动 `tests/**`（另立 BET，task #105）。本轮只把它的**前提**
  写进感知面，并给出判别方法。
- **不复制 env 优先级表**：该表唯一表述在 `bin/README.md` 与 `ARCHITECTURE.md`，本轮两处一字不动。
- **不改** `bin/**/*.py`、`.gitignore`、`.github/workflows/**`、`.omo/_truth/registry/**`。

## 4 完成判据

1. AGENTS.md 新增文字里的每个 `file:line` 指针在本检出可解析（文件存在且行号 ≤ 行数），逐条测量。
2. 每条新断言都有一条**本检出重跑**的读数支撑（不是引用记忆）：投影路径跟踪/忽略矩阵、
   `test_projection_falls_back_to_committed_legacy_path` 的 FAILED 读数与对面用例的 PASSED、
   `R-GOV-2` 分支的 `errors` 恒空、`script-registry validate()` 的 set/ls-tree 语义、
   write-guard 的 `present == declared`。
3. 纯文档交付：`git diff --name-only origin/main...HEAD`（三点式）不含 `.py`。
4. `bin/README.md` 与 `ARCHITECTURE.md` 的 diff 为空。
5. 新 spec 通过 `doc-governance-check.py --no-new-warnings --scope tracked`。
