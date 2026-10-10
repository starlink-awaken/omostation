---
schema: md/v1
schema_version: specification/v1
status: draft
lifecycle: spec
owner: dashboard-convergence
bet_id: BET-Y2Q4-T10-236
spec_version: 1.1.0
title: DCP-20 P0 Zhixing GET 方法安全与发布边界
implementation_authorized: false
value_indicator_policy: false
risk_level: L2
human_gate: true
---

# DCP-20 P0：Zhixing GET 方法安全与发布边界

## 目标与范围

在任何 Dashboard 主体会话或角色数据功能开放前，使 Zhixing 的 GET 成为纯读取面，并让未知 operation 默认拒绝。此版本仅覆盖 Zhixing observer API、它的 host-sync 发布边界和隔离测试。Cockpit 身份会话、CSRF、资源 scope 和三类主体授权仍属于 DCP-21。

当前运行服务为 `com.omostation.zhixing-dashboard`，监听 `127.0.0.1:43191`。每次服务启动都要求工作树干净，并把运行文件和 `HEAD` 对比；对活动目录做原地复制会得到 `CODE_DRIFT`。因此本 BET 只能在临时目录证明文件选择、备份、校验和回滚。除非一个干净、不可变、身份已绑定的版本已经通过 G0/M0 和 LaunchAgent 代码身份门，否则**禁止向活动运行根发布或重启服务**。这种情况下登记 `deployment_state: BLOCKED_G0_M0`，保留服务原版本和源码修复候选，待受控版本晋升 BET 完成。

## 当前缺陷

`live_server.py.asset` 的 `/api/v1/<operation>` GET 当前会把 operation 交给 `ObservationIndex.query()`；其中部分 query 分支会写入提案、自动修复、BOS 操作或推进 loop。Legacy non-projection 服务的 POST 也通过同一 query 分支调用这些 operation。投影模式拒绝 POST，但不能证明所有启动模式都安全。

活动 LaunchAgent 指向独立的干净 Git 运行根。该运行根通过 `git status --porcelain` 和文件对 `HEAD` 的比较验证代码身份，所以 host-sync 复制后不能被视为一个可晋升的可信版本。

## Route × Method × Operation 合同

`OPERATIONS` 是通用 `/api/v1/<operation>` 的唯一 operation 集合。实现必须定义互斥且完整的 `READ_ONLY_GET_OPERATIONS` 和 `DISABLED_OPERATIONS`，并以测试证明两者的并集等于 `set(OPERATIONS)`、交集为空。独立 POST `/api/v1/compute/infer` 不属于 `OPERATIONS`，必须单独登记为暂停项并覆盖测试。`GET` 先检查 method，再检查 operation；只有 `READ_ONLY_GET_OPERATIONS` 成员可以进入纯读查询分发。未知、计算、命令和副作用 operation 均拒绝，不能进入 `ObservationIndex.query()`。

| 分类 | operation |
| --- | --- |
| 只读 GET | `manifest`, `summary`, `catalog`, `search`, `entity`, `neighbors`, `brief`, `controls`, `changes`, `ontology`, `lineage`, `context_pack`, `agent/panorama`, `panorama`, `agent/capabilities`, `capabilities`, `agent/next-actions`, `next-actions`, `agent/entity`, `agent/loops`, `loops`, `agent/quickstart`, `quickstart`, `agent/readiness`, `readiness`, `copilot/presets`, `proposals/list`, `health/radar`, `evolution/timeline`, `evolution/diff`, `bos/services`, `tokenomics/stats`, `swarm/topology`, `loops/telemetry`, `loops/dag`, `topology/overview`, `topology/graph`, `topology/projects`, `topology/interfaces`, `topology/sentinel`, `topology/workspace-agents`, `topology/callchains`, `topology/compute-models`, `topology/models`, `topology/compute`, `mof/overview`, `mof/constraints`, `entity/hologram` |
| 暂停执行与计算 | `copilot/ask`, `proposals/submit`, `proposals/adjudicate`, `health/auto-heal`, `health/execute-heal`, `bos/invoke`, `loops/step`, `preflight`, `agent/preflight` |

