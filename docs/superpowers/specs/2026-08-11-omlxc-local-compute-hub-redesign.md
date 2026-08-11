# omlxc 本地算力中枢深度重构设计

> 日期：2026-08-11
>
> 状态：Approved Design
>
> 项目：omlxc
>
> 目标位置：`/Users/xiamingxing/Workspace/projects/omlxc`
>
> 目标层级：Workspace L1 本地算力运行时
>
> 上游入口：AetherForge / `bos://compute/aetherforge/infer`

## 1. 摘要

`omlxc` 将从单文件、命令驱动的个人运维脚本，重构为模块化、本地优先、可观测的算力控制面。它统一管理当前 MBP 以及经 Tailscale 连接的 Mac mini、联想 Y7000P，并适配 oMLX App、LM Studio、LM Link、Ollama 与 SSH 控制通道。

最终产品同时服务三类调用者：

1. 人：使用全屏 TUI 观察和控制本地算力集群；
2. 自动化脚本与 Agent：使用稳定 CLI、JSON/NDJSON 与退出码；
3. AetherForge：通过版本化 API 调用本地推理和控制能力。

默认策略面向低延迟交互，关闭 thinking；需要时可显式切换质量、批处理或节能策略。AetherForge 继续拥有认证、逻辑模型别名、云端决策和 Workspace/BOS 入口，`omlxc` 只拥有本地物理资源、模型驻留、容量准入、任务执行与故障恢复。

本次不追求 PyPI、Homebrew 或面向通用用户的发布，但工程结构、文档、测试、类型、错误处理、版本迁移和安全边界应达到成熟开源项目标准。

## 2. 背景与现状

当前基线具备真实可用价值：

- MBP 以 oMLX App 为主后端；
- Mac mini 提供 LM Studio 与 Ollama；
- Y7000P 通过 LM Link、LM Studio 和 OpenSSH 接入；
- 三台机器经 Tailscale 互联；
- AetherForge 已提供认证后的 OpenAI 兼容入口；
- thinking 默认关闭，已具备内存保护、模型调优和部分回滚能力。

现有实现的主要结构性问题：

- `bin/omlx` 约 2485 行、114 个函数，解析、网络、进程、配置、业务和输出耦合在单文件；
- 大量直接 `print()` 和宽泛异常捕获，难以形成稳定错误契约；
- 每次命令重复探测网络与后端，状态不一致且慢操作阻塞调用者；
- 缺少标准 Python 包、稳定内部 API、类型门禁、CI 和正式版本迁移机制；
- AetherForge 仍直接读取 `~/omlx/conf/models.json` 并 shell-out 到 `omlxc`；
- 配置含机器路径与地址，运行态、配置态和项目源码未彻底分离；
- TUI 尚不存在，机器输出也没有正式 schema 版本。

基准事实：当前测试为 32 项，`--help` 冷启动约 60ms，`cluster` 约 1s。新架构的性能目标以这些实测为对照，不以主观“更快”作为验收。

## 3. 已确认的产品决策

| 决策 | 结果 |
|---|---|
| 产品范围 | 个人本地工具，不要求公共发行 |
| 工程标准 | 按成熟开源项目标准建设 |
| 调用者 | 用户、AetherForge、Agent/自动化脚本 |
| 兼容约束 | 现有命令与输出基本无硬兼容要求 |
| 默认入口 | 交互式终端中 `omlxc` 无参数打开全屏 TUI |
| 机器入口 | `omlxc <command> --json`，流式事件使用 NDJSON |
| TUI 方向 | A：算力驾驶舱，状态优先、逐层下钻 |
| 控制深度 | 全功能控制，并按风险等级确认 |
| 调度策略 | interactive / quality / batch / eco，默认 interactive |
| thinking | 默认关闭；仅显式策略或请求可开启 |
| 可观测性 | SQLite 保存 30 天明细，不保存提示词正文 |
| 核心形态 | 常驻控制面 `omlxcd` + 薄 TUI/CLI/AetherForge 客户端 |
| 重构路线 | Python 模块化重构，不采用 Rust/Go 重写 |
| 项目归属 | Workspace 独立 L1 子项目，不归 ToolBox 所有 |

## 4. 目标与非目标

### 4.1 目标

