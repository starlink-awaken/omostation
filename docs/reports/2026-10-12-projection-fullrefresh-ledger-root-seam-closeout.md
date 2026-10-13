---
schema: md/v1
status: completed
lifecycle: report
owner: governance-team
last-reviewed: 2026-10-13
type: closeout-receipt
bet_id: BET-Y2Q4-T10-247
title: BET-Y2Q4-T10-247 closeout receipt — projection-full-refresh 的 ledger 目标改调用时刻解析（import 时常量冻结 profile 的第四面）
---

# BET-Y2Q4-T10-247 closeout receipt

台账：`docs/plans/3y-bet-ledger.yaml` `BET-Y2Q4-T10-247`（bets 段 42309–42435）
契约：`docs/superpowers/specs/2026-10-12-projection-fullrefresh-ledger-root-seam.md`（spec_version 1.0.0，225 行，digest `sha256:6d3edd72c387b3576728083cd191e1e98d49ca9628dbc5045d62609ade1c242f`，合并后逐字节复算一致）
Retro：`.omo/_knowledge/retros/BET-Y2Q4-T10-247.md`
交付：PR #4736 → squash `df9457d1d`（2026-10-13，20 pass / 2 skipping / 0 fail，无 admin、无 `--no-verify`、无 `--force`；push 前 L3 深度安全审查未发现安全问题）
性质：ADR-0456 **B4b 批次 2+ 的前置** —— 不改道任何服务，只把这个写者从「import 时定根」改成「调用时定根」

## 1 交付

| 面 | 位置 | 内容 |
|---|---|---|
| 写者 | `bin/panorama/projection-full-refresh.py` | ledger 目标改走 canonical 缝、调用时刻解析；缺副本时跳过而非建半份镜像 |
| 用例 | `tests/unit/test_projection_fullrefresh_ledger_root.py` | 新增 11 条，读数全部由被测真树产出 |
| 用例 | `tests/unit/test_resident_write_plane_split.py` | 补 4 条真树对拍用例 |
| 规格 | `docs/superpowers/specs/2026-10-12-projection-fullrefresh-ledger-root-seam.md` | 新档 225 行，§3 ISC 含 M1–M7 变异读数、§4 含 R1–R5 活线读数 |
| 台账 | `docs/plans/3y-bet-ledger.yaml` | 新条目 + `verify` 由 3 条改 5 条（逐文件实测期望） |

变异对照 M1–M7 与活线探针 R1–R5 的**逐条读数在规格里**（`spec:113-120`、`spec:175-181`），本 receipt 只指过去、不复制一份 —— 复制就是第二个真源。

## 2 读数（本检出，命令逐字可复现）

| 判据 | 读数 |
|---|---|
| `pytest tests/unit/test_projection_fullrefresh_ledger_root.py -q` | **11 passed** |
| `pytest tests/unit/test_resident_write_plane_split.py -q` | **4 failed / 20 passed**（HEAD 是 5 failed / 16 passed；`NEW_RED = []`，本版红集合 ⊆ HEAD 红集合） |
| 那 4 条红 | `test_scan_loads_the_real_omo_surface`、`test_state_reached_families_are_the_declared_set`、`test_exact_root_split_pairs_are_the_reviewed_list`、`test_caller_class_anchors_are_checkout_anchored` —— 全部由 `origin/main` 上陈旧的在册名单造成，与本文件的改动无关 |
| `make gac-local-gate` 硬失败集 | 二跑 **2 条**：`service-config-drift`、`check-work-landed`；这二条在规范检出 `~/Workspace` 上跑同两条命令的读数**逐字节相同** |
| `--reality-check` 并集 | 22 桶差异 = **0 字段**；e1=1、e2=1、e3=0、e4 false、e5 1+1、`installed_total` 66 |
| 台账完整性探针 | `BASE_REF=6d01f51ce` 下 `VERIFY_RC=0`：`added == ['BET-Y2Q4-T10-247']`、`content_digest == disk`、ISC-7 的 12 个同源探针逐个命中 |

### 2b 首跑 TIMEOUT 的定性（P75 D8，宿主读数不是仓库读数）

