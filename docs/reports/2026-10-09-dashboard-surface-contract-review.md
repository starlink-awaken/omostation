# Cockpit Dashboard Surface Contract：首轮证据审查

**状态：** `INITIAL_REVIEW / NOT_ACCEPTED`  
**复核时间：** 2026-10-08 22:45 UTC  
**目的：** 建立统一 Dashboard 路由、API、主体权限和运行验收的可审阅事实底账。本文不授权路由退役、API 写操作、生产发布或角色权限变更。

## 1. 当前可证明的产品边界

产品设计将 Cockpit `/panorama` 作为统一人类入口候选，将 Zhixing `43191` 作为只读观测来源；三类主体共享一套产品壳，但能力必须由服务端身份、scope 和 PEP 决定。页面存在、导航隐藏或 API 返回成功都不等于授权、流程闭环或业务价值完成。

本轮从 `projects/cockpit-ui/src/routes.tsx` 生成了 [路由与旧路径清单](../registry/dashboard-route-disposition-inventory.json)，其状态仍是 `UNREVIEWED_CANDIDATE`。生成器从每条路由追踪到惰性加载的组件源码，并检查 alias target 是否指向实际 route。

当前清单统计：

- 56 条 Cockpit UI route，17 条仅通过 `hidden` 从侧边栏隐藏。
- 15 条旧路径 redirect。redirect 的声明不能证明深链、查询参数、历史导航、权限或业务 parity。
- 56 个组件源码全部能解析且文件存在；所有 15 个 alias target 都命中现有 route。
- 56 条 route 和 15 条 alias 均保持 `UNDECIDED / HOLD`。主体权限、来源 owner、API/error parity、consumer、迁移回滚和浏览器运行证据仍未填写。

## 2. API 对账结果

Cockpit 当前 `/openapi.json` 返回 347 个已登记 path。该快照用于交叉核对接口声明；它不能证明页面真实调用完整、接口副作用安全、授权有效或返回数据符合页面合同。后端模块清单在 `projects/cockpit/src/cockpit/web/router_health.py`，运行时由 `dashboard_server.py` 动态导入并注册；静态搜索单个 decorator 不能覆盖所有 endpoint。

### 已由运行 OpenAPI 补证的路径

| 前端请求 | 当前 OpenAPI | 判定 |
|---|---|---|
| `/api/services`（Overview、Topology） | `GET` 存在 | 路径实际定义在 `projects/cockpit/src/cockpit/dashboard/routes.py:145`；此前限定搜索范围未覆盖该模块。仍需确认 response/error parity。 |
| `/api/commands`（Capability Explorer） | `GET` 存在 | 不应按 decorator 搜索结果判定缺失。 |
| `/api/debt`（Debt） | `GET` 存在 | 运行 path 存在不代表页面响应与错误态已验收。 |
| `/api/v1/arch-health`（Observability） | `GET` 存在 | 页面体验、权限和错误态仍待验证。 |
| `/api/governance/panorama`（Panorama） | `GET` 存在 | 当前真实响应为 `PARTIAL / field_provenance_partial`，部分关键分面缺少字段级 provenance。 |

### 当前疑似前后端契约断裂

| UI surface | UI 调用 | 当前服务 OpenAPI 与 backend 源码 | 判定 |
|---|---|---|---|
| Harness | `GET /api/cockpit/harness/compliance` | 当前 347 个 OpenAPI path 无该路径；源码中也未找到该精确 path。服务存在 `/api/console/harness/stages`、`profiles`、`runs`、`events`、`cancel`、`confirm` 等接口，但它们不是 compliance summary 的直接等价接口。 | `HOLD`。在定义产品合同前不能机械改成 console endpoints。 |
| Intent | `POST /api/intent/compile` | 当前 OpenAPI 无该路径，backend 源码也未找到该精确 path。 | `HOLD`。POST 未调用，尚未判断预期副作用、owner 或替代流程。 |
| Governance self-check | `GET /api/cockpit/governance/self-check`、`POST /api/cockpit/governance/self-check/run` | 当前 OpenAPI 和 backend 源码均未找到这两个精确路径；仅存在 `/api/cockpit/governance/queue` 等其他治理接口。 | `HOLD`。尤其不得因测试 mock 这些路径而推定生产 API 已存在。 |

静态页面扫描初步识别出约 40/56 route 可在页面或一层直接依赖中找到请求模板；约 16 条需继续追踪 hooks、barrel、子组件或条件分支。当前没有任何页面完成从 route 到所有运行时请求、后端 owner、授权策略、错误态的完整闭包。这个“约 40”只是独立静态审查估计，不能作为覆盖率验收值。

## 3. 运行与治理状态

