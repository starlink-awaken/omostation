---
schema: md/v1
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-30
type: report
bet_id: BET-Y2Q4-T10-216
title: BET-Y2Q4-T10-216 closeout — 两个根的行为后果固化进 agent 感知面
---

# BET-Y2Q4-T10-216 closeout — ADR-0456 F2 感知固化

契约：`docs/superpowers/specs/2026-09-30-bet-216-two-root-agent-perception.md`（v1.0.0，
`status: accepted`，`lifecycle: contract`，digest `sha256:61bfe1995f65a6fac8e777289be7947810ef401d7163148d9ddf088fd36e1f04`）
交付：`AGENTS.md` §1 第 9 条（ADR 指针改按文件名）+ §7 新增 5 条；台账新增 `BET-Y2Q4-T10-216` 条目。
run：`20260930T090837Z-project-doc-change-fd1910bb`（本 BET 唯一绑定 run）
复盘：`.omo/_knowledge/retros/BET-Y2Q4-T10-216.md`

## 1 本轮写了什么、没写什么

ADR-0456 的**静态** env 表早就在三处感知面（`ARCHITECTURE.md:18`、`bin/README.md:222`、
`CLAUDE.md:143-144`），本轮一个字没动那三处（判据 4：`git diff --stat origin/main..HEAD --
bin/README.md ARCHITECTURE.md` 为空）。补的是 **B5（#4570）与 F1（#4571）落地后才出现的四条行为后果**，
每条都由一次可复现测量钉住，读数为下。

| 断言（AGENTS.md §7） | 实测读数 | 支撑 receipt |
|---|---|---|
| 写面闭合靠一条沉默契约 | `bin/compass_radar.py:482` 的 `subprocess.run` 参数只有 `cwd`/`capture_output`/`text`/`timeout`/`check`（`:482-492` 逐行读，无 `env=`） | 已合并 `docs/reports/2026-09-30-bet-215-omo-write-side-single-root-closeout.md`（`sha256:48ad8ad8…`） |
| 声明 profile 后脏检出两个文件不是回归 | 真实 sync 后脏的是 `.omo/state/system.yaml` 的 `updated_at` 与 `.omo/tasks/registry/INDEX.md` 的 `Updated:`；检出的 `health_score_evidence` 三行逐字未变 | 同上（已合并） |
| 协调面是全机共享面，`gitignore` ≠ 本地化 | `stat -f "%i" .omo/_delivery/agent-workflows/locks` = **391364336** = 主区同路径 inode；机制在 `projects/omo/src/omo/workflow/delivery_anchor.py:87`（worktree 侧做成指向 canonical 的 symlink） | 本轮（同一 PR 内合并） |
| `prune-locks` 不能拿来绕锁 | `prune-locks --scan-only` 在共享面 **29 条锁里判 22 条 `zombie_stale_heartbeat`、7 条 `live`**（7 条 live 正是本轮刚 heartbeat 过的那 run 自己）；22 条分属 3 个 run，逐个读 run 记录 `status` **全是 active**，最旧心跳 76,944s | 本轮（同一 PR 内合并） |
| WorkPacket 只 gate claim，首轮改台账即漂移 | 改 `verify` 一个字后 `claim` 报 `WORK_PACKET_SOURCE_DRIFT: ledger/spec projection no longer matches the bound packet`（`bin/plan/bet-ledger.py:2336`）；把改动回退后同一条 `claim` 立即成功 —— 因果由这一来一回钉住。`refresh-packet`（`bin/agent-workflow.py:1031`）救不了首轮：`:770` 逐源比对 ledger/spec 与 `origin/main` 的字节，新 BET 的源还没合 | 已合并 `.omo/_knowledge/retros/BET-Y2Q4-T10-214.md` §6 与 `docs/reports/2026-09-29-bet-214-evidence-integrity-closeout.md` G5（同错误码的两次复发） |

`AGENTS.md` §1 第 9 条另修一处**结构性错误**：原文写 `Contract: ADR-0456`，但声明
`id: ADR-0456` 的文件有两份（另一份 `ADR-0456-governance-downshift-closeout-grading.md` 是别的决定、
且已 `ACCEPTED`，而本契约仍 `PROPOSED`），按 id 引用会命中错的那份 —— 现按**文件名**引用。
id 重号本身属 principal 决定，本轮不处理（spec §3 非目标）。

## 2 合并前被自己的测量否证、逐条改掉的写法

