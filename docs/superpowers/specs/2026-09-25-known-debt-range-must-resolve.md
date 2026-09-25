---
schema_version: specification/v1
spec_version: 1.0.0
title: "known-debt 豁免条目必须在写盘时解析成完整 commit"
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-25
---

# known-debt 豁免条目必须在写盘时解析成完整 commit

> 承接 `2026-09-25-gitlink-behind-not-rewind-design.md`（I13）里点名的第二次缺陷：
> 指纹不落 merge-base ⇒ 存量债事后不可重判。本 spec 把它从"一条字段缺失"扩成实测结论：
> **整个 `gitlink-ancestry` 债账在写下那一刻就已经不可复审**。

## 1. 实测（`origin/main` @ `52fd5147c`，只读复跑）

`.omo/_truth/registry/gate-known-debt.yaml` 共 35 条，其中 `surface: gitlink-ancestry` **30 条**
（`kind: gitlink-regress` 30 条）。逐条尝试重导：

| 事实 | 计数 | 含义 |
|------|------|------|
| `range` 的 base 侧记为字面 `origin/main` | **30 / 30** | base 是会随 main 换指的符号 ref；**没有任何一条**能复原"当时比的 base commit" |
| head 侧记为 12 位缩写 | 23 / 30 | 缩写不是身份：对象可能被 GC，且无法证明与 `signature` 同源自洽 |
| head 侧记为完整 40 位 | **0 / 30** | 无一可直接寻址 |
| head 侧记为符号 ref | 4 / 30 | 3 条字面 `HEAD`（指向"写盘那一刻的检出"）、1 条分支名 `followup/agora-pointer-fix-20260827`（分支已删） |
| head commit 本地可解析 | 4 / 30 | 对这 4 条重判：`ptr@head ≠ ptr@merge-base` 且与 `reason` 里的 new/old 完全吻合 ⇒ **4 条都是真回退**，不是误报 |
| head 仅能经 `refs/pull/*/head` 取回 | 2 / 30 | 普通 `git clone` 不含该 ref，需显式 `+refs/pull/*/head:refs/remotes/origin/pr/*` |
| head 对象在本地与 4307 条 PR ref 中皆不存在 | 17 / 30 | 不可恢复 |
| `reason` 根本不是回退陈述 | 3 / 30 | `"realigns after child origin/main force-push dropped"` / `"advances … via squash"` / `"unreachable (not in any remote ref); aligned to"` —— 被记进 `kind: gitlink-regress` 后永远匹配不上任何真实 violation |
| 带 `owner` 或 `expires_at` | **0 / 30** | `swarm_discipline.known_debt_active()` 只在 `expires_at` 可解析时判过期；缺失 ⇒ **永久有效**。而 `.agents/skills/ci-red-triage` 写的是"登记 known-debt（owner+过期）" |

结论：可复审率 **0/30**（base 侧全为符号 ref，与 head 侧能否解析无关）。这不是"某几条脏了"，
而是**写盘格式不支持复审**。

## 2. 契约

一条 `gitlink-regress` 债要能被后一次交付重判，必须独立于任何符号 ref 与分支存在。因此
`record_known_debt` 落盘的每条条目须满足：

- **C1** 携带 `base_sha` / `head_sha` / `merge_base` 三个键，值为**完整 40 位 commit**（写盘时
  用 `git rev-parse --verify --quiet <ref>^{commit}` 解析；解析不出则留空串，让缺口可见而非伪装成证据）。
- **C2** `merge_base == git merge-base <base_sha> <head_sha>`，即条目自带重判所需的第三个点
  —— 有了它，"落后 vs 回退"（I10/I13 的判据 `P_head ≠ P_merge_base`）可事后复算。
- **C3** `range` 保留操作员写入的原文（不截断），仅作 provenance；重判一律走 C1 的三个 SHA。
- **C4** 携带 `exempt_reason` = `[gitlink-regress: <理由>]` 里的 `<理由>` 原文。此前 human 理由
  只存在于被 squash 掉的 commit body 里，条目本身不含——"有意回退"的授权凭据因此随分支一起消失。
- **C5** `signature` 与 `fingerprint` 的计算方式不变（`sha256(path \n old_sha \n new_sha)[:16]`），
  所以存量条目与新条目仍在同一身份空间内，去重行为不变。

## 3. 改动范围

`bin/gac/check-submodule-rewind.py::record_known_debt` 增加写盘时的 ref 解析与 C1–C4 四个键；
调用点把 `run_ancestry_gate` 已经算出的 `merge_base` 与 `tags[0]` 传入。判据、exit code、
去重与 `--no-write-debt` 语义一律不变。

## 4. 非目标

- **不改 30 条存量条目**：它们是别人交付写下的豁免记录，且本仓 `growth_policy: shrink_only`。
  逐条补写 SHA（多数已不可补）或批量删除，都属 principal 的处置权。本 spec 只交审计与格式。
- 不动 `owner` / `expires_at` 的强制（那需要门禁改 `.omo` 写入规范，属另一条债）。
- 不做"豁免过期自动失效"的行为变更。

## 5. 验收

1. `tests/unit/gac/test_gitlink_ancestry_gate.py::TestDebtEntryReDerivable` 通过：以符号 ref
   （分支名 + `HEAD`）作 `--range` 传参触发豁免写盘后，条目的 `base_sha`/`head_sha`/`merge_base`
   均为 40 位、`range` 保留原文、`exempt_reason` 等于标签里的理由；**随后删除该分支**，
   三个 SHA 仍可 `cat-file -e`，且 `git merge-base base_sha head_sha == merge_base`。
2. `tests/unit/gac/test_gitlink_ancestry_gate.py` 与 `tests/unit/gac/test_check_submodule_rewind.py`
   全绿，既有用例（含 `test_exemption_preserves_existing_debt_entries` 的 shrink_only 保序断言）不回归。
3. `python3 -c "import ast; ast.parse(...)"` 与 `ruff check` 干净；`make gac-local-gate`（或
   `bin/gac/gac-local-gate.py --scope staged --json`）`ok=true`。
4. 本 spec 的 §1 数字可在 `origin/main` 上只读复跑得到（同一 commit 或其后；条目数只增不减）。
5. 存量 30 条在本交付后**内容不变**（`git diff` 不含 `.omo/_truth/registry/gate-known-debt.yaml`）。
6. 本 run 依 G5 对称豁免以 bet-less 起步（`governance-audit` ∈ `GOVERNANCE_EVOLVE_WORKFLOWS`），
   不新增 bet、不设 `AGCP_*`、不建 waiver 文件；台账零改动。
