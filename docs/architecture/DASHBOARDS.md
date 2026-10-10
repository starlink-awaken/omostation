---
schema: md/v1
status: active
lifecycle: ssot
owner: dashboard-convergence
last-reviewed: 2026-10-07
type: ssot
---

# 织星统一 Dashboard 平台职责边界

本文是 Dashboard 入口、数据与职责边界的 SSOT。平台只保留一套用户体验和一份治理投影合同；各服务按职责分层，不能各自维护一套“实时”状态。

## 1. 统一平台边界

| 层 | 唯一职责 | 当前实现与地址 | 用户入口 |
|---|---|---|---|
| Cockpit UI | 管理员、Agent、业务人员共享的产品壳、导航、场景工作台和全景视图 | `projects/cockpit-ui`；开发端口 `127.0.0.1:5173`；受管服务目标 `127.0.0.1:8090` | 唯一人类入口：`/panorama`，由已接受的 BET-Y2Q2-T10-166 SSOT 规范确立 |
| Cockpit BFF | 只读聚合与归一化；验证来源、快照时间、分面完整性和失败状态 | `projects/cockpit`；API `/api/governance/panorama` | UI 唯一治理数据查询面；UI 不直连 Zhixing 投影 API 或 SSE |
| Zhixing 投影 | 收集并发布来源绑定的运行/治理快照，保留 producer provenance；为 Cockpit BFF 提供数据 | `~/.local/share/zhixing-dashboard/`；当前本机 `127.0.0.1:43191` | 数据与维护底座，不作为第二套人类工作台；根页面仅作兼容和诊断，逐步收敛 |
| OMO / Runtime / Knowledge | BET、Run、Claim、门禁、事件、回执和知识的权威写入与留证 | Workspace SSOT 与各自服务 | Dashboard 只读聚合这些权威，不复制或改写真相 |
| 旧 Panorama 入口 | 旧地址兼容导流 | `127.0.0.1:43910` sunset redirector | 只允许导向 `/panorama`，不再维护第二份 UI |

`Cockpit UI` 是统一产品体验，`Zhixing` 是主要投影与数据 substrate；这让用户入口和底层采集各自只有一个职责。Zhixing 首页、Cockpit 的局部治理工作台和历史 Panorama 页面不能分别展示互相矛盾的健康结论。

## 2. 状态和真相所有权

| 内容 | 权威来源 | Dashboard 展示规则 |
|---|---|---|
| BET、Task、Run、Claim、审批、回执 | OMO ledger / Workflow Mesh | 显示稳定 ID、生命周期、owner、证据链接；未知不默认为通过 |
| 投影生成、来源观测、producer 身份 | Zhixing bound revision manifest 与各 facet 的 provenance | 显示 revision、来源、observed/generated 时间和年龄；续租不能刷新观测时间 |
| UI 可见健康、门禁、告警 | Cockpit BFF `/api/governance/panorama` | 每个 facet 使用 `LIVE/PARTIAL/STALE/UNKNOWN`；缺少来源证据的字段保持 `UNKNOWN` |
| 用户反馈与业务价值 | 经授权记录的 Episode / Outcome / Receipt | 只计真实采用、提交、派发、引用等消费证据；工程指标不能替代业务价值 |

浏览器只能请求 Cockpit BFF。Zhixing 的 `/data.json`、`/__panorama_data__`、`/agent-brief.json` 与事件流属于服务端数据通道，不得形成 Cockpit UI 的旁路缓存或第二真相源。

## 3. 本机入口与访问范围

```text
开发预览： http://127.0.0.1:5173/panorama
产品服务： http://127.0.0.1:8090/panorama
旧地址：   http://127.0.0.1:43910/  → 302 → Cockpit /panorama
```

上述 listener 当前绑定回环地址，只能从运行服务的这台 Mac 访问。面向局域网或远程设备的访问需要单独设计身份、TLS、网络暴露和审计，不能把 `127.0.0.1` 替换成 `0.0.0.0` 当作部署方案。

## 4. 当前运行差距（2026-10-07；最近复核 12:08 UTC）

