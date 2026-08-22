# 织星算力池 — 全链路系统性分析与落地规划

> 2026-08-22 · 总纲文档，整合当天全部工作（四缺陷修复、Tailscale 攻坚、y7000p 修复、35 placement 全量审计、qwythos 架构原则）+ 新增安全/持久化维度审计
> 详细技术债与逐项证据见 [`2026-08-22-architecture-review-and-roadmap.md`](2026-08-22-architecture-review-and-roadmap.md)（下称"细目文档"），本文档是四支柱框架下的决策依据与路线图

---

## 一、系统现状一句话总结

单 daemon 调度大脑（MBP）+ 三物理节点 + 1 网关，18 逻辑模型 / 35 placement。**今天之前**：y7000p 从未真正参与过算力池（控制通道常年错配到 mac-mini），四个探测/加载层缺陷让"能用"和"稳定能用"之间有巨大落差，Tailscale 断连数周。**今天之后**：三节点全部打通并逐一真实验证过推理，四缺陷根治且有回归测试，但**过程中新暴露的问题比修复的更值得警惕**——"持久可用"这个目标目前主要靠人工操作撑着，不是系统自身的能力。

按你提出的四个目标拆解现状：

| 支柱 | 现状评级 | 一句话 |
|---|---|---|
| **持久可用** | 🟡 部分达成 | daemon/tailscaled 有 launchd 自愈，但常驻策略是纸面配置，从未被代码真正执行过 |
| **安全** | 🟢 基本健康 | 权限/凭证管理规范，但有 3 处今天新发现的暴露面待收紧 |
| **稳定** | 🟢 今天大幅改善 | 四缺陷根治+回归测试+35 placement 实测，剩余的是已知边界（巨型模型、y7000p 设备侧网络） |
| **算力有效利用** | 🟡 刚起步 | mac-mini/y7000p 今天才第一次真正可用，常驻/负载分担策略基本空白 |

---

## 二、持久可用：最大的落差在这里

### 发现：`remote_resident` 是从未被实现的功能

`config.toml` 里 `policies.remote_resident` 声明了 mac-mini（`gemma-4-e4b-it-mlx`）和 y7000p（`qwen/qwen3.5-9b`）的常驻策略，看起来像是"daemon 会自动维护这些模型常驻"。**实际代码核查（`grep -rn remote_resident src/`）结果：这个字段只在 `schema.py`（定义）和 `migration.py`（配置迁移校验）里出现，全代码库没有任何执行逻辑读取它去触发加载或做周期性维护。**

这意味着：
- mac-mini 上 `gemma-4-e4b` 现在能用，纯粹是我今天手动 SSH `lms load ... --ttl 86400` 的结果，24 小时后自动过期，**过期后不会有任何机制自动重新加载**
- y7000p 的常驻声明从写入配置那一刻起就是死的，从未被执行过一次
- 没有监控/告警：常驻模型悄悄消失，你只会在下次请求命中一个未加载模型、体验到冷启动延迟时才会发现，而且系统不会主动告诉你"常驻策略失效了"

### 发现：数据面受控加载不设 TTL，模型会无限期驻留

今天验证过的核心修复（数据面 `ensure_loaded` 注入受控 `context_length`）只解决了"上下文失控"，**没有解决"资源不会自动释放"**。`composition.py` 构造 `LmsLoadOptions` 时只传了 `context_length`，从未传 `ttl_seconds`（尽管这个字段在 `LmsLoadOptions` schema 里是存在且被 `_load_arguments()` 正确处理的，只是调用方没用）。

后果：通过正常聊天流量触发的模型加载，会在内存里**永久驻留**直到手动卸载或机器重启——mac-mini 上那个 TTL 显示为空的 `qwythos-9b`（4.78GB）孤儿残留就是这个缺口的直接证据。在 mac-mini 只有 19GB 总内存的节点上，这种"静默累积"迟早会把可用内存吃光。

### 处置建议（按优先级）

