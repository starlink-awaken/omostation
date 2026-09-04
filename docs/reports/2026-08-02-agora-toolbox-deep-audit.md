---
type: ephemeral
created: 2026-09-03
---

# agora × toolbox 深度调研报告与修复规划

> **文档创建时间**：2026-08-02
> **调研方式**：4 路并行 Agent 只读调研（路由执行 / 治理安全 / toolbox 实例 / 集成一致性），所有引用均为真实文件:行号
> **调研范围**：`projects/agora`（I0 织层）与 `~/ToolBox`（L1-L3 本地服务入口）及其集成面
> **状态**：报告已落盘；修复清单为规划（P0/P1 未执行）

---

## 1. 执行摘要

| 维度 | agora (I0) | toolbox (L1-L3) |
|---|---|---|
| 本质 | BOS 路由网关 + MCP Hub | 13 个本地能力实例注册处 |
| 规模 | 181 py 文件 / 83 测试文件 | 13 实例（5 MCP + 5 Skill + 1 CLI + 2 Pipeline） |
| BOS 服务 | 184 条（stdio 74 / mcp_stdio 35 / inline 28 / internal 25 / mcp_proxy 16 / mcp 5 / http 1） | 13 条全部在 `bos://capability/` |
| 状态 | active 180 / unimplemented 3 / deprecated 1 | 13/13 注册三面一致 |
| 测试 | 1442 collected：1426 passed / 2 failed（~98.9%） | — |

**结论**：两项目「注册面」健康（三面 13/13 一致），但「运行时面」存在真实风险——agora 默认 fail-open 安全配置 + 路由分派与 YAML 声明错配（27% 服务不可正确执行）；toolbox 实例声明与可执行性脱节（3 inline 占位必失败、wps-skills command 悬空）。

---

## 2. 路由与执行链路（agora）

### 2.1 完整调用链

```
bos://domain/pkg/action
├─ 入口A MCP工具 tools_bos.py:595 resolve_bos_uri(uri)
│   → 鉴权/限流/熔断 bos_middleware → 缓存 bos_cache.get
│   → _resolve_with_router (tools_bos.py:435)
│     Step1 _bos_router.resolve (bos_router.py:169 Trie最长前缀)
│        adapter=poc → resolver/api.py:307 resolve_bos_uri
│           └ 再查 bos_router → get_service(POC_SERVICES线性查)
│              → transport==internal → importlib(api.py:349)
│              → 否则 invoke_stdio→StdioAdapter(adapter.py:270)
│     Step2 POC_SERVICES直查(兼容)
├─ 入口B HTTP/SSE mcp_entry.py:45 /v1/tools/call→mcp.call_tool; :7431 SSE
└─ 入口C Resource mcp.py:771 bos_universal_resource→router→proxy→404
```

### 2.2 关键机制

- **代理双轨**：`agora.mcp_proxy`（ProxyManager+registry+idle_timeout）经 bootstrap lifespan 拉起约 20 个下游 MCP server；POC 的 stdio/mcp_stdio 每次调用 spawn 子进程。
- **中间件**：tools_bos 层 缓存/熔断/限流；`core/router.py:580 route()` 另有 registry.mark_failure + service_cache 降级 + event_bus 发 `route:call.*` + 响应压缩；`bus/router.py:14` 写 DLQ。

### 2.3 风险点（路由/执行）

| 级别 | 风险 | 证据 |
|---|---|---|
| 🔴 高 | resolver 只实现 internal/stdio/mcp_stdio（api.py:349/389），但 YAML 含 inline 28/mcp_proxy 16/mcp 5/http 1 共 50 条（27%），seed 为 adapter=poc 后落入 `_call_stdio` 发错协议或 Popen([]) 失败 | api.py:349 · mcp.py:522 |
| 🟡 中 | http 唯一条目 `bos://memory/kos/rest-api`（仅 http_url）无 http 分支会执行报错；tools_bos.py:474 adapter=http 分支因 seed 为 poc 永不命中 | tools_bos.py:474 |
| 🟡 中 | 双重路由——tools_bos.py:451 与 api.py:315 各查一次 bos_router，seed_from_poc 被调两次（mcp.py:522/547），状态易漂移 | tools_bos.py:451 · api.py:315 |
| 🟡 中 | 负载调度 get_load 访问 orch._nodes 私有属性（bos_router.py:186），ImportError 静默降级 100.0；poc 路由 error 被包装成 status:info metadata，掩盖真实错误 | bos_router.py:186 · tools_bos.py:456 |
| 🟢 低 | deprecated 过滤依赖加载期 status（bos_registry.py:125），`AGORA_BOS_INCLUDE_DEPRECATED=1` 可绕过 | bos_registry.py:125 |