独立 GET 路由也要有显式清单，不得绕过 operation 检查：

| 分类 | route |
| --- | --- |
| 只读 GET | `/`, `/index.html`, `/agent-brief.json`, `/data.json`, `/manifest.json`, `/sw.js`, `/health`, `/document?id=…`, `/api/v1/document?...`, `/api/v1/events/stream`, `/events/stream`, `/api/v1/value/metrics`, `/api/v1/agent/objective-coverage`, `/api/v1/agent/strategic-gaps`, `/api/v1/agent/brief`, `/api/v1/agent/reconciliation-candidates`, `/api/v1/agent/value-proof-readiness`, `/api/v1/agent/authorization-desk`, `/api/v1/agent/pending-authorizations`, `/api/v1/harness/runs`, `/api/v1/resident`, `/api/logs`, `/__panorama_data__`, `/api/snapshot`, 以及 manifest 中逐一登记的只读静态 JS 文件 |
| 暂停 GET | `/api/v1/compute/live`，因为当前 handler 会探测本机算力并执行命令；任何未在上表登记的路径 |
| 暂停 POST | `/api/v1/compute/infer`，它是独立推理 handler，不属于 `OPERATIONS`；其余 `/api/v1/*` POST 均拒绝 |

Route 清单的参数规则、响应状态和内容类型必须绑定对应 handler，并在测试中与 `do_GET()` 的每个分支逐项核对。任意尾随路径、未知 `/api/v1/*`、任意 `.js` 文件名和 query 变体默认拒绝。`/api/v1/document` 的 query 必须满足 `pinned_document()` 当前契约；`/document?id=…` 只按当前独立注册文档合同读取，不得允许路径输入。

暂停项对 GET 与 POST 都返回稳定的 405 `operation_disabled`，不读请求体、不读取或写入业务状态、不启动 subprocess。所有 `/api/v1/*` POST 暂停；保留服务原先声明为只读的 GET 页面、`/health`、`/api/snapshot`、固定静态资源，以及文档读取：`GET /api/v1/document?id=…&generation=…&expected_sha256=…` 仅在独立 pinned-document handler 验证精确 generation 和 SHA 后提供文件内容。通用 operation dispatcher 不处理 `document`。`HEAD`、`PUT`、`PATCH`、`DELETE`、`OPTIONS`、`TRACE` 一律拒绝。

所有只读 operation 必须保持当前的参数 schema、状态码和响应 schema。`manifest.operations` 只能公布 `READ_ONLY_GET_OPERATIONS`；另以 `manifest.disabled_operations` 列出暂停项，并明确标注 `callable: false`。不得把 `OPERATIONS` 原样公布为可调用列表。不得以 `read_only` 标记、loopback 绑定、Origin 或 CORS 作为副作用保证。`ObservationIndex.query()` 必须只含投影读取；副作用分支在此 BET 从 query 移除且不能被 HTTP handler 调用。命令恢复另行进入 DCP-21 授权设计。

## 发布目标身份与回滚合同

host-sync 在此 BET 生产 CLI 只提供只读 `status` / `plan`；不提供生产 `apply`，也不接受目标目录、plist、host label 或 resolver 的 CLI/environment override。固定读取 `com.omostation.zhixing-dashboard` 与 `~/Library/LaunchAgents/com.omostation.zhixing-dashboard.plist`，核验 plist label 和实际 `ProgramArguments` 指向的 canonical `live_server.py` 根；不得跟随来自 Workspace 输入的 symlink。当前 LaunchAgent 直接指向 `~/.local/share/zhixing-dashboard-runtime-clean-20261008/live_server.py`，不经过稳定版本指针，因此本 BET 一律输出 `deployment_state: BLOCKED_G0_M0`，不能声称已晋升。

