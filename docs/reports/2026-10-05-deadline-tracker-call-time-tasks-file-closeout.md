# BET-Y2Q4-T10-229 deadline_tracker 台账路径改调用时解析 — Closeout 报告

- bet: BET-Y2Q4-T10-229
- date: 2026-10-05
- status: done
- workflow: project-code-change
- run: 20261004T160516Z-project-code-change-0efe0551
- owner: governance-agent

## 交付物

| 交付 | 位置 | 状态 |
|------|------|------|
| 代码修复 | PR **#4641** → squash 合并 `bb762fe0b` | ✅ origin/main |
| Spec | `docs/superpowers/specs/2026-10-04-deadline-tracker-call-time-tasks-file.md` | ✅ accepted |
| 台账条目 | `docs/plans/3y-bet-ledger.yaml` `id: BET-Y2Q4-T10-229`（全库唯一） | ✅ |
| retro | `.omo/_knowledge/retros/BET-Y2Q4-T10-229.md` | ✅ |
| canary 回执 | `docs/reports/2026-10-05-bet-229-canary.json` | ✅ |

改动面 4 个文件（`bin/ssot/deadline_tracker.py`、`runtime/ssot-stable/deadline_tracker.py`、
`bin/bc-os/policy_radar.py`、`tests/unit/test_deadline_tracker_ledger.py`），零 schema 变更、
零任务生命周期语义变更。

## 验收判据逐条实测（在合并后的 `bb762fe0b` 上复测）

| # | 判据 | 实测读数 |
|---|------|----------|
| done_when-1 | 最小复现转绿：两文件 `-p no:randomly` | **10 passed**（修复前 4 failed / 5 passed） |
| done_when-2 | `test_env_redirect` 不 reload 即断言 `tasks_file()` 跟随 `OMO_TRACKED_TASKS` | 用例存在且绿 |
| done_when-3 | 两份副本同形：`diff -u bin/ssot/… runtime/ssot-stable/…` | exit 0，**0 字节** |
| done_when-4 | `policy_radar.py` 不再对 `_dt_mod.TASKS_FILE` 赋值 | `grep -c` → **0** |
| verify-1 | 四文件组合 `-p no:randomly`（deadline_tracker 的全部消费者） | **17 passed** |
| verify-2 | `test_reporting_reads_ledger.py` 单跑仍绿 | **6 passed** |
| verify-3 | `TASKS_FILE = Path(os.environ` 在扫描面内零命中 | `bin/` + `runtime/` 全量 → **0 hits** |
| verify-4 | 本地门禁无新增硬失败 | **68 checks，`ok: true`，`hard_fails: []`**，1 项软跳过 |

`bet-ledger.py lint`（本轮改动前基线）：`OK -- 524 bets, 16 tracks, no errors`。

## 偏差（不粉饰）

1. **verify-4 的命令被替换**。`verify[4].cmd` 写字面量 `make gac-local-gate`，而新 claim 的 worktree 里
   该目标环境性不可用：uv 试图 `Creating virtual environment at: .venv` 并 canonicalize 一个已不存在的
   `/opt/homebrew/Cellar/python@3.14/3.14.7/.../python3.14` → `make: *** [gac-local-gate] Error 2`。
   这是工具链环境问题、不是治理失败，改跑同一实现的
   `python3 bin/gac/gac-local-gate.py --scope run --run-id <run> --json`，上表读数即来自后者。
   其中唯一软跳过是 `test-mcp-kos`（exit 78：`KOS database not found`，KOS 是运行态产物、不在 git 内；
   exit 78 = skipped，不是 passed）。
2. **done_when-1 的文字数字陈旧**。它写「变为 9 passed」，实测 **10 passed** —— 我在实现中补了第 4 个用例。
   判据语义（「最小复现从红转绿」）成立，条数不成立。**本轮不改台账的这个数**：`done_when` 在 WorkPacket
   投影内，`start` 之后再改会给后续 `claim` 造 `WORK_PACKET_SOURCE_DRIFT`
   （`bin/plan/bet-ledger.py:2336`）；正确修法是用 `agent-workflow.py refresh-packet` 在台账已等于
   `origin/main` 后重新编译 packet。spec 只记录「修复前」读数，故 `content_digest` 无需重算。
3. **台账是重建而非选择**。合并期与 `origin/main` 撞 `CONFLICTING`（`meta.total_bets` 是派生值，行级三方
   合并看不见超集关系）。解法按 `docs/SOPs/ledger-closeout-sop.md` §3.6：`git merge origin/main` +
   解成超集，三条断言实测 `524 == 524`、重复 id `0`、main 侧 523 条逐条存活（`done` 519 → 519），
   diff 形状 `+71 −1`。

## 残余与遗留（不在本 BET 边界）

- **顺序依赖在本集合内清零**：合并后 `tests/unit` 全量 **11 failed / 1901 passed**，本轮修掉的 4 条
  `test_reporting_reads_ledger` 已不在失败名单；残余 11 条**逐文件单跑同样全红**（5 / 3 / 1 / 1 / 1），
  即不能再拿「顺序污染」当解释。分类：panorama 投影 ×5、`collectors` 环境缺失 ×3、worker adapter ×2、
  gac-gate timeout ×1。
- `bin/ssot/_shared.py:34` 的 `ROOT = Path(__file__).resolve().parents[2]` 仍是 `__file__` 反推的缝，
  **刻意留在本轮边界外**（改它等于改真实守护进程的写入落点，属 ADR-0456 B4b 批次 2+，需逐批授权）。
  因此本 BET **不等于**「`deadline_tracker` 已 profile-clean」。
- `check-evidence-freshness` 在 worktree 里读到 83.5（canonical 实测 100.0）：检出的 `.omo/state/system.yaml`
  是**设计上的陈旧快照**，已登记为已知债（任务 #98 / G9）。本轮生成态（该文件的时间戳）未随报告 PR 提交。

## 对 ADR-0456 的推进

本 BET 是 B4b 批次 2 的**测量装置前置**：launchd/cron 改道与 ledger 权威翻转要逐批核对，前提是 `tests/unit`
的读数不因「谁先 import」而冻结在旧根上。该前置现已成立 —— 且留下了可复核的判据
（`rg "TASKS_FILE = Path\(os.environ"` 零命中 + 不依赖 reload 的回归用例）。改道本身仍需逐批授权。
