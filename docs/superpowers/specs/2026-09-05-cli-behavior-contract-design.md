---
schema_version: specification/v1
spec_version: 1.0.0
title: CLI behavior contract — ExitCode / ANSI purity / Trace-ID
bet_id: BET-Y1Q4-T8-12
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-05
last-reviewed: 2026-09-05
type: ssot
last_updated: 2026-09-05
---

# CLI behavior contract (T8-12)

## Intent

确立 Cockpit CLI 全局行为契约：

1. **ExitCode** 收敛为 `ExitCode` IntEnum（0..5）
2. **机器输出**（`--json` / `--output json` / 非 TTY）达到 **0 ANSI** 纯净度
3. **trace_id** 全链路贯穿（环境变量、日志配置、JSON 信封）

不改变底层业务执行结果；只规范出口码、渲染与追踪面。

## Current facts

- `projects/cockpit/src/cockpit/domain/exit_codes.py` 已定义 `ExitCode` IntEnum 0..5（含兼容别名）
- `projects/cockpit/src/cockpit/logger.py` 已有 `get_or_create_trace_id` / `configure_logging(..., trace_id=)`
- `cli.py` 模块级 `Console()` 未按 `--json`/非 TTY 关闭颜色；机器路径仍可能泄漏 ANSI
- 尚无统一 `output.py` 与 `tests/test_cli_contract.py`

## Architecture

```
cockpit/domain/exit_codes.py   # SSOT: ExitCode 0..5（复用，不复制）
cockpit/logger.py              # SSOT: COCKPIT_TRACE_ID + configure_logging
cockpit/output.py              # NEW: get_console / ansi_free_print / json envelope
cockpit/cli.py                 # Wire Console via output.py; inject trace_id into JSON errors
tests/test_cli_contract.py     # ExitCode · ANSI purity · trace_id envelope
```

### output.py 合同

- `get_console(*, force_json=False, stderr=False) -> Console`
  - `force_json=True` 或 `not sys.stdout.isatty()` → `no_color=True`, `force_terminal=False`
  - 否则保持 Rich 默认交互行为
- `ansi_free_print(text, *, file=None)` — 明文 print，不做 markup
- `json_print(payload: dict, *, include_trace_id=True)` — `json.dumps` 到 stdout；默认注入 `trace_id`

### cli.py 接线

- 模块级 `console` / `err` 经 `get_console()` 创建（TTY 感知）
- 进入 `--json` 路径后，将模块级 console 切换为无色 Console（或局部使用 `get_console(force_json=True)`）
- `configure_logging` 传入 `trace_id`（已有）；JSON 错误信封补齐 `trace_id`
- Exit 返回值统一经 `ExitCode`（已有）；不新增平行退出码枚举

## Acceptance

- `ExitCode.SUCCESS..UPSTREAM_ERROR` 分别为 0..5；兼容别名映射正确
- 任意 `--json` / `--output json` 路径的 **stdout** 不含 `\x1b` ANSI 转义
- `get_or_create_trace_id()` 非空；JSON 错误/信封含 `trace_id`；`configure_logging` 可固定注入
- `uv run --project projects/cockpit pytest projects/cockpit/tests/test_cli_contract.py` exit 0

## Non-goals

- 不改变底层业务命令的语义结果
- 不强制全量子命令立即改用 `output.py`（本 BET 收敛入口层与契约测试；逐步扩散为 follow-up）
- 不引入第二套 ExitCode / Trace 实现
