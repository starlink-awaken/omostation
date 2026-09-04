---
lifecycle: history
owner: governance-team
last_updated: 2026-08-18
title: BET-Y1Q3-T8-02 复盘
type: retro
---
# BET-Y1Q3-T8-02 复盘

## Q1 实际耗时 vs appetite？超出比例？
单 session 完成两个缺陷修复 + 测试（约 1 小时 vs appetite 1 天），未超出。
主要耗时在理解 cockpit CLI 命令分发结构（dispatch Namespace 构造）+ PASW 子模块提交流程。

## Q2 done_when 是否全部通过？哪条没过，为什么？
| done_when | 状态 |
|---|---|
| cockpit events-watch 无参运行不再报 AttributeError | ✅ dispatch Namespace 补 `url` 属性 (默认 SSE URL), 实测无参运行 rc=0 (连接 SSE 流, 无 AttributeError) |
| cockpit audit 无参运行不再报路径错误 | ✅ `WORKSPACE_AUDIT` 从 `bin/workspace-audit` 改到 `bin/ssot/workspace-audit` (实际路径), 实测正常跑维度 |
| 两个修复均有单元测试或集成测试覆盖 | ✅ `test_t8_02_cli_fixes.py` 4 个测试 (Namespace url 属性/默认 URL/路径解析/缺失提示), 1071 cockpit tests 全绿 |

未过: 无。

## Q3 过程中发现的与 plan 不符的事实（打假）
1. **events-watch 的 AttributeError 根因**: L761 dispatch lambda 构造 `Namespace(watch=True, limit=..., topic=None)` 缺 `url` 属性 → `_c_events(a)` 调 `run_events_dashboard(a.url)` 报 AttributeError。修法是在 Namespace 补 `url=getattr(a, "url", <默认SSE>)`。
2. **audit 路径硬编码**: `WORKSPACE_AUDIT = WORKSPACE_ROOT / "bin" / "workspace-audit"` — 实际脚本在 `bin/ssot/workspace-audit`。主仓 `bin/workspace-audit` 不存在 (已迁移到 bin/ssot/)。修法改路径 + 更新错误提示。
3. **affected-hash 强制检查 (并发 agent #1238 引入)**: 本 bet claim 时报 "Missing or invalid affected-hash. You must run affected-graph.py first." — 这是 `0deecdd4 feat(omo): enforce affected-hash requirement` 新增的必填参数, 但无生成方式说明。解法: `python3 bin/gac/affected-graph.py --changed-projects cockpit --json | shasum` 生成 hash 传 `--affected-hash`。
4. **run-all.sh 环境性**: cockpit 全量 1071 tests 全绿, 根仓 run-all 的 kairon/gbrain/runtime-e2e 失败是环境性 pre-existing。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）
本 bet 净增（cockpit 子模块 commit f044d30）:
- `src/cockpit/cli.py` +4 行: events-watch dispatch Namespace 补 url 属性
- `src/cockpit/commands/audit.py` -2/+2 行: WORKSPACE_AUDIT 路径 bin/workspace-audit → bin/ssot/workspace-audit + 提示更新
- 新测试 `src/cockpit/tests/test_t8_02_cli_fixes.py` (4 个)

无新增 GaC 规则 / ADR / bin 脚本。净增 ~70 行 (测试为主)。

## Q5 下一个认领本 track 的 agent 需要知道什么？
1. **affected-hash 必填**: claim 命令现要求 `--affected-hash` (并发 agent 0deecdd4 引入), 生成方式 = `python3 bin/gac/affected-graph.py --changed-projects <proj> --json | shasum | cut -d' ' -f1`。
2. **PASW 子模块提交流程**: `projects/cockpit` (detached) 提交 → `.subtrees/cockpit` checkout 到新 commit + branch -f agent 分支 → push --force → bump-pointer。
3. **cockpit 命令注册模式**: 子命令 dispatch 在 `cli.py` 的 dispatch map, 构造 Namespace 时须包含命令实现访问的所有属性 (如 `_c_events` 访问 `a.url`), 否则 AttributeError。
4. **workspace-audit 位置**: 主仓 `bin/ssot/workspace-audit` (不在 bin/ 根)。
5. **待办**: events-watch 当前连接 SSE 流显示事件表; "重构为 events 子命令" 属体验优化 (non_goals 明确排除), 留后续。
