---
status: active
lifecycle: entry
owner: auto-fix-loop
last-reviewed: 2026-08-30
---
# BET-Y1Q3-T4-05 Retrospective — Product P0 WP2 Honest Agent Cell Effect Receipt

- date: 2026-08-30
- bet: BET-Y1Q3-T4-05 (T4-OUTCOME, human_gate, value_indicator_policy=false)
- status: engineering VERIFIED / operational PROVEN / value NOT_PROVEN → delivery_accepted

## 交付（实现早已在 main，本轮只欠收尾）

本 BET 的真实缺口不是代码，而是 **台账收尾**。开工前先跑 verify 才发现实现齐备：

| 项 | 状态 | 证据 |
|----|------|------|
| `executor.py` fixed-success 分支移除 | 已在 main | omo `204e51b` (PR #118, merged 2026-08-29T22:19:12Z) |
| 无 admitted context → `effect=not_executed` | 已在 main | `executor.py:45-50` |
| sandbox durable receipt | 已在 main | `sandbox_tool_runner.py` ToolInvocationRecorded |
| 重放幂等 | 已在 main | `_append` 同 `idempotency_key` 同 payload 复用 prior |
| digest conflict 拒绝 | 已在 main | `sandbox_tool_runner.py:219-220` |
| verify 27 passed | 通过 | 3 个测试文件全绿 |

主仓落地 commit：`c3f7cff179e46433f0fded42dd14337ae427fd84`（bump omo 指针含 `204e51b`）。

## 本轮新增：端到端 canary

`bin/ssot/agent-cell-effect-receipt-canary.py` 六步验证，报告
`docs/reports/2026-08-30-agent-cell-effect-receipt-canary.json`：

1. `no_context_zero_effect` — 预置 target/provider/tool/ledger 哨兵，执行前
   后做**全量文件树 sha256 快照**对比，断言完全一致
2. `admitted_context_receipt` — 产生 `sandbox-invocation:<digest>` durable receipt
3. `replay_idempotent` — 相同 identity 重放，`invocation_count` 恒为 1
4. `digest_conflict_rejected` — 同 step 换 target →
   `sandbox invocation replay changed its request`，仍只有 1 个 receipt
5. `local_backend_read_only` — local 只放行只读，effectful 一律 `not_executed`
6. `cleanup` — 临时 workspace 回收

## 陷阱

1. **先跑 verify 再动手**：T4-04/T4-05 连续两例「用户说推进」时交付物已在 main，
   真缺口是三轴矩阵 + attestation + retro。盲目开工等于重写已有代码。
2. **`merged_reachable_commit` 必须是主仓 bump commit**：lint 用
   `git -C <workspace> cat-file -e` 校验，子仓 commit 在主仓对象库根本不存在
   （`fatal: Not a valid object name`）。要沿 `git log -- projects/omo` 找
   gitlink 是目标 commit 后代的主仓 commit。
3. **bin-quota 只管 `bin/*.py`**：pathspec 的 `*` 不跨目录，`bin/ssot/` 下新增
   脚本不触发守恒。但 `script_baseline` 会算，须同步 536 → 537。
4. **python3=3.9 无 `datetime.UTC`**：为隔离环境手动限制 `PATH=/usr/bin:/bin`
   会拿到 Xcode 的 3.9，canary 直接 ImportError。用绝对路径 `/opt/homebrew/bin/python3`。
5. **grep 被 alias 成 rg**：`grep -E "passed|failed"` 报 `unknown encoding`。
   用 Grep 工具或 `tail` + 管道过滤。

## value 轴

保持 `NOT_PROVEN`（policy=false → `delivery_accepted` 路径）。本 BET 不主张个人价值，
只证明效果层不再伪造成功。
