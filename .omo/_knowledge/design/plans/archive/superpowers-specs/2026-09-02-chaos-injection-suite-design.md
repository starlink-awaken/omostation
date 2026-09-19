---
schema_version: specification/v1
spec_version: 1.0.0
title: 混沌工程常态化注入套件与防腐护栏自动化巡检
bet_id: BET-Y1Q3-T10-120
status: accepted
lifecycle: contract
owner: ml-platform
created: 2026-09-02
last-reviewed: 2026-09-02
type: ssot
last_updated: 2026-09-03
---

# 混沌工程常态化注入套件与防腐护栏自动化巡检

## Intent

扩展现有 `bin/ssot/chaos-governance-drill.py` 6 项 governance 混沌演练,
新增 6 项生产故障注入场景 (12 项全覆盖), 并接入防腐护栏自动化巡检
(`make chaos-drill-full`), 验证系统 5 层并发锁 + GaC 门禁 + git guard
+
harness admission 的绝对韧性。

## Contract

- 6 项新增 drill 实现位置: `bin/ssot/chaos-governance-drill.py::run_drill_N_*`
- 自动化巡检接线: `Makefile::chaos-drill-full` (严格模式 + 全 12 项 + JSON 输出)
- 测试用例: `tests/chaos/test_chaos_injection_suite.py` (每项 drill 至少 1 个
  positive + 1 个 negative test)
- 验证报告: `docs/reports/2026-09-09-chaos-suite-validation.md`
- 复盘: `.omo/_knowledge/retros/BET-Y1Q3-T10-120.md`

## 12 项故障清单

| # | 场景 | Category | 注入方式 |
|---|------|----------|----------|
| 1 | Documents Plane Invasion Mutation | Plane Boundary | illegal script/dependency writes |
| 2 | Corrupted & Stale Fact Mutation | Facts SSOT | corrupted + 60-day stale mutations |
| 3 | Policy-as-Code Regulatory Red-Line Bypass | Domain Policy | health budget / transfer reward violation |
| 4 | Compute Fabric VRAM Shock & Thermal Chaos | Compute Fabric | VRAM compaction + thermal throttle |
| 5 | Intent Spec, Shadow Challenger & Broken Cartridge | Cognitive Mesh | intent grounding + red-team + cartridge |
| 6 | Merkle Ledger, Memory Distillation & Edge Roaming | Next-Gen OS | merkle tamper + distillation + roaming |
| **7** | **ThunderBolt 5 link disconnect** | **双机雷雳 5** | `iptables -A OUTPUT -p tcp --dport 9001 -j DROP` (受限环境用 timeout 模拟) |
| **8** | **Dirty worktree exploit** | **工作树** | `git status --porcelain` 注入 submodule pointer drift + staged untracked |
| **9** | **Zombie lock injection** | **并发锁** | 注入过期 lock.yaml (TTL 已过), 验证 stale-lock-cleanup 自动回收 |
| **10** | **Submodule pointer drift** | **子模块** | 改写 `.git/modules/*/HEAD` 与父 gitlink mismatch, 验证 git submodule sync 修复 |
| **11** | **Harness admission bypass attempt** | **harness** | 在 excluded_dirty_paths 之外注入关键文件 (bin/gac 目录), 验证 admission gate 拒入 |
| **12** | **Mass deletion guard test** | **git guard** | 模拟 `git rm -rf` 大面积删除, 验证 bulk-deletion-guard 拦截 |

## Non-goals

- 不在生产工作树中执行真实 `rm -rf` / `iptables` / `kill`
- 不注入会污染 git history 的不可逆操作 (所有 fixture 用临时 git worktree + 自动清理)
- 不动现有 6 项 drill

## Risks

- **R1 误伤其他 agent**: drill 在 `.tmp/chaos-fixture/` 子目录执行, 不碰主仓
- **R2 子模块污染**: drill 用独立 git worktree (基于 detached HEAD), 退出自动清理
- **R3 注入死锁**: circuit breaker: drill 失败超 60s 自动 abort + 清理

## Circuit Breaker

- 单个 drill 超 60s → 自动 abort 并标记 `timeout`
- 单个 drill 触发不可自愈错误 → 演练终止, 输出堆栈到 `runtime/chaos-drill-abort.log`

## Verify

- `make chaos-drill-full` 期望 exit 0 + 12/12 PASS
- `make gac-local-gate` 期望全绿 (drill 不破坏现有 GaC)
- `python3 -m pytest tests/chaos/test_chaos_injection_suite.py -v` 期望全过