# omlxc v3 本地算力中枢实施计划

> **执行约定：** 使用 `subagent-driven-development` 串行推进。每个任务均执行 TDD 微循环、独立实现、独立规格/质量审查、提交、交付标签与验证。跨仓修改必须遵守各仓库治理流程。

**目标：** 将现有 `omlxc` 重构为 Workspace L1 独立子项目和个人本地算力中枢，由 MBP 上的 `omlxcd` 统一调度 oMLX App、LM Studio/LM Link 与 Ollama，并通过 AetherForge 暴露唯一公共推理入口。

**架构：** `Workspace/BOS → AetherForge（认证、逻辑别名、云端决策）→ omlxcd（本地调度、容量、故障转移、指标）→ oMLX App / LM Studio / LM Link / Ollama`。

**技术栈：** Python 3.13、uv、Hatchling、Typer、Textual、Pydantic v2、FastAPI、Uvicorn、httpx、AnyIO、aiosqlite、platformdirs、tomlkit、keyring、structlog、pytest、Ruff、Pyright。

## 全局约束

- 默认路由配置为 `interactive`；thinking 默认关闭，只有 `quality` 且请求显式授权时允许传递 reasoning 字段。
- 仓库保持 private，不新增 LICENSE，不公开发布。
- 不复用或覆盖 `omlx-orchestration` 历史；其未提交内容只做二进制 diff 与 bundle 备份。
- Workspace 共享主树只读；所有根仓变更必须使用 GaC 隔离 worktree 和 `bootstrap → start → claim → verify → closeout`。
- 每个交付物执行 `git add → commit → tag`，远端分支/标签必须可达；不得覆盖并发或用户改动。
- 适配器任务串行实施，每个适配器完成审查后再开始下一个。
- legacy 推理路径保留到 active 切换后的 72 小时观察完成；清理后通过基线标签重新部署回滚，不依赖已删除的 legacy 运行分支。
- 控制面和数据面均不自动启用云端；云端 fallback 始终归 AetherForge 所有。

## 公共契约

- CLI：`omlxc`、`status`、`nodes`、`models`、`routes`、`jobs`、`metrics`、`config`、`daemon`、`doctor`、`benchmark`。
- 机器输出为版本化 JSON，事件流为 NDJSON。退出码：`0/2/3/4/5/6/7/10` 分别表示成功、参数/配置、daemon、容量、超时、部分失败、安全拒绝、内部错误。
- 权限 `0600` 的 Unix Socket 提供 `/api/v1/health|nodes|models|routes/plan|jobs|metrics/summary|events`。
- 同一 Socket 提供 `/openai/v1/models|chat/completions|embeddings` 与 `/api/v1/rerank`。
- 响应 envelope 固定为 `schema_version`、`request_id`、`data` 或结构化 `error`。
- 核心类型：`NodeState`、`JobState`、`RiskLevel`、`RouteProfile`、`BackendKind`、`Node`、`BackendInstance`、`ModelSpec`、`Placement`、`HealthSnapshot`、`RouteRequest`、`RouteDecision`、`Job`、`ErrorEnvelope`。
- 配置 schema v1 使用 TOML；密钥只保存 Keychain 引用。SQLite 以 `PRAGMA user_version` 管理迁移，明细保留 30 天并按日聚合。

---

### Task 1: 仓库持久化与 Workspace 归位

**所有权：** `/Users/xiamingxing/omlxc-v3-bootstrap` 的远端持久化；独立 Workspace worktree 中的 `.gitmodules`、项目注册表与 L1 分层契约；旧仓只读备份。

**步骤：**

1. 确认基线提交与 characterization tests，创建 private 远端 `starlink-awaken/omostation-omlxc`。
2. 推送 main、工作分支、既有标签和 `omlxc-redesign-baseline-20260811`。
3. 对 `/Users/xiamingxing/omlx-orchestration` 生成带时间戳的 binary diff、Git bundle 和校验清单，不修改源目录。
4. 通过 `gac-worktree.sh claim omlxc-v3` 建立 Workspace 隔离树，清理 zombie workflow locks。
5. 启动并 claim `project-code-change/engineering-agent`；需要触及 MOF/治理面时分别启动 `mof-model-change/mof-agent` 与 `governance-state-mutation/governance-agent`。
6. 将新仓以 `projects/omlxc` submodule 加入，登记 `.gitmodules`、`docs/project-registry.yaml` 与 `docs/layer-contract.yaml`；生成面只通过既有生成器更新。
7. 验证 clone、tag、submodule init、分层门禁和旧稳定入口未切换。

**验收：** 远端及标签可达；Workspace 修改只出现在隔离 worktree；旧脏仓有可验证备份；Task 1 各仓提交和标签可达。

### Task 2: Python 包骨架与旧行为特征测试

**文件：** `pyproject.toml`、`src/omlxc/**`、`tests/{unit,contract,integration,tui,hardware}/**`、CI、README、CHANGELOG、CONTRIBUTING、SECURITY、AGENTS、CLAUDE。

