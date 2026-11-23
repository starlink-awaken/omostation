---
schema: md/v1
status: active
lifecycle: history
owner: governance-agent
last-reviewed: 2026-11-23
type: report
bet_id: BET-Y2Q4-T10-350
title: BET-Y2Q4-T10-350 closeout — omo-debt 非 str 条目 ref 判 stale 而非崩投影平面
---

# BET-Y2Q4-T10-350 收口收据

主体改动分两段落地：子模块侧 omo#258（squash `08ce92a`，lint / test / test-cov 三项 pass）；
主仓侧 PR #5488（squash `2e26f8441`）把 `projects/omo` gitlink 从 `d87a680` 推到 `08ce92a`，
并铸本 BET（`meta.total_bets 597 → 598`，与 `len(bets)` 一致）。契约见
`docs/superpowers/specs/2026-11-23-omo-debt-malformed-ref-plane-freeze-bet-t10-350.md`。

## 读数前置条件（这条决定其余读数是否成立）

本收据所有读数取自 **`origin/main` 的 pin 检出**（`/Users/xiamingxing/ws-leg2close`，HEAD
`2e26f8441`，`projects/omo` = `08ce92a`），不是规范主检出。

规范主检出 `/Users/xiamingxing/Workspace` 停在 `53a9abfbe` 世代、且持有其它 agent 的未提交工作，
按约定不在共享主树上做 `reset / clean`，`bash bin/gac/sync-main.sh` 属 principal 动作。
⇒ **运行面（launchd `com.omostation.omo-debt-refresh` 的 WorkingDirectory 即规范主检出的
`projects/omo`）在 canonical 同步之前仍执行旧代码**。本 BET 修的是代码与投影平面的结构缺陷，
部署滞后如实登记在下面「未执行动作」，不用作 PROVEN 的替代口径。

## 受控测试（verify[0]）

```
$ cd projects/omo && uv run pytest tests/unit/test_omo_debt_malformed_refs.py -q
4 passed in 0.44s
```

四条用例分别钉：resolver 对 dict/int 返回 `None`、对 str 返回路径；fixture 的 YAML **确实**把带
ASCII `: ` 的那一行解析成 dict（前提而非假设）；`refresh_outputs` 遇畸形 ref 不抛且 `generated_at`
等于本次 `now`；畸形条目在 review queue 里**可见**且 `stale_evidence: True`。走的是真实入口
`refresh_outputs`，不是从生产脚本抽函数直调（AGENTS §6：测试绕过接线就钉不住接线）。

## 组合复测（verify[1]）

```
$ uv run pytest tests/unit/test_omo_debt_malformed_refs.py \
      tests/unit/test_omo_debt_naive_timestamps.py \
      tests/unit/test_omo_debt_metrics_terminal_vocab.py
10 passed
```

收口当天在 `ws-leg2close` 复测同读数（2026-11-23，`10 passed in 0.61s`）。时间戳 naive 与终态词汇
两条既有契约无回归 —— 这两条正是本平面历史上另外两类「单条目打崩全局」的形状（`TypeError` 比较 /
`resolved` 被误计为开放项）。

## 门禁（verify[2]）

```
$ make governance-release-gate   → rc=0
$ make gac-local-gate            → PASS (76 checks executed, 1 SOFT WARN)
```

唯一 SOFT WARN 是 `concurrent-write-drift: .omo/state/system.yaml mutated mid-run`（本机物化器与
门禁并发写运行态，与本 diff 内容无关）。CI 侧 PR #5488 全绿，`mergeStateStatus: CLEAN`，
2 项 `skipping`（`doc-freshness`、`Documents domain projects` —— 域未命中）。

## 判读要点（变异自证）

- **判据能红**：把同一用例跑在**未修树**（`git archive` 自 pin `d87a680` 的 `src`）上 ⇒
  `TypeError: argument should be a str or an os.PathLike object where __fspath__ returns a str, not 'dict'`
  （`pathlib/__init__.py:150`）—— 与生产日志 59 段 Traceback 同签名。
- **装置口径踩坑一次**：第一次变异证明无效 —— `PYTHONPATH=<未修树>/src` 被 pytest rootdir 的
  `pythonpath=["src"]` 重新指回已修树，跑出 `4 passed`。判据改用**真实未修树**重建后才拿到红。
  教训登记在 retro §4：外部 `PYTHONPATH` 不是权威，`import` 后打 `__file__` 才算证过。
