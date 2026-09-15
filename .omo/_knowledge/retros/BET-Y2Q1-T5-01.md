---
schema: bet-retro/v1
bet_id: BET-Y2Q1-T5-01
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-14
type: ssot
---

# BET-Y2Q1-T5-01 retro — 个人战略决策沙盘（第一批，最小闭环）

## What changed

- **`agora/orchestration/sandbox_sim.py`**（新，纯标准库零模型调用）：
  `extract_factors`（信号词规则 → gain/cost/risk/variance/schedule）
  + `run_simulation`（seeded RNG 蒙特卡洛：均值/标准差/p5-p50-p95/
  止损线=p5/4 角均值/单因子 +20% 敏感性排序/耗时计量）
  + `simulate_proposal`（空文本 `empty_proposal` 诚实失败）。
- **`cockpit/commands/strategy.py`**（新）：`strategy simulate
  --proposal <file> [--rounds N] [--seed S] [--json] [--out md]` +
  `--demo` 内置样例；直接 import agora 核心（缺失诚实报错）；
  报告含收益分布表/止损线/4 角均值/敏感性因子。
- **注册**：`_subcommands.py` 加 strategy parser（simulate 子动作），
  `cli.py` dispatch dict 加 `"strategy"`。
- **spec**：`docs/superpowers/specs/2026-09-14-t5-01-strategy-sandbox-design.md`
  + ledger `accepted_specifications` 恰 1 条 digest 回填；
  `write_surfaces` 补注册文件/测试/spec/ledger/retro（9 面）。
- 测试 10/10（agora 5：确定性/分位单调/止损语义/seed 差异/空提案失败；
  cockpit 5：demo/demo-JSON/文件+落盘/缺文件/缺参）；
  `strategy simulate --demo` exit 0（100 轮 0.001s）；
  conformance 21/21，voice_memo 3/3，bdsk demo 回归 exit 0。

## Q3 (打假)

- work packet scope = ledger `write_surfaces` 精确匹配：首版遗漏注册文件
  与测试导致 SCOPE_MISMATCH；补面后旧包 SOURCE_DRIFT，需 closeout 舊
  run（blocked/superseded）重开新 run 重新绑定——面变更必须发生在 start 前。
- root 级文件（ledger/spec/retro）claim 需 affected-graph 含
  `workspace-root`；默认只传子项目会报 missing。
- 子模块 worktree 默认未 init：cockpit/omo/ecos/cockpit-ui 逐个 init；
  ecos  онлайн clone 超时，改用 main 本地 clone `--reference` 秒级完成；
  ecos 路径下残留 `.omo/_derived` 空壳会阻塞 clone，需先清。
- `uv run` 跨子模块解析失败（family-hub/kairon 未 init）：单测改用系统
  python3 + PYTHONPATH；voice_memo 单测失败系缺 omo 路径（环境性，非回归）。

## Q4 (遗留)

- 推演为规则 + RNG（模板级对抗，非真 LLM 多智能体博弈）——LLM 增强另起 bet。
- 未持久化历史推演库（`--out` 落盘即交付面）；分布可视化为文本表，无图形。
- `make gac-local-gate` 全绿依赖 cockpit-ui submodule init（环境性）。
