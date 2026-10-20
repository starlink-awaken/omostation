---
type: report
status: completed
owner: governance-team
last-reviewed: 2026-10-20
bet_id: BET-Y2Q4-T10-259
title: BET-Y2Q4-T10-259 closeout — B3 准入评审清单（E4 19 + E5 2）
---

# BET-Y2Q4-T10-259 closeout — B3 准入评审清单

交付物：`docs/superpowers/specs/2026-10-19-b3-admission-review-checklist.md`（spec_version 1.0.0，
content_digest `sha256:f4556ffb6f0f5374c830760f544c78ac683d014a0b2e35a6576c8a0dd27ac630`）
台账：`docs/plans/3y-bet-ledger.yaml` `BET-Y2Q4-T10-259`
PR：#4829 —— squash 合并为 `91107174f`（`mergedAt 2026-10-20T01:57:43Z`；
分支上两个 commit：`31ec6364c` 初版 + `5f43abbcb` 复测修订）；CI 终态 20 pass / 2 skipping；
合并前 L3 深度安全评审 `findings_count=0`
Retro：`.omo/_knowledge/retros/BET-Y2Q4-T10-259.md`

## 1 交付了什么

把 B3 `--reality-check` 仅剩的 **21 条署名准入 finding**（E4 未分区 19 + E5 双向不一致 2）
逐条取证摊成一次可答的清单，每条含：实际执行的 argv、调度形状、`EnvironmentVariables`
**条数**（值一律不抄）、mtime(UTC)、字节数、sha256 前 16 位、仓内 `bin/ops/launchd/` 镜像
是否存在、拟用 classification。21 条的仓内镜像**全部为 N** —— 这是「本仓不拥有这些 plist」
的实测依据，也是 `external` 提案不被「仓内自有 plist」反驳的证据。

同时把准入机制收敛为**恰好三条**（读 `classify_label` `bin/mof/gen-service-configs.py:345-357`）：
① 追加 `workspace_prefixes`（整族纳管，该前缀下未登记 plist 立刻进 E2 而红）；
② 追加 `exempt_labels` 且 classification ∈ external/unclassified/owned（拼错 fail-closed
落 `unmanaged_unknown` 并继续计入 E4）；③ 改运行面（署名面，B4b 批次 2+ 未获逐批授权前不做）。
本轮只交付清单与选项，**不替任何一条选**。

## 2 复测把交付物改了一次（这是本轮最重要的一次自我否决）

| 字段 | 基线 2026-10-19T10:08Z | 复测 2026-10-20T01:29Z |
|---|---|---|
| `installed_total` | 76 | **77** |
| E4 未分区 | 18 | **19** |
| `e1_drift` / `e2_undeclared` / `e3_lint_debt` / `unclassified` | 0 / 0 / 0 / 0 | 未变 |
| `workspace_scoped` | 38 | 未变 |
| `owned_declared` = `owned_installed` | 47 = 47 | 未变 |
| `registry_declared_total` | 75 | 未变 |
| E5 | 1 + 1 | 未变 |

差额是一条 `com.local.magpie-refresh`，mtime 2026-10-19T19:26:33Z —— **落在两次测量之间**，
由本机运行面落盘，与本轮交付无关。原 `done_when`「交付后读数逐字段相同」因此按构造不可满足：
交付者什么都没做，判据自己变红，且会把真回归埋进「机器自己动了」的噪声里。
已按分档改写（回归敏感字段逐字段相同 / 运行面自变量只允许可指认外部落盘且须记名放行），
并在 spec §5 固化「清单是快照、命令才是判据；作答前按当次 findings 双向对拍重导」。

## 3 历史文档不回改（同一失效面的一侧）

扫描 `docs/reports` + `docs/superpowers/specs` + `.omo/_knowledge/retros`（1351 个跟踪文件）后，
仍写着「E4 未分区 18 条」的是 **T258 自己的 spec §8 与 retro §5** 两处。二者都是其测量时点
的真实读数，且各自被 ledger 的 `content_digest` 绑定 —— 回改会破绑定（`COMPLETION_FILE_DIGEST_MISMATCH`）
且超出本轮 claimed write_surfaces。处理方式不是回改历史，而是**指定活计数的归属**：
本轮 spec 是当前 E4/E5 清单的唯一持有者，其余文档的计数按「该 BET 测量时点」读。

