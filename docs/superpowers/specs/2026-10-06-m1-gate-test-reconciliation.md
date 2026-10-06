---
schema_version: specification/v1
spec_version: 1.0.0
title: M1 gate-test reconciliation — register bin/ssot/test-mcp-kos.py as a claimed surface
bet_id: BET-Y2Q4-T10-231
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-10-06
---

# M1 Gate-Test Reconciliation (specification/v1)

承 `BET-Y2Q4-T3-04` 的 D3 偏差收口。背景与证据（2026-10-06 实测）：

- `bin/gac/gac-local-gate.py:53` 把 `bin/ssot/test-mcp-kos.py` 注册为 `test-mcp-kos`
  gate。该脚本原 `:135` 断言 DROP 拒绝文本含 `"prohibited"`；M1 修复后 handler 走
  默认拒绝的 SQLite authorizer，消息是 `not authorized`，旧断言会在任何存在
  `data/kos/` 的主机上把 gate 打红。
- M1 修改了 `bin/ssot/test-mcp-kos.py`（断言改为 isError + 非读载荷 + 拒绝词汇，
  并新增 `check_authorizer_default_deny()` —— 不需要 runtime DB、恒运行）。
- `BET-Y2Q4-T3-04` 的 `write_surfaces` 只含 `bin/gac/mcp-server-kos.py`，**不含**
  `bin/ssot/test-mcp-kos.py`；`agent-workflow claim` 实测拒绝
  （`WORK_PACKET_SCOPE_MISMATCH`）。
- human decision（2026-10-06）：不在 T3-04 的 spec 上加面（会破坏 accepted
  `content_digest` 的 sha256 绑定）；记 D3 偏差于 T3-04 复盘，另开本 BET 让
  `bin/ssot/test-mcp-kos.py` 获得正式写面，可 claim/verify/close。

## Scope

本 BET 的交付物已存在于父仓工作树（未 stage、修改自 M1/Task A）：
`bin/ssot/test-mcp-kos.py`（M1 断言 + default-deny 子测试）与
`bin/gac/mcp-server-kos.py`（default-deny authorizer + SQLITE_RECURSIVE 允许——后者
与 T3-04 共享该文件，本 BET 只在其上补写面登记与门禁验收，不重复实现）。
本 BET 的工作是：登记写面 → claim → 跑门禁验收 → 正式交付这两处父仓改动
（`bin/ssot/test-mcp-kos.py` 为 write 面；`bin/gac/mcp-server-kos.py` 因与
T3-04 共享，本 BET 记录为关联 read/output 面，实际改动与验收仍以 T3-04 为准）。

## Acceptance criteria

- `agent-workflow claim` 对 `bin/ssot/test-mcp-kos.py` 成功（携带 affected-graph
  receipt，project=workspace-root）。
- `python3 bin/ssot/test-mcp-kos.py`：default-deny authorizer 子测试恒 PASS；
  无 `data/kos/` 时其余协议检查 exit 78（软跳过，不算 PASS）。
- 存在 `data/kos/` 的主机上，`test-mcp-kos` gate 为 PASS（exit 0）：
  isError=True 且 DROP 拒绝、SELECT 正常、递归 CTE 允许。
- `bin/ssot/test-mcp-kos.py` 与 `bin/gac/mcp-server-kos.py` 通过 `ruff check`。
- `python3 bin/plan/bet-ledger.py lint` 保持 OK。
- T3-04 复盘已记录 D3 偏差并引用本 BET（已落盘，见
  `.omo/_knowledge/retros/BET-Y2Q4-T3-04.md`）。

## Non-goals

- 不修改 `BET-Y2Q4-T3-04` 的 spec / accepted_specifications（digest 绑定不可破坏）。
- 不修改 `.omo/tasks/active/BET-Y2Q4-T10-CJK-ROUTING.yaml`。
- 不使用任何 gate waiver。
- 不触碰 kairon 子模块（本 BET 全部为父仓 surface）。