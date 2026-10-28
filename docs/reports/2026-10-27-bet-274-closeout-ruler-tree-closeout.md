---
schema: md/v1
status: completed
lifecycle: report
type: closeout-receipt
owner: governance-team
last-reviewed: 2026-10-27
bet_id: BET-Y2Q4-T10-274
---

# BET-Y2Q4-T10-274 收口 receipt —— 把「尺跟着 kernel 换树」变成一个可复算的读数

台账：`docs/plans/3y-bet-ledger.yaml` `BET-Y2Q4-T10-274`
规格：`docs/superpowers/specs/2026-10-27-bet-274-closeout-ruler-tree.md`
retro：`.omo/_knowledge/retros/BET-Y2Q4-T10-274.md`
run：`20261027T055325Z-project-doc-change-a20aa965`（profile `governance-agent`，workflow `project-doc-change`）
交付基线：本腿从 `14ee5723e` 起；写本腿期间上游前进到 `a1ecb980b`（#4921，CI checkout token），
逐面核对不碰本腿五个写面、也不碰被引用的尺本体三个文件。

## 1. 交付面（五个，全部显式列路径）

| 文件 | 内容 |
|---|---|
| `docs/superpowers/specs/2026-10-27-bet-274-closeout-ruler-tree.md` | 契约：双重绑定的机制、分叉触发面三类、四条固化判据、反证表 |
| `docs/plans/3y-bet-ledger.yaml` | 新条目 `BET-Y2Q4-T10-274`（`ledger-safe-insert.py` 定位插入，非按行号盲插）；`total_bets` 同步 |
| `AGENTS.md` §7 | 固化条（证据→判据→纪律三段，含否证记录） |
| `.omo/_knowledge/retros/BET-Y2Q4-T10-274.md` | 四问 retro |
| 本 receipt | 读数与验收映射 |

代码绑定语义（`bin/agent-workflow.py:278` / `:282-287`）**未改**，运行面**未动**。

## 2. 读数（每个读数标注产出它的树/base）

| 判据 | 命令/装置 | 读数 |
|---|---|---|
| V1 尺根分叉 | 探针复刻 `:278` 与 `:282-287`，kernel 供给根分别取本检出与 `~/Workspace/projects/omo/src` | 本检出 `diverge=False`；异树供给 `diverge=True`，kernel-level=`/Users/xiamingxing/Workspace` |
| V2 链与证据复算 | 含交付物的树（`ws-t274-closeout-ruler` @ `14ee5723e`）直接调 `validate_completion_evidence` + `chain_bind.evaluate_complete`，runs 面先经 `ensure_delivery_anchor()` | `derived_state=delivery_accepted errors=[]`；`chain ok=True reasons=[]`；run 记录可见 **359** 条 |
| V3 两树实存对拍 | 同一对路径在两棵树里各测一次 | worktree `retro=True receipt=True`；canonical 主检出（`dc67a0f5f`）`retro=False receipt=False` |
| 台账 lint | `python3 bin/plan/bet-ledger.py lint` | `OK -- 571 bets, 16 tracks, no errors`（改前基线 570 bets 无 ERROR） |
| 文档治理 | `python3 bin/ssot/doc-governance-check.py --no-new-warnings --scope tracked` | `PASS (4704 files, 31 warnings)` —— 告警数与基线同为 31，零新增 |
| 本地门禁 | `python3 bin/gac/gac-local-gate.py --scope staged --json` | `ok=True hard_fails=[]`，2 条 SOFT WARN（见 §3） |
| 行指针复核 | `git show origin/main:<file>` 逐行取 `:278`、`:282-287`、`:1138`、`:3259`、`:3275-3277`、`core.py:43` | 六处全部命中所述内容 |

## 3. 红灯如实登记（不修、不绕、不 `--no-verify`）

两条 SOFT WARN 都是环境类，与 T10-272 腿同形，非本腿引入：

1. `current-state-coherence` rc=2 `missing input: .omo/state/system.yaml` —— 该文件自 T10-235 起被
   `.gitignore` 正向忽略，干净检出按构造没有它；需要时显式跑创建者 `bin/gac/materialize-system-state.py`，
   本腿不为此改动门禁。