- 2026-10-08 22:39 UTC，Cockpit `/panorama`、`/api/health`、5173 Vite 预览、Zhixing `/` 与 `/health` 连续 3 次均为 HTTP 200。该证据只证明同一台 Mac 上的 HTTP 响应稳定，不等于真实浏览器渲染通过。
- Zhixing `/health` 当时报告 `BOUND_FRESH`、`code_drift=false`，投影 revision `ef1e20ecbfb81f8a6d6cc89985a38547c3a1350075884cb0b961b67dd77c6076`，有效期至 `2026-10-08T22:47:50Z`。新鲜度是短时状态，必须在使用前重探。
- Cockpit BFF `data_state=PARTIAL`，`partial_facets` 有 10 项；HTTP 200 不能消除这些缺口。
- `/api/health` 当前未返回 `Cache-Control`。本轮没有改变服务器或验证缓存在故障时的表现，此项列入响应路径验收。
- 真实浏览器验收仍 `DEFERRED`：Interceptor 安装器进程仍在运行，安装回执、CLI 与 Chrome 扩展尚未出现；silent install 需要当前使用者的 macOS 管理员凭据。没有使用 curl 或旧浏览器自动化替代视觉结论。

## 4. 结论与交付门

Cockpit 具备一套可作为收敛主体的产品壳和较完整的 route/API 资产；但“所有 Dashboard 已合并”尚未成立。最先要关闭的是页面/API 合同断裂与 Panorama 的 provenance 缺口，其次是 71 条 route/alias disposition、三个主体的逐 action/resource 服务端授权、端到端真实业务旅程以及唯一入口迁移证据。

下一步按以下顺序推进，未满足条件的项目继续 `HOLD`：

1. 对 56 个组件执行函数级依赖闭包，记录 `route → component → hook → endpoint → method → backend router → owner`，将静态不确定项留为 `PARTIAL/UNKNOWN`。
2. 由各 API owner 对 Harness、Intent、Governance self-check 的缺失 path 做产品合同裁决；在此之前，不把 UI mock 测试当成 API 存在证据。
3. 建立管理员、Agent、业务人员的 `principal × action × resource scope × allow/deny` 矩阵，并核验服务端 PEP 和撤销/过期/重放负测。
4. 为所有 route/alias 完成 disposition、消费者、deep-link/query/error parity、回滚及三 persona walkthrough；再由独立产品/架构 reviewer 逐项接受。
5. 通过 G0/M0 后再做真实浏览器、冷启动、自恢复和入口切换验收；此前不对生产端口、LaunchAgent、Zhixing 投影或 Ledger/Run 做绕门修改。

## 5. 证据来源

- `docs/plans/2026-10-07-dashboard-product-design.md`：产品定位、三主体、交互不变量和 IA 验收。
- `docs/plans/2026-10-07-whitepaper-v21-traceability-matrix.md`：白皮书需求追踪和阶段门边界。
- `docs/registry/dashboard-route-disposition-inventory.json`：从当前 route 声明生成的候选清单与源文件摘要。
- `projects/cockpit-ui/src/routes.tsx`：route 与 15 个 redirect 声明。
- `projects/cockpit-ui/src/components/harness/HarnessDashboard.tsx`、`src/components/intent/IntentCompiler.tsx`、`src/components/governance/GovernanceSelfCheck.tsx`：三个疑似断裂页面的请求调用点。
- 当前本机 `http://localhost:8090/openapi.json`：347 个运行时注册 path 的核对快照。
- `projects/cockpit/src/cockpit/web/router_health.py` 与 `projects/cockpit/src/cockpit/dashboard_server.py`：后端 router 注册与启动加载行为。

## 23:44 UTC 补记：Intent 服务降级语义

- Intent 的 `/api/intent/compile` 与 `/api/intent/history` 在当前后端仍无对应路由，API 合同继续 `HOLD`。
- UI 原先在 compile API 失败时返回一个成功、置信度 87% 的演示 DAG；历史 API 失败时展示三条仿真的历史记录。现在失败会保持失败：编译区显示 API 错误，历史栏显示“编译历史不可用”，不会再把模拟结果呈现为真实项目状态。此修复没有伪造或新增后端接口，也没有解除该功能的 `HOLD`。
- 失败时会清除上一次成功编译结果，避免旧 DAG 冒充当前结果；测试同时覆盖网络/API 错误与 HTTP 200 但 `available=false` 的编译和历史响应。
- 验证：Intent 组件测试 32 passed；组件路由 E2E 测试 18 passed；TypeScript typecheck 与 ESLint 定向检查通过。
- 改动仅在 Cockpit UI 源码，运行中的 5173/8090 资产尚未重新构建或发布。

## 23:47 UTC 补记：M1 分面与 last-good 证据

