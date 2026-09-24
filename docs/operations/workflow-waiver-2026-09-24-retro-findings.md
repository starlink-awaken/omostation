---
type: operations
status: active
owner: governance-agent
created: 2026-09-24
last-reviewed: 2026-09-24
scope: workflow-requirement-iteration-waiver
---
# Workflow Waiver Record

**Date**: 2026-09-23（三次交付）/ 2026-09-24（本记录 + 修正交付）
**Agent**: governance-agent
**Escape hatch**: `AGCP_REQUIREMENT_ITERATION_GATE=0`（`requirement-iteration start requires --bet`）
**用于**: workflow `start` 与 `closeout`（后者同样因无 bet 而断 vision→retro 链）

## Reason

ADR-0203 的 requirement-iteration 门要求 `start --bet <BET-ID>`，但 **3Y-BET-LEDGER 当时 448 条 bet 全部
`status: done`，开放数为 0**（`docs/plans/3y-bet-ledger.yaml` 实测），不存在可绑定的 bet。
因此这不是"跳过门禁图省事"，而是**台账耗尽后的结构性必然**：只要继续交付，就必须走豁免。

> 本记录同时是该空档的可审计报告（"只报告，不处置"）：台账规划权属 principal，Agent 未增删任何 bet。
> 在补充新 bet 之前，**后续每一次交付都会需要同类豁免**——这是需要 principal 决策的点，不该被 env 变量静默抹平。

## Authorized Work

| PR | merged SHA | 内容 |
|----|-----------|------|
| #4244 | `b229a77da` | Agent Brief `resolve-failing-gates` 时效性提示 |
| #4245 | `b7052a2a6` | 两条治理踩坑固化（PITFALL-GAT-011 + pattern） |
| #4246 | `5b1564662` | `docs/operations/claims-activation-checklist.md`（只读） |
| #4266 | `af33a3e80` | 复盘 findings F1–F4 修正：豁免留痕、删除无消费方字段、Claims 数值指针化、修 `gen-knowledge-index.py` 前缀元数据丢失 + 重建知识索引 |
| #4275 | `a05524920` | 二次复盘 findings H1–H3：`submodule-reachability-gate.py` 网络工作加有界预算（超时降级为 unverified 而非 unreachable）、`hook-runner.sh` 死超时参数改名并说明真相、生成物（BRIEF.md / CLAUDE.md 注入段）去除主机绝对路径 |
| #4280 | `4f8a64705` | 把上一行 "PR 待登记" 占位符绑到真实 PR（#4275 / `a05524920`）——占位符本身就是 F1 要消灭的东西 |
| #4285 | `0a129eb13` | 固化本次复盘教训为 error-knowledge 条目 PITFALL-GAT-012（pre-rebase 缺执行位是保护而非缺陷）+ PITFALL-MEA-004（hook-runner 死超时参数）；同一豁免（`governance-state-mutation` run 20260924T072410Z） |
| #4287 | `6f3fc3220` | 把上两行（#4280 / #4285）登记进本表——F1 留痕补齐，单文件 docs 变更 |
| #4295 | `eac467af8` | 修 error-knowledge 召回路径静默丢条目：`_load_all` 归一 legacy 条目、不可召回文件上报而非吞掉、`check` 与召回同源计数（`recall divergence`）、`_save_entry` 不再落盘 `_path`/`_file`（清理 6 条已被写入主机绝对路径的 pitfall 记录）+ 5 条回归测试（`project-code-change` run 20260924T133342Z） |

**2026-09-24 复核**（本行由 #4295 之后的登记交付补写）：空档仍未闭合——`bets` 段全部条目 `status: done`，
开放数 0。因总条数会随台账增长而腐坏，此处不留数字，复核用：

```bash
python3 -c "import yaml,collections;d=yaml.safe_load(open('docs/plans/3y-bet-ledger.yaml'));b=d['bets'];b=b if isinstance(b,list) else [x for v in b.values() for x in v];print(collections.Counter(str(x.get('status')) for x in b))"
```

注意 `campaigns` / `milestones` 段有 `status: active` 条目（`CMP-*` / `MS-*`），但它们不是 bet，
不能用于 `--bet` 绑定；只统计顶层全部条目会把它们误算成开放 bet。

## User Confirmation

- "可以，依次推进吧"（授权按 #4 → #5 → #1 顺序推进）
- 既有常置授权链："pr 合并提交" / "我给你授权，推进吧"
- 复盘后选择："F1 补豁免留痕、F2 删死字段、F3 数值指针化、F4 补可发现性；F5 只报告不处置"
- 二次复盘："go"（授权处置 H1/H3；H2 经实测改判为**只报告**，见下）

## H2 改判（实测推翻初始假设）

初始报告称 `.githooks/pre-rebase` 缺执行位是缺陷。实测三点推翻：

