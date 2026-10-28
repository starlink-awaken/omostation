---
schema_version: specification/v1
spec_version: 1.0.0
title: 运行时写进检出的 .omo/state 面必须既不被跟踪也不被看见 —— 摘库未完成 = 脏检出 + 可被扫进 commit
bet_id: BET-Y2Q4-T10-276
owner: governance-agent
status: accepted
lifecycle: contract
last-reviewed: 2026-10-28
---

# BET-Y2Q4-T10-276 — `.omo/state` 运行时面摘库收尾（ADR-0456 B5 残面）

> 范围：`.gitignore` 对 `.omo/state/**` 的覆盖面 + 一条由**写者源码派生**的守卫用例。
> 不改任何写者代码、不删机器上的运行时文件、不碰 launchd/plist/crontab。

## 1. 缺陷的可测形状

`nimble-bay-asp.md` B5 的 verify 判据是「一次 dev 运行后 `git status --short .omo/state` 为空」。
2026-10-28T03:45Z 在 canonical 检出实测（`git status --porcelain --untracked-files=all .omo/state`）：

```
?? .omo/state/daemon/resident.pid
?? .omo/state/daemon/service_state.json
?? .omo/state/healer/approvals.jsonl
?? .omo/state/healer/heal-179200.json … heal-f18369.json   (11 个)
?? .omo/state/memory/distilled_crystallization.json
?? .omo/state/notification/history.jsonl
```

= **4 个目录 / 15 个文件**，既未被跟踪也未被忽略。同一目录下 `.gitignore` 已经有 9 条同类规则
（`:46 history/`、`:136 agent-cell/`、`:138 value-baselines/`、`:296 policy-radar/`、
`:297 agent-beliefs/`、`:298 agent-cards/`、`:299 swarm/`、`:347 observability-adapters/`、
`:368 attestations/`），也就是说「运行时 state 目录一律 ignore」这条约定**存在**，这 4 个是漏项，
不是另一种设计。`git ls-files .omo/state` 只有 1 份被跟踪
（`collab-dualtrack.yaml`，由 `:306` 显式反选保留）。

未被忽略的运行时文件的代价不是「不好看」：`git add -A` / 交付期 hook 扫盘可以把 daemon 心跳、
healer 记录、通知历史整块扫进 commit（本仓 §7「生成态不随功能 PR 走」多次剔除过同类搭车），
而 `status: dirty` 判据（`gac-worktree.sh merge/release` 的守卫、发布器的
`projection_dashboard_tree_dirty`）也把它们当在制工作。

**漏项不止这 4 个。** 真机上只长出了这 4 个目录，是因为常驻族恰好只跑过这几条路径；把写者面
按源码字面量横扫（§3.2），治理内核包共声明 **14 个** `.omo/state/<dir>/` 写面目录，其中
`agent-cell` / `agent-beliefs` / `policy-radar` / `runtime` 四个已有规则，**其余 10 个与本轮这 4 个
一样既未跟踪也未忽略**。按实测的 4 个补规则会把「这次扫到几个」当成契约内容 —— 那 10 个目录
一旦在别台机器上被跑到，就是同一缺陷复发。故本轮范围取**派生全集**，不是实测集。

## 2. 写者侧不是缺陷 —— 本轮的否证记录

进入本轮前的假设是「这些目录的写者绕过了 profile 缝」。实测否证它：写者的**读用点**一律过
`omo.resident.write_path()`（`service_runner.py:55-56`、`memory_distiller.py:68/221-222/234`、
`notification.py:199/210/218/221`）。声明 `OMOSTATION_STATE_ROOT` 后 `omo.omo_paths.STATE_ROOT`
实测随 env 移动（`/Users/xiamingxing/Workspace` → 哨兵目录），而模块级常量仍钉检出根，那是
T10-233 spec §2 写明的设计（「修在读用点而不是定义点」，另有 89 处 `monkeypatch.setattr` 测试缝
依赖常量）。⇒ 本轮**不动写者**；未忽略的根因是 canonical 机器未声明 profile，
`state_root == code_root`，写进检出**按契约成立**，需要收尾的是「检出里看见了它」。

