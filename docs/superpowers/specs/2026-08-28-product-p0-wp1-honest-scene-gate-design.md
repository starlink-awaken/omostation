---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-28
last-reviewed: 2026-08-28
bet_id: BET-Y1Q3-T4-03
risk_level: L1
human_gate: false
type: ssot
last_updated: 2026-09-03
---

# Product P0 WP1 — Honest Scene Card Gate

## 1. 目标

让 `make scene-card-check` 的退出码如实反映聚合结果：任一 Scene Card validator 失败或任一卡片带 blocker 时必须返回非零；只有全部 ready 时才返回零。

本 WorkPacket 只修正聚合门语义，不修改任何 Scene Card 内容、approval state 或 blocker。

## 2. 当前反例

`Makefile::scene-card-check` 正确统计 `ready` 和 `blocked`，但最后一条命令是帮助文本 `echo`，因此即使 `blocked > 0` 整个 target 仍返回成功。单卡 validator 已有非零语义，缺口只在 Make 聚合层。

## 3. 设计

保留当前单次遍历和人类可读输出：

```text
scene-cards: ready=<n> with-blockers=<n>
```

在输出统计后，以 `test "$blocked" -eq 0` 作为 recipe 最后的权威命令。帮助文本可在此前输出，不得覆盖最终退出码。

测试必须从命令入口运行真实 Make target，而不只单测 Python validator。固定两个反例：

- 一张 ready、一张 blocked：输出 `ready=1 with-blockers=1`，退出非零。
- 所有卡片 ready：`with-blockers=0`，退出零。

## 4. 写面

- Root: `Makefile`
- Root test: `tests/test_scene_card_lifecycle_check.py`

不得修改 `docs/scene-cards/**`、`docs/journey-specs/**`、Scene Card 生命周期工具、approval 证据或运行态。

## 5. 验收

1. 新增聚合退出码 RED 测试，在当前实现上必须因 false-green 失败。
2. 修正后聚合退出码测试与已有单卡测试全绿。
3. 在当前存在 blockers 的真实仓库上，用包装命令证明 `make scene-card-check` 确实返回非零。
4. `git diff --name-only` 只包含两个授权写面。
5. 该 BET 的 engineering 轴可由测试、diff 和 merged mainline 证据推进；operational/value 仍为 `NOT_PROVEN`。

## 6. 验证命令

```bash
uv run --with pyyaml --with pytest python -m pytest tests/test_scene_card_lifecycle_check.py -q
bash -c 'if make scene-card-check; then echo unexpected-green; exit 1; else echo honest-block; fi'
git diff --name-only origin/main...HEAD
```

## 7. 回滚与停机

回滚只撤销 Make target 和对应测试的单一 child commit。如果修改导致“无卡片”或“全部 ready”仍非零，立即停机并修正聚合边界；不得用恢复无条件 `echo` 成功的方式回滚。

## 8. 价值政策

`value_indicator_policy=false`。这是工程真实性修正，不计个人价值。
