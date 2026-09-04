---
lifecycle: history
owner: governance-team
last_updated: 2026-08-18
title: BET-Y1Q2-T9-02 复盘
type: retro
---
# BET-Y1Q2-T9-02 复盘

## Q1 实际耗时 vs appetite？超出比例？
单 session 完成 4/4 deliverable（约 1 天 vs appetite 1 周），未超出。
主要耗时在事件面架构理解（bus-foundation ↔ 事件面耦合方式）+ PASW 子模块提交流程。

## Q2 done_when 是否全部通过？哪条没过，为什么？
| done_when | 状态 |
|---|---|
| observability 栈决策: 修复 Langfuse (.env + up) 或退役 | ✅ 修复路径: 生成 .env (gitignored, 含随机 secret), `docker compose up`, langfuse 健康 (HTTP 200, v2.95.11), webhook-bridge 拉起 |
| agora /metrics 补 RED 指标 (QPS/延迟直方图/错误率) | ✅ 补 `bos_errors_total` Counter (按 prefix), record() 失败时递增; QPS=counter rate, 延迟=既有 histogram, 错误率=errors/calls |
| bus-foundation trace_id → 事件面导出 | ⚠️ 已交付+E2E 实测命中, 但合并前被 T6-01 (bus-foundation 全量退役 #1233) 取代 — 模块在 main 上已清空, 导出代码保留在子模块分支 agent/bet-y1q2-t9-02-bus-foundation; 建议后续把该能力直接并入事件面 (trace_id 字段已支持) |

| cockpit 可观测页聚合统一事件面 | ✅ 后端 `/api/observability/events` + `/api/observability/stats` 读事件面; 实测对真实事件面返回 (含 bus_trace 贯穿记录) |

未过: 无。前端 (cockpit-ui) 切换页面数据源在 write_surfaces 之外，作为后续项记录。

## Q3 过程中发现的与 plan 不符的事实（打假）
1. **台账 verify 格式 bug**: BET-Y1Q2-T9-01/T9-02 的 `verify:` 是字符串列表，而 `bet-ledger.py verify` 要求 `{cmd, expect}` dict → 工具 AttributeError 崩溃。已最小机械修复两个 bet 的 verify 格式（同命令 + expect: exit 0）。lint 25 个问题是存量（T6-04 等 done_when 未加引号冒号），非本 bet 引入。
2. **bos_quota 曾疑似误用模块级指标**: 初看 class 方法 `return _get_prom_metrics()` 以为委托 bos_metrics 模块函数，实际是 Python 名字遮蔽调用了 bos_quota 自己的模块级函数（已有正确的 quota Counter/Gauge）。已回退误改，未造成变更。
3. **Langfuse db 密码失配**: 原 db 10 天前以随机密码初始化（无 .env），langfuse 空密码连接失败 P1000；且 db 仅 langfuse 使用无业务数据，重建 volume 解决。这是"声明 ≠ 事实"的实例：compose 配置存在但从未真正跑通。
4. **gate 前置 FAIL 为存量**: service-config-validate (omlx 'shell' interpreter) + ci-surfaces unregistered checks (debt-audit/state-goals 并发 workflow) 均与本 bet 无关，系共享环境存量问题。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）
```
adr_total     366 → 344     (+0 本 bet)
gac_rules     136 → 136     (+0)
gac_required   26 → 26      (+0)
bin_scripts   389 → 310     (+0 本 bet)
src_loc       +67,225 (观察量, 非本 bet 贡献)
test_loc      未下降 (+16,333)
```
本 bet 净增: agora +88 行 (RED 错误率+测试), bus-foundation +110 行 (事件面导出+测试),
cockpit +1 新文件 api_observability.py + 1 注册行 + 测试 (~150 行)。均为核心能力 (RED E 维/
trace 贯穿/统一查询面)，无新增规则/ADR/脚本。Langfuse 栈从"死配置"转为"可用服务" (ops 变更,
. env gitignored)。

## Q5 下一个认领本 track 的 agent 需要知道什么？
1. **事件面扩展模式**: 新数据源 = 在源侧写 jsonl (对齐 events.jsonl schema, sort_keys=True,
   fcntl 锁) + 事件面侧加 adapter 或直接由 cockpit 读。bus-foundation 出口 env:
   `BUS_FOUNDATION_EVENT_PLANE=<path>` (空=关闭)。
2. **PASW 提交流程**: 子模块编辑在 `projects/<sub>` (detached) 提交 → `.subtrees/<sub>` FF 分支
   → push 分支 → `gac-worktree.sh bump-pointer`。bump-pointer 若读到旧 SHA, 先 push 分支再重跑。
3. **cockpit 可观测页前端切换**: `/api/observability/events` 已就绪; ObservabilityView.tsx /
   AlertCenterPage.tsx 数据源切换在 cockpit-ui (write_surfaces 之外), 需扩写面或另开 bet。
4. **T9-01 待办**: 告警到人需真实 webhook URL (`ALERT_<PROVIDER>_WEBHOOK` env), 配后转 done;
   done_when "5 分钟内可达" 需真实 channel 验证。
5. **Langfuse 现已可用**: http://localhost:3050, .env 在 projects/observability/.env (gitignored)。