1. **P0：给数据面受控加载补上默认 TTL**（对应细目文档 P1 债务的延伸，实际影响更大）——在 `build_configured_adapters()` 里除了 `load_context_length` 之外，同时算一个合理的默认 `ttl_seconds`（比如复用 `policies.idle_ttl_seconds = 1800`），传给 `LmsLoadOptions`。这是本次分析里**唯一一个建议立即写代码修复**的项，因为它直接决定"稳定"和"持久可用"能否兑现，且改动面明确、可控、可回归测试。
2. **P1：`remote_resident` 要么实现要么删除**——现状是"配置存在但代码不读"，这是比"没有这个功能"更危险的状态（会让人误以为有保护）。两个方向选一个：
   - 实现一个轻量的周期性维护 job（daemon 内部定时器，或者独立的 launchd 任务），定期检查 `remote_resident` 声明的模型是否还在线，不在就按策略重新加载
   - 或者，如果近期没有资源实现，直接从 config.toml 删除这段声明，避免误导，把"mac-mini 常驻 gemma-4-e4b"这件事写成一条运维 SOP（比如加进 `full-status.sh` 的检查项，发现失效就提醒手动补）
3. **P2：常驻状态要能被看见**——`full-status.sh` 已经有 mac-mini 常驻模型的检查，建议把 y7000p 和这次新发现的"孤儿无 TTL 模型"也纳入巡检范围。

---

## 三、安全：三处新发现的暴露面

今天之前的会话几乎没有专门审计过安全维度，这次补上。整体评级健康（daemon 权限规范、凭证走 Keychain、config 无明文密钥），但有三处值得收紧：

### 1. Ollama 监听全网卡（`*:11434`），不像其他后端严格限定 loopback

对比：LM Studio(`localhost:1234`)、oMLX App(`localhost:8000`) 都严格锁在本机回环，只有 Ollama 监听 `*:11434`（IPv6 通配，实际覆盖所有网卡包括局域网）。Ollama 本身无内建认证，意味着**同一局域网内任何设备理论上都能直接调用你的 Ollama**（不需要经过 tailnet，也不需要 omlxc 的任何路由/鉴权）。

处置：检查 Ollama 的 `OLLAMA_HOST` 环境变量设置，收紧为 `127.0.0.1:11434`（如果不需要局域网内其他设备直连它）；如果确实需要局域网可达（比如手机 App 直连），至少确认家庭路由器/防火墙的信任边界符合预期。

### 2. AetherForge 网关的 4000 端口实测只绑定 `localhost`

早前会话记录里这个端口被描述为"tailnet-bound"（意图是让 tailnet 上的其他设备能连），但今天 `lsof` 实测显示它和 9290 端口一样只监听 `localhost`。这是**功能性缺口而非安全问题**（更安全但可能达不到预期的可达性）——如果你确实需要从手机或其他 tailnet 设备访问网关，这个需要专门核实网关自己的绑定配置（不在 omlxc 仓库范围内，是 AetherForge 项目自己的配置）。如果本来就只想本机用，现状正好，不用动。

### 3. sudoers 里有一条今天产生的永久免密授权

`sudo -n -l` 显示：`(root) NOPASSWD: /usr/sbin/networksetup`。这条规则大概率是今天 Tailscale DNS 排障时被权限系统自动授予的（用于 `networksetup -setdnsservers` 那次操作），授权范围严格限定在 `networksetup` 这一个命令，不是全面提权。但它是**永久性**的——任何脚本/进程只要以你的身份运行，都能无提示地静默修改网络设置（DNS、WiFi 等）。

处置：这是个需要你知情的既成状态，不是紧急风险（范围窄），但建议评估是否要保留。如果不需要长期保留，`sudo visudo` 或直接检查 `/etc/sudoers.d/` 找到具体文件删除即可（我没有在未经你确认的情况下动 sudoers，这类改动应该由你决定）。

---

## 四、稳定：今天的核心战果（细目文档已详尽记录，这里给决策摘要）

- **四个探测/加载层缺陷全部根治**（probe 预算、数据面失控加载、busy-probe 摆动、stale-loaded 竞态），全部有回归测试，全部有 live 验证
- **35 个 placement 逐一真实推理验证**：19 个 OK，3 个真实故障（1 个模型文件损坏已移除死配置、1 个 MoE 模型响应超时记录待评估、1 个 omlx-app 接口缺口记录待评估），2 个死配置已清理（mac-mini 的 xlm-roberta 架构不兼容）
- **qwythos-9b 的 852736 上下文问题定位到底**：模型/架构层面硬限制，CLI `-c` 参数不生效，无法从配置层面控制。已确立 **omlx-app 优先**的使用原则（`mythos` 走 omlx-app 是受控、验证过、质量正常的路径；LM Studio 直连留给愿意接受峰值风险的场景）
- **y7000p 网络本身不稳定**是设备侧问题（Windows 机器的 WiFi/电源管理），不是 omlxc 或配置问题，今天观测到反复的 direct→relay→offline 波动，这是需要接受的外部约束，不是能在这个仓库里修的

