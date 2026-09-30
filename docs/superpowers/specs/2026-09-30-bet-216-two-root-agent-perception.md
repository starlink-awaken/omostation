---
schema_version: specification/v1
spec_version: 1.0.0
title: BET-Y2Q4-T10-216 — 两个根的行为后果固化进 agent 感知面
bet_id: BET-Y2Q4-T10-216
status: accepted
lifecycle: contract
last-reviewed: 2026-09-30
owner: governance-team
---

# BET-Y2Q4-T10-216 — 两个根的行为后果固化进 agent 感知面

## 0 为什么单独立一轮

`ADR-0456` 的静态契约（哪个 env 解析到哪个根、优先级如何）**已经**写在感知面上：
`ARCHITECTURE.md:18`、`bin/README.md:222`、`CLAUDE.md:143-144` 三处都给了
`code_root()` / `state_root()` / `OMOSTATION_STATE_ROOT` 的读法。缺的不是那张表，
而是 **B5 + F1（#4570 / #4571）落地之后才出现的运行后果**：

1. 声明 profile 后跑一次真实 `omo state sync`，检出**仍然会脏两个文件** —— 那是 tasks 面
   时间戳，不是投影面回归。不知道这件事的 agent 会把它读成"我改坏了"，或者反过来
   把它当豁免条件放掉真正的回归。
2. 写面收敛能闭合，前提是 `bin/compass_radar.py:482` 的 `subprocess.run` **不传 `env=`**
   （:482-492 实测参数只有 `cwd/capture_output/text/timeout/check`）。这条沉默契约
   不在任何一处文档里；谁给它加一个 env 白名单，`OMOSTATION_STATE_ROOT` 就断在子进程边界，
   投影写回检出，且**没有任何测试会红**。
3. 治理协调面 `.omo/_delivery/*` 由 `.gitignore:12` 忽略，**但"不进 git"不等于"每个检出各一份"**：
   `ensure_delivery_anchor()`（`projects/omo/src/omo/workflow/delivery_anchor.py:87`）把每个 worktree 的
   `.omo/_delivery/agent-workflows/` 做成指向 canonical 检出的 symlink（实测两侧 `locks/` 同一 inode），
   并发会话的 run 与 scope 锁因此互相可见。`agent-workflow.py closeout --status ok` 的前置
   `heartbeat_run()`（`projects/omo/src/omo/workflow/lifecycle.py:1592-1593`）会逐一校验 run 记录里列出的锁
   （`:1017-1020`），scope 锁被并发 run 接管时直接拒绝整个 closeout；而
   `prune-locks` 的 zombie 阈值是 `_HEARTBEAT_STALE_SECONDS = 3600`
   （`projects/omo/src/omo/workflow/lifecycle_locks.py:27`，本轮实测一次 `--scan-only` 把共享面 29 条锁里的
   22 条判成 zombie，而这三个 run 的 `status` 全是 active），用它绕自己的锁问题会连带删掉并发会话的活锁。
4. WorkPacket 在 `start` 时从 ledger+spec 编译，`verify` / `done_when` / `scope` 都在投影里，
   所以**台账条目定稿之后才能 `start`**；中途改这些字段会让后续 `claim` 一律
   `WORK_PACKET_SOURCE_DRIFT`（`bin/plan/bet-ledger.py:2336`；BET-Y2Q4-T10-214 的 retro §6 与
   closeout 报告 G5 已各记一次复发）。`refresh-packet`（`bin/agent-workflow.py:1031`）救不了首轮：
   它逐源比对 ledger/spec 是否已在 `origin/main`（`:770`），新建 BET 的源还没合。

这四件事都只在**做的时候**才知道，且各自的教训都来自一次可复现的测量。本 BET 把它们
固化成后续 agent 读得懂、门禁查得到的文字，不再新增代码。

## 1 契约

### P1 感知面必须分层，不复制 env 表

`AGENTS.md` 只写**后果 + 指针**，env 优先级表由 `ARCHITECTURE.md` / `bin/README.md` 持有；
`AGENTS.md` 出现第二份优先级表即为回归（判据 4）。

### P2 每条新断言绑定一条实测 receipt

新增的每一条 AGENTS.md 条目必须能指到本轮已合并的 receipt（closeout report 或 retro）
里的一个具体读数；写不出读数的句子不进契约（判据 2）。

### P3 引用的 `file:line` 必须可解析

AGENTS.md 新增段落里所有 `path:NN` 形式的指针，在本检出必须存在该文件且该行号落在
文件行数内（判据 1）。本 BET 的 C6 沉默契约、lifecycle 行号、`.gitignore` 行号都按此钉。

## 2 done_when 的可测量形态

- 判据 1（指针可解析）：对新增段落逐条抽 `path:NN`，`os.path.exists` + `NN <= len(readlines())`
  全部成立；任一不成立即 fail。
- 判据 2（有 receipt）：每条新断言在 closeout report 里有一句对应的实测读数，
  report 用 `receipt://` 形式被台账绑定。
- 判据 3（文档治理）：`doc-governance-check.py --no-new-warnings --scope tracked` 绿，
  新 spec frontmatter 含 `owner`（`accepted-specifications` 桶未基线告警 = error，
  本轮 T10-215 实测过一次）。
- 判据 4（不重复真值）：`AGENTS.md` 里不出现 `OMO_EVENT_LEDGER_DB → OMOSTATION_STATE_ROOT →
  code_root()` 这条优先级链的第二次表述；`bin/README.md:222` 与 `ARCHITECTURE.md:18`
  两处一字未动。
- 判据 5（纯文档）：`git diff --name-only origin/main..HEAD` 只含 `AGENTS.md`、
  本 spec、台账、closeout report、retro 五类路径，出现任何 `.py` 即越界。
- 判据 6（不动他人在跑的面）：不碰 `.github/workflows/**`、`.omo/_truth/registry/**`、
  `bin/**`；不改 `.gitignore`。

## 3 非目标

- 不翻 `ADR-0456` 的 `status`（PROPOSED → ACCEPTED 属 principal），也不处理它与
  `ADR-0456-governance-downshift-closeout-grading.md` 的 `id` 重号 —— 本 BET 只把
  "按 id 引用会命中另一份决定"这一条写进感知面。
- 不修 `.omo/state/system.yaml` 的跟踪状态、不修 B5 残留的六个检出侧读者（另立 BET）。
- 不给 `.omo/_delivery/*` 新增 git 跟踪，也不改动它既有的 symlink 桥接语义 ——
  `ensure_delivery_anchor()` 已经把它做成全机共享面；本 BET 只描述现状，不动机制。
- 不 prune 任何并发会话的锁。