- 一个权威控制面统一三机状态、模型目录、任务、路由与指标；
- TUI、CLI 与 AetherForge 共用同一套应用用例和错误模型；
- 明确 AetherForge 与 `omlxc` 的职责边界，移除跨仓读配置；
- 提供可解释、可回滚、可观测的本地路由与故障转移；
- 将后端差异封装在可测试适配器中；
- 将配置、状态、密钥、日志与源码彻底分离；
- 通过类型、测试、构建、安全和性能预算防止回退；
- 分阶段迁移，任一阶段均有明确回滚路径。

### 4.2 非目标

- 不在本轮发布到 PyPI、Homebrew 或公共包市场；
- 不在远端节点强制部署新 Agent；
- 不实现模型训练、微调或权重同步平台；
- 不替代 AetherForge 的认证、逻辑别名、云端路由和 BOS 入口；
- 不实现 Web Dashboard；
- 不实现多租户、组织级 RBAC 或公网暴露；
- 不长期维护新旧两套业务实现。

## 5. 项目归属与系统边界

### 5.1 物理归属

目标路径为：

```text
/Users/xiamingxing/Workspace/projects/omlxc/
```

它应作为独立 Git 仓库和 Workspace submodule 注册，语义上属于 L1 本地算力运行时。项目名为 `omlxc`，命令为 `omlxc`，守护进程为 `omlxcd`。

ToolBox 仅可保留能力发现注册或迁移指针，不拥有源码、运行数据库、设备配置或推理业务。现有 `/Users/xiamingxing/ToolBox/omlx` 指针应在迁移后更新为新位置，不复制仓库。

### 5.2 职责边界

```text
Workspace / Agent / Application
              │
              ▼
     AetherForge / BOS ingress
  auth · aliases · cloud policy · facade
              │ versioned local API
              ▼
            omlxcd
 inventory · placement · capacity · execution
              │
   ┌──────────┼────────────┐
   ▼          ▼            ▼
 oMLX App   LM Studio    Ollama
   MBP      remote/local remote/local
              │
        SSH / Tailscale control
```

AetherForge 不再读取 `omlxc` 文件，也不直接实现本地模型加载逻辑。`omlxc` 不决定云端供应商、不暴露 Workspace 公共认证入口，也不拥有逻辑业务别名。

## 6. 变更状态

| 状态 | 组件 | 说明 |
|---|---|---|
| NEW | `src/omlxc/domain` | 节点、模型、路由、任务、错误等纯领域模型 |
| NEW | `src/omlxc/application` | 用例、调度、健康管理、任务编排 |
| NEW | `src/omlxc/daemon` | 唯一状态所有者与异步后台服务 |
| NEW | `src/omlxc/api` | Unix Socket 上的版本化控制与推理 API |
| NEW | `src/omlxc/tui` | Textual 全屏算力驾驶舱 |
| NEW | `src/omlxc/storage` | SQLite、迁移、聚合与保留策略 |
| CHANGED | CLI | 从 argparse 单文件迁移到 Typer 薄客户端 |
| CHANGED | 后端接入 | 收敛为 `BackendAdapter` 契约 |
| CHANGED | 配置 | JSON 与硬编码路径迁移到版本化 TOML/Pydantic |
| CHANGED | AetherForge 联动 | 从文件读取和 shell-out 迁移到 API |
| UNCHANGED | 物理拓扑 | MBP、Mac mini、Y7000P 与 Tailscale 继续使用 |
| UNCHANGED | 后端选择 | oMLX App、LM Studio/Link、Ollama 继续保留 |
| UNCHANGED | 默认策略 | 本地优先，thinking 默认关闭 |
| RETIRED | `bin/omlx` 单文件业务实现 | 完成切换后删除，不长期双轨维护 |
| RETIRED | AetherForge 跨仓读配置 | 由版本化 API 替代 |
| RETIRED | 遗留 LiteLLM/旧网关所有权 | AetherForge 是唯一公共入口 |

## 7. 目标代码结构