**步骤：**

1. 先将当前 32 项测试组织为旧实现 characterization suite，并确认红/绿边界。
2. 建立 `src` 布局、`3.0.0a1` 版本、`omlxc`/`omlxcd` console entry points 和最小可导入包。
3. 配置 Python 3.13、uv lock、Hatchling、Ruff、Pyright strict、pytest/cov、pip-audit。
4. 建立 macOS/Ubuntu CI、构建 smoke test 和项目文档。

**验收：** 旧 32 项行为不变；wheel/sdist 可构建；新入口可运行；Task 2 测试、静态检查与审查全绿。

### Task 3: 领域模型、错误模型与配置迁移

**文件：** `src/omlxc/domain/**`、`src/omlxc/config/**`、相应 unit/contract tests。

**步骤：**

1. 先写枚举、实体、状态机、错误映射和 adapter Protocol 的失败测试。
2. 实现纯领域层，禁止导入 HTTP、SQLite、Textual、Typer。
3. 实现安全默认值 → TOML → `OMLXC_` 环境变量 → 单次参数的配置优先级。
4. 实现 `config migrate --from ~/omlx/conf/models.json`：默认计划模式，只有 `--apply --yes` 写入；写前创建 `0600` 快照；原子写失败可恢复。
5. 保留 23 个模型、三节点、fallback、resident、内存阈值和 thinking 设置；地址不得再充当节点主键。

**验收：** 旧 JSON 往返迁移无语义丢失；无效 schema 失败闭合；敏感字段不落日志。

### Task 4: 后端与 Tailnet 适配器

**执行顺序：** oMLX App → LM Studio/LM Link → Ollama → Tailscale。每个子阶段单独 TDD、审查、提交和标签，不并行修改共享契约。

**文件：** `src/omlxc/adapters/**`、`tests/contract/**`、`tests/integration/**`。

**步骤：**

1. 建立统一 adapter 契约套件，覆盖能力发现、模型同步、load/unload、chat、vision、embedding、流式错误与脱敏。
2. oMLX App：真实生成就绪探针与设置调优。
3. LM Studio/Link：HTTP 推理；OpenSSH 使用参数数组控制 macOS/Windows `lms`，严格 known-host 校验。
4. Ollama：模型目录、驻留、chat/embedding、`keep_alive` 和 thinking 归一化。
5. Tailscale：解析 `tailscale status --json`，只允许显式 allowlist；SSH 仅用于控制，推理优先 tailnet API。

**验收：** 所有契约正确处理不支持版本、超时、半响应、空正文、断流；默认请求无 reasoning 泄漏；shell 输入无字符串拼接。

### Task 5: SQLite、事件总线、健康与自治任务

**文件：** `src/omlxc/storage/**`、`events/**`、`health/**`、`autonomy/**` 及测试。

**步骤：**

1. 实现单写者 SQLite、WAL、迁移、指标批写、30 天清理和日聚合。
2. 实现有界 AnyIO 事件总线；队列满只丢低优先级指标，绝不丢 Job 状态。
3. 实现节点/Job 状态机、健康 TTL、stale、熔断、半开恢复与自适应探测。
4. 迁移 resident 自愈、空闲卸载、内存准入、远端 resident 和 placement single-flight。
5. 禁止 Workspace 直写和重拉其他服务；只提供显式只读投影导出。

**验收：** 重启恢复；库损坏隔离并受限只读；离线节点不阻塞其他节点；事件总线集成测试覆盖背压。

### Task 6: 调度器与本地推理数据面

**文件：** `src/omlxc/scheduler/**`、`dataplane/**` 及 unit/integration tests。

**步骤：**

1. 实现 `interactive/quality/batch/eco` 配置驱动权重。
2. 固定候选过滤顺序：健康/新鲜度、能力、上下文、内存、并发、安全；评分纳入热模型、TTFT、吞吐、队列、错误率、网络和亲和性。
3. AetherForge 只传已解析的本地模型 ID；omlxc 只做物理 placement。
4. 节点、后端、placement 使用独立并发闸门；加载 single-flight。
5. 首 token 前可在剩余预算内切换；首 token 后断流返回结构化错误且不重放。
6. thinking 默认关闭；仅 `quality + explicit opt-in` 传递后端 reasoning 字段。

**验收：** 决策确定、可解释；chat、vision、embedding、rerank 和流式故障均有测试。

### Task 7: omlxcd API 与 launchd 服务

**文件：** `src/omlxc/daemon/**`、`api/**`、`service/**` 及 integration tests。

**步骤：**

1. FastAPI/Uvicorn 仅监听 Unix Socket；父目录 `0700`、socket `0600`。
2. 实现控制/数据面全部公共端点、request ID、统一 envelope、Job 异步操作和 NDJSON 事件恢复。
3. 实现 daemon install/uninstall/status/start/stop/restart；plist 固定调用 `~/.local/bin/omlxcd`，不得使用 `uv run` 或外置卷入口。
4. `doctor --direct` 只做只读配置、Socket、Tailscale、SSH、后端诊断，不创建临时数据库。

