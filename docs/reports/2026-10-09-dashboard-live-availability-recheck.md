---
schema: md/v1
status: observed
lifecycle: evidence
owner: dashboard-convergence
generated-at: 2026-10-08T23:22:06Z
---

# Dashboard 在线可用性复核

## 结论

Cockpit 统一入口可访问：`http://127.0.0.1:8090/panorama` 返回 HTTP 200。`http://localhost:5173/panorama` 和 `http://127.0.0.1:5173/panorama` 也返回 HTTP 200；5173 是 Vite 开发预览。Zhixing `http://127.0.0.1:43191/` 和 `/health` 返回 HTTP 200，但不能据此判定页面稳定可用或数据新鲜。

## 现场证据

- Zhixing `/health` 报告 `projection_status=BOUND_FRESH`、`code_drift=false`，代码 OID 为 `1da01d6a1e5378e14acf3b5ae7f30d2e0ea28414`；新鲜窗口截至 `2026-10-08T23:29:24Z`。
- Zhixing `/data.json`、`/agent-brief.json`、`/api/v1/value/metrics`、`/api/v1/agent/brief`、`/api/v1/agent/objective-coverage`、`/api/v1/agent/strategic-gaps` 和 `/api/snapshot` 的串行请求均返回 HTTP 200。
- 同一组七个接口由 30 个并发连接请求 50 次，只有 7 次成功；其余 43 次遭遇 `Connection reset by peer`。这复现了浏览器加载时的并发故障，说明服务监听正常，但请求并发期间不稳定。
- Zhixing 的 `/data.json` 与 Cockpit `/api/governance/panorama` 均显示快照生成时间为 `2026-10-08T23:19:24Z`；复核时间为 `23:22:06Z`，所以快照当时仍处于新鲜窗口。Cockpit Panorama 返回 HTTP 200、`data_state=PARTIAL`，表示来源完整度仍有缺口。

## 根因与修复候选

根因为每个请求都同步执行投影代码身份验证；并发页面/API 加载触发竞争，部分请求被服务端重置。当前活动服务从干净的 pinned runtime 运行；直接修改运行文件会造成代码身份与投影绑定漂移。

资产源 `bin/panorama/assets/host/live_server.py.asset` 已实现严格绑定的 single-flight 身份缓存：并发请求共享一次验证；等待者在复用成功或失败结果前重新核对受保护文件指纹。`tests/unit/test_live_server_projection_size.py` 覆盖 50 路成功与失败并发及缓存命中期间代码变化。

## 验证与发布状态

- 定向测试：7 passed。
- `py_compile` 与目标文件 `git diff --check`：通过。
- 独立代码审查：APPROVE，无 CRITICAL/HIGH 阻塞。
- 修复仍是未发布候选；当前 43191 仍运行旧 pinned runtime。本复核没有重启服务、修改 LaunchAgent 或发布投影。
- 当前发布路径仍受工作区门禁状态影响：`gac-local-gate` 报 `service-config-drift`，`ssot-guardian` 报 Kairon gitlink pointer drift。应先由各自 owner 解决并重新验证门禁，再部署此候选。

## 使用建议

日常访问使用 Cockpit `http://127.0.0.1:8090/panorama`。5173 仅用于前端开发预览。Zhixing 43191 当前可作为受限观测入口；其并发稳定性恢复之前，不应当作可靠的主入口。

## 23:33 UTC 复核补记