1. `SWARM_ESCAPE_ID=rebase-ci bash .githooks/pre-rebase HEAD^ origin/main` → 仍 exit 1，文档宣传的逃生口是死的
   （`[ "$x" != rebase-* ]` 是字面串比较，只有 `[[ ]]` 才做模式匹配）。
2. git 的 `pre-rebase` 签名是 `<upstream> [<branch>]`，`$2` 是被 rebase 的分支名而**不是 onto**，
   所以脚本从未实现它声称的"拒绝 rebase onto main"。
3. 在落后于 main 的分支上 `git rebase origin/main` 会被该 hook exit 1 拦下——而这正是 PITFALL-GAT-007
   规定的 push 前动作。**补上执行位等于让全场 Agent 的 push 前 rebase 失败**。

因此 H2 不修：激活危害大于收益，且修复方向（重写判定逻辑 + 真正的逃生口 + 回归测试）超出本次"有界性"范围。
已作为需 principal 决策项上报。

## I1（第三次复盘发现：closeout 的 verify 腿在提交后是空跑）

实测：本日 #4295 / #4296 / #4298 三次交付的 closeout **全部**输出 `verify checks=0 ok=True`。

根因是代码定位，不是推测：

- `closeout_run` → `build_verify_report(execute=True)`，`--from-diff` 的文件集合来自
  `changed_files_from_git()` = `git diff --name-only` + `git diff --cached --name-only`（工作树/索引相对 HEAD）。
- 正常时序是 commit → push → PR → merge → closeout，此刻工作树干净 ⇒ 文件集合为空 ⇒ `select_diff_checks`
  返回 0 条 ⇒ `ok = all([]) and claim_coverage["ok"]` 为 **True**。**零条校验执行，closeout 却报 ok。**
- 侧效应：该函数还会扫 `load_external_write_roots()`。实测在交付后跑 `verify --from-diff` 采到 3 个
  **他人仓库**的文件（`external/zhixing-dashboard/*`），与本 Agent 的交付毫无关系——即文件集合既可能为空，
  也可能非我。

今天可用的替代路径：`closeout <run> --status ok --file <本 run 已 claim 的路径>`。实测它选出 **4** 条
真检查并全部执行（`doc-ssot-lint` / `ssot-guardian` / `gac-local-gate` / `doc-claims-check`）。

`--all` 反而不可用，实测记入：它确实选出 **32** 条（不空），但在 PASW worktree 里被
`omo-state-projection-guard` 卡死——`.omo/state/runtime/*` 是**未入库的本地产物**（该目录只有 `README.md`
被 track；主工作区有 10 个文件，新 worktree 只有 README），于是 10 条 `canonical_missing: halt` 与本次
交付无关地阻断 closeout。换句话说：**`--all` 把"环境缺运行时产物"报成交付失败**，而 `--from-diff` 把
"提交后无脏文件"报成交付通过——两个方向都错，只是错得相反。

**未在本文档这轮直接修**：收紧 `ok` 语义会让所有并发 Agent 的 closeout 从"通过"变"失败"，且实现在
`projects/omo` 子模块内（改动需指针事务）。属需 principal 决策项。建议方向：`from_diff` 且文件集合为空时
fail-closed（要求显式 `--all` / `--file`），或把 `check_count=0` 记为 DEGRADED 而非 ok；并把 `--from-diff`
的文件集合限定为该 run **已 claim** 的路径。

## Boundary

- Claims Authority 激活保持 fail-closed，未由 Agent 代办；#4246 仅为只读文档。
- 未补录价值记录（30 条门保持 NOT_PROVEN）；未做 weekly-review（principal-only）。
- 台账未改动。

## Follow-up

本记录自身的存在即是 F1 的修正：此前三次豁免只落在 `.omo/_delivery/*`（gitignored），git 上零痕迹。

需要区分两套**互不相通**的 waiver 机制，避免误以为本记录会生效于门禁：

| 位置 | 消费方 | 契约 |
|------|--------|------|
| `docs/operations/workflow-waiver-<date>-<slug>.md` | 人 / git 审计痕迹（本文件） | 无机器读取方 |
| `.omo/_truth/governance-evidence/waiver-*.md` | `bin/gac/check-governance-ratio.py::_active_waivers()` | frontmatter `status: active` + `pr_numbers` 命中 `GITHUB_PR_NUMBER` |

`check-governance-ratio.py` 只认第二处，且是**治理配额上限**的单 PR 豁免，与 `AGCP_REQUIREMENT_ITERATION_GATE`
无关。本次交付未触配额上限，因此**未**创建第二类豁免记录——若后续需要，必须显式登记 `pr_numbers` 才有效。

**自指上限（结构性，非疏漏）**：登记表只能由"后一次"交付补写前一次，因此**本 PR 自身的行必然缺失**，
且不会由本 PR 补上（那需要一个尚无 SHA 的占位符，正是 F1 禁止的东西）。下一次豁免交付负责补写本 PR 的行。
台账补齐可绑定的 bet 之后，这条链条整体消失。