- **`rg -rl` 复发**：本轮又一次把 `-rl` 当 `-l` 用（实为 `-r l`，把命中行改写成 `l`），伪造出
  `from omo.omo_debt_metrics import l` 这种不存在的符号。该坑早有文字固化但仍复发 —— 文字层固化
  不足以保证不再犯，属 harness 层缺拦截（retro §4 记为待裁项，不自行开面）。

## operational-轴

| 项 | 读数 |
|---|---|
| fresh_receipt | 本文件，2026-11-23 现采（canary 与复测均在 `ws-leg2close` 当场跑出，非沿用 PR 描述） |
| live_canary | 真机 `refresh_outputs(omo_dir=<临时目录>, now=<本次>)` 喂**含畸形 ref 的条目**：`parsed_type_of_evidence_refs[1] = dict`、`resolver_on_dict = None`、rc=0 无异常、`generated_at` 命中本次 `now`、写出 5 个投影面（dashboard / reviews / review-queue / action-packet / owner-routing，共 8 个文件）、`backlog_pressure: 1.5`（未归零）、`BAD-REFS` 在队列可见（未被静默丢弃） |
| replay | `.omo/_knowledge/retros/BET-Y2Q4-T10-350.md`（含 Q1–Q5 与本收据的口径互指） |
| cleanup | canary 只写 `tempfile.mkdtemp`，规范主检出与 `.omo/debt/**` 未被本次收口写入；`ws-refsguard` 已随 merge 释放、远端源分支由 squash 删除；`ws-leg2close` 在本 PR 合并后释放 |
| 未执行动作 | 未跑 `sync-main.sh`、未 `launchctl kickstart`、未重装 plist、未改 `close` 旗标（spec 非目标）。规范主检出同步前，运行面仍是旧码 —— 这条留给 principal，且 `DEBT-DASHBOARD-STALE-CHECKOUT-FALSE-GREEN` 的 A/B/C 菜单仍未选 |

## rollback

`git revert 2e26f8441` 退 gitlink 与台账；子模块侧 revert omo#258 即恢复原 `Path(dict)` 抛错行为。
无数据写入、无 schema 迁移、无对外接口变更，回滚即恢复原语义（含原停摆行为）。注意 gitlink revert
会连带把 `00b809d`（另一 agent 已合入 omo main 的 close 旗标修复）一起退回 —— 回滚前先看这条。

## §14.2 运行记录

```json
[
  {
    "run": "live-canary-refresh-outputs",
    "inputs": ["projects/omo/src/omo/omo_debt.py::refresh_outputs",
               "projects/omo/src/omo/omo_debt_metrics.py::_resolve_ref_path",
               "/tmp/canary350.py",
               "tempfile:.omo/_truth/registry/debt.yaml",
               "tempfile:.omo/debt/items/BAD-REFS.yaml",
               "tempfile:.omo/debt/items/GOOD-REFS.yaml"],
    "basis": "spec §目标 1-3（不抛、判 stale、其余不受影响）+ done_when[0][1]；台账 circuit_breaker「禁止用静默跳过换平面存活」",
    "approver": "principal（2026-11-23「我给你充分授权，全面推进吧，完成剩余所有任务」；spec frontmatter `accepted` 同记）",
    "result": "rc=0；resolver(dict)=None；generated_at=本次 now；5 投影面 8 文件写出；backlog_pressure 1.5；BAD-REFS/GOOD-REFS 均在队列可见",
    "duration_ms": null,
    "model_usage": "none（纯脚本调用，无模型参与判定）"
  },
  {
    "run": "controlled-tests-and-gates",
    "inputs": ["projects/omo/tests/unit/test_omo_debt_malformed_refs.py",
               "projects/omo/tests/unit/test_omo_debt_naive_timestamps.py",
               "projects/omo/tests/unit/test_omo_debt_metrics_terminal_vocab.py",
               "docs/plans/3y-bet-ledger.yaml",
               "docs/superpowers/specs/2026-11-23-omo-debt-malformed-ref-plane-freeze-bet-t10-350.md"],
    "basis": "台账 verify[0]/[1]/[2] 三条命令原文；AGENTS §8（Python 改动 → targeted pytest）",
    "approver": "principal（同上）",
    "result": "4 passed → 合并前；收口复测 10 passed in 0.61s；governance-release-gate rc=0；gac-local-gate PASS 76 checks / 1 SOFT WARN；未修树变异复现生产 TypeError",
    "duration_ms": 5887,
    "model_usage": "qoder-cn agent session，无独立子调用计量"
  }
]
```