**订正一处起手时的错误引用**：起草时把 `healer.py:160` 也列为缝内写者，实测该文件
**不在 gitlink 钉住的那个 omo commit 里** —— canonical `projects/omo` 检出带着并发在制工作
（`?? src/omo/resident/healer.py` 及 4 个 `M src/omo/resident/*.py`）。后果两条：① 本轮的源码派生尺
按构造扫不到 `healer`，因此它作为**实测单列项**进规则（`.gitignore` 注释里点名理由）；② 那批未提交
改动属别人的在制工作，本轮**未触碰** canonical，也不把它登记成仓库缺陷。

## 3. 交付内容

1. `.gitignore` 在既有 `.omo/state/**` 段之后增 **11 条**目录规则（10 条来自派生全集 +
   `healer/` 实测单列），形状与既有 9 条逐字同构：尾斜杠、目录级、不用通配吞掉 §1 的反选清单。
2. `tests/unit/test_omo_state_plane_ignore_invariants.py`（6 条用例）：
   - **派生集合**：从**整个内核包** `projects/omo/src/omo/**` 的源码字面量导出 `.omo/state/<dir>`
     的目录段，五种写法都算命中 —— `/` 链（`ROOT / ".omo" / "state" / "daemon" / …`）、整串
     （`ROOT / ".omo/state/daemon/x.json"`）、`Path("…")` 直接构造、文档串与任意内联串
     （`_INLINE_DIR`）、f-string 的字面部分。目录段必须是首尾字母数字的标识符，于是
     `system.yaml`、`health.yaml.bak-*`、`.omo/state/**` 这类文件段/glob 与 `convergence-pulse-`
     这类 f-string 断头都是**排除项而不是漏项**（§7④：匹配来源而不是名单）。
   - **集合相等断言**：派生集合 = 14 名基线，漏一种形状或新增长出目录都在这里红。
   - **两把互不共享失效模式的尺**：AST 扫源码给「该忽略哪些目录」，`git check-ignore --no-index`
     与规则文本解析（last-match-wins + `!` 反选）各自判「实际忽略了没有」，两把尺读数必须一致。
   - **改前 N / 改后 0 由同一装置产出**：scratch repo 物化 §1 那 15 个运行时文件，`before` 用
     `git show HEAD:.gitignore`、`after` 用工作树那份，同一条 `git status --porcelain
     --untracked-files=all .omo/state` 读出 **15 → 0**（§7⑤）。
   - **检测器自证**：合成模块注入四种字面量形状，断言点名命中，且文件名段不被误认成目录；
     摘掉一条真实规则后文本尺必须返回 `None`（§7①③）。
   - **反面**：`collab-dualtrack.yaml`（唯一被跟踪项）与 `:306-309` 四条反选都不得被新规则吞掉 ——
     文本尺读 `False`、`git check-ignore` 不命中，且 `git ls-files .omo/state` 仍为 1。
   - hermetic：不读本机 `.omo/state` 是否存在这些目录（那会随 host 翻红），只读**规则面**与
     **源码面**；根走 `bin/lib/repo_root.py::code_root()`，不由 `__file__` 反推。

## 4. 不在范围与登记的残留

- 不改 `omo.resident` 任何写者；若后续发现缝外的写点，另立 BET。
- **不删除**机器上这 15 个运行时文件（那是运行数据，不是我的清理对象），也不 `git rm` 任何
  已跟踪文件。
- 不收紧既有 ignore / re-include 行的语义（`:294 *.jsonl`、`:295 *.json`、`:304 system.yaml`、
  `:306-309` 反选）；本轮只加，不改。