剩余不阻塞但值得关注：`coding-fast`（qwen3-coder-next MoE）响应偏慢的场景定位、omlx-app 缺 reranker 接口。

---

## 五、算力有效利用：三节点刚刚具备被真正利用的条件

| 节点 | 内存 | 今天之前 | 今天之后 |
|---|---|---|---|
| MBP (主力) | 128G | 正常工作，但 17/18 omlx-app 模型 `resident=false`，冷启动代价高 | 未变——这是下一步优化空间 |
| mac-mini | 24G | 长期几乎不参与（探测常抖动） | 首次有手动常驻验证（3.4s 响应），但缺乏自动化维护（见二） |
| y7000p | 8G(显存) | **从未真正可用**（控制通道错配到 mac-mini） | 首次真正打通，端到端验证通过，但同样没有常驻策略在生效 |

**核心判断**：三节点的物理连接和控制通道问题今天才刚刚清干净，"有效利用"这件事本质上还没真正开始——之前的问题是"链路不通"，现在的问题变成了"链路通了但没有调度策略"。这解释了为什么第二节的"持久可用"问题（`remote_resident` 死配置）会显得格外关键：它本该是"让算力池自动把负载分散到三节点"的核心机制，但目前完全没有实现。

### 建议的下一步方向（不是本次要立即做的，是排优先级用）

1. **先把二节提到的 TTL 缺口和 remote_resident 落地**——没有这个基础，任何"利用率优化"都是在流沙上建楼
2. **MBP 常驻策略扩展**（细目文档已记录）：挑 1-2 个高频模型从 `resident=false` 改 `true`，复刻 mac-mini 常驻的验证收益
3. **给 y7000p 一个明确的角色定位**：8GB 显存注定它只能跑小模型，config 里已经标注"CUDA 小模型"，今天验证过 `mythos-fast` OK——可以考虑把它定位为"轻量级请求优先路由目标"（省 MBP/mac-mini 的算力），但这需要路由算法层面的权重调整，属于下一阶段的架构改动，不建议现在贸然动路由逻辑

---

## 六、总路线图

**P0（建议立即做，改动面小、直接决定持久可用能否兑现）**
- [x] 数据面受控加载补上默认 TTL（`composition.py` 加 `ttl_seconds` 注入，`bdf809e`）——端到端验证：`lms ps` 确认 `TTL: 30m/30m` 精确对应 `idle_ttl_seconds=1800` 配置，3 个回归测试固化

**P1（本周内，需要你决策方向）**
- [x] `remote_resident`：**已实现**（`scripts/remote-resident-maintain.py`，`c9eeb1b`/`d263c4c`，接入 watchdog 每 5 分钟跑一次，`7eddf58`）——见下方"P1 落地记录"
- [ ] Ollama 收紧监听范围到 loopback（除非确认需要局域网直连）
- [ ] sudoers 的 networksetup 免密授权：评估是否保留

### P1 落地记录：remote_resident 从死配置到真正生效

**实现**：`scripts/remote-resident-maintain.py`，由 watchdog 每 5 分钟调用。`lm_studio`/`lm_link` 走 SSH `lms ps` 检查 + `lms load` 补齐（复用 backends 已声明的 `control_endpoint`，不新增信任面）；`ollama` 走纯 HTTP `/api/ps` 检查 + `/api/generate` 空请求 `keep_alive` 补齐（已验证 `keep_alive` 精确生效）。GENERATING 保护、SSH 超时静默容忍、加载成功判定统一用 `lms ps` 复核（不信任 stdout 字符串匹配）。

**实测过程中揪出两个新问题（均已修复）**：

