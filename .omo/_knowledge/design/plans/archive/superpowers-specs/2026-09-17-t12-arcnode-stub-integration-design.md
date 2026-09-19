---
schema_version: specification/v1
spec_version: 1.0.0
title: arcnode-* 外部依赖纳入主仓 (stub 占位集成)
bet_id: BET-Y1Q4-T12
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-17
last-reviewed: 2026-09-17
implementation_authorized: true
value_indicator_policy: false
risk_level: L2
human_gate: false
---

# arcnode-* 外部依赖纳入主仓 — Stub 占位集成 (BET-Y1Q4-T12)

## 背景

`cockpit governance` 5 个子命令 (calibrate/rechain/evolve/drift-check/validate) 当前
依赖 `~/.hermes/scripts/arcnode-*` 外部脚本, 用户装上就报错 (T12 任务发现 4 个 arcnode
入口在系统中无源码).

## 调研结论

详见 `docs/reports/arcnode-integration-survey.md`:
- 调研搜索: `find / -name "arcnode-{calibrate,rechain,evolve,drift-check}*"`
- 结果: `~/.hermes/scripts/arcnode/` 目录只有 `schema.py`, 不含 4 个入口
- 主仓 `bin/ssot/arcnode-validate` 是唯一真实实现

## 决策

选项 A: 关闭 5 个子命令 — 否决 (用户失去入口)
选项 B: 创建 stub 占位 — 采纳 (4 个 stub + arcnode-validate 委派)

## 实施

主仓 `bin/arcnode/` 目录:
- `arcnode-calibrate` — no-op stub
- `arcnode-rechain` — no-op stub
- `arcnode-evolve` — no-op stub
- `arcnode-drift-check` — no-op stub
- `arcnode-validate` — 委派到 `bin/ssot/arcnode-validate` (真实实现)

`bin/arcnode/README.md` 文档化:
- 调用顺序: PATH → ~/.hermes/scripts/ → 主仓 bin/arcnode/
- 5 个 stub 行为 + 推荐替代
- cockpit governance fallback 链

## Acceptance

- 6 个 arcnode-* 脚本全部 exit=0 (graceful no-op)
- 不依赖 `~/.hermes/scripts/` 即可跑
- worktree 环境下 cockpit governance 6 全部 exit=0
- ops status 0 missing (跟 T16 防漂移双闸互补)

## 验证

```bash
$ for cmd in calibrate rechain evolve drift-check validate; do
    bin/arcnode/arcnode-$cmd
done
# 6/6 exit=0

$ python3 bin/ssot/check-doc-ssot-lint.py  # 0 冲突
```

## 关联

- T12 task: `.omo/tasks/planned/BET-Y1Q4-T12-arcnode-integration.yaml`
- T16 (ops drift guard): 防漂移双闸
- T14 (ops services cleanup): 修 19 条 stale signal