- 23:34 UTC 再次检查入口：Cockpit Panorama `127.0.0.1:8090/panorama`、Vite 预览 `localhost:5173/panorama` 与 `127.0.0.1:5173/panorama`、Zhixing `127.0.0.1:43191/` 和 `/health` 均返回 HTTP 200。
- 2026-10-08 23:32:54 UTC 实测 Zhixing `/health` 与 `/data.json` 均返回 HTTP 200。投影为 `BOUND_FRESH`，生成时间 `23:29:34Z`，新鲜窗口截至 `23:39:34Z`，`code_drift=false`；当前仍是运行中的旧 pinned runtime。
- DCP-20 GET 安全候选已加入固定只读路由、禁用操作拦截及静态 JS 文件白名单。静态 JS 现在要求 `O_NOFOLLOW`，从已打开的文件描述符校验普通文件、1 MiB 大小上限和读取前后元数据一致性；缺少 `O_NOFOLLOW` 的平台会关闭该资源服务。回归覆盖白名单、查询参数、符号链接和超限文件。
- 定向测试现为 14 passed；Python 编译和目标文件 `git diff --check` 通过。候选未部署、未重启；本补记也没有进行投影发布。
- 静态 JS 符号链接修复已获独立复核 `CLEAR / APPROVE`，未发现剩余阻塞。生产发布仍需遵守上文 G0/M0 门禁；此候选状态不代表门禁通过或产品目标完成。

## 23:40 UTC 运行时复核

- 23:40:13 UTC，Zhixing `/health` 与 `/data.json` 均 HTTP 200；投影 `BOUND_FRESH`，生成时间 `23:39:44Z`、有效期至 `23:49:44Z`、`code_drift=false`，代码 OID 仍为 `1da01d6a1e5378e14acf3b5ae7f30d2e0ea28414`。
- Cockpit `/api/health` 与 `/api/governance/panorama` 均 HTTP 200；Panorama 仍为 `PARTIAL`，列出 10 个不完整分面。传输与投影租约正常，不代表分面完整。
- launchd 当前任务仍运行旧的 180 秒 collector 命令；登记表要求 21,600 秒专用 refresh driver。该差异已独立追溯为真实运行配置与 SSOT 不一致；直接重写 plist 会改变刷新行为，且 6 小时投影与 Cockpit 现有 300 秒聚合新鲜度门槛冲突。暂不做单边配置改写，先收敛分面 freshness 合同。

## 00:42 UTC 浏览器可用性复核

- 本机 Cockpit `http://127.0.0.1:8090/panorama`、Vite 预览 `http://127.0.0.1:5173/panorama` 均返回 HTTP 200。使用隔离的真实浏览器会话打开 Cockpit 页面后，标题、导航、全景视图和主内容均已渲染；未观察到浏览器 Console 或页面异常。
- 当前 Cockpit BFF `/api/governance/panorama` 返回 `PARTIAL`，`generated_at=2026-10-09T00:41:17Z`、新鲜期截至 `00:51:17Z`，`partial_facets` 共 10 项；可见直接观察只有 `experience_graph` 和 `connectors` 为 LIVE，`knowledge_health`、`bos_verifier` 为 UNKNOWN。界面将 11 个门禁展示为 UNKNOWN，符合缺少字段级证明时的降级合同。该状态会让内容看起来空或异常，但页面本身没有白屏。
- Zhixing `http://127.0.0.1:43191/` 返回 HTTP 200 并成功渲染。`http://127.0.0.1:43191/panorama` 返回 HTTP 404；此服务没有 `/panorama` 路由，根页才是它的入口。浏览器 Console 出现 `live proposals` 和 `swarm topology` 两条 `Failed to fetch` 警告，需后续分别追查，不影响根页面载入。
- 当前统一人类入口仍为 Cockpit `http://127.0.0.1:8090/panorama`；5173 是开发预览，43191 是 Zhixing 观测页。实际服务与数据请求虽可达，Cockpit 的 PARTIAL 投影和 Zhixing 的两条请求警告仍需按产品数据合同继续处理。本轮未重启、发布代码或修改服务配置。

## 00:57 UTC 继续复核与准入进度

