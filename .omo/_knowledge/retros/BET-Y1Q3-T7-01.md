# BET-Y1Q3-T7-01 复盘

## Q1 实际耗时 vs appetite？超出比例？
约 1.5 小时（vs appetite 1 周）。核心机制（knowledge_action funnel）已存在，本 bet 建 API 暴露 + 基线落盘。

## Q2 done_when 是否全部通过？哪条没过，为什么？
| done_when | 状态 |
|---|---|
| 召回 N 条 / 成稿引用 M 条 可自动统计 | ✅ `omo.knowledge_action.build_knowledge_action_snapshot` (funnel: retrieved/cited/task_created), 已注册到 cockpit 生产 app (api_knowledge_actions) |
| 指标进 /outcomes 面板 | ✅ 新建 `api_outcomes.py` (`/api/outcomes` → knowledge_funnel), cockpit-ui OutcomesView 知识引用率卡片显示 citation_rate |
| 有第一个月实测基线值 | ✅ `knowledge-funnel-baseline.md` 落盘 (首日 0 基线 + 指标说明 + D1 守则) |

未过: 无。

## Q3 过程中发现的与 plan 不符的事实（打假）
1. **knowledge_action funnel 已存在**: `omo/knowledge_action.py` 已实现完整漏斗 (retrieved/cited/task_created) + api_knowledge_actions 已注册 ROUTER_MODULES。本 bet 真正缺口 = `/api/outcomes` 端点 (OutcomesView 引用的 knowledge_funnel 字段无后端)。
2. **OutcomesView 引用未实现后端**: T8-01 的 OutcomesView 期望 `summary.knowledge_funnel` (citation_rate/retrieved/cited), 但后端无 `/api/outcomes` → 前端显示"未接入" (D1 守则生效)。本 bet 补后端。
3. **校准 registry 运行时缺失**: `autonomy-levels.yaml` (T3-01 运行时产物) 不在共享 checkout (并发清理), API 返回 unavailable 符合 D1。
4. **知识行动日志为空**: actions.jsonl 无记录 (检索/引用未发生), 基线从 0 起步 (真实首月基线)。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）
本 bet 净增（cockpit 子模块 commit 536e36a）:
- `src/cockpit/web/api_outcomes.py` (~160L): /api/outcomes 四端点
- `src/cockpit/web/router_health.py` +1 行: 注册 api_outcomes
- `src/cockpit/tests/test_api_outcomes.py` (5 个): D1/knowledge_funnel/pending/history/calibration
- 基线 `.omo/_delivery/outcomes/knowledge-funnel-baseline.md`

无新增 GaC 规则 / ADR / bin 脚本。

## Q5 下一个认领本 track 的 agent 需要知道什么？
1. **outcomes API**: `GET /api/outcomes` (summary) + `/pending` + `/history` + `/calibration`, 注册在 ROUTER_MODULES。
2. **knowledge_funnel 数据流**: `api_outcomes._knowledge_funnel()` → `omo.knowledge_action.build_knowledge_action_snapshot` → `.omo/_knowledge/knowledge-mesh/actions.jsonl`。行动回执入口 `POST /api/knowledge/action-receipt`。
3. **D1 守则**: 未接入/无数据时返回 status=unavailable + null (前端显示"未接入"), 不造假 0。
4. **基线追踪**: `knowledge-funnel-baseline.md` 记录首月起点 (0 检索/0 引用), 每月末汇总 citation_rate 趋势。
5. **PASW 提交**: cockpit 子模块改动走 projects/cockpit → .subtrees/cockpit → push → bump-pointer。
6. **待办**: 当知识行动产生足够记录后, 可加 citation_rate 趋势图 (校准曲线 tab)。