```text
omlxc/
├── pyproject.toml
├── uv.lock
├── README.md
├── CHANGELOG.md
├── CONTRIBUTING.md
├── docs/
│   ├── architecture.md
│   ├── configuration.md
│   ├── operations.md
│   ├── troubleshooting.md
│   └── superpowers/specs/
├── src/omlxc/
│   ├── __init__.py
│   ├── cli/
│   ├── tui/
│   ├── api/
│   ├── daemon/
│   ├── domain/
│   ├── application/
│   ├── adapters/
│   │   ├── omlx_app.py
│   │   ├── lmstudio.py
│   │   ├── ollama.py
│   │   ├── ssh.py
│   │   └── tailscale.py
│   ├── storage/
│   ├── config/
│   └── observability/
├── tests/
│   ├── unit/
│   ├── contract/
│   ├── integration/
│   ├── tui/
│   └── hardware/
└── packaging/
    └── launchd/
```

依赖方向必须单向：UI/API → Application → Domain；Adapters 与 Infrastructure 实现 Domain 定义的端口。Domain 不导入 Textual、Typer、HTTP、SSH、SQLite 或平台路径。

## 8. 进程与通信模型

### 8.1 进程角色

- `omlxcd`：唯一权威状态所有者；负责探测、调度、任务、指标与持久化；
- `omlxc`：交互式 TTY 无参数时启动 TUI；有子命令时作为一次性客户端；
- AetherForge：通过本机 Unix Socket 调用 `omlxcd`，再向 Workspace/BOS 暴露认证入口。

MBP 上只运行一个权威 `omlxcd`。Mac mini 和 Y7000P 初期不安装新 Agent，继续暴露现有后端和 SSH 控制通道。

### 8.2 通信约束

- 默认控制端点为权限 `0600` 的 Unix Socket；
- 不默认监听公网或 tailnet 控制端口；
- TUI 与 CLI 不直接访问后端；
- `doctor --direct` 是守护进程故障时唯一有限直连入口；
- 直连诊断只读，不建立第二套运行状态；
- API 带显式版本，响应包含 request ID 与 schema version。

## 9. 核心领域模型

### 9.1 Node

表示一台物理或逻辑计算节点，包含稳定 ID、显示名、平台、Tailscale 身份、控制端点、推理端点、能力标签、资源上限和当前健康快照。地址是配置属性，不作为身份主键。

### 9.2 Backend

表示 oMLX App、LM Studio 或 Ollama 实例。每个实例声明后端类型、协议版本、能力、上下文限制、thinking 控制方式、流式支持和控制能力。

### 9.3 Model 与 Placement

`Model` 表示规范化模型能力和逻辑标识；`Placement` 表示某个后端上的具体模型、路径或后端模型 ID，并记录上下文、量化、内存预算、驻留状态和加载代价。

### 9.4 RoutePolicy 与 RouteDecision

`RoutePolicy` 包含策略配置、约束和评分权重；`RouteDecision` 保存候选、淘汰原因、最终选择、预期降级链和配置版本，支持完整解释。

### 9.5 Job

所有模型加载、卸载、配置应用、服务重启、基准测试和长时间诊断都建模为 Job。Job 有唯一 ID、发起者、风险等级、状态、进度、日志引用与回滚信息。

## 10. 状态机

### 10.1 节点状态

```text
unknown → probing → healthy
                 ↘ degraded
                 ↘ unreachable → recovering → probing
```

- `healthy`：核心探针通过且状态新鲜；
- `degraded`：节点可达，但部分后端、控制通道或容量异常；
- `unreachable`：连续探测失败或 Tailscale/网络不可达；
- `recovering`：恢复探测已成功，但尚未达到健康阈值。

每个状态必须带采集时间。过期快照显示为 stale，不得冒充在线。

### 10.2 Job 状态

```text
pending → planning → awaiting_confirmation → running
                                      ├→ succeeded
                                      ├→ failed
                                      └→ cancelling → cancelled
```

状态转换由应用层统一验证。后端回调、TUI 与 CLI 不得任意改写状态。

## 11. 后端适配器契约

每种后端实现统一 `BackendAdapter` 能力面：

- `discover()`：发现版本、能力与端点；
- `health()`：返回结构化健康快照；
- `list_models()`：返回规范化 Placement；
- `load_model()` / `unload_model()`：执行模型生命周期操作；
- `infer()`：流式或非流式推理；
- `normalize_request()`：映射 thinking、上下文和采样字段；
- `collect_metrics()`：获取可用资源和性能数据；
- `explain_capabilities()`：说明不支持的操作及原因。

