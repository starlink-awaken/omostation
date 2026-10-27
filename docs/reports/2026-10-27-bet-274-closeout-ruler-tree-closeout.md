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
