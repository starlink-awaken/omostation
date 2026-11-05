---
type: report
status: completed
owner: governance-team
last-reviewed: 2026-11-05
bet_id: BET-Y2Q4-T10-278
title: 双根决策入口对齐验证收尾
---

# 双根决策入口对齐验证收尾

状态：本 BET 的规范四条必须满足项已在 `origin/main` 上成立，本记录为验收与簿记收尾。该文档记录非生产
文档变更，不声明多机 writer、运行健康或生产迁移已完成。

## 变更与依据

- `AGENTS.md` 按完整文件名区分同编号决策，并将开发/运行根决策状态更新为当前 `ACCEPTED`。
  实测位：`origin/main:AGENTS.md:45-48`（两份 `id: ADR-0456` 文件的消歧）与 `:59`（Key SSOT Registries 行）。
  引入提交 `ec2f14252`（2026-09-30，T10-216 / ADR-0456 F2，PR #4586）——**早于本 BET 登记日（2026-10-31）**。
- `ARCHITECTURE.md` 指向现有根解析器与决策，区分活动账本解析和非权威快照，不以目录名判定权威。
  实测位：`origin/main:ARCHITECTURE.md:21`（`state_root()` / `event_ledger_path()`）、
  `:22`（`install_root()` + “Verify each service's effective code and dependencies separately”）、
  `:23`（活动库按相关进程环境的 `event_ledger_path()` 解析、按 provenance 区分快照、
  “A directory name alone does not establish authority”）。
  引入提交 `f8ac358f8db3ac7c0f4b9deb0a4b8657d85b59df`（2026-11-01，PR #4996，squash 合并）。
- 决策依据是 `.omo/_knowledge/decisions/0456-dev-runtime-profile-root.md` 的当前状态与 2026-10-29 addendum；
  历史验收与后续现场验证是不同证据。

## 本地验证与限制

三条 `verify` 判据在本轮收口工作树（base `48aec0086` = 当时的 `origin/main`）重跑，读数以定稿时的最终树为准：

| # | 判据 | 期望 | 实测 |
|---|------|------|------|
| 1 | `python3 bin/change-lane-check.py --file AGENTS.md --file ARCHITECTURE.md --json` | exit 0，两文件均 docs lane | `LANE_RC=0`，`{"ok": true, "by_lane": {"docs": ["AGENTS.md", "ARCHITECTURE.md"]}, "files": 2}` |
| 2 | `git diff --check` | exit 0 | 见下「定稿复核」 |
| 3 | `make gac-local-gate` | exit 0；任何环境或预存失败单独记录 | 见下「定稿复核」 |

原生 `verify --from-diff --execute` 曾在禁网络、隔离状态的环境中执行，选中五项检查返回 0；全量本地治理门禁
在隔离状态与受控依赖下返回 0，包含软告警，KOS 协议及部分不可用检查跳过。检查不验证生产运行状态。

限制：`change-lane-check` 的 CI 侧接线存在已登记的装置缺口（`bin/change-lane-check.py` 的 `PUSH_RANGE`
在 `.githooks/` 未被赋值；CI 以缺省 `--scope staged` 运行，干净检出无 staged 文件 ⇒ `PASS (0 files, lanes=-)`），
所以判据 1 的效力来自本地显式 `--file` 调用，不来自 CI。缺口记录在
`.omo/_knowledge/decisions/0456-dev-runtime-profile-root.md` 的 2026-10-29 addendum，属另一授权面。

## 定稿复核

在同一收口工作树（`ws-t278-closeout`，base `48aec0086`）对**含本次定稿的最终树**复跑三条判据
（2026-11-05，staged 后执行，退出码显式打印，不经过管道）：

| # | 判据 | 实测 |
|---|------|------|
| 1 | `change-lane-check.py --file AGENTS.md --file ARCHITECTURE.md --json` | `LANE_RC=0` · `ok: true` · `lanes: ["docs"]` · `by_lane.docs: ["AGENTS.md", "ARCHITECTURE.md"]` · `files: 2` |
| 2 | `git diff --check` | `WHITESPACE_RC=0`（零输出） |
| 3 | `make gac-local-gate` | `GATE_RC=0` · `GaC local gate: PASS (70 checks executed, 2 SOFT WARN)` · 另 6 项已知不可用检查被跳过（`--strict` 才计入） |

两条 SOFT WARN 均与本 diff 无关，逐项点名：`test-mcp-kos`（KOS 数据库
`data/kos/kos-index.sqlite` 是运行态产物、不在 git，协议检查以 exit 78 **跳过而非通过**）；
`current-state-coherence`（缺输入 `.omo/state/system.yaml` —— 该文件已于 BET-Y2Q4-T10-235 摘库，
干净检出里缺席是常态而不是回归）。

`change-lane-check` 的 `staged: false` 字段说明本轮是按显式 `--file` 断言两文件的 lane 归属，
而不是依赖 git 状态推断 —— 与上面「限制」段的 CI 接线缺口一致。

## 未闭环项

本 BET 不覆盖、也不得据其推断的边界：

- 多机实际 writer、首项服务迁移的排程与消费者仍待独立确认（属 ADR-0456 B4b 运行腿）。
- 「入口改到安装位」不等于「码面改到安装位」：逐服务的 effective code/dependency 实测由 `e6_kernel_pin`
  承重，本 BET 只做文档入口对齐。
- 台账 `status: done` 与三轴 `completion_evidence` 的写入在下一次 ledger 窗口与本报告的合并 SHA 一起入账
  （该窗口由并发 agent 的活锁决定，不在本轮抢占）。