---

## 3. 治理与安全面（agora）

### 3.1 防护链

| 层 | 实现 | 关键文件 |
|---|---|---|
| 认证 | API Key（PBKDF2-SHA256+盐 6000 轮）+ JWT(HS256) + Bearer(HMAC-SHA256) + OAuth2 + Agent token 防伪 | `auth/governance.py` · `auth/mcp_auth.py` · `server/tools_auth.py` |
| 授权 | CapabilityGrant（SQLite，约束 expire/max_calls/max_cost） | `auth/authorizer.py` |
| 准入 | AdmissionPort SPI（CR-ADMISSION-01，realized_by `agora.admission.AdmissionPort`） | `admission/port.py` · `mcp_proxy/manager.py:223` |
| 执行 | docker 沙箱（network=none、read-only、no-new-privileges、drop ALL caps、512m/1.0cpu）+ local 回退 | `execution/container_executor.py` |
| 审计/观测 | AuditLogger+AuditSubscriber(SQLite)、BOS 限流/熔断/缓存/重试、metrics 持久化 | `audit.py` · `mcp/bos_middleware.py` |

### 3.2 安全风险清单

| 级别 | 风险 | 证据 |
|---|---|---|
| 🔴 高 | **认证默认 fail-open**：`AGORA_API_KEY` 未配置即 `return True` 且 role=admin；无 `Authorization` 头完全跳过认证 | `server/tools_auth.py:26-28` · `mcp/mcp_transport.py:187-202` |
| 🔴 高 | **硬编码回退 token**：env 缺失时用明文 `"eCOS-v5-Trust-Token"`，可伪造任意 agent 身份 | `middleware/middleware.py:155` |
| 🟡 中 | **授权默认 pass-through**：`ENFORCE_TOOLS=["collab.*"]`，非 collab 工具无 grant 也放行（仅日志） | `auth/authorizer.py:14` |
| 🟡 中 | **凭据泄漏进日志**：含 `Authorization` 的全部请求头打到 info 级 | `server/tools_auth.py:52` |
| 🟡 中 | **CR-ADMISSION-01 部分落地 + 默认 degraded 放行**：`AGORA_ADMISSION_MODE=degraded` 时 provider 缺失即 admit；`bos_router.py:134 register()` 完全不调用 admission（含 seed_from_poc/reload_from_m1 旁路）；信任判定用硬编码绝对路径 `/Users/xiamingxing/Workspace/` | `admission/port.py:170-178` · `mcp_proxy/manager.py:260-264` · `bos_router.py:134` |
| 🟡 中 | **SSRF 面**：market `httpx.get(f"https://api.github.com/repos/{repo}")` 拼接用户可控输入；`multi_instance_middleware.py:50` urlopen(peer.a2a_endpoint)；`tools_registry_mcp.py:42` 拼接 path | `plugins/market/market.py:302` 等 |
| 🟢 低 | `mcp_registry/router.py:46` 硬编码 `api_key="ollama"`；container_executor docker 镜像已 pin digest（良好） | — |

未发现 `eval/exec`、`shell=True`；subprocess 均为 argv 列表（`container_executor.py:491`、`market.py:370`）。

### 3.3 治理完备度