- Cockpit `:8090`、Vite `:5173` 与 Zhixing `:43191` 均仍在本机回环地址监听。Cockpit `/api/health` 为 HTTP 200（约 1–2 ms）；统一页面路由 `/panorama` 可渲染。`:43191/panorama` 仍不是有效路由，Zhixing 页面入口为 `/`。这些地址仅能从运行服务的本机访问。
- Cockpit 当前 `/api/governance/panorama` 为 HTTP 200、`data_state=PARTIAL`。来源快照 `observed_at=2026-10-09T00:54:59Z`，投影租约截至 `01:04:59Z`，revision `556ee90aefcd1ec2eb9d931de2e46c13adae2e7020b9bfba0982b8821d6de48b`。10 个分面缺少完整字段级证明：`gates`、`alerts`、`posture`、`guardian`、`topology`、`evolution`、`knowledge_health`、`workspace`、`launchd_health`、`agent_visibility`；compact observation 中 `experience_graph`、`connectors` 为 LIVE，`knowledge_health`、`bos_verifier` 为 UNKNOWN。页面可访问，但不能据此判定业务数据完整。
- 性能采样在本次读取时为 64 对样本，健康接口 p50/p95/max 为 2.29/3.87/9.51 ms，无失败；Panorama API 为 221.26/523.47/4,845.16 ms，无失败。暂测 p95 低于 2 秒，但 100 对完整基线尚未完成，最终结论待定；最大值仍有 4.845 秒离群请求，初段还出现 3.363 秒和 2.169 秒请求，后续样本主要在约 0.2–0.55 秒。另做 20 次低负载现场复测，BFF p50/p95/max 为 333.5/522.5/590.9 ms；43191 `/data.json` 为 63.1/261.1/968.7 ms（约 459 KB），compact 为 51.8/112.0/123.9 ms（约 63 KB）。慢请求只在较大 full projection 读取中有迹象，现有证据不足以把早期秒级离群归因于单一组件，需等 100 对采样完成并关联服务日志。
- 采集来源也显示局部重活：`connectors` 最近一次耗时 7.28 秒，`bos_verifier` 5.26 秒，`knowledge_health` 0.68 秒；前两者仍返回 UNKNOWN。它们解释了部分分面不可证，不足以解释 BFF 每个慢请求的耗时。
- M0 最新治理状态：`agent-workflow status` 返回 `ok=true`、15 条 active run；`agent-workflow compliance` 返回 `ok=true / continue`、237 runs、0 locks、无阻断 findings；治理 surfaces 检查返回 `status=ok`、无未登记顶层目录。活动 run 仍由既有 owner 管理，本次未关闭或接管。
- Portfolio Markdown 已由当前 Ledger 投影同步并通过 `git diff --check`；严格 lint 通过（529 BET、16 tracks），严格 projection check 仍只报告 `.omo/goals/current.yaml bytes differ`。该文件属于 OMO 治理目标面，自动 broker apply 尚未接通，因此未覆盖或手改。严格 coverage 的两个未决项是 `KR-TRUST-CHAIN-COVERAGE` 与 `KR-HOLDABILITY-ORPHAN-BETS`；独立复核定位到 9 个不同的已完成 BET 存在重复覆盖且未逐项填写 `coverage_rationale`：`T1-03`、`T1-04`、`T1-05`、`T1-06`、`T1-07`、`T1-08`、`T1-09`、`T1-10`、`T8-05`。需通过授权的 Ledger/治理工作流补充理由，不通过改状态或伪造完成证据绕过。
- Zhixing stderr 曾记录一次启动代码身份检查失败：逐个执行的 Git 身份读取遇到约 0.524 秒子进程超时并以 `IDENTITY_UNBOUND` 退出。当前常驻服务仍为 HTTP 200、`BOUND_FRESH`、`code_drift=false`。这是启动校验的瞬时脆弱性，当前无需重启即可继续使用；修复身份校验或新增 `/panorama` 路由都要经过候选代码绑定、投影发布、服务切换和独立验证，尚未发布。
- 当前判断：本机三处入口可用；统一 Cockpit 是 `http://127.0.0.1:8090/panorama`，Zhixing 是 `http://127.0.0.1:43191/`。如从其他设备访问，本机回环地址会指向访问者设备，应改用服务主机地址并另行配置监听与访问控制。当前观察到的可能影响因素包括入口误用、回环监听范围和 Cockpit 数据分面 PARTIAL；尚未把其中任何一项与用户遇到的故障建立因果关系。没有重启、发布服务或改动 LaunchAgent。

