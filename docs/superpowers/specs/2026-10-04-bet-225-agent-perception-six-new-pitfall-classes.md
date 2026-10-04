---
schema_version: specification/v1
spec_version: 1.0.0
title: BET-Y2Q4-T10-225 — agent 感知固化：AGENTS.md §7 六类新踩坑 + 台账 tail-append 冲突重建配方
bet_id: BET-Y2Q4-T10-225
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-10-04
---


> 承接 `BET-Y2Q4-T10-222` closeout report §5 的自陈：「是否转化为持续收益，取决于任务 #107
> （把时钟炸弹这一类补进 AGENTS.md §7 的 hermetic 条目）」。本 BET 就是那一笔落地，
> 并一并固化 T10-224 与本轮收尾实测中新暴露的四类形状。

## 1. 为什么这六条，而不是更多

判据（沿用 `BET-Y2Q4-T10-221` 立下的准入）：一条教训进 AGENTS.md §7 当且仅当
①它**已在两个以上独立交付里复发**，或②它**当场会让安全检查/验收判据静默失效**，
③且能被一条**不依赖本机状态**的判据指认。不满足的写进 report/retro，不进协议层。

本 BET 的六条全部命中②或③，且证据均可在 `origin/main` 上逐字复核。

## 2. 交付内容

### 2.1 `AGENTS.md` §7 新增六条

| # | 条目 | 实测证据（合并态可复核） | 固化进协议的判据 |
|---|---|---|---|
| E1 | **YAML 重复键静默 last-wins** | `.omo/cron/registry.yaml` 两条 panorama 记录各带两个 `reality` 键，全文件 dup-aware 扫描恰好 2 处、其余 68 条干净（PR #4623 → `d8ab0aa58`） | 改这类文件**只改其中一行无效**，另一行仍会赢；必须删被遮蔽的键。检测器须带 dup-aware `MappingNode` constructor，且**自证**——`tests/unit/test_cron_registry_reality_invariants.py` 的 `test_duplicate_key_detector_is_not_a_no_op` + `test_safe_load_alone_would_have_missed_that_violation` 是标准形状 |
| E2 | **时钟炸弹（绝对时间戳 × 相对窗口）** | `tests/unit/test_projection_reader_resolution.py` 三处 fixture 写绝对 `generated_at`，2026-10-02 起必红；T10-222 用 `_fresh_ts()` 把这类不可复现红从 3 处降到 0 处（PR #4617 → `e43d6bc9d`） | fixture 时间一律相对 now 派生；指认命令：`grep -rn "write_text.*generated_at:[ ]20" tests/unit --include="*.py"` 必须 CLEAN |
| E3 | **「按构造就绿」——断言的成立前提由 fixture 自己写出** | `tests/unit/test_repo_root_profile.py:146` 的「退回仓内已提交的 legacy」按构造不可满足（17 条投影只 1 条被跟踪）；`test_projection_reader_resolution.py:42` 之所以绿是它自己物化了 legacy；T10-222 verify-3 用变异对照（`legacy.write_text(` → `pass` → `MUTATION_EXIT 1`）才证明断言真依赖该前提 | 任何这类断言必须配**变异对照或合成违规自证**，否则「绿」只是检测器没命中（#4606 同族）。同族变体：**被检对象的根不得由 `__file__` 反推**——用例/检查器指向的根要走 `bin/lib/repo_root.py` 显式 resolver，与「写路径要在调用时刻解析」是同一错误的两端 |
| E4 | **GitHub「no checks reported」的第一因是 CONFLICTING，不是 paths 过滤** | PR #4623 首报零 checks，`gh pr view --json mergeable,mergeStateStatus` = `CONFLICTING` / `DIRTY`；`.github/workflows/governance-check.yml` 的 `on.pull_request.paths` **不含 `tests/unit/**`** 是另一件独立事实 | 零 checks 先看 `mergeable`，再看 `on.paths`；两者搞混会把「冲突未解」读成「CI 放过我了」，并把本地 pytest 唯一证据的那批文件误当成有 CI 覆盖 |
| E5 | **本机 shell 别名把「命令成功」变成「什么都没做」** | 实测：`grep -iE` → `error: unknown encoding`（此处 grep 实为 ripgrep，`-E` 是编码、`-r` 是 replace）、`grep -rn … -name` → `fd` 用法错误、`cp` 被 alias 成 `cp -i` 对已存在文件**静默拒绝覆盖**并返回成功 | 一次性脚本里的文件复制/查找/计数一律用 Python，或写绝对路径 `/usr/bin/grep`、`/bin/cp`；凡「命令 0 退出但断言没变」先怀疑别名，再用 sha 逐字节复核 |
| E6 | **行号指针会随上一轮交付漂移** | 本文件 §7 里 `test_projection_reader_resolution.py:42`、`test_repo_root_profile.py:146` 写在 T10-221 基线上，T10-222 重写后 `:42` 变成 `registry = next(...)`、`:146` 变成 TRUTH_DIR 注释，断言本体在 `:61` / `:174` | 优先写符号名（测试函数名/键名），行号只作辅助；引用前 `git show origin/main:<path>` 取该行内容核一遍；发现陈旧指针就地修正（本轮修这两条） |