- 独立逐项审计确认，现有 M1 候选还只采集旧四分面（knowledge health、experience graph、connectors、BOS verifier）；合同要求的 evolution、workspace、launchd health 与 generation-bound `agent_visibility` 尚未落地。实时 API 仍显示 10 个 partial facets，不能验收为 M1 完成。
- 修复了 compact collector 的 last-good 证据边界：复用仅接受通过载荷校验的 `OBSERVED/STALE`，校验来源身份、摘要、成功时间和状态一致性；摘要损坏或 `UNKNOWN` 残值都会丢弃并保持 `UNKNOWN`。
- 验证：摘要保留、篡改拒绝及 UNKNOWN 不得升级为 last-good 的回归先在旧代码上失败，修复后 `tests/unit/test_compact_observation.py` 10 passed；`py_compile` 和目标文件 `git diff --check` 通过。该修复仍是源码候选，没有接入调度器或运行时发布。

## 23:51 UTC 补记：M1 状态字段与未来时间防线

- compact collector 现在同时输出 `status` 与契约字段 `observation_status`，读取历史状态时兼容仅含 `status` 的旧记录；两字段同时存在但冲突时拒绝复用 last-good。
- 修正 future timestamp 测试：从完整有效的 OBSERVED 记录构造 prior，只将 `observed_at` 和 `last_success_at` 改为未来时间，确保用例实际触发时间边界校验；另覆盖状态字段冲突。
- 验证：`tests/unit/test_compact_observation.py` 11 passed，`py_compile` 与 `git diff --check` 通过。独立代码审查批准了状态兼容、last-good 边界与未来时间测试；审查后新增的冲突专测也通过同一 suite。
- 运行端只读复查：Cockpit `/panorama`、Vite `/panorama`（localhost/127.0.0.1）及 Zhixing `/`、`/health` 均 HTTP 200；Zhixing 当前报告 `BOUND_FRESH`，生成时间 `2026-10-08T23:49:54Z`，有效期至 `23:59:54Z`。Cockpit Panorama API 仍为 `PARTIAL`。本轮未构建或发布源码，浏览器视觉验收和并发稳定性仍未证明。

## 00:09 UTC 补记：Evolution 与 Workspace 分面接入

- compact collector 已把 `evolution`、`workspace` 纳入每 240 秒的限界观察：evolution 记录排序后的 proposal 相对路径与数量；workspace 报告 worktree/lock 文件路径清单，不再使用“orphan lock”或“stale worktree”诊断。Cockpit adapter 按当前 collector digest、source ref、规范化值摘要和 300 秒年龄验证两分面；失败的 last-good 在有效期内显示 `PARTIAL`，过期为 `STALE`。UI 新增两个分面详情，并移除“无僵尸锁”“Remote 隔离正常”等无来源结论。
- 运行证据：活跃的 `com.omostation.panorama-compact-observation` LaunchAgent 每 240 秒执行 `/Users/xiamingxing/Workspace/bin/panorama/compact-observation.py`。2026-10-09 00:05:45Z 运行产出六个分面；新增的 evolution/workspace 均为 `OBSERVED`，有值与 source digest。Cockpit API 仍返回旧已加载 BFF 的 `PARTIAL` 和 10 个 partial facets，未提供这两个分面的 adapter 观察；服务未重启或发布。
- 验证：compact collector 12 passed，Cockpit adapter 22 passed，Cockpit UI 相关测试 40 passed；UI TypeScript 与 ESLint 定向检查通过。UI 全套 98 个测试文件中 95 通过、3 个文件有 5 个失败：TopologyView/StudioView 的 React invalid hook call，以及 ChainStudio 无法找到 DAG 可视化。失败不在本次修改文件；保留为全套测试阻塞记录。
- 服务生成器复查仍只有既有 `com.omostation.zhixing-projection-fullrefresh` plist/SSOT 漂移。当前实现未接入 launchd_health 与 generation-bound `agent_visibility`，M1 仍未完成；真实浏览器视觉验收、发布和运行样本门槛也未完成。

## 00:22 UTC 补记：M1 合同缺口修正与只读 launchd 探针