本 BET 最初的 spec 与 AGENTS.md 草稿把协调面写成"`.gitignore:12` 忽略它，所以每个检出各一份、
run/锁不跨 worktree 传播"。写完后按判据 1 去逐条验指针，顺手 `ls -l` 了那个目录，实测它是
**指向主区的 symlink 且两侧 inode 相同** —— 那句话的机制是错的，而结论方向恰好相反：
并发会话的锁**正因为共享才互相可见**，`closeout` 被别人的锁拒绝、`prune-locks` 会拆别人的活锁，
都由此成立。合并前把 spec §0 第 3 条、§3 非目标、台账 `goal`/`non_goals`/`done_when-2` 与
AGENTS.md 那条一起改掉，并重算了 spec digest。

同一轮里 `prune-locks` 的数字也从"32 条全判成 zombie"更正为本轮实测的"29 条里 22 条判死、7 条 live"
—— 原句把一次性的扫描读数写成了永恒事实，而 live/zombie 的划分只取决于最后一次心跳距 `3600s`
阈值多远。保留的量是**阈值语义**与"三个 run 全 active"这两条不会被时间冲掉的读数。

第三处是**判据自己**错：台账与 spec 记录的纯文档判据写作 `git diff --name-only origin/main..HEAD`，
commit 后按它跑，返回 12 条路径含 6 个 `.py` —— 一度读成"越界碰了代码"。实际是 base 漂移
（`git rev-list --count HEAD..origin/main` = 2）下两点式把主仓的前进反向报成本分支的删除，
三点式 `origin/main...HEAD` 返回正好 5 条文档路径（读数见 §3 判据 5）。判据 4/5 与两条 verify
命令一并改为三点式，spec 重算 digest（`18d6ebb9…` → `61bfe199…` → 本轮末值）。

第四处是**从别处借来的一个计数**：spec §3 与本报告 §4 都写"B5 残留的六个检出侧读者"，而那个"六"
是从 B5 自己的 closeout 报告抄的 —— `docs/reports/2026-09-29-projection-plane-phase2-pr3-closeout.md:251`
原文是"暂存 `bin/compass_radar.py` + 六个 `bin/gac/*.py`"，它数的是**那一笔 governance_code lane
里被转换掉的文件**，不是剩余未转换的读者。合并后要复核才发现：我手上没有任何一个仪器能复现"六"——
按"文件里出现 registry 登记的 17 条 canonical/legacy 字面路径、且全文不含 seam 词"数得 **26**（把
`tests/**` 和 `check-dead-path-tool-fallback.py` 这类专门扫字面路径的检查器也算进来了，人群不同）；
按"提到 `.omo/state` 且不用 `repo_root`"数得 **62**（其中 13 条落在 `bin/_archive/**`）。两个都不等于契约里的"六"，所以本轮**不替换成
一个新数字**，只把计数的归属交还给 B5 侧（spec 与本报告同步去掉该数，spec 再算一次 digest）。

四处都是判据 1 与判据 2 存在的理由：先跑一次，再写进契约 —— 包括"怎么跑"和"这个数是谁的"这一层。

## 3 四条判据的读数

1. 指针可解析：对 `AGENTS.md` 新增段落抽 `path:NN`，共 **8 条**
   （`.gitignore:12`、`bin/compass_radar.py:482`、`bin/plan/bet-ledger.py:2336`、
   `bin/agent-workflow.py:1031`、`delivery_anchor.py:87`、`lifecycle.py:1307`、
   `lifecycle.py:1592`、`lifecycle_locks.py:27`），`bad=[]`，exit 0。
   逐条还做了语义核对：`lifecycle.py:1592` = `if status == "ok":`（其后 `:1593` 才调 `heartbeat_run`）、
   `lifecycle_locks.py:27` = `_HEARTBEAT_STALE_SECONDS = 3600`、`.gitignore:12` = `.omo/_delivery/*`、
   `compass_radar.py:482` = `res = subprocess.run(`。
2. 每条断言有读数：见 §1 表第五列；其中两条绑定本轮 receipt（同一 PR 合并），三条绑定已合并 receipt。
3. 文档治理：`doc-governance-check.py --no-new-warnings --scope tracked` 跑了两次 ——
   commit 前 **PASS（4524 files，145 warnings）**，`git add` 三份新文档后 **PASS（4527 files，145 warnings）**。
   两次之差正好是新面进入受检集合（+3 files、告警数不变）。第一次那条不构成证明：
   `--scope tracked` 不含 untracked，也就是说它当时根本没看过新 spec/report/retro 的 frontmatter。
   判据 3 以第二次读数为准。