- **X1-C02/C03**：Agora 确为 I0 路由与 register 写入口；但 X1-C03 存在 `seed_from_poc`/`auto_register_from_m1` 绕过 register 的旁路注册。
- **CR-ADMISSION-01**：`realized_by` 指向 SPI，但仅 ProxyManager 接入、BOSRouter 未接入；degraded 默认 fail-open；信任判定靠硬编码绝对路径。
- **CR-RBAC-01**：`server/tools_bos.py:72` 实现 evaluator 域拦截，但 admin 可绕过且默认 permissive 模式 role=admin → 实际零拦截。
- **审计**：`bos_middleware.py` 实为**可靠性层**（限流/熔断/缓存/重试）而非审计；审计在 `audit.py`+AuditSubscriber。文档若称其为"审计中间件"则名实不符。

### 3.4 测试质量

- 83 个测试文件，1442 collected：**1426 passed / 2 failed / 8 skipped / 4 xfailed / 2 xpassed**（~98.9%）。
- **2 个失败同为 BOS 注册表 schema 漂移**：`bos-services.yaml` 5 条 `bos://memory/inbox/*` 声明 `transport: mcp` 但缺 `command`（实为内部 handler）；`bos://omo/tasks/active` 缺 description（`test_bos_registry.py`、`test_bos_yaml_lint.py`）。
- **盲区**：`oauth2_server`/`identity_ca`/`node_identity` 无直接测试；`tools_auth.py` fail-open 默认行为无断言；market 外部安装路径、`multi_instance_middleware`、凭据泄漏行为未覆盖。

---

## 4. toolbox 实例与 SSOT 一致性

### 4.1 实例全景（13 注册实例）

| 实例 | 目录存在 | 独立 git | 声明能力 | 实际状态 |
|---|---|---|---|---|
| wps-office-mcp | ✅ | ✅ 无 remote | 无 README，「243 工具」ToolBox 内查无此声明 | src/tools 仅 4 域共 35 个 ts 文件（excel 11/ppt 14/word 4/common 3） |
| claude-skills | ✅ | ✅ github origin | 354 skill/593 CLI/711 模板 | README 自证一致；实测 SKILL.md 772 个（口径差异） |
| headroom | ✅ | ✅ github origin | 60-95% token 压缩 | README 自证 ✅ |
| media-crawler | ✅ | ✅ github origin | 「12 平台」 | media_platform/ 仅 7 平台（douyin/xhs/bilibili/kuaishou/tieba/weibo/zhihu）；dirty 1 |
| open-montage | ✅ | ✅ | Agentic 视频系统 | dirty 11（5 改 + 6 untracked 新文件） |
| 其余 8 实例 | ✅ | ✅ | 与 registry 描述相符 | 无异常 |

### 4.2 未纳入 registry 的项目

- **ruflo**（skills/ 分区，完全游离）：非独立 git（属根仓）、无 registry 条目、无任何文档提及，有完整 bin/crates/plugins/tests 结构。
- 观察期 5 项（均独立 git，符合 CLASSIFICATION 声称）：agent-governance-toolkit（4637 文件）、gsd-core（2614）、VoxCPM（75）、harness-anything（146）、anysearch-skill（14）。
- **omlx**：纯指针目录，真身在 `~/omlx-orchestration`。
- `_archive/` 仅 skills-legacy；`_runtime/`、`_staging/` 均为空目录。

### 4.3 SSOT 失真点

| 声称（SSOT-SNAPSHOT / REVIEW） | 实测 | 说明 |
|---|---|---|
| M1 节点数 1340 | 1422 | 快照 07-21 后未刷新 |
| BOS 服务数 114 | 184 | 同上 |
| port-registry 18 | 46 个端口 key | 18801 已入列 |
| staging 5 项 | 目录全空 | registry 元数据与文件系统脱节；skills-legacy 实际在 _archive/ |
| routes.json 20 条 | 20 条一致 | 但生成时间 07-31 晚于快照 07-21 |

---

## 5. toolbox ↔ agora 集成一致性

### 5.1 三面一致矩阵（13 实例）

A=`ToolBox/registry/tools.json` | B=`agora/etc/bos-services.yaml` | C=`kairon/packages/forge/tools-registry.json`