1. **y7000p/mac-mini 的 LM Link 错配今天上午修过又复发了，这次是双向的**——上午只发现 y7000p 单向连到 mac-mini；这次验证时发现 mac-mini 也反向 "connected" 回了 y7000p（`lms link status` 两边互相可见对方 "connected"）。两边重新 `lms link disable` + `lms server` 重启（显式 `--bind 0.0.0.0` 避免重启后回退成仅本地监听，这个坑今天上午也踩过一次）。**这暗示 LM Link 的 enable 状态可能不是持久化关闭的**，需要观察是否会再次复发，如果反复出现，需要找 LM Studio 是否有自动重连机制或者版本更新触发重新配对。
2. **脚本自身的 shell 引号 bug**：用 `repr(model_id)` 包裹传给远程 SSH 命令，`repr()` 是 Python 调试表示不是 shell 转义，在 y7000p（远程 shell 很可能是 Windows `cmd.exe`，不识别 POSIX 单引号）上把字面引号传给了 `lms load`，报 "No model found that matches model key `'qwen/qwen3.5-9b'`"。修复：当前所有 model_id 都不含空格，裸传是唯一对 macOS/Windows 两种远程 shell 都安全的写法；含空白字符时显式跳过并记录，不猜测转义规则。

**端到端验证**：y7000p 的 `qwen/qwen3.5-9b` 首次被自动补齐成功（`context=8192/parallel=1/ttl=3600` 精确匹配声明），幂等性验证通过（已在线时 4 秒内静默完成，无新日志）。

**P2（架构级，需要专门评估，不是这次的产物）**
- [ ] MBP 常驻策略扩展
- [ ] 跨节点负载调度权重（把 y7000p/mac-mini 真正纳入路由决策，不只是"能连上"）
- [ ] 探针取消机制、跨后端内存预算协调层（细目文档已记录的历史债务，今天未新增进展）

---

## 七、给你的一句话结论

三节点的"通不通"问题今天彻底解决了，且有详尽的实测证据背书。但"持久可用"目前是靠我今天的手动操作在硬撑——`remote_resident` 这个本该自动化的机制是空的，数据面加载不设 TTL 会导致内存静默累积。这两点不解决，明天你打开电脑，mac-mini 的常驻模型大概率已经消失，一切要重新手动来一遍。**这是接下来最值得投入的地方，优先级高于继续扩大测试覆盖面或者深挖 y7000p 的偶发网络问题。**

## 八、AetherForge 对外可达性根治（全链路终于闭环）

### 根因

网关进程从今天早上 9:39 就一直在跑（早于 Tailscale 修复），启动参数 `--bind tailnet` 的解析逻辑（`packages/gateway/src/llm_gateway/openai_proxy.py::_tailnet_ip()`）调用 `shutil.which("tailscale")` 找不到就回退到 `/Applications/Tailscale.app/Contents/MacOS/Tailscale`（连的是官方僵尸 daemon 的标准 socket，永远拿不到结果），然后诚实地退回只绑 `127.0.0.1` 并记警告日志。代码本身设计良好（只认 `100.` 段，天然规避了误绑到猎豹 VPN 22.x 网段的风险），问题纯粹是 **launchd 环境的 `PATH` 不含 `/usr/local/bin`**（brew tailscale wrapper 所在位置），`com.aetherforge.gateway.plist` 的 `EnvironmentVariables` 里压根没有 `PATH` 键。

### 修复

给 plist 补上 `PATH=/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin`（备份原文件、`plutil -lint` 验证语法后落地），`launchctl unload`+`load` 重新加载。新进程确认同时监听 `localhost:4000` 和 `macbook-pro-brew.tail0483a1.ts.net:4000`（即 `100.68.80.44:4000`）。

### 端到端验证（从真正的外部 tailnet 设备发起，不是本机 loopback）

从 mac-mini SSH 发起真实请求打 `100.68.80.44:4000`：认证通过，路由到 `mac-mini-m4-24g-lm_studio`，真实生成 "贯通"，`finish_reason: stop`。**这是今天第一次真正验证"外部可用"这件事——此前所有测试都是本机 loopback，掩盖了这个缺口。**

## 九、AetherForge 安全升级 + 生产部署同步

### 依赖升级（修复 GitHub Dependabot 发现的高危漏洞）

推送战略文档时 GitHub 提示了 19 个开放漏洞，6 个 high severity，其中 4 个直接在 `projects/aetherforge/uv.lock`——时效性高：网关当天刚从仅 loopback 可达修复为 tailnet 对外可达，依赖链风险因此被放大。定向升级（`--upgrade-package`，不做全量升级）：