2. `test-mcp-kos` rc=78（该脚本自己写明 `exit 78 = skipped, not passed`）—— KOS 库是运行态产物、不在 git 内。
   注意它的报错路径解析到**本 worktree**（`ws-t274-closeout-ruler/data/kos/…`），正是本 BET 固化条的同族一例。

E1（`gen-service-configs --check` `drift_count=1`，`com.omostation.agent-brief-materialize` 注册在案而本机无 plist）
是 task #150 的署名裁定项，本腿不复评、不接线、不改 `services.yaml`。

## 4. done_when 映射

| done_when | 落点 |
|---|---|
| ① AGENTS.md §7 有固化条并写明读数须标 kernel 供给根 | 新增条首段（证据）+ 判据 ① |
| ② 取证须在含交付物的检出上复算 | 判据 ②，本 receipt §2 的 V2 即该复算本身 |
| ③ runs 面折叠用 `ensure_delivery_anchor()` 而非手工 `ln -s` | 判据 ③，V2 实测 359 条 |
| ④ `cmd_complete` 在 done 后是 no-op | 判据 ④（`:3275-3277` 早退） |
| ⑤ 记录面：实质闭合走原生 `close --status ok --evidence` | 纪律 ① |
| ⑥ 基线面：不用 `sync-main.sh` 快进共享主区 | 纪律 ② |
| ⑦ 行号指针经 origin/main blob 复核 | §2 末行，六处命中 |
| ⑧ spec 落 canonical 位、frontmatter 八项齐、lint 零 ERROR | §2 的 lint/doc-governance 两行 |

## 5. 本腿不主张的事

- 不主张「双重绑定已修复」——只固化了读数与取证纪律，绑定语义改动是独立工程腿。
- 不主张 E7 该不该升级为阻塞、不主张 agent-brief-materialize 该装机还是 `generate: false`。
- 不宣布 ADR-0456 B1/B3/B4/B4b/B5 或整个 plan 完成。
- 不据 squash 合并后的新 OID 反推「分支提交已落地」；落地判定用逐文件内容对拍
  （`git diff --stat origin/main HEAD -- <file>` 为空），这是 task #135 记下的既有判据形状。

## 6. 合并后订正与交付留痕（第二腿）

- **交付**：PR **#4924** squash-merged as **`b72705e9f7d2893617c1c53c186976af015315d5`**
  （`mergedAt 2026-10-27T08:50:01Z`）；本腿 base `14ee5723e`，合并时 `origin/main` 为 `dd4a603aa`。
  CI 终态 **20 SUCCESS / 2 SKIPPED / 0 fail**，`mergeable=MERGEABLE` + `mergeStateStatus=CLEAN`；
  承重三条实测 `bet-done-transition` pass(43s)、`governance-verify` pass(2m44s)、`evidence-gate` pass(28s)。
  产读本终态的那份 `governance-verify` 检出在 `dd4a603aa`（它评分支自己的 head tree，
  `.github/workflows/governance-check.yml:176-177`），按本 BET 判据 ① 标注。
- **落地判定（按 §5 承诺执行）**：`git fetch origin main` 后五个文件逐一
  `git diff --stat origin/main HEAD -- <file>` 读数全为**空**；而
  `git merge-base --is-ancestor HEAD origin/main` = **NO**。两者并读正是本条承诺的形状。
- **订正 1 —— 台账 `merged_reachable_commit.ref`**：第一腿只能写分支 commit `de20deb53…`，
  它在 squash 后不在 main 上。邻居对照实测：origin/main 上 T10-270 `9c7d2c0fd` /
  T10-271 `63d389cee` / T10-273 `c2255b477` 该字段**全部**是 main 上的真实 commit
  （三条 `merge-base --is-ancestor … origin/main` 均 YES）。据此把该**单字段**改写为 `b72705e9f…`。
