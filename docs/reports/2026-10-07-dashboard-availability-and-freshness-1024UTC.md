---
schema: md/v1
status: observed
lifecycle: evidence
owner: dashboard-convergence
generated-at: 2026-10-07T10:24:31Z
---

# Dashboard 可用性与新鲜度复核

本报告记录 2026-10-07 10:22–10:24 UTC 对 Cockpit、Zhixing 与 Vite 本机链路的现场验证。目的是区分页面可达、数据接口可达和分面可信度，不将 HTTP 200 解释为完整 LIVE。

## 执行和发布证据

从 Workspace 根运行：

```bash
/opt/homebrew/bin/python3 -B bin/panorama/projection-full-refresh.py
```

脚本使用专用发布检出 `/Users/xiamingxing/.local/opt/omostation-publisher`，没有 reset 或 clean 共享 Workspace。日志记录 checkout 同步至 `5dbe543a6038ab351bc8f96dfd9b1a91a9784e41`，并于 `2026-10-07T10:24:17Z` 发布 revision `8737ec59e3ce445f6055d6966fde3a9bf3daef53d01ac98e0a708e23048f7c02`。快照生成时间为 `2026-10-07T10:23:10.858018Z`。

## 运行验证

通过 Python `urllib.request.urlopen(..., timeout=15)` 读取以下地址，并解析 JSON 状态：

| 检查 | 结果 |
|---|---|
| `http://127.0.0.1:43191/` | HTTP 200，8,679,971 bytes |
| `http://127.0.0.1:43191/health` | HTTP 200，`projection_status=BOUND_FRESH`、`code_drift=false`、观察时间 `2026-10-07T10:24:31Z` |
| `http://127.0.0.1:43191/data.json` | HTTP 200，8,844,267 bytes，响应通过 JSON 解析 |
| `http://127.0.0.1:8090/api/health` | HTTP 200 |
| `http://127.0.0.1:8090/api/governance/panorama` | HTTP 200，11 gates，`data_state=PARTIAL` |
| `http://127.0.0.1:5173/api/governance/panorama` | HTTP 200，与 Cockpit BFF 相同的 revision 和状态 |
| `http://127.0.0.1:5173/panorama` | HTTP 200 |
| `http://127.0.0.1:8090/panorama` | HTTP 200 |

BFF 来源状态为 `PARTIAL`，错误为 `field_provenance_partial`，来源观察时间 `2026-10-07T10:23:10.858018Z`。本次复核时快照小于五分钟，但没有字段级来源证明的内容继续维持部分或未知；未把来源 lease 当成观测时间。

三个端口 `5173`、`8090`、`43191` 均绑定 `127.0.0.1`。Cockpit UI 与 BFF 是手工启动进程；本次没有证明产品服务的受管启动、冷启动恢复或崩溃自恢复。该运行复核不关闭 DCP-00、DCP-01、DCP-11，也不证明角色权限或真实业务闭环已验收。

## 验证命令

本次代码验证：

```bash
cd projects/cockpit-ui
pnpm exec vitest run src/api/hooks/__tests__/useGovernancePanorama.test.ts src/api/__tests__/client.test.ts
pnpm run build

cd ../cockpit
uv run --with pytest python -m pytest -q src/cockpit/tests/test_panorama_adapter.py
```

结果分别为 13 项 UI/API 测试通过、TypeScript 与 Vite production build 通过、14 项 BFF adapter 测试通过。以上结果针对当前工作树代码；生产 8090 的完整 code-identity 发布仍未验收。

## Lease-expiry follow-up（10:39 UTC）

复核发现全量刷新生成的 10 分钟 lease 在下一次 8 分钟 republisher 调度前可能过期。根因是旧 `RENEW_THRESHOLD=180s`：调度落在 lease 中段时会跳过，下一轮到达时 lease 已过期。已将阈值改为 540 秒，并加入测试：阈值必须大于 `.omo/_truth/registry/services.yaml` 中实际登记的 480 秒 interval，且小于 10 分钟 lease。

更新后运行：

```bash
launchctl kickstart gui/$(id -u)/com.omostation.zhixing-projection-republisher
/opt/homebrew/bin/python3 -B bin/panorama/projection-republisher.py --status
```

`--status` 报告 `fresh`、`seconds_left=568`；Zhixing `/health` HTTP 200、`BOUND_FRESH`、`code_drift=false`，lease 到 `10:48:39Z`；`/data.json` HTTP 200、8,844,267 bytes，可解析。Cockpit BFF 与 Vite 代理分别用时 3.919s 和 3.108s，均 HTTP 200、11 gates、`data_state=STALE`，来源时间仍为 `10:23:10.858018Z`。由此区分了 lease 可用性与数据新鲜度：续租故障已修，数据刷新节奏和字段级 provenance 仍未闭环。