- `starlette` → 1.6.0（CVE-2026-54283：`request.form()` 大小限制被静默忽略，DoS）
- `mcp` → 1.29.0（CVE-2026-59950：WebSocket transport 缺 Host/Origin 校验，DNS rebinding 类攻击面）
- `cryptography` → 50.0.0（CVE-2026-69249 证书链指数级 DoS；CVE-2026-69247 PKCS#7 Bleichenbacher oracle；打包的 OpenSSL 已知漏洞）

`make test` 403 passed（gateway 全部 + mesh 全部），无回归，已推送到 dev 仓库 main（`6c255ec`）。

### 生产 pinned 部署同步

顺带发现 pinned 部署（`~/aetherforge-final-ae3570f`）有两个文件的本地未提交修改（`aliases.yaml`/`gateway.py`）——核实后确认这不是需要保留的独立 hotfix，而是内容已经和 dev 最新代码完全一致（`mid-local` 死链修复等），只是 git HEAD 指针从未跟上。安全丢弃后切换到 `6c255ec`，`uv sync` 确认安全版本生效，`make test` 403 passed，重启网关服务。

**端到端验证**：从 mac-mini 真实 tailnet 设备访问 `/v1/models`，200（0.88s）。一次真实推理请求撞上了用户当时正在使用 `qwythos-9b`（GENERATING）触发的容量保护（409/no_capacity），这是系统按预期工作，不是升级引入的问题——日志确认该请求实际推理耗时 34.8 秒，只是客户端 30 秒超时提前放弃，不是失败。

## 十、场景化性能优化（务实收窄范围，两项已验证落地）

### 根因诊断：coding-next 慢不是配置问题，是架构/框架成熟度问题

`qwen3-coder-next`（`coding-next`/`coding-fast` 背后的模型）架构是 `qwen3_next`——512 专家超稀疏 MoE（每次仅激活 10 个）+ 混合线性注意力（`linear_num_key_heads`/`linear_num_value_heads`）。这类新颖架构的专家路由本身对内存访问模式要求高，**MLX 后端对这个新架构的推理 kernel 优化还不成熟**，这是今天多次尝试调参（`-c`/`--parallel`）都没用的根本原因——瓶颈不在参数，在底层框架实现。

**关键发现**：`dev`/`coding` 这两个最常用场景预设，默认就指向了这个慢模型——不只是"某个 placement 慢"，是默认路径本身把慢模型设成了首选。

### 已落地

1. **场景预设修正**：`dev`/`coding` 改为默认用 `coding`（qwopus3.6-27b-coder-mlx，传统架构，今天已验证响应正常稳定）。`coding-next` 保留为独立可点名场景 `coding-batch`，定位为后台批处理/长上下文专用，不再是交互式默认候选。
2. **coding 场景保活**（`scripts/scenario-warm-keep.py`，接入 watchdog）：填补了 `placement.resident` 机制的执行缺口——这个字段在类型系统里"活着"（`PlacementTarget` 引用它，`autonomy/runtime.py` 里有完整的 `_reconcile` 逻辑），但真正执行周期检查的循环从未被 `composition.py` 的 daemon 组装流程实例化启动，和 `remote_resident` 是同一类"写好了但没接入"的问题。用今天验证过的"外部脚本 + 现有接口"模式补齐，只覆盖 `coding` 一个最高频场景，内存红线比常规审计更保守（20GB），不做大范围预热。

### 刻意不做的（超出今天能安全验证的范围）

- **修复 `autonomy/runtime.py` 的 reconcile 循环真正接入 daemon**：这是更"正确"的修复方式，但改动面是 daemon 核心组装逻辑，风险和测试成本都更高，不适合在长会话尾声仓促做
- **其他场景（chat/vision）的保活扩展**：`qwen-3.8-27b`/`vision` 暂不主动预热，只做了路由预设指向修正，避免多模型同时驻留的内存风险进一步扩大
- **跨节点负载调度权重、探针取消机制**：细目文档已多次记录，仍需专门评估窗口，不是这次"性能优化"任务该碰的

## 十一、daemon 核心真正接入 resident reconcile（补上 §十"刻意不做的"那一项）