- **订正 2 —— run 记录的 evidence 串**：run `20261027T055325Z-project-doc-change-a20aa965`
  实测已于 `06:05:25Z` 闭合 `status: ok`、7 把锁 released，但其 `evidence:` 列表只有一条
  `PR #4919 merged in 14ee5723e; ADR-0209 A1 manual evidence` —— 那是 **T10-272** 的交付串，
  且闭合时刻（06:05:25Z）早于本腿 PR 创建时刻（08:43:29Z）。
  正解按 `_close_run_locked`（`projects/omo/src/omo/workflow/lifecycle.py:1522`）的实测语义走：
  它对已闭合 run **没有拒绝分支**，`:1547-1551` 覆写 status 后对 `evidence` 做 `extend`，
  `:1552-1553` 的 `release_locks()` 只 unlink 本 run_id 的锁（已释放即 no-op）——
  所以用原生 `close --status ok --evidence` **追加**本腿真实交付串，历史串不抹；
  **不**手改 run YAML（AGENTS.md §4：governed state 走 broker）。
- **为什么这两条要写进 receipt 而不只记在台账里**：订正 1 是单 PR 交付的**时序结构性欠账**
  ——「自己的 merge SHA」在该字段被写入的那一刻还不存在，与任何人的谨慎无关；
  订正 2 是「闭合动作先于交付动作」的症状，与本 BET 主题同源：
  **记录面把「装置跑过」当成了「交付发生过」**。两者都属于本 BET 判据 ①② 的反面实例。
- **本腿没有 governed run —— 两条原生入口都实测失败，如实记**（ADR-0203 要求交付前 `start`）：
  ① `bin/agent-workflow.py start project-doc-change --bet BET-Y2Q4-T10-274` →
  `BET_STATUS_NOT_STARTABLE: BET-Y2Q4-T10-274 status=done; allowed=['blocked','candidate','in_progress','pending']`，
  即**已闭合的 BET 按构造开不出新 run**，这是机制缺口而不是拦截；
  ② 换 `spawn <parent-run>` 这条子 run 路径 → `WORK_PACKET_COMPILER_UNAVAILABLE`（本机装置面不可达）。
  两条都留原始报错串。**不做的三件事**：不把台账状态翻回 `in_progress` 去迁就门禁（那是伪造状态）、
  不用 `--force-lock`、不用 `--no-verify`。

## 7. 第二腿写回后的实测读数（产读基线 = 本分支 `HEAD`，含第一腿已合并内容）

- **改动量**：`git diff --numstat -- docs/plans/3y-bet-ledger.yaml` = **8 增 8 删**，块内行数不变
  （`45370..45982`）。这 8 行按**键路径**定位，不是按值反选：`ref` 位 1 处（`:45459`）、
  `completion_evidence.axes.*.evidence.*.sha256` 位 7 处（`45462/45465/45468/45474/45477/45480/45483`，
  其中 `replay` 指向 retro 故取 retro 摘要）、`accepted_specifications[0].content_digest`（`:45449`）
  **逐字节未变**。写回脚本自身的断言同时覆盖这两类摘要（receipt/retro 位 == 磁盘文件、
  `content_digest` == spec 文件字节摘要），缺任一条即视为该次写回未完成 —— 这是 T10-267 那次
  「按值排除把规范绑定摘要一起改掉」的正面防线。
- **订正 1 的承重判据（这就是它"做完了"而不是"打算做"的证据）**：
  `python3 bin/plan/bet-ledger.py lint` → `OK -- 571 bets, 16 tracks, no errors`，
  且点名 `b72705e9f` 的 `not ancestor of origin/main` WARN 条数为 **0**；
  独立复核 `git merge-base --is-ancestor b72705e9f… origin/main` = **YES**。
  对照：同一 lint 共打印 **27** 条该 WARN（其余 BET 的该字段仍是分支 commit），
  说明这把尺没有整体松掉，本条的零命中是**逐条**结果而不是判据失效。
  （⚠️ 我第一版把这里写成「其他 7 条」——那是 `tail -8` 截断的读数被当成了总数，
  正是本 BET 要防的那类「装置跑过 ≠ 交付发生过」的同形自伤，改用 `grep -c` 全量复算为 27。）