后续独立的 release BET 必须先将受管 LaunchAgent 路径迁移到稳定入口 `<dashboard-home>/current/live_server.py`，并用单独人类门禁批准；该 migration 不属于本 BET。迁移后的 `current` 是唯一允许的 symlink，symlink 本身由当前用户拥有，目标必须落在 `<dashboard-home>/releases/<40位commit-OID>` 下。版本目录必须是当前用户拥有的普通目录、无内部 symlink、Git clean，且 `HEAD`、tree SHA、服务文件 SHA 与待发布 manifest 一致。任意额外 symlink、其他 label、LaunchAgent 与 root 不匹配一律在写入前拒绝。

多文件版本准备和 `current` 原子切换只由后续 release BET 实施。本 BET 的单测可以通过私有 Python 依赖注入提供临时 plist、临时 release root 和 resolver；该 seam 不进入生产 CLI/API，生产 resolver 固定读取上述受管 plist 并拒绝覆盖。测试证明对完整 manifest 的准备、SHA 校验和 symlink 原子切换/回滚；测试不得操作真实 LaunchAgent、43191 或任何生产文件。生产侧 `apply` 请求明确返回 `RELEASE_GATE_REQUIRED`，不写入任何文件。

不得直接替换当前活动干净 Git 根内的文件，因为这会使代码身份失败。若版本晋升和运行身份无法按上述方式证明，保持 `deployment_state: BLOCKED_G0_M0`，不得通过修改环境变量、关闭 code-drift 检查、手工复制、重发 projection 或重启绕开门禁。当前没有已授权的 DCP-20 修复 commit，因此本 BET 的生产部署默认状态为 `BLOCKED_G0_M0`；创建该 commit 和晋升版本由单独的人类门禁与后续发布 BET 决定。

## 验收

- 逐 operation × method 的临时 loopback 测试覆盖 `OPERATIONS`、unknown operation、`document`、静态页和特殊方法；GET allowlist 与 `OPERATIONS` 完整对账。
- `/api/v1/manifest` 的 `operations` 与 `READ_ONLY_GET_OPERATIONS` 完全相等；暂停项只出现在 `disabled_operations` 且每项 `callable: false`。
- 所有暂停项经 GET/POST 均稳定返回 405；调用计数、测试文件摘要、proposal、heal、BOS 和 loop 状态前后完全相同；没有 subprocess 调用。
- `ObservationIndex.query()` 对所有 operation 只读；直接调用暂停 operation 也会拒绝，不触发任何副作用。
- 所有 allowlist GET 参数错误、generation 过期、projection 缺失和正常读响应都满足当前 schema；`/health`、`/api/snapshot`、HTML、静态 JS 和 pinned document 回归通过。
- 临时目录发布测试覆盖 CLI/environment 任意路径覆盖被拒绝、私有测试 resolver 注入、错误 symlink 目标、用户/label/plist/root 不匹配、非 clean commit、源 SHA 漂移、worktree 准备失败、切换失败、恢复失败和恢复后的完整 manifest 校验。生产 `apply` 必须保持无写入并返回 `RELEASE_GATE_REQUIRED`。
- 本 BET 的生产 `deployment_state` 固定为 `BLOCKED_G0_M0`。后续 release BET 才能产生 `PROMOTED_CLEAN_REVISION`；本 BET 不得标为 complete 或声称生产服务已获得代码修复。
- 独立复核确认方法×operation 表、源码分支、测试、发布 manifest、回滚证明和部署状态。此 Spec 本身获 Principal 接受与 BET 绑定更新前，不开始实现。

## 写入与非目标

候选写入面仍限于 `live_server.py.asset`、`observatory_query.py.asset`、`zhixing-host-sync.py`、相应隔离测试、此 BET 和证据文档。不得更新或重启其他服务，不清理或接管既有 Run/Lock，不重发 dashboard projection，不实现 DCP-21 Principal/Agent/业务人员 session、CSRF、资源 scope 或身份授权，不开放 Decision Graph，不宣称白皮书整体验收。

## 回滚与失败处理

任何负测产生副作用、只读 GET 回归、operation 对账不完整、目标身份异常、SHA 或 manifest 不符、混合版本可见、恢复失败、G0/M0/代码身份不满足时立即停止。只恢复本次临时发布中已保存的版本；活动根回滚仅由已通过身份门的晋升器执行。不得删锁、接管旧 Run 或跳过状态门。