适配器必须声明能力，禁止通过捕获异常来猜测“可能不支持”。所有网络调用有独立连接、首包、读取和总超时。

## 12. 调度设计

### 12.1 候选过滤

调度器依次排除：

1. 节点离线、恢复未完成或状态过期；
2. 后端熔断或版本能力不兼容；
3. 模型/能力不匹配；
4. 上下文窗口不足；
5. 内存或显存准入失败；
6. 并发闸门已满；
7. 请求指定的节点、数据或安全约束不满足。

### 12.2 候选评分

通过过滤的候选按以下维度加权评分：

- 模型与任务能力匹配；
- 已热加载与预估冷启动时间；
- 历史首字延迟与吞吐；
- 当前队列、并发与资源压力；
- 最近错误率和熔断历史；
- 网络延迟；
- 节点亲和或用户固定选择。

具体权重由版本化策略配置持有，不散落在代码中。分数相同时使用稳定、可预测的节点优先级，保证路由可复现。

### 12.3 策略配置

| 策略 | 目标 | thinking |
|---|---|---|
| `interactive` | 首字延迟和热模型优先 | 默认关闭 |
| `quality` | 能力、上下文和质量优先 | 仅显式请求开启 |
| `batch` | 吞吐和空闲容量优先 | 默认关闭 |
| `eco` | 内存、显存和功耗优先 | 默认关闭 |

### 12.4 重试与故障转移

- 首个 token 发出前发生可重试错误，可选择下一候选；
- 首个 token 发出后不得静默重放，避免重复输出；
- 流中断返回结构化错误、request ID、已选路由和已输出状态；
- 模型加载使用 placement 级互斥锁，防止重复拉起；
- 同一请求的重试预算有上限，禁止跨节点无限循环；
- 云端降级只能由 AetherForge 显式决定。

## 13. AetherForge 集成契约

### 13.1 所有权

| 能力 | AetherForge | omlxc |
|---|:---:|:---:|
| Workspace/BOS 入口 | ✓ | |
| 客户端认证与授权 | ✓ | |
| 逻辑模型别名 | ✓ | |
| 云端供应商与成本决策 | ✓ | |
| 本地节点健康 | | ✓ |
| 物理模型目录与驻留 | | ✓ |
| 本地容量准入 | | ✓ |
| 本地路由和故障转移 | | ✓ |
| 后端进程与配置控制 | | ✓ |

### 13.2 API 面

控制面最小资源：

```text
GET  /api/v1/health
GET  /api/v1/nodes
GET  /api/v1/nodes/{id}
GET  /api/v1/models
POST /api/v1/models/{id}/load
POST /api/v1/models/{id}/unload
POST /api/v1/routes/plan
GET  /api/v1/jobs
GET  /api/v1/jobs/{id}
POST /api/v1/jobs/{id}/cancel
GET  /api/v1/metrics/summary
```

推理面使用 AetherForge 易于适配的 OpenAI 兼容流式语义，但只在本机 Unix Socket 上提供。AetherForge 传入已解析的本地模型/能力、策略提示、thinking 意图和追踪上下文；`omlxc` 返回最终物理路由、后端 request ID 和性能元数据。

## 14. CLI 设计

```text
omlxc status
omlxc nodes list|show|probe
omlxc models list|show|load|unload|reconcile
omlxc routes show|plan|test|pin
omlxc jobs list|watch|cancel
omlxc metrics show|export
omlxc config validate|diff|apply|rollback
omlxc daemon status|start|stop|restart
omlxc doctor [--direct]
omlxc benchmark
```

输出契约：

- 人类输出默认使用紧凑表格、颜色与进度；
- 非 TTY 自动禁用动画和 ANSI；
- 查询支持 `--json`；
- 持续事件支持 `--output ndjson`；
- stdout 仅承载结果，stderr 承载诊断；
- JSON/NDJSON 包含 schema version；
- 退出码区分参数错误、部分失败、后端离线、超时、权限和内部错误；
- 变更操作支持 `--dry-run`；
- 非交互跳过确认必须显式传入 `--yes`。

## 15. TUI 设计

### 15.1 信息架构

算力驾驶舱固定包含：