- **receipt/retro 正文不含自指摘要**：`grep -cE '[0-9a-f]{64}'` 对本文件与 retro 命中均 **0**。
  这不是排版偏好而是**可满足性**问题：本文件的字节决定台账里指向它的那 6 位摘要，
  所以正文里任何「本 receipt 的 sha256 = …」这类句子按构造不可为真 —— 我第一版就在最后一条
  写了两个当时的实测值，随后一次编辑使其立刻为假（已删除该字面值）。
  纪律：**自指对象的摘要只落在他方记录里**（台账 = 由外部按磁盘字节重算），正文只写**定位方式与断言**。
- **本 worktree 的门禁先红后绿，红因全部是装置面，与我的 diff 无关**（逐条取证，不 `--no-verify`）：
  首跑 `make gac-local-gate` rc=2，三条非绿 ——
  ① `gac-bootstrap`：缺 `projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml`；
  ② `current-state-coherence`：缺 `.omo/state/system.yaml`；
  ③ `check-evidence-freshness`：`generation_failed — import_failed`（实为 `No module named 'fastmcp'`）。
  取证读数：五个子模块目录（ecos/agora/cockpit-ui/runtime/kairon）被并发守卫清空，
  判别量**不是「目录为空」而是 `git -C <sub> status --porcelain` 报全量 `D ` staged 删除、
  且 `HEAD == gitlink pin`、零其他条目** ⇒ 此时 `git submodule update --init` 是 **no-op**（它见 HEAD 已等于 pin），
  必须 `git checkout HEAD -- .` 才回得来 —— 这是 AGENTS.md「并发 update 清空 worktree 检出」条的**第二次实录**，
  且补上了它没写的这一半（复原命令不是 `submodule update`）。
  `.omo/state/system.yaml` 按 T10-235 已摘库 ⇒ 跑创建者 `materialize-system-state.py`
  （`key_set_equals_declared: True`，产物未跟踪、`git check-ignore` 命中 `.gitignore:304`）；
  `fastmcp` 由 `uv sync --project projects/agora` 补齐 —— 它先要 `projects/bus-foundation` 复原
  （同样被清空），否则 uv 报「not a Python project」。复原后 `git status` 只剩
  `projects/l4-kernel` / `projects/omlxc` 两项 `M`（claim 时即 `HEAD != pin`，**不是本次造成**）。
- **两个子模块我特意不复原**：`l4-kernel` / `omlxc` 的 `HEAD != gitlink pin`，
  对它们跑 `checkout HEAD -- .` 会还原成**父仓并未记录的那个 commit** —— 那是伪造子模块图而不是修装置。
  正路是 `git submodule update`（切到 pin），但我的 diff 不依赖它们，故不动、如实登记。
- **门禁终态读数，以及 `make` 与脚本的 rc 为何不同**：
  `python3 bin/gac/gac-local-gate.py --json` → `ok=true / hard_fails=0 / soft_warns=1`，**rc=0**；
  同内容下 `make gac-local-gate` **rc=2** —— make 目标把 SOFT WARN 也计为失败。
  那唯一一条是 `test-mcp-kos` exit **78**，其自述为「skipped, **not passed**」（本机 worktree 无
  `data/kos/kos-index.sqlite` 运行态产物，该文件不在 git 里）。**判据**：读门禁不要只读 shell rc，
  `--json` 的 `hard_fails` 才是承重面；`rc=2 + hard_fails=0` 与 `rc=1 + hard_fails=1` 不是一回事。
- 装置面遗留（不在本腿范围，登记不复修）：`gac-bootstrap` 的 `tools: {alive: 0, total: 0}`
  在 canonical `~/Workspace` 上读数**一字不差也是 0**，所以它是仓级/宿主级状态而非 worktree 伪影；
  一处计数为 0 却伴随 `ok: true` 的形状，正是本 BET 判据⑨（「解析失败退回空」）的同类，留作独立腿。