| 实例 | A | B | C | B 面 transport / i0_route |
|---|---|---|---|---|
| wps-office-mcp | ✓ | ✓ | ✓ | stdio / pending |
| wps-skills | ✓ | ✓ | ✓ | stdio / pending |
| bos-skill-cli | ✓ | ✓ | ✓ | stdio / pending |
| code-review-graph | ✓ | ✓ | ✓ | stdio / pending |
| headroom | ✓ | ✓ | ✓ | stdio / pending |
| deer-flow | ✓ | ✓ | ✓ | stdio / pending |
| datafoundry | ✓ | ✓ | ✓ | stdio / pending |
| media-crawler | ✓ | ✓ | ✓ | stdio / host_cli |
| open-montage | ✓ | ✓ | ✓ | stdio / host_cli |
| claude-skills | ✓ | ✓ | ✓ | inline / skill_host |
| skills-for-fabric | ✓ | ✓ | ✓ | inline / skill_host |
| knowledge-work-plugins | ✓ | ✓ | ✓ | inline / skill_host |
| last30days-skill | ✓ | ✓ | ✓ | stdio / skill_host |

**三面注册一致：13/13 全 ✓**（bos_uri 逐一比对完全吻合，C 面 79 条目中 13 条均含 bos_uri+domain+cross_references）。注册层无缺失。

### 5.2 gap 清单（可执行性层）

1. **wps-skills command 悬空**（B 面 `bos-services.yaml:2008-2010`）：指向 `ToolBox/skills/wps-skills/dist/index.js`，但该 dist 目录不存在（未 build）。
2. **3 个 inline 占位**（claude-skills/skills-for-fabric/knowledge-work-plugins，B 面 2072-2083/2135-2146/2179-2190）：无 command，`bos_registry.py:63-69` 明确注释为"不可调用的文档锚点"，但 status=active，误调用必失败。
3. **4 个 `python3 -m` 依赖缺失**（headroom/code-review-graph/deer-flow/datafoundry）：系统 python3 无对应模块，ToolBox 实例无 .venv，command 未指向任何虚拟环境。
4. **7 个实例 i0_route=pending**：I0 路由未真正就绪。
5. **运行时路由镜像为 0**：`~/.ecos/bos/routes.json` 是 ecos L0 文档路由（20 条），capability 域 0 条。

### 5.3 X1 遵守评估

- **X1-C02**（`L0-constraints.yaml:19-21`，`cross_call.route=='I0/Agora'`）：**声明满足**，13/13 的 cross_references.realized_by=agora.register；但 7 个实例 i0_route=pending，运行时 I0 路由未全落地。
- **X1-C03**（`:84-85`，`write.entry=='agora.register'`）：**满足**，未发现绕过 agora 直接写 .omo 的路径。
- 缺：i0_route 全量脱离 pending + inline 占位应降级为显式 anchors（否则 X1-C02 的"可路由"承诺打折）。

### 5.4 可解析性

- 声明解析：13/13 可被 `get_service()` 命中。
- 执行解析：仅 wps-office-mcp（node dist 存在）、bos-skill-cli、3 个 bash 脚本（last30days/media-crawler/open-montage）可真正执行；wps-skills 失败；4 个 `python3 -m` 大概率 ModuleNotFoundError；3 个 inline 必失败。`resolve_bos_uri`（`api.py:307-393`）本地 stdio 走 `StdioAdapter._call_stdio`，command 为空时 `Popen([])` 抛错。

### 5.5 mcp_proxy 迁移影响

agora 已有 `mcp_proxy/`（manager/client/registry/feature_gate），capability 域 enabled=True 但描述仅"forge"（`feature_gate.py:34`）。toolbox 13 服务 transport 全为 stdio/inline，**未纳入 mcp_proxy**；当前 proxy→local fallback 可兜底，但迁移方向与 toolbox 直连 stdio 不一致。

---

## 6. 修复清单（P0/P1 规划，未执行）

### P0 — 必须修复（安全 + 路由正确性）