4. 不重复真值：`git diff --stat origin/main...HEAD -- bin/README.md ARCHITECTURE.md` 为空。
5. 纯文档：`git diff --name-only origin/main...HEAD` 只含 `AGENTS.md`、本 spec、本 report、retro、台账
   五类路径（**共 5 条**）。同一分支改用两点式 `origin/main..HEAD` 得到 **12 条**，其中 6 条是 `.py`
   （`bin/gac/agent-clone.py`、`bin/gac/gac-local-gate.py`、`bin/mof/gen-service-configs.py`、
   `tests/unit/test_clone_indeterminate_gate.py`、`tests/unit/test_gate_timeout_budget.py`、
   `tests/unit/test_service_interpreter_stability.py`）外加 gitlink `projects/knowledge/kairon`，
   而 `git rev-list --count HEAD..origin/main` = 2 —— 那 7 条全是主仓自己的前进被两点式
   反向读成"本分支删了它们"。台账里原先记录的两点式判据据此改为三点式。

## 4 交付边界

未启停任何服务、未改 `.py`、未改 `.gitignore`、未动 registry 与 workflow —— 台账 `circuit_breaker`
列出的越界面全部为空。`BET-Y2Q4-T10-216` 完成后，ADR-0456 的感知面即为
「静态表（三处）+ 行为后果（本五则）」。仍未闭合的两件已在台账另立：
`ADR-0456` 的 `status` 翻转与 id 重号（principal），B5 侧残留的检出侧读者（其清单与计数归 B5 拥有，
本轮未复算，见 §2 第四处）与
`tests/unit/test_repo_root_profile.py::test_projection_falls_back_to_committed_legacy_path`。

## 5 合并路径：同一批内容、换 base 即绿

首轮交付是 **PR #4583**（base `ff9070d55`）。它只有一个红：`governance-verify → Submodule pointer
drift check`，`check-submodule-pointer-drift.py --json` 报 `diverged: 2` —— `projects/agora` 分支
gitlink `85003b315ae7` vs 子模块自己的 `origin/main` `46f84b12791f`，`projects/knowledge/kairon`
`2c07c5ecc117` vs `11a48bf2067a`，detail `gitlink NOT on origin/main - code may be invisible from root`。

三条读数说明红不在我的改动里：

1. 分支那两个 gitlink 与 base `ff9070d55` **逐字节相同**（`git rev-parse HEAD:<path>` 两侧对比），
   本轮一个指针都没碰；
2. `main` 自己在 `ff9070d55` 上就是 **success**（run 36692174674），随后 #4580 / #4582 / #4584
   把两个指针都对齐了 —— 被评的是"旧 base 的树"，不是"本分支的 delta"；
3. `governance-check.yml:169` 的 `governance-verify` 显式 `ref: github.event.pull_request.head.sha`
   （`:176`）、`fetch-depth: 0`（`:177`），评的是**分支自己的 head tree** 而非 merge tree ——
   这正是 `AGENTS.md` 那条"别据 base 漂移推论 CI 无所谓"的反面用例。

分支内补救两条都不成立：`submodule-guard` 拒绝 kairon 的非 fast-forward 移动
（`❌ projects/knowledge/kairon 不是 fast-forward (base=2c07c5ecc117, staged=11a48bf2067a)`），
而 `--fix` 选的是 kairon 自己的 tip `3e3189cc3396`（≠ 当时主仓钉的 `11a48bf2067a`）；gitlink bump
本身也超出本 BET 的 `write_surfaces`（只有这 5 个文档），且 `AGENTS.md` 明令不由交付分支去吸收上游。

**处置**：`claim t10-216-recast` 从 `da35d6563`（已含 `agora=46f84b12` / `kairon=3e3189cc`）重落，
五个文件用 `git show <旧 HEAD>:<path>` 逐字节复用（sha256 全等，不是重写）。读数：

- 新 base 上 `check-submodule-pointer-drift.py --json`：**`diverged: 0, behind: 0`**（红那条门禁的前置检查）；
- 台账 4 条 verify 在新 base 复跑，读数与旧 base 一致：**8 pointers `bad=[]`**、
  **PASS (4527 files, 145 warnings)**、纯文档与单一 owner 两条**均空**、D0 **5×[OK]**；
- #4586 CI **20 pass / 0 fail**（含 `bet-done-transition`、`evidence-gate`、`interface-check`），
  squash 合并为 `ec2f142524b0082cb61769f744c26ac3063f0560`；#4583 关闭并在评论里留下上面的证据链。

**同一个协调面还多送一条副产品读数**：新 run 第一次 `claim` 报
`A2A Path Lock Collision: path '.omo/_knowledge/retros/BET-Y2Q4-T10-216.md' overlaps with active
claim … in run 20260930T090837Z-project-doc-change-fd1910bb` —— 旧 run 的路径锁跨 worktree 挡住了
新 run，这是 §1 第 3 行"协调面全机共享"的第二次独立实证（本轮撞出来的，不是回忆）。
`closeout <旧 run> --status blocked` 释放锁之后 claim 才通过。