## 00:59 UTC 路由与采样复核

- Cockpit `:8090/panorama`、Vite `:5173/panorama` 和 Zhixing `:43191/` 分别返回 HTTP 200，响应约 3、6、41 ms；Zhixing 根页面为约 1.56 MB。`:43191/panorama` 返回 HTTP 404。结果支持“入口路径不同”，不支持当前仍有本机页面不可达故障。
- 性能采样已到 74/100 对，健康接口 p50/p95/max 为 2.30/3.89/9.51 ms，Panorama API 为 232.88/553.99/4,845.16 ms，均无失败。暂测 p95 小于 2 秒；因基线尚未完成，M1 延迟验收结论继续标为待定。

## 01:05 UTC 数据分面进程差异

- Cockpit LaunchAgent 当前进程 PID `61653` 自 `2026-10-08 18:18:28` 起持续运行，工作目录为 `projects/cockpit`，启动脚本用 `uv run --project ...` 加载源码。其环境未设置 `OMOSTATION_STATE_ROOT` 或 `PANORAMA_COMPACT_OBSERVATION_PATH`，按当前适配器默认值应读取 `/Users/xiamingxing/Workspace/runtime/dashboard/compact-observation.json`。
- 核对 compact observation 中 7 个直接分面，并单独核对 full projection 派生的 `agent_visibility`；当前工作区适配器共得到 8 个有来源记录的分面：`experience_graph`、`connectors`、`knowledge_health`、`bos_verifier`、`evolution`、`workspace`、`launchd_health`、`agent_visibility`。其中 `evolution`、`workspace`、`launchd_health`、`agent_visibility` 在本次当前代码调用结果中为 LIVE；`knowledge_health`、`bos_verifier` 保持 UNKNOWN。当前常驻 BFF 仍只返回 4 个 facet observation，且把上述另外 4 个分面留在 PARTIAL 清单中。当前新适配器文件在 Cockpit 子仓中为未跟踪候选，进程启动时间早于该候选；这强烈指向长驻进程尚未加载新适配器，但尚未在受控重启后验证。
- 因此 Cockpit 的部分 PARTIAL 清单有实际代码代际差异，不全是来源数据缺失。候选适配器将 compact observation 中 3 个额外直接分面判为 LIVE，并从 full projection 派生出 LIVE 的 `agent_visibility`；未知的 posture、guardian、topology、gates 和 alerts 仍受 M1/DCP-20 证据契约约束，不能据此提升为 PASS。候选所在子仓 dirty，服务运行文件未完成干净绑定与发布准入；本轮没有重启以加载候选。

## 01:07 UTC 性能基线收尾

- 100 对低频本机请求样本已完成（健康与 Panorama 各 100 次，约每 18 秒一对），全数 HTTP 200、无失败。健康接口 p50/p95/max 为 2.35/3.89/9.51 ms；Panorama API 为 245.51/1,117.8/4,845.16 ms。按当前 p95 <2 秒目标，这轮低频基线通过；最大单次延迟仍有明显尖峰。
- 此结果不覆盖浏览器并发加载、多人访问或持续压力，因此不能替代并发与耐久验收。它也说明早先 58 对阶段的 p95 超过 2 秒属于暂时样本结果；完整 100 对最终 p95 低于门槛。
- 同轮路由复核：`http://127.0.0.1:5173/panorama` 返回 HTTP 200（约 6 ms，932 字节），`http://127.0.0.1:8090/panorama` 返回 HTTP 200（约 3 ms，1,256 字节），`http://127.0.0.1:43191/` 返回 HTTP 200（约 41 ms，1.56 MB）；`:43191/panorama` 为 HTTP 404。后续一次 Zhixing 根页采样为 1.17 秒，紧接着三次复测为 50–86 ms，页面可达但响应时间有瞬时波动。三项有效入口均可从本机打开。