**验收：** 并发、权限、重启、取消、断线重连和故障恢复测试全绿。

### Task 8: CLI 与全屏 TUI

**文件：** `src/omlxc/cli/**`、`tui/**`、`tests/tui/**`。

**步骤：**

1. Typer CLI 只调用 daemon client；严格实现 stdout/stderr、JSON、NDJSON 和退出码契约。
2. Textual TUI 实现总览、节点、模型、路由、任务、性能、日志、设置八页。
3. 支持 `g / : r ? q Esc`；颜色不是唯一状态；窄终端降级。
4. R0 直接执行；R1 一次确认；R2 影响计划、二次确认和回滚点。
5. 通过事件流增量刷新；daemon 断开保留 stale 快照；非 TTY 无参数不打开 TUI。

**验收：** Textual Pilot 覆盖键盘流、确认门、断连重连、窄终端和错误界面。

### Task 9: AetherForge API 化

**所有权：** AetherForge 独立隔离 worktree；新增 `OmlxcClient` 和 legacy/shadow/active 模式。

**步骤：**

1. httpx UDS transport；配置 `OMLXC_SOCKET` 与 `AETHERFORGE_OMLXC_MODE`。
2. shadow 仍由旧路径真实推理，只请求 `/api/v1/routes/plan` 比较，不产生第二次推理。
3. active 把 local/hybrid 本地阶段交给 omlxcd；认证、aliases、敏感流、云端 fallback 和成本策略仍归 AetherForge。
4. active 路径删除跨仓 JSON、omlxc subprocess、重复 MemoryGuard 和本地物理 fallback；legacy 分支在 72 小时观察完成前保留。
5. 更新测试、项目文档和架构边界；验证 BOS、9290 与过渡端口 4000 流式 E2E。

**验收：** legacy/shadow/active 合约全绿；shadow 无双推理；active 无跨仓物理调度逻辑。

### Task 10: Workspace 治理、SSOT 与服务收敛

**所有权：** Workspace 独立 worktree、ECOS/MOF 工作流、ToolBox 精确指针修改。

**步骤：**

1. 注册 omlxc L1 项目与 MOF Component；更新 oMLX ComputeEngine/MODEL-BREW 来源为 omlxc API/导出。
2. 服务注册新增 `omlxc.daemon`；旧 gateway、UI、autopilot、autostart 标为 disabled/retired。无专用 broker 时仅在 governance run 中记录 waiver 后做最小直接变更。
3. 保持唯一公共 URI `bos://compute/aetherforge/infer`。
4. ToolBox `omlx` 指针改为 `Workspace/projects/omlxc`，只暂存目标文件。
5. 完成三类 workflow verify/closeout；最后由 `release-agent` 执行 `submodule-pointer-close`。

**验收：** 项目层级、MOF、服务、BOS、文档 SSOT、submodule reachability 与 Workspace GaC 全绿。

### Task 11: 实机切换、稳定观察、清理与发布

**步骤：**

1. `uv tool install --force /Users/xiamingxing/Workspace/projects/omlxc`，先运行 shadow；迁移配置、备份、日志和必要状态。
2. 实测 MBP oMLX App、Mac mini LM Studio/Ollama、Y7000P LM Link/OpenSSH/Ollama。
3. shadow 至少收集 100 次真实/合成 route plan，所有差异可解释且无错误 placement。
4. 切 active，验证 chat、vision、embedding、thinking-off、首 token 前故障转移、内存准入和 BOS E2E。
5. 连续 72 小时满足无崩溃、无 reasoning 泄漏、无错误路由、无不可解释 partial failure、性能不回退；期间保留 legacy 路径。
6. 观察通过后才归档旧 `/Users/xiamingxing/omlx`、建立兼容软链、原子切换 CLI、bootout 旧服务、删除 AetherForge legacy 运行分支、发布 `3.0.0` 和 release tag，并将旧 GitHub 仓标记 archived。
7. 清理后回滚通过部署 `omlxc-redesign-baseline-20260811` 及对应 AetherForge/Workspace 基线标签完成；不得依赖已移除的 legacy 分支，不 hard reset，不删除旧归档。

**验收：** 三仓提交/标签/远端、submodule 指针、workflow closeout、72 小时实机证据和可演练的标签回滚全部齐备。

## 全局质量门槛

- Ruff 零错误、Pyright strict 零错误、pytest 全绿；核心覆盖率 ≥90%，整体 ≥85%。
- wheel/sdist 构建通过；依赖漏洞无高危。
- 缓存查询 p95 `<100ms`，TUI `<500ms` 可操作，调度 p95 `<10ms`，daemon 空闲 RSS `<100MB`，事件循环单次阻塞 `<50ms`。
- 每个任务的实现报告、审查包与审查结论写入 `.superpowers/sdd/`；该目录为本地执行台账，不进入产品提交。