1. 总览；
2. 节点；
3. 模型；
4. 路由；
5. 任务；
6. 性能；
7. 日志；
8. 设置。

左侧为领域导航，顶部为全局健康、活动任务与策略，主区域展示当前页面，底部提供命令面板和快捷键提示。

### 15.2 键盘契约

- `g`：快速跳转；
- `/`：搜索当前资源；
- `:`：命令面板；
- `r`：刷新；
- `?`：快捷键帮助；
- `q`：退出；
- `Esc`：关闭浮层或取消当前输入。

所有核心操作必须可仅使用键盘完成。颜色不是唯一状态表达方式，组件需满足基本对比度和窄终端降级。

### 15.3 风险等级

| 等级 | 示例 | 交互 |
|---|---|---|
| R0 查询 | 状态、日志、指标 | 直接执行 |
| R1 可逆变更 | 加载/卸载模型、临时 pin | 一次确认 |
| R2 服务影响 | 重启、持久配置应用 | 预览影响 + 二次确认 + 回滚点 |

TUI 不实现独立业务逻辑，所有动作调用与 CLI/API 相同的应用用例。

## 16. 配置与文件布局

使用 `platformdirs` 解析平台路径。macOS 目标布局为：

```text
~/Library/Application Support/omlxc/config.toml
~/Library/Application Support/omlxc/models.toml
~/Library/Application Support/omlxc/state.db
~/Library/Caches/omlxc/
~/Library/Logs/omlxc/
```

配置优先级：

```text
安全默认值 < 用户配置 < 环境变量 < 单次命令参数
```

规则：

- Pydantic 负责强类型校验；
- 配置带 schema version；
- 应用前先生成 diff 与执行计划；
- 持久变更采用原子写入；
- 第一次变更前生成权限受限的回滚快照；
- 项目仓库只保存 schema、示例和迁移器；
- 地址、密钥和个人路径不进入仓库；
- 旧 `models.json` 由一次性迁移器导入。

## 17. 持久化与可观测性

SQLite 使用 WAL、单写者和批量写入。保存对象包括：

- 节点与后端健康快照；
- 路由决策及候选淘汰原因；
- 请求延迟、首字时间、吞吐和错误；
- 模型加载、卸载与驻留历史；
- Job 生命周期与回滚信息；
- 配置版本与应用记录。

保留策略：最近 30 天保存明细，更早数据仅保留按日聚合。提示词和响应正文默认不保存；身份令牌、API key、SSH 细节和敏感 header 必须在进入日志前脱敏。

日志使用结构化事件，至少包含时间、级别、组件、事件名、request/job ID、节点、后端和错误码。TUI 日志页订阅内部事件流，不读取和解析人类文本日志。

## 18. 安全设计

- 控制 Socket 权限为 `0600`；
- `omlxcd` 默认不监听公网或 tailnet 控制端口；
- AetherForge 是唯一对外认证入口；
- 密钥优先存入 macOS Keychain，配置只存引用；
- SSH 强制 known-host 校验，不使用静默 `StrictHostKeyChecking=no`；
- 远端节点必须在显式 allowlist 中，并校验 Tailscale 身份；
- shell 命令必须使用参数数组，不拼接用户输入；
- 配置、备份和数据库采用最小文件权限；
- 变更操作记录发起者、计划、结果和回滚点；
- `doctor` 输出默认脱敏，显式 debug 也不得输出密钥。

## 19. 错误模型与恢复矩阵

统一错误结构：

```text
code · message · technical_detail · suggested_action
request_id · retryable · affected_resources · partial_result
```

| 类别 | 示例 | 默认行为 | 自动重试 | 回滚/恢复 |
|---|---|---|:---:|---|
| E1xx 配置 | schema 无效、引用缺失 | 拒绝带变更启动，开放只读诊断 | 否 | 使用最后有效配置/快照 |
| E2xx 守护进程 | Socket 不可达、协议不匹配 | CLI 明确失败 | 否 | `doctor --direct` 只读诊断 |
| E3xx 后端 | 超时、格式错误、版本不支持 | 标记后端 degraded | 有界 | 探测恢复、熔断半开 |
| E4xx 容量 | 内存不足、并发已满 | 拒绝候选或排队 | 有界 | 切换候选/等待容量 |
| E5xx Job | 冲突、取消、部分失败 | 保留逐资源结果 | 否 | 按 Job 回滚信息处理 |
| E6xx 存储 | SQLite 写失败、迁移失败 | 降级为受限只读 | 否 | 隔离原库，保留证据后重建 |
| E7xx 安全 | SSH 身份变化、未授权节点 | 立即拒绝 | 否 | 人工核验身份与 allowlist |
| E9xx 内部 | 未分类异常 | 失败闭合并记录 request ID | 否 | 保留诊断，不泄露堆栈给普通用户 |

