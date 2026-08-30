---
status: active
lifecycle: history
owner: engineering-agent
bet: BET-Y1Q3-T4-02
last-reviewed: 2026-08-30
title: 复盘：T4-02 父编排推进 — 证据工程与人类裁决边界 (2026-08-30)
type: retro
---
# 复盘：T4-02 父编排推进 — 证据工程与人类裁决边界 (2026-08-30)

> 触发: 用户"继续推进 T4-02 父编排" → 本轮交付 → "先做一个复盘吧，然后再看要不要继续推进"
>
> 数据基线: worktree `ws-t4-02-parent`，主仓 PR #2656（MERGEABLE，required checks 全 pass），
> cockpit PR #97（MERGED `4501ca90`），台账 lint 222 bets 无问题

## 1. 做对了什么

| 动作 | 效果 |
|------|------|
| **先跑 verify 再动手** | 发现 T4-05/T4-07 实现全在 main（27 / 126 passed），缺口只是证据与复盘，避免了重写已有实现 |
| **主动 skip 重复劳动** | rebase 时发现 T4-05 已被并发 agent 独立收尾升 done（主仓 `77f94f25e`），skip 自己的台账 commit，只保留增量 |
| **诚实停在 blocked** | T4-07 的 `value_indicator_policy: true` 要求真实人类裁决，不伪造 ACCEPTED |
| **证据从占位升级为真实运行** | 两个 BET 的 operational 四键从「引用 spec 设计文档」改为「canary 实际运行报告」 |
| **先 ls 再相信 verify** | T4-07 verify 指向的 cockpit 测试文件从未创建，否则会一直跑一个必然失败的命令 |

## 2. 交付清单

| # | 交付 | 落点 |
|---|------|------|
| 1 | T4-07 cockpit 测试 13 用例（真实缺口） | cockpit `4501ca90`（PR #97 MERGED） |
| 2 | T4-05 端到端 canary 六步 | `bin/ssot/agent-cell-effect-receipt-canary.py` |
| 3 | T4-07 机制 canary 四步 | `bin/ssot/human-adjudication-canary.py` |
| 4 | 两份 canary 报告 | `docs/reports/2026-08-30-*.json` |
| 5 | 证据升级 + T4-07 三轴 | `docs/plans/3y-bet-ledger.yaml` |
| 6 | BET 级复盘 ×2 | `retros/BET-Y1Q3-T4-05.md`、`BET-Y1Q3-T4-07.md` |
| 7 | script-registry 登记 ×2 + baseline 536→538 | `.omo/_truth/registry/` |
| 8 | 主仓汇总 PR | #2656 |

T4-05 canary 的零副作用断言值得一提：不是查"有没有新增文件"，而是对预置的
target/provider/tool/ledger 哨兵做**执行前后全量文件树 sha256 快照对比**——
后者才能证明"零副作用"，前者只能证明"没新增"。

## 3. 一次自纠（值得记）

首版 T4-07 canary 把「相同裁决重放产生第二条 adjudication 记录」断言为 bug，
报了 `records_after_replay: 2`。

**实际是设计**：裁决日志 append-only，accept → reject 后 effective verdict 取最新
（`test_effective_verdict_accept_then_reject` 已覆盖）。计数去重不在这一层，
由 `PersonalEpisodeService.verdict_distribution` 承担。

> 教训：看到运行时行为与 done_when 字面不符，先查测试是否已覆盖该语义，再断言是缺陷。
> done_when 说的"重放不增加计数"指的是 **qualifying count**，不是 adjudication 记录数。

## 4. 陷阱清单（工程可复用）

1. **canary 报告不要记录主仓 HEAD**。含 `workspace_head` 会让报告的 sha256 随每次
   commit 变化，而台账 evidence 引用的是报告 digest → 鸡生蛋死循环。只记 `omo_head`
   这类 commit 后不变的值。
2. **`value_indicator_policy` 决定两条完全不同的推导路径**：
   `false` + VERIFIED/PROVEN/NOT_PROVEN → `delivery_accepted`（可自动化闭环）；
   `true` → 必须 `outcome_accepted`，value 轴 ACCEPTED 的四键证据必须绑定真实
   non-test 人类裁决，自动化止步 `blocked`。
3. **`merged_reachable_commit` 必须是主仓 bump commit**。lint 用
   `git -C <workspace> cat-file -e` 校验，子仓 commit 在主仓对象库不存在。
   找法：沿 `git log --format=%H -- projects/<sub>` 取候选，再用子仓
   `git merge-base --is-ancestor <实现commit> <候选gitlink>` 判定。
4. **本地 `ci-local-fast` 的 gac 项报 `bin/ssot/bus-usage-report.py not found`**：
   该脚本是 PACK symlink，`src/dormant_adapter.py` 从未入库（git 未跟踪、共享 checkout
   同样缺失），而 `gac-local-gate.py:297` 仍声明该 gate → **main 级 pre-existing**。
   判据：CI 上 `gac-gate` pass，本地红 → 环境性，可逃生，不必"修"。
5. **并发 agent 会在你工作期间完成同一件事**。本轮 T4-05 retro 撞 add/add 冲突。
   遇到冲突先看对方做了什么，已完成且等价就 skip 自己的，只保留增量。

## 5. 验证数据

```
bet-ledger lint           OK — 222 个 bet，11 条轨道，无问题
gac-validate --gate       ✅ 0 error, 0 warning
script_baseline           538 = 活跃脚本 538
T4-05 canary              六步全绿（零副作用 / receipt / 幂等 / conflict / 只读 / cleanup）
T4-07 canary              四步全绿（happy / 7 负例 / append-only / cleanup）
cockpit PR #97            lint pass + test pass
主仓 PR #2656             gac-gate / bet-done-transition / evidence-gate / phase-gate 全 pass
```

## 6. 剩余与决策建议

**T4-02 父编排只差 T4-07 一个子 BET**：T4-03/04/05/06/08 均 done。

T4-07 的阻塞是**结构性**的，不是工作量问题：

- `value_indicator_policy: true` → 必须 `outcome_accepted`
- value 轴 ACCEPTED 需要 `real_signal` / `human_verdict` / `revision` / `time_burden` 四键
- 四键必须绑定**一条真实 non-test 的人类裁决**
- 机制和证据已全部就绪，但"人真的判了一次"这件事无法由 agent 代劳

三个可选项：

| 选项 | 代价 | 收益 |
|------|------|------|
| **A. 现在走真实裁决** | 需要 principal 到场，走一次 Decision Inbox 真实流程 | T4-07 → done，T4-02 父编排闭环 |
| **B. 转去推别的 BET**（如 T6-15） | 中断当前上下文 | 不空等，但 T4-02 继续挂着 |
| **C. 就此收手** | T4-02 保持 candidate | 本轮交付已入库，不浪费 |

**建议 A**：本轮已把所有前置铺完，裁决本身只需一次真实操作，之后四键补齐和升 done
是机械工作。若信号源尚未就绪，则 B 更合适——不要让已就绪的证据继续空转等待。