- 不碰 plist / launchd / crontab / 权威 ledger（B4b 逐批授权面）。
- 不宣布 ADR-0456 B1/B2/B3/B4/B4b/B5 或整个 plan 完成 —— B5 的「dev 禁 git 写」条款不在本轮。

**残留一（写面范围）**：守卫只覆盖治理内核包 `projects/omo/src/omo/**`（本轮 claim 的面）。把同一
派生尺架到 `bin/**` 上另读出 **5 个既未跟踪也未忽略**的目录：`evolution-proposals`、`handoffs`、
`heartbeats`、`mos`、`proposals`（各自有 `bin/` 内写者，`panorama-collect.py`、`session-handoff.py`、
`meta-doctor.py` 等）。它们不在本轮 claim 面内，**按此登记而不是顺手扩范围** —— 扩了会让「派生集 =
规则集」这条断言的验收基线与被交付的 diff 不是同一件事。`bin/**` 侧另有 `convergence-pulse-{周}`、
`m2-ssot-batch-{N}` 两个带变量后缀的文件名，静态目录规则写不出来，是另一种形状。

**残留二（canonical 检出带并发在制工作）**：`projects/omo` 主检出有 `?? src/omo/resident/healer.py`
与 4 个 `M src/omo/resident/*.py`（别人的活，本轮未触碰）。这直接影响派生尺的可见面：同一份规则在
「gitlink 钉住的 commit」与「本机当前检出」上派生出的集合可以不同。判据已按前者写（派生自本检出
的 `projects/omo`），healer 作为实测单列项进规则并在 `.gitignore` 注释点名原因。

## 5. done_when 的可复现读数

| 判据 | 装置 | 实测读数 |
|------|------|----------|
| 派生全集各有 `.gitignore` 规则 | `git check-ignore --no-index` + 规则文本解析两把尺互证（15 个目录 = 14 派生 + healer） | uncovered **0/15**，两把尺读数一致 |
| 检出面不再看见运行时文件 | scratch repo 物化 §1 那 15 个文件，`before` 用 `git show HEAD:.gitignore`、`after` 用工作树那份，同一条 `git status --porcelain --untracked-files=all .omo/state` | **15 行 → 0 行**（同一装置、同一条命令） |
| 唯一跟踪项未被吞 | `git ls-files .omo/state` = `collab-dualtrack.yaml` 一条；四条反选文本尺读 `False` 且 `check-ignore` 不命中 | 成立 |
| 守卫由源码派生且能自证 | `test_derivation_is_not_a_no_op`（五种字面量形状 + 两类排除项）、`test_kernel_state_write_dirs_are_the_reviewed_list`（集合相等） | 6 passed |
| 变异对照（牙齿） | 六组，每组改法不同、按改法分别记读数 | M1 摘内联常量分支 → **2 failed**（自证 + 集合相等）；M2 摘派生扫描本体 → **2 failed**（同两条）；M3 放宽目录段形状回收 f-string 断头 → **1 failed**（自证）；M4 摘本轮全部规则 → **3 failed**（覆盖 + 缺规则点名 + 15 行实测）；M5 只摘 `daemon/` 一条 → **3 failed**（同 M4，说明单条缺失即红，不是整体缺失才红）；M6 摘掉四条反选 → **1 failed**（跟踪项被吞那条） |
| hermetic | `env -u OMOSTATION_ROOT -u OMOSTATION_STATE_ROOT -u OMO_EVENT_LEDGER_DB HOME=<空目录> UV_CACHE_DIR=<空>` + 最小 venv（`uv run --no-project --with pytest --with pytest-timeout --with pyyaml`）复跑 | **6 passed**（不读本机 `.omo/state` 是否存在这些目录） |
| 台账与规范绑定 | `python3 bin/plan/bet-ledger.py lint` + `accepted_specifications[0].content_digest` = spec 文件字节 sha256 | lint `573 bets … no errors`；摘要按字段路径回写，不按值反选 |