措辞要求：每条含 ①复发/失效证据（可指认的 ref 或 file:line）②判据（可执行命令或可复制的测试形状）③纪律（下一步做什么）。禁止只写结论。

### 2.2 `docs/SOPs/ledger-closeout-sop.md` 新增一节：台账 tail-append 冲突重建配方

多 agent 并发下 `docs/plans/3y-bet-ledger.yaml` 的冲突固定形态：两侧都在 `bets:` 尾段追加、
或改相邻 `completion_evidence`。`meta.total_bets` 是**派生值**，两侧写同一个数字时 git 会静默合并成功，
于是声明开始说谎（先例 `BET-Y2Q3-T10-202.md:82-84`）。配方：以最新 `origin/main` 的整份文件为底，
只把自己那一段插到唯一锚点之前、`total_bets` 加一，然后**三条断言缺一不可**：

1. `total_bets == len(bets)`；
2. `len(set(ids)) == len(ids)`（重复 id 为 0）；
3. main 侧已存在的 `status: done` 转换与 `completion_evidence` 逐条存活。

禁止：用整文件 `yaml.dump` 重排（会把别人的条目按 key 排序重写，diff 淹没真实改动）、
在共享主工作区 merge/rebase 吸收上游。

## 3. done_when / verify

| # | 命令 | 期望 |
|---|---|---|
| V1 | 抽取 AGENTS.md §7 新增六条的锚点串并逐条断言存在 | 6/6 命中 |
| V2 | 从新增条目中提取反引号内的路径/`path:line` 引用，断言路径存在**且该行内容与所述语义相关**（⑥ 的判据）；陈旧指针修正前后各测一次 | 0 处虚构、2 处陈旧已修 |
| V3 | `uv run --with pyyaml python3 bin/ssot/doc-governance-check.py --no-new-warnings --scope tracked` | PASS（不因本轮新增告警） |
| V4 | `git diff --name-only origin/main...HEAD` | 严格等于 §4 write_surfaces，无越界 |
| V5 | 台账三条断言（§2.2） | 全绿 |
| V6 | `python3 -m pytest tests/unit/test_cron_registry_reality_invariants.py -q` | 全绿（证明 E1 的判据形状确实可跑，不是纸面） |

## 4. write_surfaces

- `AGENTS.md`
- `docs/SOPs/ledger-closeout-sop.md`
- `docs/plans/3y-bet-ledger.yaml`
- `docs/superpowers/specs/2026-10-04-bet-225-agent-perception-six-new-pitfall-classes.md`
- `docs/reports/2026-10-04-bet-225-agent-perception-closeout.md`
- `.omo/_knowledge/retros/BET-Y2Q4-T10-225.md`

## 5. non_goals

- 不改任何门禁脚本、registry、测试代码（E1–E3 的判据已由 T10-222/T10-224 落仓，本 BET 只固化感知）。
- 不新增 BET 之外的第 6、7 条教训：候选「`prune-locks` 危险」「closeout 需在含 retro 的检出跑」已在
  `BET-Y2Q4-T10-221`/`T10-224` 的 report 里，未达两条准入，留在 report 层。
- 不动 `docs/architecture/ops-services-health.md`（`type: ephemeral`，且 launchd 事实的真值是
  `.omo/cron/registry.yaml`，不在文档里复制第二份）。
