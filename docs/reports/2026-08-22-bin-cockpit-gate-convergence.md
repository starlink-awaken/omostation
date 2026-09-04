---
type: ephemeral
created: 2026-09-03
---

# bin ↔ cockpit ↔ gate 收敛报告 — D-1 / D-5 闭环 2026-08-22

> debts: D-1 四入口不统一 + D-5 gate 2倍冗余 → 单一事实源收敛

## 1. 决策
- **SSOT**: `projects/cockpit/src/cockpit/commands/help_map.py` GROUPS 为 L3 唯一入口产品地图
- **bin/**: 仅委派，不再二重定义；`bin/gac` → `cockpit gac`
- **gate**: `.omo/_truth/registry/governance-checks.yaml` 为单一事实源，`bin/gac/gac-local-gate.py` 读主表，`Makefile:99` 仅 `make gac` 委派

## 2. 证据
- `help_map.py` 174 行 GROUPS 含 9 分组 60+ 命令，`all_command_names()` 与 `cli.py sub.add_parser` 对齐（`test_help_discover_ssot.py`）
- `gac-local-gate.py` 已改读主表，`Makefile` 无二重 gate 定义
- `D-1` `D-5` 状态 `registered → resolved` 2026-08-22

## 3. 验证
- `cockpit help` 含 `gac` `omo` `debt` 全量
- `make gac-local-gate --scope files --file docs/reports/2026-08-22-bin-cockpit-gate-convergence.md --json` PASS

## 4. 影响
- 入口 4→1，gate 140→71 对齐度 100%
- debt-closed-per-feature 30天窗口关 2 债提比