## 4 验收逐条实测

1. spec 在 canonical 位、frontmatter 九键齐全：`doc-governance-check.py --no-new-warnings
   --scope tracked` → `PASS (1 files, 0 warnings)`，exit 0。
2. 台账绑定 digest 与文件实际 sha256 逐字节相等：`digest bind==file: True`（重算后同步）。
3. 覆盖度**双向集合相等**：live E4 19 条 ↔ 表内 19 行，`missing=[] extra=[]`；
   E5 两条（`com.l4.omo.sync` / `com.cockpit.dashboard`）在 §4 各自成行。
4. `bet-ledger.py lint` → `OK -- 553 bets, 16 tracks, no errors`（total_bets 未被扰动）。
5. **合并后在 `origin/main@91107174f` 那棵树重导**（`bin/mof/gen-service-configs.py
   --reality-check --json`，判据必须由交付落地的那棵树产出）：
   - 回归敏感字段与 §2 复测读数逐字段一致：`e1_drift=0 / e2_undeclared=0 /
     e3_lint_debt=0 / unclassified=0 / workspace_scoped=38 /
     owned_declared=owned_installed=47 / registry_declared_total=75 / e5=1+1 / external=5`；
   - 运行面自变量 `installed_total=77`、E4 19 条，与 spec §1 记名读数一致；
   - 覆盖度**双向**：live 19 ↔ 表 19 行，`missing=[] extra=[]`；
   - 逐行属性：19 行的 `EnvironmentVariables` 条数 / mtime / 字节 / sha256:16
     **四列零不一致**，`镜` 列 19 个 N 与「仓内 `bin/ops/launchd/<label>.plist` 不存在」逐条相符。

⚠️ 一处必须写出来的口径限制：表的 `调度形状` 列是**语义简写**。重导比对时有 8 行低估实况
（`Calendar` 省略了同时存在的 `RunAtLoad`，`ThrottleInterval` 一律不记）；反向检查为**零**
—— 没有任何一行把 live 里不存在的键写成存在。即该列只欠陈述、不产生假陈述，
作答时以当次重导为准（spec §5 第 3 条）。

## 5 运行面未动的证据（本轮 non_goal 的可测后果）

三个哈希在**交付前与合并后各测一次**，两次读数逐字节相同：

- `crontab -l` sha256 前 16 位 = `cbf14ddc2fdd972a`（8491 字节），与 T258 四次快照相同；
  合并后复量仍是这一个值。
- `~/Library/LaunchAgents` 共 77 份 plist（= `installed_total`），最新 mtime 仍是外部的
  `com.local.magpie-refresh.plist`（`2026-10-19T19:26:33Z`）—— 本轮没有任何 plist 被写入；
  无 `bootout` / `bootstrap` / `kickstart`。
- `.omo/_truth/registry/services.yaml` sha256 前 16 位 `45f56048eb74a782`（195641 字节）
  两次相同；`workspace_prefixes` / `exempt_labels` / `--reality-check` 判据本体零改动。
- 交付 diff 只落在两条 claimed write_surfaces，无生成态混入（`git status --short`
  收口腿只列出本报告与 retro 两个新文件）。

## 6 B3 的剩余路径（不在本轮）

`ok=true` 只能由署名准入达成：`com.local.*` 13 条可整族裁定（全部无仓内镜像），
`com.localbrain.*` 4 条需先确认落盘意图（全部 2026-10-19 当天落盘，指向
`~/Project/work-agent/scripts/`；其中 `preseed-http` 以 `--bind 0.0.0.0` 在 8088
常驻暴露静态目录服务且 `KeepAlive` —— 本 receipt 只转述清单，不处置），
E5 两条各自在 A/B/C 中选一。

本 receipt 不宣布 ADR-0456 B1 / B3 / B4 / B5 或整个 plan 完成。
