---
schema: md/v1
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-27
type: ssot
last_updated: 2026-09-27
---


# 织星全景驾驶舱（Panorama Dashboard）

> 本文记录 Cockpit `/panorama` 的产品入口和数据新鲜度合同。Cockpit 是唯一人类工作台；Zhixing `:43191` 是投影和采集底座。

## 访问

```bash
open http://127.0.0.1:5173/panorama             # 本机开发预览
open http://127.0.0.1:8090/panorama             # 受管产品服务目标
open http://127.0.0.1:43910                     # 旧地址 → 302 → Cockpit-UI /panorama
```

> 2026-09-27 核验：`:43910` 由 `com.omostation.sunset-redirector`（KeepAlive）持有并 302 导流；
> 旧 serve job `com.omostation.panorama-dashboard` 已下线（BET-Y2Q2-T6-02）。
> `make panorama-serve` 会与导流器抢 `:43910`，前台调试请显式 `--port <空闲端口>`。

## 数据链路与新鲜度合同

```text
OMO / Runtime / Knowledge SSOT
        ↓ collector + bound revision manifest
Zhixing projection (:43191)
        ↓ server-side adapter; provenance + observed_at + facet completeness
Cockpit BFF (:8090/api/governance/panorama)
        ↓ one shared query/cache contract
Cockpit UI (/panorama)
```

- `bin/panorama/projection-full-refresh.py` 驱动来源绑定的全量 revision 发布。本机 LaunchAgent 配置为每 21,600 秒一次。
- `com.omostation.zhixing-projection-republisher` 每 480 秒重发布/续租 revision lease；它**不**采集新数据，不得改变 `observed_at` 或把旧快照标成 LIVE。
- `com.omostation.panorama-dashboard-refresh` 每 240 秒更新历史扁平消费者使用的 `runtime/dashboard/` 文件；这不是 43191 bound revision，也不能证明 Cockpit 投影新鲜。
- Cockpit 浏览器只读 `/api/governance/panorama`；前端不得直连 Zhixing 数据 API 或 SSE。
- freshness 由各 facet 的 `observed_at` 判定。来源缺失/时间无效/时间在未来/超过阈值/返回失败时显示 `UNKNOWN`、`STALE` 或 `PARTIAL`，不能以续租时间、空数组或 HTTP 200 伪造成功。

**当前限制（2026-10-07 10:14 UTC 现场复核）：** Zhixing `/health`、`/data.json` 与 Cockpit BFF 均返回 200；完整投影为 13,314,309 bytes，生成于 `2026-10-07T09:58:09Z`。投影续租后读取恢复，但数据年龄超过 Cockpit 的 5 分钟 freshness 阈值，BFF 正确返回 `data_state=STALE`，11 个门禁可见，不能据此声称数据实时或系统健康。此前 BFF 把来源的 `NOT_ADMITTED`、`ABSENT`、`PARTIAL` 状态整体判为 schema invalid；适配已修复并通过聚焦验证。8 分钟 republisher 只续租，不推进 `observed_at`；全量刷新与冷启动管理仍需单独验收。

## 七大板块

| 板块 | 内容 | 数据源 |
|---|---|---|
| 体系总览 | 5+4+1+1 层、OMO 单控制面、健康 KPI | bet-ledger + gates |
| 门禁 A1–A9 | 实时 verdict / exit / 依赖边界 | gate-health-check.py |
| Agent 全景 | worktree/分支/最近活动（全 agent 可见） | git worktree list |
| 任务与里程碑 | Y1Q1→Y3H2 窗口进度、in_progress/blocked | 3y-bet-ledger.yaml |
| 运行态 | meta-doctor 摘要、launchd/crontab、调度 | meta-doctor + launchctl |
| 治理 | 本文档 + 经验入口 | docs |
| 知识入口 | 白皮书/架构/流程卡片（存在性+直达） | 文档存在性探测 |

## 统一边界

- Cockpit `/panorama` 是**唯一人类主控总视窗**：汇集治理、运行、任务、场景和业务结果；具体动作由各 SSOT/服务授权执行。
- Zhixing `:43191` 是**只读投影与来源观测底座**：保留 revision、manifest、reference-cell 与来源证据；不再形成另一套人类导航/健康判断。
- Cockpit UI 不直写 ledger、claim、approval 或投影；所有写操作必须进入各自受授权的业务 API，并保留回执。
- 质量原则：`PARTIAL ≠ PASS`；来源不确定就展示不确定，并提供错误原因和证据下钻。
- 副作用自检：`python3 bin/panorama/panorama-collect.py --check-side-effects`

## 关联

- 规划：BET-Y1Q4-T10-163（驾驶舱）/ T10-164（A1-A9 receipt）/ T10-165（Role/Capsule 语义）/ T10-166（ASD 契约）
- 采集器：`bin/panorama/panorama-collect.py` · 服务：`bin/panorama/panorama-serve.py`
- 产物：`runtime/dashboard/`（gitignored，勿手编）
- 刷新：launchd `com.omostation.panorama-dashboard-refresh`（登记于 `.omo/cron/registry.yaml`，sfop_slot=S）