- 产品入口 Cockpit `127.0.0.1:8090/panorama` 已由 `com.cockpit.dashboard` LaunchAgent 受管启动；脚本在独立端口启动通过，受管服务加载后 `/api/health`、`/panorama` 和全景 BFF API 均返回 HTTP 200。
- 本次按 `projection-full-refresh.py` 的专用发布检出流程执行全量采集，发布 revision `8737ec59e3ce445f6055d6966fde3a9bf3daef53d01ac98e0a708e23048f7c02`，快照生成时间 `2026-10-07T10:23:10.858018Z`。Zhixing `/`、`/health`、`/data.json`、Cockpit `/api/health`、Cockpit BFF、Vite 代理及两个 `/panorama` 页面均返回 HTTP 200；`/data.json` 为 8,844,267 bytes 且通过 JSON 解析，其中 Zhixing `/health` 报告 `BOUND_FRESH`、`code_drift=false`。
- 刷新后 10:24 UTC 的 Cockpit BFF 与 Vite 代理返回 11 个门禁，`data_state=PARTIAL`、`error=field_provenance_partial`。10:39 UTC 再探测时同一快照已超过 5 分钟，两个入口均如实返回 `STALE`、`projection_stale`；来源观察时间仍为 `10:23:10.858018Z`。
- 10:39 UTC 对齐 republisher 后，Zhixing `/health` 为 `BOUND_FRESH`、`code_drift=false`，`/data.json` HTTP 200、8,844,267 bytes 且可解析。服务租约恢复不刷新来源观察时间，Cockpit 因而继续标记 `STALE`。
- 全量投影每 21,600 秒刷新；8 分钟 republisher 只续 revision lease，不推进 snapshot 的 `observed_at`。这个节奏尚不能满足 Cockpit 对来源新鲜度的目标。
- 已新增 `com.omostation.panorama-compact-observation` LaunchAgent，每 240 秒运行一次，仅采集 `knowledge_health`、`experience_graph`、`connectors`、`bos_verifier`，使用独立进程超时、单飞锁和 last-good 文件。初次 launchd 运行因默认 PATH 不含用户安装的 `iris` 而将 connectors 标为 `STALE`；修正该服务 PATH 后，10:53:55 UTC 四个 facet 均为 `OBSERVED`，单次总耗时约 14.7 秒。
- Cockpit BFF 已在完整投影与 compact fallback 两条路径读取直接观测文件，并按各 facet 的 `observed_at` 单独计算 `LIVE/STALE`。11:04 UTC 实测 BFF 与 Vite 代理 HTTP 200、投影 `PARTIAL/field_provenance_partial`，四个直接观测 facet 均为 `LIVE`，其他缺少来源证据的 facet 仍列在 `partial_facets`。这不刷新或掩盖投影整体年龄。
- 修正 PATH 后的两次连续 launchd 周期分别在 `10:53:55Z` 与 `10:58:09Z` 完成，四个 facet 均为 `OBSERVED`，单次耗时分别 14,733 ms 与 13,956 ms；service label 退出码为 0，下一周期仍按 240 秒间隔排定。
- 第三次周期在 `11:02:23Z` 完成，四个 facet 均 `OBSERVED`，耗时 14,182 ms；三次连续调度均成功。期间 Zhixing 曾短暂进入 `CODE_DRIFT` 并令投影接口 503；通过既有专用发布检出触发一次全量刷新后，于 `11:03:34Z` 发布新 revision `78bdc03102368f8d37d642ad1990a82c2dd109bd937dcd6fb307fddfe9f54efe`，`/health` 恢复 `BOUND_FRESH`、`code_drift=false`。
- 第四次周期于 `11:06:36Z` 完成，耗时 12,661 ms，四 facet 继续全为 `OBSERVED`；11:07 UTC 在 8090 与 5173 再次实测 Panorama 页面和 BFF API 均 HTTP 200，BFF 为 `PARTIAL/field_provenance_partial`，四个直接观测 facet 均 `LIVE`。
- LaunchAgent 对 `uv` 主进程执行 SIGKILL 后，`KeepAlive: crashed` 没有重新拉起；已改为 `KeepAlive: true` 并设置 10 秒 throttle。第二次故障注入后，`runs` 从 1 增至 2，`/api/health` 首次探测即恢复 HTTP 200。运行态 `state=running`，没有执行操作系统重启，因此完整冷启动验收仍未完成。
- 11:29 UTC 通过专用全量发布服务刷新 Zhixing：发布 checkout 同步至 `f0b165d49524bd476f43a9d5c8d662bddd4aed5e`，新 revision `b86d7c0becae39def6f6dd85d98ed402b4d950c2e360cb8fc6669115cbbd709d`，`/health` 为 `BOUND_FRESH`。Cockpit BFF 与页面数据年龄回到新快照时间，但继续标记 `PARTIAL/field_provenance_partial`；四个直接观测 facet 为 LIVE，七个来源分面仍缺字段级 provenance。
- 11:35–11:37 UTC 用户再次报告页面打不开后复测：开发预览 `5173/panorama`、Cockpit `8090/panorama`、Zhixing `/` 与 `/health` 均 HTTP 200。发现 Zhixing lease 虽新鲜，完整快照的观察年龄已令 Cockpit BFF 正确转为 `STALE`；通过已有全量刷新 LaunchAgent 触发安全刷新，发布 revision `94d796cd21dfe5a7eb437516f6649e99f18c6ea19cd61feacb98f485ae772725`，采集检出 `1e05a57f149754dd973bf7d95daa2179fd500d0f`，完成后 BFF 恢复为 HTTP 200 `PARTIAL`。投影健康 `BOUND_FRESH`、`code_drift=false`；九项字段仍缺失，来源分面继续部分可证。
- 11:42 UTC 再复测三个人类页面仍 HTTP 200；Cockpit BFF 已再次进入 `STALE`。原因已证实为 full refresh 每 6 小时运行一次，而 BFF 对完整快照采用 5 分钟 freshness 门槛；手动恢复只能暂时重置快照年龄。compact observation 只更新四个直接来源分面，不刷新完整快照年龄。需要设计并验收增量快照/分面 freshness 合同，不能用不断手动 kickstart 伪装持续 LIVE。
- 12:08 UTC 用户再次反馈打不开后复核：`localhost:5173/panorama`、`localhost:8090/panorama`、`localhost:43191/` 与 `/health` 均可达；根因仍是全量快照 `generated_at=11:35:56Z` 超过 5 分钟门槛，尽管 Zhixing lease 保持新鲜。确认专用发布检出 `main` 干净后，触发既有 `com.omostation.zhixing-projection-fullrefresh`，于 `12:08:01Z` 发布 revision `c3ee3dd81d2d7cf496ee6e877f9a235f456136a0c6cac767cad5cb3ac3f78201`。复验 `/health` 为 `BOUND_FRESH`、`code_drift=false`，`/data.json` 与 Cockpit BFF 的观察时间均为 `12:08:01Z`；8090 与 5173 的页面及 BFF API 均 HTTP 200，BFF 恢复 `PARTIAL/field_provenance_partial`，四个已观测 facet 可独立验证，七个分面仍列为 partial。此次刷新恢复当前数据，不消除 6 小时刷新与 5 分钟门槛的持续性不匹配。
- 为避免旧管理命令误报或误杀 LaunchAgent，`make cockpit-dashboard-{start,stop,status}` 已改用统一 LaunchAgent 管理脚本；服务声明的重复 `notes` 键也已合并。当前运行态未被管理命令重启或停止。
- `5173`、`8090`、`43191` 均仅 loopback；5173 是手工开发预览，8090 是受管产品入口，43191 是投影和诊断底座但其 root 页面仍可直接浏览。Cockpit 代码身份尚未绑定到干净发布树；DCP-00/01、角色授权和旧入口退役门继续开放。

