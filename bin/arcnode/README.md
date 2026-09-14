# bin/arcnode/ — arcnode-* Stub 占位实现 (BET-Y1Q4-T12)

> **状态**: placeholder
> **关联 BET**: BET-Y1Q4-T12 (调研结论 → done, 源头缺失)

## 背景

`cockpit governance` 5 个子命令 (calibrate / rechain / evolve / drift-check / validate)
原本委派给 `~/.hermes/scripts/arcnode-*` 外部脚本。

**调研结论** (详见 `docs/reports/arcnode-integration-survey.md`):

| 脚本 | 系统中源 |
|---|---|
| `arcnode-validate` | ✅ 存在 (`bin/ssot/arcnode-validate`) |
| `arcnode-calibrate` | ❌ 无源码 |
| `arcnode-rechain` | ❌ 无源码 |
| `arcnode-evolve` | ❌ 无源码 |
| `arcnode-drift-check` | ❌ 无源码 |

`~/.hermes/scripts/arcnode/` 目录只有 `schema.py`, 不包含上述 4 个入口脚本。

## 本目录内容

5 个 arcnode-* 占位脚本, 让 cockpit governance 6 个 arcnode-* 子命令立即可用 (exit=0),
不再依赖 `~/.hermes/scripts/`。

| 脚本 | 行为 | 推荐替代 |
|---|---|---|
| `arcnode-calibrate` | no-op | cockpit governance calibrate |
| `arcnode-rechain` | no-op | cockpit governance rechain (若需 chain 操作) |
| `arcnode-evolve` | no-op | cockpit governance evolution |
| `arcnode-drift-check` | no-op | cockpit governance drift-check |
| `arcnode-validate` | 委派给 `bin/ssot/arcnode-validate` | (原始实现) |

## 调用顺序 (cockpit governance fallback)

1. `PATH` (系统 PATH)
2. `~/.hermes/scripts/arcnode-*` (向后兼容)
3. **`主仓 bin/arcnode/`** ← 此目录 (新增, 批次 16)

## 退出码语义

- `0`: 成功 (含 no-op 占位)
- `1`: 参数错或外部依赖缺失

## BET-Y1Q4-T12 跟踪

本 BET 已转 done (无法实施真正集成, 因为 arcnode-calibrate/rechain/evolve/drift-check
在系统中无源码)。如未来找回源码, 可直接覆盖本目录的占位文件。