| # | 修复项 | 面 | 证据 | 验收标准 |
|---|---|---|---|---|
| F-01 | **agora 认证 fail-closed**：`AGORA_API_KEY` 缺失时拒绝启动（而非 return True）；无 Authorization 头时拒绝而非跳过 | agora | `server/tools_auth.py:26-28` · `mcp/mcp_transport.py:187-202` | 未配 key 启动失败；无头请求 401 |
| F-02 | **移除硬编码回退 token**：`"eCOS-v5-Trust-Token"` 改为 env 必填，缺失即拒绝 | agora | `middleware/middleware.py:155` | 无 env 时认证失败 |
| F-03 | **admission fail-closed**：`AGORA_ADMISSION_MODE` 默认 degraded→required；`bos_router.register()` 接入 admission 调用（含 seed/from_m1 旁路） | agora | `admission/port.py:170-178` · `bos_router.py:134` | provider 缺失即拒绝注册；旁路路径同走准入 |
| F-04 | **resolver 与 YAML transport 对齐**：inline/mcp_proxy/mcp/http 50 条条目补 resolver 分支或改 seed 逻辑，消除 Popen([]) 类错误 | agora | `resolver/api.py:349` · `mcp.py:522` | 4 种 transport 均有执行路径或显式降级 |
| F-05 | **修复 BOS 注册表 schema 漂移**：5 条 `memory/inbox/*` 补 command 或改 transport；`omo/tasks/active` 补 description | agora | `etc/bos-services.yaml` | 恢复 2 个失败测试全绿 |

### P1 — 应修复（toolbox 可执行性 + SSOT 刷新）

| # | 修复项 | 面 | 证据 | 验收标准 |
|---|---|---|---|---|
| F-06 | **wps-skills build dist** 或改 command 指向真实入口 | toolbox | `bos-services.yaml:2008-2010` | `bos://capability/wps-skills/load` 可执行 |
| F-07 | **3 个 inline 占位降级**：补 command 或标 status=deprecated，避免"active 但不可调" | toolbox | B 面 2072-2083/2135-2146/2179-2190 | 无 active-but-uninvokable 服务 |
| F-08 | **统一 ToolBox 执行环境**：4 个 `python3 -m` 改 `uv run --directory $TOOLBOX_ROOT/...`（对齐 bos-skill-cli） | toolbox | headroom/code-review-graph/deer-flow/datafoundry | 各实例可经 uv 执行 |
| F-09 | **mcp_proxy 迁移纳入 toolbox**：13 服务迁向 mcp_proxy 或显式列入 capability feature gate，i0_route 脱离 pending | agora+toolbox | `feature_gate.py:34` | capability 域经 proxy 管理 |
| F-10 | **SSOT 快照刷新**：M1 1422/BOS 184/port 46 更新；ruflo 注册或归档；_staging 清账 | toolbox | `SSOT-SNAPSHOT.md` | 快照数字与实测一致；无游离实例 |

### 治理面修复（可选）

- F-11 凭据泄漏：`server/tools_auth.py:52` 去掉 Authorization 头进日志。
- F-12 RBAC 收紧：非 collab 工具默认 require grant。
- F-13 SSRF 白名单：market/multi_instance_middleware 对外 URL 加白名单。
- F-14 补齐盲区测试：tools_auth fail-open 断言、oauth2/identity 单测、凭据泄漏回归。

---

## 7. 后续规划建议

1. **执行顺序**：F-01/F-02/F-03（安全 fail-closed）→ F-05（测试恢复）→ F-04（路由对齐）→ F-06/F-07/F-08（toolbox 可执行性）→ F-09/F-10（集成与 SSOT）。
2. **每项走独立 agent-workflow run**（本报告为 planning/调研，不含代码改动）。
3. **验证**：agora 侧 `uv run pytest tests/ -q`；toolbox 侧 `bin/check-toolbox-ssot.py` + 各实例冒烟。
4. **治理**：F-11~F-14 视安全预算决定是否纳入 P0。

---

*本报告数字为 2026-08-02 调研时点快照，动态值以 SSOT 为准。*