- BFF 将无法验证的 facet 归为 `UNKNOWN` 时现在同时清空 `observed_at`、`last_success_at`、摘要和值，避免旧成功时间制造“有最近成功证据”的错觉。
- `agent_visibility` 在全量投影路径中仅当 `available=true`、输入来源结构有效、嵌套 generation id 与全量投影 generation 一致、生成时间与投影一致，并且全量投影已通过紧邻 compact artifact 与 `/health.state_revision` 的绑定校验时才生成 `projection-derived` 信封。信封绑定该 generation 和 revision，摘要覆盖完整规范化值，保留 subordinate `input_sources` 状态，时间来自投影生成时间；超过 21,600 秒为 STALE。UI 单独按 6 小时 TTL 处理该 facet，其他直接观察仍按 300 秒。
- 新增只读 launchd 观察器：规范化选中任务并在调用前计算 registry SHA-256；每个任务单独保留 label、uid、观察时间、stdout、stderr、退出码、解析结果与结果分类。只有退出码 113 且 stderr 同时含 `Could not find service` 和请求的完整 label 才判为确认未加载；其他错误为 UNKNOWN。空 registry / 全未知不产生有效成功值，混合 job 结果保留为 PARTIAL，已加载但最近退出码非零单独表达语义 FAILED。compact provenance、BFF 与 UI 都验证 registry 摘要。
- 定向验证：Cockpit adapter 26 passed；compact observation 与 launchd collector 17 passed；Cockpit UI 24 passed；UI TypeScript 检查、定向 ESLint、Python `py_compile` 与 `git diff --check` 均通过。只读实机探针读取到 13 个登记任务：6 个加载、7 个经严格 exit-113/stderr 条件证实未加载；这 7 个是 `resident-launchd-{decision,execute,signals,inbox,promote,event-ingest}` 与 `zhixing-host-drift-hourly-active`，都标为语义 FAILED。该探针没有卸载、加载、kick 或重启任务。
- 当前 `/panorama` 页面入口 `8090`、`5173` 及 Zhixing `43191` 均返回 HTTP 200。Cockpit 正在运行的 BFF 仍是旧加载版本：当前 API 保持 `PARTIAL`，可见的观察分面只有旧的 `knowledge_health`、`experience_graph`、`connectors`、`bos_verifier`，缺少新的 `evolution`、`workspace`、`launchd_health` 和代际绑定 `agent_visibility`。源码尚未进入运行时；本补记不代表生产集成验收或发布。
- M1 仍未满足：launchd 新 collector 尚未经过四个连续调度周期；新 BFF 仍未集成；真实浏览器全分面检查、30 分钟 API 延迟样本和独立复核结论仍待完成。没有重启服务或发布投影。

## 00:27 UTC 补记：独立复核后的三项闭环修正

- full projection 先生成的 `agent_visibility` envelope 现在与后续 compact facet observations 合并，不再被整体覆盖；新增适配器用例同时断言两类证据并存。
- Zhixing `build_payload()` 在最终 generation id 和 source-state provenance 固定后，为 agent visibility 写入一致的 generation id、规范化生成时间及按 source 索引的 input 状态/来源快照 provenance。缺来源证据时明确放入 UNKNOWN 记录。适配器仍要求 full/compact artifact generation 一致且 revision 与 health 对齐。
- launchd job 新增现有 Drawer 所需的 `verdict`、`loaded`、`state`、`pid`、`last_exit_code`、`last_exit_ok` 兼容字段；TypeScript 覆盖 DEGRADED/UNKNOWN，Drawer 对 UNKNOWN 使用中性提示色，避免把采集未知误画成失败。
- 修复后验证：Panorama BFF 26 passed；compact observation、launchd health、agent brief 三组测试合计 49 passed；UI Panorama 与 DeepTelemetryDrawer 36 passed；TypeScript、定向 ESLint、Python 编译及 diff whitespace 检查通过。独立复核第二轮正在进行。
- 运行态边界未改变：当前页面与 API 仍可通过 HTTP 访问，但 BFF 是旧进程，最新源代码尚未集成进服务；这一轮没有重启、部署、投影刷新或修改任何 LaunchAgent 状态。等待连续周期、API 延迟样本与真实浏览器逐分面检查仍属 M1 验收项。

## 00:33 UTC 补记：发布边界复核通过

- 第三轮独立审查确认：发布器必须在读取并验证权威 `source_states` 后重新绑定 `agent_visibility`。现已在发布路径执行该顺序，并在没有权威快照时将 input 状态降为 UNKNOWN；有效且 generation 匹配的来源快照则保留状态与 provenance。发布级测试覆盖这两条路径。
- 独立审查结论 `APPROVE / CLEAR`，无剩余代码阻断。复跑为 agent/collector 49 passed、Cockpit BFF 26 passed；UI 36 passed、TypeScript、定向 ESLint、Python 编译和 diff 检查通过。
- 最新可达性复查：`8090/panorama`、`5173/panorama`、`43191/` 均 HTTP 200。当前 Cockpit 仍由旧进程提供，API 为 PARTIAL；本轮已通过源码审查与定向测试，但没有把代码切入线上进程。仍需完成四个调度周期、30 分钟 API 延迟样本、真实浏览器全分面验收和项目 M0/G0 发布条件，才能闭合 M1。
