---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-04
type: ssot
---

# Sovereign CLI Behavior and Surface Contract (PSC v1)

> **状态**: active | **生命周期**: contract | **所有权**: governance-team  
> **适用范围**: 所有由 `cockpit`、`bin/` 暴露的命令、子命令及终端工具  
> **对标标准**: Tier-1 顶级开源 CLI 规范 (`gh`, `kubectl`, `cargo`)

---

## 1. 核心设计原则

1. **零破坏向后兼容 (Zero-Break Compatibility)**:
   任何对已有命令的参数、领域结构升级，必须通过双轨路由器提供兼容分发，严禁破坏已有的脚本或 CI 管道调用。
2. **机器纯净度铁律 (Machine Purity Law)**:
   当用户或智能体传入 `--json` 时，命令输出必须为 100% 严格纯净的 JSON 字符串，严禁夹杂任何 Rich ANSI 彩色转义码、进度条、提示 Banner 或未处理的异常回溯。
3. **确定性退出码 (Deterministic Exit Codes)**:
   严禁随意 `sys.exit(1)` 或在发生业务故障时隐式返回 `0`。必须遵循统一的退出码矩阵。
4. **预检就绪 (Preflight Readiness)**:
   任何带有写入、调度、外发副作用的命令，必须支持 `--dry-run` 标志，在不产生落盘和系统变更的前提下完成参数校验与环境就绪性预检。
5. **可观测与低延迟 (Observability & Low Latency)**:
   高频核心命令必须支持 Fast-path 冷启动加速（<50ms），关键生命周期事件必须向本地环形缓冲进行遥测埋点（<0.5ms 写入开销）。

---

## 2. Exit Code 退出码规范矩阵

所有命令必须使用 `cockpit.domain.exit_codes.ExitCode` 枚举作为唯一的进程退出状态码定义：

| 退出码 | 枚举标识 | 语义说明 | 适用场景 |
| :---: | :--- | :--- | :--- |
| **`0`** | `SUCCESS` | 成功执行 | 命令按照预期完整执行完毕，或预检顺利通过 |
| **`1`** | `GENERAL_FAILURE` | 一般性业务失败 | 内部未捕获异常、底层执行失败、不可自愈的运行时错误 |
| **`2`** | `USAGE_ERROR` | 参数或用法错误 | 非法 Flag、必要位置参数缺失、未知子命令、参数解析失败 |
| **`3`** | `PERMISSION_DENIED` | 权限或访问拒绝 | 缺少鉴权 Token、无权操作受保护的工作区或受限目录 |
| **`4`** | `RESOURCE_NOT_FOUND` | 资源不存在 | 指定的 Task-ID、BET-ID、模型检查点、BOS 服务或文件不存在 |
| **`5`** | `UPSTREAM_ERROR` | 上游或依赖故障 | 远程 RPC 超时、BOS 服务网络不可达、外部依赖子进程崩溃 |

---

## 3. 全局通用选项 (Universal Flags) 契约

所有由 Cockpit 注册的命令与子命令，必须在顶层解析器或分发层支持以下通用选项：

| 选项名称 | 短别名 | 参数类型 | 行为契约 |
| :--- | :---: | :---: | :--- |
| `--help` | `-h` | Flag | 输出结构化格式帮助信息，子命令退出码必须规范捕获为 0 |
| `--version` | `-V` | Flag | 极速打印当前 CLI 版本（走 Fast-path，避免构建完整解析树） |
| `--json` | - | Flag | 启用机器纯净输出模式，自动关闭 Rich 控制台样式 |
| `--dry-run` | - | Flag | 预检模式，仅校验参数与环境依赖，输出预检回执 |
| `--quiet` | `-q` | Flag | 静默模式，抑制信息性 Header、Logo 及进度条输出 |
| `--verbose` | `-v` | Flag | 详细调试模式，打印底层 Trace 链路与诊断耗时 |
| `--output` | `-o` | String | 输出格式控制：`text` (默认), `json`, `tui`, `markdown` |
| `--trace-id` | - | String | 显式注入分布式跟踪 ID，贯穿 OpenTelemetry / Langfuse 链路 |