数据库损坏时不得自动覆盖原文件。配置应用失败时只回滚本次事务拥有的字段，避免覆盖并发或人工变更。

## 20. 性能设计与预算

性能预算以 MBP 主控机器为基准：

| 指标 | 预算 |
|---|---:|
| 缓存查询 p95 | < 100ms |
| TUI 首次可操作 | < 500ms |
| 调度计算 p95 | < 10ms |
| 守护进程空闲 RSS | < 100MB |
| 事件循环阻塞 | 单次 < 50ms |

实现策略：

- 复用 HTTP 连接池；
- 健康探测异步执行并动态调整频率；
- 网络探测结果带 TTL，读缓存不触发同步全网扫描；
- SSH、子进程和阻塞文件操作移出事件循环；
- SQLite 批量落盘，指标队列有容量上限；
- 节点、后端和模型使用独立并发闸门；
- TUI 使用增量事件刷新，不整屏轮询；
- benchmark 输出冷启动、预热和稳态分位数，不能只报平均值。

## 21. 质量与测试策略

### 21.1 工具链

- Python 3.13；
- `uv` 管理环境、锁文件和构建；
- Ruff 负责格式与 lint；
- Pyright strict 负责静态类型；
- pytest 负责测试；
- 依赖漏洞扫描与构建验证进入 CI；
- 构建 wheel/sdist 仅用于可重复安装，不在本轮发布。

### 21.2 测试分层

| 层 | 目标 |
|---|---|
| Unit | Domain 与 Application 纯逻辑、状态机、调度和错误映射 |
| Contract | 所有 BackendAdapter 运行同一契约测试 |
| Integration | 假 HTTP、SSH、Unix Socket、SQLite 与子进程 |
| TUI | 快照、键盘导航、窄终端和错误状态 |
| Fault injection | 超时、半响应、断流、数据库失败、SSH 身份变化 |
| Hardware smoke | 真实 MBP/Mac mini/Y7000P，显式标记且不阻塞普通开发 |
| AetherForge E2E | BOS → AetherForge → omlxc → backend 的流式链路 |

宽泛 `except Exception` 仅允许出现在明确的进程/API 边界，并必须立即映射为结构化错误；领域代码不得吞异常或直接 `print()`。

## 22. 迁移计划与回滚

### Phase 0：冻结与仓库归位

- 保留当前 `omlxc-hub-v2.4-20260811` 可恢复标签；
- 核对当前仓库与历史 `omlx-orchestration` 的远端谱系；
- 建立可靠远端后再迁为 `Workspace/projects/omlxc` submodule；
- 暂时保留 `~/omlx` 兼容软链接；
- 不在仓库移动和远端未验证时切换服务。

### Phase 1：包骨架与领域模型

- 建立 `pyproject.toml`、`src/`、测试和质量门禁；
- 先为现有行为建立 characterization tests；
- 实现领域模型、错误模型和配置 schema；
- 旧 CLI 继续承担生产流量。

### Phase 2：守护进程与适配器

- 实现 `omlxcd`、SQLite 和后端适配器；
- 使用影子模式探测真实节点；
- 对比新旧模型目录、健康和调度结果；
- 不执行自动变更和正式推理切换。

### Phase 3：CLI 与 TUI

- 新 CLI 调用控制 API；
- 上线全屏算力驾驶舱；
- 对模型与服务变更启用风险门；
- 保留显式旧入口用于快速回滚，但不继续扩展旧实现。

### Phase 4：AetherForge 切换

- AetherForge 通过 Unix Socket API 调用 `omlxcd`；
- 影子比较旧、新路由结果和性能；
- 停止读取 `~/omlx/conf/models.json`；
- 停止 shell-out 调用模型加载；
- 完成 BOS 端到端和真实硬件 smoke。

