---
schema: md/v1
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-25
type: ssot
schema_version: specification/v1
spec_version: 1.0.0
created: 2026-09-14
bet_id: BET-Y2Q1-T5-01
risk_level: L1
human_gate: true
value_indicator_policy: false
---


# T5-01 个人战略决策沙盘（Strategy Sandbox）设计

## 1. 目标

针对重大技术选型、团队业务规划与资源投入，提供多智能体蒙特卡洛
模拟沙盘：商业 / 研发 / 安全 / 财务 4 角对抗 Agent 并发推演 N 次
（默认 100 轮）不同场景博弈，输出收益期望、风险边界与敏感性因子。
落地 `cockpit strategy simulate --proposal <file>`（`--demo` 内置样例）。

## 2. In scope

1. `projects/agora/src/agora/orchestration/sandbox_sim.py`（新文件，
   纯标准库、零模型调用、确定性可复现）：
   - `extract_factors(proposal_text)`：规则信号词 → 4 角基础参数
     （期望收益 / 成本 / 风险 / 方差）。
   - `run_simulation(factors, rounds=100, seed=42)`：seeded RNG 蒙特卡洛，
     输出均值 / 标准差 / p5-p50-p95 分位 / 最坏情况止损线（p5 下界）/
     单因子扰动敏感性排序；附耗时计量。
   - 诚实失败：空提案文本 → `empty_proposal` 非零退出，不伪造分布。
2. `projects/cockpit/src/cockpit/commands/strategy.py`（新文件，命令面）：
   - `cockpit strategy simulate --proposal <file> [--rounds N] [--seed S]
     [--json] [--out report.md]`；`--demo` 内置样例提案。
   - 直接 import agora 核心（sys.path 回退）；agora 缺失 → 诚实报错。
   - 渲染报告：收益分布表（均值/p5/p50/p95）、最坏情况止损线、敏感性因子。
3. 注册：`_subcommands.py` 加 `strategy` 解析器（含 `simulate` 子动作），
   `cli.py` 加 `dispatch_strategy`。
4. 测试：核心确定性（同 seed 同分布）、分位键齐全、止损线语义
   （p5 ≤ p50）、空提案失败、CLI demo exit 0、缺文件 exit 1、
   100 轮耗时 < 30s（实测毫秒级）。

## 3. Out of scope

- 不调用 LLM / AetherForge（确定性规则 + RNG 足够首版；增强另起 bet）。
- 不做未经夏明星本人审阅的自动化投资或重大架构调整（只出报告）。
- 不持久化历史推演库（`--out` 落盘报告即交付面）。

## 4. 验收（对齐 ledger done_when）

1. 100 轮蒙特卡洛多 Agent 模拟推演在 30 秒内完成（实测断言）。
2. 自动输出决策收益分布图（分布表）、最坏情况止损线与敏感性因子分析报告。
3. `cockpit strategy simulate --proposal <file>` 可用；`--demo` exit 0。