根仓定向回归命令 `uv run --no-sync pytest -q tests/unit/test_projection_republisher_schedule.py tests/unit/test_compact_observation.py` 结果为 9 passed；`git diff --check` 通过。测试确认续租阈值至少为调度间隔加 60 秒裕量，并覆盖子进程忽略 SIGTERM 后被升级到 SIGKILL 的清理路径。compact-observation 超时进程组修复的原始证据存于 `.omo/evidence/compact-observation-timeout-process-tree-20261007T103127Z.json`。

## Compact observation 部署及 Cockpit 接线（10:50–11:00 UTC）

在 Workspace registry 新增 `omostation.panorama-compact-observation`，LaunchAgent label 为 `com.omostation.panorama-compact-observation`，每 240 秒调度一次，RunAtLoad；输出仍为 Cockpit adapter 默认读取的 `runtime/dashboard/compact-observation.json`。服务只采集 `knowledge_health`、`experience_graph`、`connectors`、`bos_verifier` 四个 facet，预算 240 秒、每项 timeout 45 秒。补充的 `--service-id` 只生成、检查或验证指定注册项，避免在有脏工作区时调用全量 plist 写入。

第一次 launchd 执行时 connectors 因 launchd 默认 PATH 不含 `iris` 可执行文件而返回 `collector_error`；last-good 内容与原成功时间未变。为这个服务声明包含 `/Users/xiamingxing/.local/bin` 的 PATH 并重载后，10:53:55 UTC 写入结果为四 facet `OBSERVED`，总耗时 14,733 ms；下一次周期在 10:58:09 UTC 再次四 facet 全部 `OBSERVED`，总耗时 13,956 ms，label 上次退出码为 0。上一轮失败期间 `connectors` 曾显示 `STALE`，没有冒充新鲜。注册生成器 scoped 回归覆盖了仅写目标 plist、保留无关 plist 和未知 service id 拒绝。`launchctl print` 显示 240 秒 interval；`--check --service-id` 无 drift，`plutil -lint` 成功。

Cockpit adapter 现已在 full projection 和 compact fallback 路径读取同一观测文件。通过 BFF 实测 `/api/governance/panorama` HTTP 200，顶层仍是 `STALE/projection_stale`（全量快照观察时间未变），四个直读 facet 的 `source.facet_observations.*.state` 为 `LIVE`，其他缺少直接证据的 facet 仍在 `partial_facets`。`5173` 代理保持同一数据路径。BFF 为应用新代码已用不包含凭据的最小环境重启；`8090` 仍是手工启动，未形成 launchd 冷启动和自恢复证据。

本轮验证：根仓 `uv run --no-sync pytest -q tests/test_gen_service_configs.py tests/unit/test_compact_observation.py` 为 25 passed；Cockpit `uv run --no-sync pytest -q src/cockpit/tests/test_panorama_adapter.py` 为 15 passed；Cockpit UI 两个聚焦 Vitest 文件 22 passed，`pnpm run build` 中 TypeScript 检查与 Vite 构建成功。四个连续调度周期均成功，故障后的全量刷新恢复也已在现场验证；性能样本和浏览器现场验收尚未完整，DCP-11/M1 继续开放。

## Code drift 现场恢复（11:02–11:04 UTC）

全量投影在复核期间转为 `CODE_DRIFT`：Zhixing `/health` 仍 HTTP 200，但报告 `code_drift=true`，`/data.json`、compact 和 brief 三个接口返回 HTTP 503 `projection_code_drift`；Cockpit 依约降级为 `UNKNOWN`。没有修改或重置共享 Workspace。通过既有 LaunchAgent `com.omostation.zhixing-projection-fullrefresh` 触发专用发布检出刷新：检出同步至 `bbcb4e2795dce3ec30eec76bc1250e15dc109f7d`，11:03:34Z 发布 revision `78bdc03102368f8d37d642ad1990a82c2dd109bd937dcd6fb307fddfe9f54efe`。随后 `/health` 为 `BOUND_FRESH`、`code_drift=false`；`/panorama`、BFF API 与 Vite 代理均 HTTP 200。BFF 当前为 `PARTIAL/field_provenance_partial`，四个 compact observation facet 均 `LIVE`，其它缺来源证明的 facets 保持 partial；未把接口恢复解释为整体 LIVE。

在 `11:02:23Z` 的第三个间隔周期，四 facet 再次全部 `OBSERVED`，总耗时 14,182 ms；第四次于 `11:06:36Z` 完成，耗时 12,661 ms，四 facet 仍全部 `OBSERVED`。launchd 状态为 `runs=4`、`last exit code=0`、`run interval=240 seconds`。UI 聚焦测试现为 22 tests 通过，生产 build 成功；前端 hook 会把缺失/未来 observation 降为 UNKNOWN、过期 LIVE 降为 STALE，页面显示每个直接观测 facet 的状态与观察年龄，同时保留整体投影状态条。

## Cockpit 受管启动及崩溃恢复（11:20–11:25 UTC）

将 `cockpit.dashboard` 注册项从 disabled 改为生成 LaunchAgent，label `com.cockpit.dashboard`，入口脚本 `bin/runtime/run-cockpit-dashboard.sh` 前台运行 uvicorn，端口 `127.0.0.1:8090`。脚本在测试端口 `18090` 启动成功；`/api/health` 与 `/panorama` 均 HTTP 200。单服务 plist 生成后，`plutil -lint`、服务声明 `--validate` 与目标 `--check --service-id cockpit.dashboard` 均通过。