### Phase 5：收尾

- 正式切换本地流量；
- 观察稳定窗口；
- 删除单文件业务实现和旧网关遗留；
- 更新 ToolBox 指针、Workspace registry、BOS/MOF 与运行文档；
- 在确认所有服务不再依赖旧路径后移除兼容软链接。

每一阶段都必须记录：前置条件、验证命令、性能对比、已知风险和回滚步骤。任何跨阶段失败都回滚到最近稳定标签或上一阶段入口，而不是在生产链路上临时补丁。

## 23. 验收标准

### 23.1 功能

- TUI 可完整观察三台节点、后端、模型、任务、路由、指标和日志；
- TUI 可安全执行加载、卸载、pin、重启、配置应用和回滚；
- CLI 查询具有稳定 JSON schema，事件具有 NDJSON；
- AetherForge 不读取 `omlxc` 配置文件、不 shell-out 执行业务操作；
- 三种后端均通过统一 adapter contract；
- 默认 thinking 关闭，并可验证请求与响应没有 reasoning 泄漏；
- 首 token 前可故障转移，流中断不静默重放。

### 23.2 质量

- Ruff、Pyright strict、pytest、构建和漏洞扫描全部通过；
- 新核心路径不存在未解释的宽泛异常捕获；
- 配置迁移、数据库迁移和回滚均有自动化测试；
- 文档覆盖安装、配置、架构、运维、故障排查与恢复；
- 真实硬件 smoke 有可重复记录。

### 23.3 性能与可靠性

- 达到第 20 节性能预算；
- `cluster/status` 类查询不再同步等待全网探测；
- 任一远端节点离线不会阻塞其他节点；
- 守护进程重启后可从配置与数据库恢复；
- 数据过期、部分失败和降级状态不会显示为全绿。

### 23.4 迁移

- 当前稳定版本和运行配置均可恢复；
- 新旧影子结果差异有解释和处置记录；
- Workspace、ToolBox、AetherForge 与 LaunchAgent 路径全部收敛；
- 旧实现删除前，无活跃调用者依赖其文件或命令细节。

## 24. 反方审查

### 风险 1：守护进程成为单点

回应：单一状态所有者是消除状态竞争的必要条件，但查询与诊断不应完全失明。通过 launchd 自动恢复、Unix Socket 健康检查、持久状态、只读直连诊断和明确 degraded 模式降低影响。

### 风险 2：缓存换来了假状态

回应：所有快照携带采集时间和 TTL；stale 是独立状态，不能被格式化成 healthy。变更操作必须在执行前重新验证关键前置条件。

### 风险 3：AetherForge 与 omlxc 双重路由

回应：AetherForge 只做语义、认证、云端与成本决策；`omlxc` 只在已批准的本地候选中做物理放置。契约测试应禁止双方越权。

### 风险 4：大重构造成长期双轨

回应：双轨仅用于有限影子验证。每阶段设退出条件，旧实现不接受新功能，最终必须删除。

### 风险 5：把个人机器信息纳入 Workspace

回应：Workspace 保存代码、schema 和治理注册；机器地址、密钥、模型路径和运行数据库留在用户配置目录与 Keychain，不进入仓库。

## 25. 待实施阶段决定

以下事项不改变本设计，但需要在实施计划中给出具体任务：

- 当前本地仓库与历史 `omlx-orchestration` 远端的谱系收敛方式；
- Workspace submodule 的最终远端 URL；
- 本地安装采用 `uv tool install` 还是项目专用虚拟环境；
- Unix Socket HTTP 实现库与 API schema 生成方式；
- 对外公开前的许可证选择。本轮不执行公开发布。

## 26. 设计审批记录

用户于 2026-08-11 逐项批准：

- 算力驾驶舱 TUI；
- TUI/CLI 双入口；
- 全功能控制与分级安全门；
- 四种路由策略；
- 30 天本地可观测性；
- 常驻控制面架构；
- Python 模块化重构路线；
- `Workspace/projects/omlxc` 独立 L1 子项目归属；
- 本文所述五部分整体设计。

实现必须另行生成详细计划，并在计划评审完成前保持代码不变。
