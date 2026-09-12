---
status: active
lifecycle: entry
owner: auto-fix-loop
last-reviewed: 2026-09-12
---
# Retro — BET-Y1Q4-T7-05 业务场景五档生命周期自动巡航与金牌样例自学习闭环

- run: 20260912T113503Z-bet-execution-e24144d8
- date: 2026-09-12
- status: delivered (第一可交付 PR)

## 做了什么

- `projects/omo/src/omo/scene/golden_samples.py`：金牌样例库
 （digest 去重、calibration 排序检索、JSONL 落盘）。
- `projects/omo/src/omo/scene/cruiser.py`：`SceneLifecycleCruiser.observe`
  五档自动巡航（3-sample→shadow、30+0.6→assisted/supervised、
  calibration<0.5 熔断降级、routine 只报 needs_human 永不自动晋级）。
- `projects/cockpit/src/cockpit/handlers/scene_lifecycle.py`：
  生命周期分布 + 晋级缺口雷达纯函数聚合。
- `projects/omo/tests/unit/test_scene_lifecycle_cruiser.py`：15 用例全绿；
  scene/anchor 相关 41 用例无回归。

## 关键决策

- 阈值唯一 SSOT 为 `.omo/standards/scene-card-lifecycle.yaml`，
  代码内阈值常量注释指向该文件，不自立口径。
- 熔断只对 assisted+ 执行档生效：shadow 以下低校准只 hold 不降级
 （非执行档无自动执行风险，降级无意义）。
- supervised→routine 达到门也只返回 needs_human（ledger non_goals 硬边界）。

## 过程教训（可复用）

1. `agent-workflow start` 在 candidate 无 `accepted_specifications`
   时报 SPEC_BINDING_REQUIRED——先写
   `docs/superpowers/specs/<date>-<bet>-design.md` 再
   `bet-ledger.py spec-init <BET> --spec <path>`，一键解决。
2. `claim --path` 报 affected-hash 缺失时，先跑
   `bin/gac/affected-graph.py --changed-projects <...>` 拿 receipt；
   根目录 `.omo/**` 路径需把 `workspace-root` 列入 changed-projects，
   否则 claim 逐条通过、retro 那条单独失败。
3. `gac-worktree.sh claim` 在子模块全量 init 阶段易超时：
   worktree 本体已建好时直接进 worktree 对所需子模块
   `git submodule update --init --no-fetch <path>` 即可继续。
4. `uv run` 在 worktree 根会新建 `.venv` 污染工作树——用完即删；
   子模块内有 pyproject 的目录下跑 `uv run pytest` 则无此问题。

## 残留风险

- Cockpit 侧只交付聚合函数，未接真实路由/看板（spec §3.3 明确范围）。
- 金牌样例与 Semantica 先例库的自动对齐（done_when 第一条后半段）
  留待 T6-26（Semantica 内核）落地后联调，本 bet 以 Store API 就绪为准。
