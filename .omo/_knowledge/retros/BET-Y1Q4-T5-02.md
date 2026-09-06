---
schema: bet-retro/v1
bet_id: BET-Y1Q4-T5-02
status: closed
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-06
type: ephemeral
---

# BET-Y1Q4-T5-02 retro — B.D.S.K. 四角对抗审议融入 Cockpit

## What changed

- **`cockpit/commands/bdsk.py`**（新）：`evaluate_spec`（信号词规则推导
  四角 verdict + 五维风险雷达）+ `render_madr`（Markdown MADR 决策报告：
  背景/四角评语/雷达表/折中方案/决议建议）+ `--demo` 内置样例 +
  `--out` 报告落盘 + `--json` 机器可读。安全角一票否决语义（敏感/外发
  信号密集 → reject）。
- **cli.py**：dispatch_bdsk 加 evaluate 分支；**_subcommands.py**：既有
  bdsk 注册挂 evaluate 的 4 个 flags。
- 测试 6/6（四角+雷达结构、安全否决、MADR 结构、demo/spec-file JSON、
  缺参拒绝）+ spine 相关回归 10 个全过，ruff clean，端到端冒烟
  （demo 方案正确触发安全角 reject、MADR 落盘）。

## Q3 (打假)

- **写面修正第 8 次**（cli.py/_subcommands.py/ledger 均不在铸造写面）。
  根因再确认：cockpit CLI 的命令注册分散在 cli.py dispatch dict +
  _subcommands.py parser 两处，铸造者无法从单点预见全部触点。
- 既有 bdsk 注册是 positional `bdsk_subcmd`（debate|simulate），evaluate
  作为新 subcmd 值零 parser 冲突——首版重复 `add_parser("bdsk")` 触发
  conflicting subparser，撤块改为父 parser 挂 flags。
- 规则启发式评语的"对抗性"是模板级（信号词映射），非真对抗——
  真对抗依赖 bdsk_engine 的 BOS persona 路径（NOT_PROVEN fail-closed）。

## Q4 (遗留)

- 雷达评分为规则增量（0-5 整数），连续化/历史对比待后续。
- 自动触发门禁（高风险外发自动跑 evaluate 并阻塞）衔接 T4-06 网关。
