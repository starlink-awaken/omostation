---
schema_version: specification/v1
spec_version: 1.0.0
title: P0 core command group dry-run / JSON contract
bet_id: BET-Y1Q4-T8-13
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-05
last-reviewed: 2026-09-05
type: ssot
last_updated: 2026-09-05
---

# P0 core command group dry-run / JSON contract (T8-13)

## Intent

统一 9 个高频 P0 命令的参数面与机器可读输出：

`dashboard` · `quickstart` · `journey` · `capabilities` · `data` · `iterate` · `workflow` · `compass` · `brain`

每条命令必须支持：

1. **`--json` / `-o json`** — stdout 为可 `json.loads` 的结构化载荷，**零 ANSI**
2. **`--dry-run`** — 预检/不落盘（纯读命令可用 `--json` 代替，语义上不产生写入）
3. **格式一致性** — 与 `JSON_CAPABLE` / 全局 `--dry-run` 接线兼容

不改动非 P0 存量命令；PSC v1 已落地的实现以契约测试锁定，缺口以最小补丁补齐。

## Current facts

- 9 命令实现已在 tip 具备 dry-run / json 分支（PSC v1）
- 分测：`test_dashboard_modernized.py` · `test_modernized_p0_commands.py` · `test_modernized_p0_wave2.py`
- 缺统一入口：`tests/test_core_commands.py`（本 BET verify 目标）
- `commands/output_mode.py::JSON_CAPABLE` 已收录上述命令（含 data/workflow/compass/brain）

## Architecture

```
projects/cockpit/src/cockpit/commands/
├─ dashboard.py / quickstart.py / journey.py / capabilities.py
├─ data.py / iterate.py / workflow.py / compass.py / brain.py
└─ output_mode.py          # JSON_CAPABLE 声明面

projects/cockpit/tests/test_core_commands.py   # NEW: 9 命令统一契约
```

### 契约矩阵

| Command | Dry-run 语义 | JSON 最低断言 |
|---------|--------------|---------------|
| dashboard | 不启动服务；回报 port/url/ready | `dry_run=true` |
| quickstart | 只跑环境检查，不改文件/DB | list of check items |
| journey | 检查 specs/runner 就绪 | `dry_run=true`, `runner_exists` |
| capabilities | 摘要/过滤，无写入 | `total` + capabilities list；`--dry-run` → `dry_run=true` |
| data | 顶层摘要为纯读；`gc --dry-run` 不删 | `status=ok` 或 `dry_run=true` |
| iterate | 生成任务结构不落盘 | `dry_run=true`, `ok=true` |
| workflow | 空参引擎矩阵预检 | `status=ok`, `dry_run=true` |
| compass | 空参流水线规约预检 | `status=ok`, `pipeline`, `dry_run=true` |
| brain context | 记忆摘要预检 | `status=ok`, `dry_run=true` |

## Acceptance

- 9 命令均可通过 `cockpit <cmd> ... --dry-run --json`（或纯读 `--json`）产出可解析 JSON
- `uv run --project projects/cockpit pytest projects/cockpit/tests/test_core_commands.py` exit 0
- 不修改非 P0 命令行为

## Non-goals

- 不改动非 P0 存量命令
- 不强制重写已通过的 modernized 分测（可并存；本文件为 canonical verify 面）
- 不引入第二套输出协议
