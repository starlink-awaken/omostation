---
schema: md/v1
status: active
lifecycle: production
owner: compute-fabric-team
last-reviewed: 2026-09-27
type: runbook
---

# 本机 AI 算力栈运维手册（门面 · 验证 · 故障切换 · 自愈）

> 本页讲"怎么运维、怎么验证"。接入方式见 [compute-mesh-handbook.md](compute-mesh-handbook.md)，集群架构见 [omlx-cluster-architecture.md](omlx-cluster-architecture.md)。
> 运维工具（`aictl`、菜单、场景脚本、守护脚本）在私有仓库 `starlink-awaken/local-ops`，通过 `install.sh` 软链到本机。

## 1. 拓扑

- **门面（aetherforge gateway）**：本机 `:4000` 和 `:9290`（同一个进程），运行的是**发布副本**而不是工作区里的代码。合并 PR 之后必须执行 `aetherforge-gw-deploy [--all] <提交>` 才会生效；`--all` 会让本机和备用站部署同一个版本。
- **后端**：oMLX（常驻的 mythos-fast、embedding、语音、重排）；LM Studio（Splash 分档、视觉、Coder-Next，按需加载并有 TTL）；Ollama（兜底）；phosphene（图像和视频）；决策服务。
- **控制面**：omlxc 负责模型落位与状态探测。门面在 shadow 模式下会先询问 omlxc 的路由意见。
- **备用站**：tailnet 上的 macmini 常驻一套门面。客户端通过 `gw-resolve` 选址，优先级为：`GW_HOST` > 手动固定（`aictl site`）> 本机 > 备用站。
- **密钥**：统一放在 macOS Keychain，服务名 `aetherforge-gateway`。所有客户端都在运行时读取，配置文件里只写 `{env:AETHERFORGE_API_KEY}` 这样的引用。

## 2. 日常命令（aictl）

| 命令 | 用途 |
|---|---|
| `aictl status [--json]` | 服务、节点、已加载模型、内存、电源模式、GPU、swap、竞争进程、主备状态、自愈状态、最近验证结果 |
| `aictl check [--live]` | 核对别名是否漂移；加 `--live` 时用真实请求探测主干能力（视觉类用看图题） |
| `aictl load/unload <lmstudio\|omlx> <模型>` | 加载或卸载单个模型 |
| `aictl heal` | 清理残留锁 → 拉起 oMLX → 重启 omlxcd，刷新落位状态 |
| `aictl site [auto\|local\|macmini]` | 固定门面站点，或恢复自动选址 |
| `aictl verify [quick\|cockpit\|full]` | 验证并写入 `last-verify.json`，完成后发通知 |
| `aictl e2e [--heavy] [--failover] [--only=…]` | 全链路验证（见第 3 节） |
| `aictl mode daily\|create\|save` | 切换运行模式 |

SwiftBar Hub 的「算力」域就是这些命令的可视化面板，并提供"一键 AI"（总结、翻译、解释代码、截图理解、朗读剪贴板，全部经门面走本地算力）。

## 3. 验证（aictl e2e）

**判定原则：HTTP 200 不算通过。**
- chat 类：响应里的 `model` 必须等于请求的别名，否则说明被门面兜底了；provider 必须属于期望的后端；答案内容要正确。
- 媒体类：检查产物本身。TTS 生成的音频交给 ASR 识别后比对文本；重排要把正确文档排在第一；图像检查尺寸；视频用 ffprobe 检查时长和音轨。
- 场景类：调用方的真实入口跑完之后，门面 `/stats` 中对应别名的计数必须增加。这证明请求真的走到了本地算力，而不是被静默降级到规则、Mock、FTS5 或直连后端。

| 层 | 覆盖 |
|---|---|
| 能力 | 每个物理 chat 目标；SSE；OpenAI、Anthropic、Responses、Gemini 协议；工具调用往返；5 个带真实图片的视觉档；embedding；rerank；TTS→ASR 回环；决策；并发 |
| 重型（`--heavy`） | FLUX 图像、LTX 视频、H3 视频 |
| 场景 | 各调用方的真实入口；cockpit 复杂场景：知识问答 RAG、会议纪要闭环、票据理解、研究加董事会决策、告警分诊 |
| 切换（`--failover`） | 停掉本机门面 → 选址切到备用站 → 各调用方在备用站可用 → 本机恢复 → 选址回切 |

**定时回归**：launchd 每天 09:10 运行 `verify quick`，每周日 03:30 运行 `verify cockpit`。

## 4. 故障速查

| 现象 | 根因 | 处置 |
|---|---|---|
| 两个互相独立的引擎同时慢了好几倍 | **macOS 低电量模式**（`pmset -g` 显示 `powermode 1`，接着电源也会生效；`pmset -g custom` 可能显示 0，容易误判） | 关闭低电量模式；菜单标题会变橙提示 |
| oMLX 挂掉后一直不自愈 | ensure-loop 的锁目录 `/tmp/.omlx-server-ensure.lock` 残留，循环一直在"让路" | 超过 180 秒的锁会被自动清除；也可以手动 `aictl heal` |
| oMLX 已恢复，但门面仍报 502 或兜底 | 重启后 omlxcd 的落位状态卡在 `available=False` | ensure-loop 拉起 oMLX 后会自动重启 omlxcd；也可以手动 `aictl heal` |
| 某个档偶发被兜底，mythos-fast 或 embedding 被连带拒绝 | 调用方的非标准参数触发 omlxc 422，旧逻辑会把 4xx 计入熔断 | 已修复：omlxc 接受 `reasoning_effort`，4xx 不再计入熔断 |
| 录音转写或大图请求返回 413 | 门面请求体上限（aiohttp 默认 1MB） | 已调整为 64MB（`AETHERFORGE_MAX_BODY_MB`） |
| 在途请求时卸载 LM Studio 模型后，JIT 不再加载 | LM Studio 进入 "Model is unloaded" 的卡死状态 | 执行 `lms unload <模型>`，再 `lms load <模型>` |
| 冷加载时首个请求 504 | 冷加载时间超过超时 | 门面默认超时 300 秒（`AETHERFORGE_REQUEST_TIMEOUT`）；客户端 provider 的超时应不低于 600 秒 |
| GLM 视觉档短问题被兜底 | GLM 的思考只能通过 `/nothink` 后缀关闭，`reasoning_effort` 反而会让正文为空 | 门面对 GLM 使用后缀方式关闭思考（`no_think_suffix_models`） |
| `/ready` 显示 degraded | 请求的档不可用，由兜底档承接 | 需要精确判活时使用 `?strict=1` |

## 5. 调用方约定

- 地址先读 env，默认 `http://127.0.0.1:4000`；密钥先读 env，其次读 Keychain；请求体使用 OpenAI chat 格式，从 `choices[0].message.content` 解析结果。
- **模型名一律使用门面别名**，不要使用后端原生名，也不要把 shell 全局变量 `OLLAMA_MODEL` 当作别名。
- 失败时必须打日志或显式报错，**不允许静默退回规则或 Mock**。`CR-LLM-GATEWAY-ONLY`（`bin/gac/check-llm-gateway-only.py`）会拦截绕过门面、直连运行时的写法。