本次增加的现场运行证据和边界见 [2026-10-07 dashboard availability/freshness 复核](reports/2026-10-07-dashboard-availability-and-freshness-1024UTC.md)。后续调度周期、操作系统冷启动、完整 code-identity 发布、旧入口迁移和 p95 仍待验收；DCP-00/01/11、DCP-20/21 与 M1 均未关闭。

详见 [`docs/plans/2026-10-04-dashboard-platform-convergence-execution-plan.md`](plans/2026-10-04-dashboard-platform-convergence-execution-plan.md)、[本次运行复核](reports/2026-10-07-dashboard-availability-and-freshness-1024UTC.md) 与 `.omo/evidence/2026-10-07-dashboard-unified-diagnostics-0313.md`。本文件描述目标职责和当前限制，不代表 DCP-01 部署门通过。

## 5. 依据

- [`docs/superpowers/specs/2026-09-25-dashboard-ssot-documentation-convergence.md`](superpowers/specs/2026-09-25-dashboard-ssot-documentation-convergence.md)（accepted，BET-Y2Q2-T10-166）
- [`docs/PANORAMA-DASHBOARD.md`](PANORAMA-DASHBOARD.md)
- [`protocols/port-registry.yaml`](../protocols/port-registry.yaml)
- [统一平台收敛执行计划](plans/2026-10-04-dashboard-platform-convergence-execution-plan.md)