受管服务首次加载后，`/api/health`、`/panorama` 和 `/api/governance/panorama` 返回 HTTP 200。用 SIGKILL 终止 LaunchAgent 跟踪的 uv 主进程后，`KeepAlive: crashed` 未恢复；按该证据改为 `KeepAlive: true`、`ThrottleInterval=10`，重新加载后再注入 SIGKILL，launchd 的 `runs` 从 1 增至 2，健康接口首次探测即 HTTP 200。最终监听进程由 launchd 拉起。Zhixing 43191 保持运行。

受管服务配置位于 `~/Library/LaunchAgents/com.cockpit.dashboard.plist`，由 Workspace 注册表生成。该检查证明 service bootstrap 与进程崩溃恢复；未执行 macOS 重启，故不证明系统冷启动恢复。服务从当前 dirty Workspace 启动，尚无 clean code-identity 发布证明；页面数据为 `PARTIAL/field_provenance_partial`，不能据 HTTP 200 宣称完整产品或白皮书功能验收完成。三主体 route/action/resource 授权、真实业务闭环、Zhixing 人类 root 迁移、性能样本仍未验收。

同一轮发现 Zhixing lease 有效而数据快照停在 `11:07:27Z`，BFF 因此标记 `STALE/projection_stale`。kickstart 既有全量 publisher 后，checkout 同步到 `f0b165d49524bd476f43a9d5c8d662bddd4aed5e`，`11:28:50Z` 发布 revision `b86d7c0becae39def6f6dd85d98ed402b4d950c2e360cb8fc6669115cbbd709d`；服务退出码 0，`/health` 回到 `BOUND_FRESH`、无代码漂移。随后 Cockpit BFF 刷新到同一 revision，HTTP 200、状态 `PARTIAL/field_provenance_partial`、四个直接观测 facet LIVE、七个 facet 保持 partial。Chrome 现场渲染 Panorama 成功且无 console/page errors。publisher 日志报告快照仍缺九项投影字段，数据链路尚未达到全量合同。

## 页面访问复测与刷新恢复（11:35–11:37 UTC）

用户再次报告站点无法打开后，现场复测 `http://127.0.0.1:5173/panorama`、`http://127.0.0.1:8090/panorama`、`http://127.0.0.1:43191/` 和 Zhixing `/health` 均 HTTP 200。5173 是开发预览；8090 是 Cockpit 产品入口；43191 提供 Zhixing 投影与诊断，root 首页仍可直接打开。

复测时 Zhixing `/health` 为 `BOUND_FRESH`，但 Cockpit BFF 返回 `STALE`，因为最新数据快照观察时间为 11:28:50Z，已超过 5 分钟 freshness 门槛。通过既有 `com.omostation.zhixing-projection-fullrefresh` LaunchAgent 触发一次全量发布；专用发布检出同步至 `1e05a57f149754dd973bf7d95daa2179fd500d0f`，11:36:37Z 发布 revision `94d796cd21dfe5a7eb437516f6649e99f18c6ea19cd61feacb98f485ae772725`。完成后 `/health` 仍为 `BOUND_FRESH`、无 code drift，Cockpit BFF 和 Vite 代理均 HTTP 200、`PARTIAL`；九项快照字段仍缺失，因此保留部分状态。

修正 Cockpit 服务管理入口：Makefile 的 start/stop/status 目标改用 LaunchAgent 管理脚本；合并 `services.yaml` 中重复的 `notes` 键。start 会先执行 `gen-service-configs.py --check --service-id cockpit.dashboard`，防止加载过期 plist。只执行了 status 检查，没有通过该管理命令停止或重启正在服务的进程。验证结果：脚本 `bash -n` 通过，服务配置 `--check --service-id cockpit.dashboard` 为零漂移、`--validate` 零违规，script registry 715 项有效，文档 SSOT lint 182 个文件零冲突，相关三个 pytest 文件共 31 项通过，`git diff --check` 通过。

页面访问恢复与正式治理准入分开记录：G0-BIND v0.6 独立复核仍为 REJECT，DCP-00/01 仍未取得 PASS 证据；这次运行恢复和显式用户操作授权不构成 G0 binding 或 clean code-identity 正式发布证明。三个服务仅监听 loopback，局域网访问不在当前配置范围内。

11:42 UTC 再测时三个页面仍 HTTP 200，但 Cockpit BFF 已回到 `STALE`；Zhixing `/health` 仍 `BOUND_FRESH` 且 revision 未变。其解释是完整刷新周期 6 小时，BFF 的快照 freshness 门槛为 5 分钟；上文手动全量刷新只把数据新鲜窗口恢复约 5 分钟。compact observation 每 240 秒更新四个直接 facet，却不会更新完整快照时间。页面路由可访问与完整数据持续新鲜是两项独立状态，刷新频率/数据合同缺口仍未解决。