### 3.1 贪婪参数级联保护
对于声明 `nargs=argparse.REMAINDER` 的多参数委派命令（如 `workflow`, `compass`），主分发器必须在解析前探测原始 `sys.argv`，确保尾随的 `--json` 与 `--dry-run` 能够被正确级联至子系统，不得被贪婪参数意外吸收掩盖。

---

## 4. 8 大正交一级领域树 (Orthogonal Domains) 规范

工作区所有人机交互命令在逻辑上必须归属于且仅归属于以下 8 个正交一级领域：

```
cockpit <domain> <subcmd> [flags]
```

| 领域 Key | 中文命名 | 核心覆盖边界 (Scope) | 示例命令 |
| :--- | :--- | :--- | :--- |
| **`governance`** | 架构与治理 | 契约校验、GaC 门禁、ADR 覆盖率、漂移自愈、文档 SSOT 审计 | `cockpit governance gac` |
| **`workflow`** | 智能体与交付 | Agent 协同、工作流调度、Swarm 监控、常驻 Resident、BCOS | `cockpit workflow swarm` |
| **`memory`** | 记忆与认知 | Memory OS、知识图谱、KOS / GBrain 检索、个人大脑偏好 | `cockpit memory brain` |
| **`compute`** | 算力与推理 | 异构算力织网、DFlash 扩散投机、雷雳 5 DMA、KV 快照、显存治理 | `cockpit compute fabric` |
| **`bus`** | 总线与通信 | Omni-Bus 三平面、Agora BOS 网关、SSE 事件流、服务发现 | `cockpit bus events` |
| **`scene`** | 业务场景 | 场景卡 (Scenario Cards)、业务旅程 (Journeys)、公文写作、家庭枢纽 | `cockpit scene journey` |
| **`system`** | 系统与运维 | 系统体检、Web Dashboard 守护、沙箱环境、健康度与遥测 | `cockpit system status` |
| **`user`** | 体验与向导 | 新手 Quickstart、产品地图 Help、Shell 自动补全、CLI 手册生成 | `cockpit user completion` |

### 4.1 双轨兼容路由准则
- 允许直接调用 `cockpit <subcmd>`（存量语法）以及 `cockpit <domain> <subcmd>`（正交领域语法）；
- `LEGACY_COMMAND_MAPPING` 作为唯一的向后兼容映射字典，任何新增命令均需自报其归属的 `domain`。

---

## 5. 遥测埋点与性能预算契约 (Telemetry & Perf Budget)

### 5.1 性能预算 (Performance Budget)
- **极速查询冷启动**: `--version`、`-h`、简单 status 等高频命令执行延迟必须 `<50ms`；
- **埋点开销约束**: 每次命令执行结束写入指标的耗时必须 `<0.5ms`，且必须采用临时文件原子重命名机制，严禁因埋点文件写入异常阻断业务执行。

### 5.2 Prometheus 指标格式规范
`cockpit telemetry export` 必须导出标准 Prometheus text exposition 格式：
- `cockpit_command_total{command="<cmd>",domain="<domain>",exit_code="<code>"}` (Counter)
- `cockpit_command_duration_seconds{quantile="0.5|0.9|0.99"}` (Summary)
- `cockpit_command_duration_seconds_sum` 与 `cockpit_command_duration_seconds_count`
- `cockpit_command_errors_total{command="<cmd>",domain="<domain>"}` (Counter)

---

## 6. 文档同源与 SSOT 维护准则

- **派生文档单一生成源**: `docs/CLI-REFERENCE.md` 由 `bin/ssot/gen-help-docs.py` 与 `cockpit docs` 统一基于 `projects/cockpit/src/cockpit/commands/registry.py` 反向生成；
- **禁止手工更改**: 严禁直接手动编辑 `docs/CLI-REFERENCE.md` 的正文部分；如需变更命令说明或属性，必须修改 `registry.py` 中的 `CommandMeta`，并运行 `make sync-all-docs` 自动同步。