### 为什么回头做这个

§十把"reconcile 循环真正接入 daemon"列为"刻意不做的"，理由是"改动面是 daemon 核心组装逻辑，风险和测试成本都更高"。但那个判断是在没有真正去读 `autonomy/runtime.py` 实现细节的情况下做出的——重新评估后发现风险被高估了：

- `ReconciliationEngine`/`ReconcileLoop` 本身是完整、依赖注入、带异常隔离的既有代码（`_run()` 单轮失败不会打垮循环），不是要新写的核心逻辑
- `ProductionPlacementOperator`（满足 `PlacementOperator` Protocol 的具体实现）早就在 `build_production_daemon()` 里构造好了，只是没人把它接进 `ReconciliationEngine`
- `PlacementOperationCoordinator` 也是现成的，`ReconciliationEngine.__init__` 的 `coordinator` 参数设计本来就允许复用外部实例，不需要重复构造一套并发控制

真正缺的只是"连接组织"：内存探测 callable、resident 目标筛选 callable、以及把 `ReconcileLoop.start()/stop()` 接进 daemon 生命周期——这些都是新写但边界很小的胶水代码，不是架构级改动。

### 改动内容

- `config/schema.py`：`DaemonConfig` 新增 `reconcile_interval_seconds`（默认 300s，与 `probe_interval_seconds` 同级但独立，reconcile 语义上不需要 probe 那么高频）
- `daemon/runtime.py`：`DaemonRuntime` 新增可选第四个 `RuntimeComponent`（`reconcile`），追加在 `(config_runtime, recovery, event_runtime)` 之后——启动时最后起（此时依赖已就绪），关闭时最先停（LIFO，避免它在 adapters/bus 关闭后仍发起调用的竞态）。默认 `None`，完全向后兼容。
- `daemon/composition.py`：新增 `_sample_memory_snapshot()`（vm_stat + sysctl，复用今天验证过的 `free+purgeable+inactive*0.7` 公式）、`ReconcileRuntime`（把 `ReconcileLoop` 的 `start()/stop()` 适配成 `RuntimeComponent` 的 `start()/close()`），`build_production_daemon()` 内接入 `ReconciliationEngine` + `targets_provider`（从 catalog 快照筛出 `resident=True` 的 `PlacementTarget`）+ `ReconcileLoop`，并把 `memory_probe` 开成可选注入参数方便测试。
- `tests/integration/test_resident_reconcile_loop.py`：3 个新测试覆盖 resident 自动加载、非 resident 保持不动、内存压力下被正确拒绝。

验证：全量测试套件 1070 passed（原 1067 + 新增 3），ruff 全绿。debug 过程中发现一个真实的接线细节——`ProductionPlacementOperator.load()` 生成的 idempotency_key 不是 `None` 而是 `placement:load:{id}` 格式，第一版测试断言写死了 `None` 导致假失败，用独立脚本手动单步跑通 `reconcile_engine.reconcile()` 才定位到是断言问题而非接入逻辑问题。

### 有意推迟的部分：daemon restart + live 验证

代码、测试、commit（`98c052d`）、push 全部完成，wheel 已构建并通过 `uv tool install` 装到本机 CLI（`omlxc v3.4.0`）。但触发实际重启的那一步——`omlxc daemon restart`——在执行前照例做了内存/GENERATING 检查，结果是：

- 可用内存（校正公式）仅 9.5GB，低于 20GB 安全线
- `qwythos-9b-claude-mythos-5-1m-mlx` 正处于 `status=generating`

本会话内存安全是最高优先级纪律，两个条件任一触发都不该重启 daemon，所以主动推迟。**这意味着新代码目前还没有在生产 daemon 里真正跑起来**，只是完成了实现+测试+静态验证。待内存恢复且无生成中任务时需要补做：`omlxc daemon restart --yes --confirm-impact` → 观察 `resident=True` 的 placement 是否在无人工干预下被自动加载 → 确认 `scenario-warm-keep.py`/`remote-resident-maintain.py` 两个外部脚本 workaround 此时理论上已经冗余（daemon 原生机制接管了同样的职责），可以考虑后续从 `pipeline-watchdog.sh` 移除，但这一步要等 daemon 原生路径实测稳定运行一段时间后再做，不是今天就动。