首跑硬失败是 **3** 条，第三条是 `check-evidence-freshness`。计时取证：`evidence-smoke.py` 直跑 **196.95s**，
而 `bin/gac/check-evidence-freshness.py:73` 写死 `timeout=60`；门禁自己的步骤包装另有 15s
（`bin/gac/gac-local-gate.py:1057` 打印 `TIMEOUT after {timeout}s`）。warm 后同一条检查 **6.15s PASS**
（`score=100.0, age=0d`），二跑门禁内转 PASS。**没有**为此放宽任何门禁、也没登记 known-debt。

## 3 这一轮真正修的是判据，不是代码

三个「绿」当场被否证，每个都换了判据形状（详 `retro §2`、`§4`）：

1. **合同期望必须由被测树产出** —— 原先 ISC-7 与 `verify` 的「全绿 exit 0」读数取自 `/tmp` 合成树，
   在真树上按构造不可满足。
2. **多文件粘一条命令 = 假象** —— 预存红会遮蔽新增绿，非回退性无从判定；拆成逐文件后才有
   `NEW_RED = []` 这条可证判据。
3. **自证探针的基线不能是可变的 HEAD** —— commit 后 HEAD 含本条目，`added` 从 `[BET-Y2Q4-T10-247]`
   静默变 `[]`，判据在同一棵树上失去对象；改钉记录的交付前 base 才又有牙。

## 4 安全

push 前跑 L3 深度安全审查，未发现安全问题。合并走正常 squash：**无** admin merge、**无**
`--no-verify`、**无** `--force`；第一次 `gh pr merge` 因 `TLS handshake timeout` 返回 rc=1，
先读 `state / mergedAt / mergeCommit` 确认**未合并**才重试（`retro` lesson 8）。

## 5 遗留（本 BET 不解，逐条已有去处）

| 项 | 状态 |
|---|---|
| `tests/unit/test_resident_write_plane_split.py` 那 4 条红（`CALLER_EVIDENCE` / `SPLIT_EXACT` / `STATE_FAMILIES` 在册名单相对真跟踪面结构性陈旧：`bin/_archive/**` 175 py、`bin/ssot/**` 228、`bin/kb/**` 3、`bin/gac/m1-closeout-report.py`、5 份 `.omo/_knowledge/*.jsonl` 的 omo 字面量） | 需专门 catch-up BET；`tests/unit/**` 不在 `governance-check.yml:118-127` 白名单里，CI 看不见 |
| plan §风险与检测「B1–B5 的 verify 在两个 profile 上各跑一遍进 CI」 | **未实现**，`.github/workflows/gac-gate.yml:137-143` 只声明单根；已登记为下一项工作（task #121），按其自身 BET + accepted spec 走 |
| 新建 BET 的 `start` 后改台账投影字段 → `WORK_PACKET_SOURCE_DRIFT`，而 `refresh-packet` 要求 ledger+spec 已在 `origin/main` | 两边互锁，本轮靠「retro/receipt 可在未 claim 状态提交」绕过，未用 `prune-locks`、未用 `SWARM_ESCAPE_ID` |
| `check-evidence-freshness.py:73` 的 `timeout=60` vs 宿主 197s | 报告项，不改门禁 |

## 6 验证工装（全部在 `/tmp/t247`，12,090 个文件，一个未进 commit）

| 目录/文件 | 用途 |
|---|---|
| `prep/verify_ledger.py` | 台账完整性探针（`BASE_REF` 参数化） |
| `prep/mut_M1…M7*.py` + `mutate_driver.py` | 7 份变异样本与驱动 |
| `prep/gate_mine.log` / `gate_mine_2.log` | 门禁首跑/二跑逐行读数 |
| `prep/ef_2nd.log` | evidence-freshness warm 复跑（6.15s PASS） |
| `prep/c.log` | 契约↔落地文件交叉核对（6 条命名用例映射、8 个符号双侧 True） |
| `clean/`、`split/` | `git archive` 造的规范对照树（双树逐字节对拍用） |
| `rt/`、`fc/`、`bak/` | 逐文件 pytest 读数、ledger 事务日志、改前备份 |
| `ci_final.txt`、`ci_poll.log`、`pr_body.md`、`push2.log`、`merge.log` / `merge2.log`、`release.log` | CI 终态、轮询史、PR 正文、push/merge/清理记录 |

这些不落库，所以本表就是它们的位置说明；任何一条读数都可在当前 `origin/main` 上用 §2 的命令重放。
