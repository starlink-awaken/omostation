---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-05
last-reviewed: 2026-09-05
bet_id: BET-Y1Q4-T8-15
risk_level: L2
human_gate: false
value_indicator_policy: false
type: ssot
---

# T8-15 CLI 冷启动 Fast-path 直通分发与全域 Lazy Import 设计

## 1. 目标

使 cockpit 高频命令冷启动耗时压降至 <150ms：Fast-path 直通分发（跳过重型
导入链直达目标命令模块）、全域 Lazy Import（未触发的模块绝不被贪婪加载）、
Flags 层级继承最小化。

## 2. In scope

1. `projects/cockpit/src/cockpit/cli.py`：
   - 命令分发路径上的重型 import 延迟到 dispatch 之后（lazy dispatch）。
   - Fast-path：高频命令（help/status/telemetry 等零依赖命令）在 argparse
     构建前直通。
   - 保持既有行为契约（dry-run/json/trace_id）不变。
2. `projects/cockpit/tests/test_fast_path.py`（新文件）：
   - 冷启动基准（import 时间上限断言 + 直通路径断言）。
   - 懒加载验证：未触发命令的重型模块不在 `sys.modules`。

## 3. Out of scope

- 不改命令行为语义、不改输出格式契约。
- 不引入新依赖、不动其他 bet 的交付面。

## 4. 验收（对齐 ledger done_when）

1. 核心命令冷启动耗时优化 >50%（以 import + dispatch 到首输出计时）。
2. 未触发的模块绝不被贪婪加载（sys.modules 断言）。
3. `uv run --project projects/cockpit pytest projects/cockpit/tests/test_fast_path.py`
   exit 0。
