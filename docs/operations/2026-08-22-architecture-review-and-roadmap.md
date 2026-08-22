# 织星算力池 — 全局架构评估与规划

> 2026-08-22 · 承接当天四缺陷根治 + Tailscale 攻坚之后的整体盘点
> 范围：三节点算力拓扑、omlxc 路由/调度、AetherForge 网关、技术债清单、优先级路线图

---

## 一、拓扑现状

```
AetherForge 网关 (dev 最新 / 生产 pinned 落后若干 commit)
  └─ omlxc daemon (MBP, 唯一调度大脑)
       ├─ MBP  M5 Max 128G  "主力+网关"
       │    ├─ oMLX App   (primary, 16 placement, 仅 embedding 常驻)
       │    ├─ LM Studio  (fallback, 受控加载已修 4 缺陷)
       │    └─ Ollama     (二级兜底)
       ├─ mac-mini  M4 24G  "第二节点"
       │    ├─ LM Studio  (SSH 受控, gemma-4-e4b 常驻 24h)
       │    └─ Ollama     (二级兜底)
       └─ y7000p  RTX4070 8G  Windows  "CUDA 小模型"
            ├─ LM Studio  (kind=lm_link, ⚠️ 见债务 #1)
            └─ Ollama     (二级兜底)
```

18 个逻辑模型 × 最多 3 个物理后端 = **37 个 placement**，全部由 `~/.config/omlxc/config.toml` 单文件描述，daemon 单进程调度。

---

## 二、技术债清单（严重度排序）

### P0 · 严重 / 安全相关

#### 债务 #1：y7000p 的 SSH 控制通道被错误配对到 mac-mini（今日新发现，未修复）

**证据链**：
1. `ssh xia@100.64.43.36 hostname` → 正确返回 `xia-y7000p`，SSH 目标本身没连错机器
2. 但同一连接里 `lms ps --json` 返回的模型是 `"format":"safetensors"`、`"path":"sahilchachra/Qwythos-9B-Claude-Mythos-5-1M-mxfp4-mlx"` —— **MLX 格式模型不可能运行在 Windows/CUDA 机器上**，这是物理不可能的组合
3. 返回的具体状态（`gemma-4-e4b-it-mlx` TTL `86400000ms`＝24h、`qwythos` `contextLength:2048`）与当时 mac-mini 的真实加载状态逐字节吻合（今天早些时候我刚在 mac-mini 上以 `-c 16384 --ttl 86400` 加载过 gemma-4-e4b）
4. 而 y7000p 自己真正的本地服务器（`netstat` 确认 `0.0.0.0:1234 LISTENING`，PID 33692）通过裸 HTTP `curl http://100.64.43.36:1234/v1/models` 查询，返回的是完全不同的、真实的 GGUF/CUDA 模型清单（`qwen/qwen3.5-9b`、`glm-ocr`、`whisper-large-v3-turbo`、`deepseek-ocr`、`kokoro-82m` 等）

**根因**：LM Studio 自带「LM Link / Remote Instances」配对功能（`lms link` 子命令一类）。y7000p 上的 `lms` **CLI 客户端**在某次操作中被配对到了 mac-mini 的 LM Studio 实例，此后所有在 y7000p 本机敲的 `lms` 命令（包括 omlxc 通过 SSH 送达的）实际操控的都是 mac-mini，而不是 y7000p 自己端口 1234 上真正在跑推理的那个服务器。

代码侧核实：`kind = "lm_link"` 在 omlxc 全部代码路径里（`diagnostics.py`/`schema.py`/`composition.py`）都和 `kind = "lm_studio"` 走同一个 `LmStudioAdapter`，同一套「SSH 到 control_endpoint 执行 `lms load -c ...`」逻辑——**没有为 LM Link 协议做任何特殊处理**，这个 kind 目前只是语义标签，不是功能分支。所以这不是 omlxc 代码的 bug，是 y7000p 那台 Windows 机器上 LM Studio 的配对状态问题，但后果由 omlxc 的路由承担。

**影响面**：
- y7000p 上 3 个 placement（`mythos-fast--y7000p...`、`embed-bge-m3--y7000p...`、`baai-bge-reranker...--y7000p...`）的受控加载（`_ensure_loaded_before_http` guard，今天刚修的缺陷④）实际上什么都没有控制到 y7000p 自己——guard 认为「已下发受控加载，可以放行 HTTP」，但真正收到 HTTP chat 请求的是 y7000p 自己未被保护的 LM Studio，JIT 失控加载风险原样存在，而且赌注是一块 **8GB 显存**的游戏本，比 128GB 统一内存的 MBP 炸得快得多
- mac-mini 同时被两个源头下发控制指令：它自己合法的 `mac-mini-m4-24g-lm_studio` backend，以及来自 y7000p 幽灵配对的指令，状态有被交叉污染的风险
- `policies.remote_resident` 里给 y7000p 定义的常驻策略（`qwen/qwen3.5-9b -c 8192 --ttl 3600`）如果有对应的维护任务在跑，同样会打偏到 mac-mini

**处置建议**：需要在 y7000p 机器上执行 `lms link` 相关命令解除配对，或直接在 LM Studio GUI 断开 remote 连接——这是改动远程机器状态的操作，需要你确认后我再执行（或你自己在 Windows 上点一下更快）。**在解除配对前，不建议真实生产流量路由到 y7000p 的 lm_studio/lm_link placement**，config 层面可以考虑临时降权或标记该风险。

#### 债务 #2：内存读数口径不统一

`scripts/full-status.sh` 仍用朴素 `vm_stat` 的 `Pages free` 计算可用内存，今天读到「可用 ~0GB」，吓人但不准；用 `free + purgeable + inactive*0.7` 精确公式复核后是 **22.4GB**。这个更准的公式今天早些时候已经在 `safe_audit.py` 里验证过并用于实际审计判断，但没有回填到 `full-status.sh`——同一个仓库两套口径，容易在真正需要快速判断的时刻误导决策。**低风险、高价值，可以立即修。**

### P1 · 架构债务（不阻塞，但持续放大维护成本）

#### 债务 #3：`legacy_extensions_json` — TOML 里嵌了一整块 JSON 字符串

`config.toml` 第 2 行 `legacy_extensions_json` 字段塞进了完整的 `engine_policy`/`fallback_metadata`/`omlx_app_metadata` 等结构，本该是 2026-08-10 从外置卷紧急迁移（macOS TCC 权限问题）时的**过渡态**，现在事实上已经变成永久态。这块内容拿不到 TOML 的 schema 校验、拿不到 lint、拿不到 diff 友好性，任何人工编辑都是在裸改一个被转义过的 JSON 字符串。

#### 债务 #4：placement 组合爆炸

18 个逻辑模型 × 最多 3 个后端 = 37 个 placement，几乎每次新增/淘汰模型都要同步改 3-4 处（`[[models]]`、多个 `[[placements]]`、`policies.fallbacks`、`policies.ollama_fallbacks`）。今天之前审计抓出的死链问题（`qwen3.5:9b` 不存在、`gemma-4-26b` 自引用死链等）本质上都是这套纯人工同步机制迟早会漂移的必然结果，不是一次性修完就完事的。

#### 债务 #5：y7000p 的 ollama backend 平台标注错误

`config.toml` 里 `y7000p-rtx4070-8g-ollama` 的 `lms_platform = "macos"`——Windows 节点被标成了 macOS。ollama kind 大概率没真正读这个字段，属于卫生债，但容易在将来某次改动里绊到人。

#### 债务 #6：MBP 主力节点几乎不用常驻策略

`config.toml` 里 `resident_models = ["embedding"]`，oMLX App 承载的 17/18 个模型全部 `resident=false`、按需冷启动。今天在 mac-mini 上验证过常驻模式的效果（gemma-4-e4b 常驻后端到端 3.4 秒出结果，对比冷启动通常 8-60 秒）。MBP 是 128GB 统一内存的主力节点，却几乎没用上这个已验证有效的模式——是当前性价比最高的性能优化方向。

#### 债务 #7、#8：此前会话已记录、今天复核仍然成立的两项

- **探针无真正取消机制**：探测超时不会终止 LM Studio 侧的孤儿生成，会持续烧 CPU（8/20 深夜卡死事件的根因之一）
- **跨后端/同后端内存预算不感知**：128G 统一内存下，多个大模型可能被两套独立的内存看护逻辑分别放行、叠加击穿（8/20 实测 LM Studio 单进程同时驻留两个模型打到 510MB free 的先例）
- **`reload_daemon()` 半吊子热重载**：诚实度已修（`88a5ba1`，不再谎报 reloaded），但真正的原子对象图热替换仍未做，config 改动生效依然要整体重启 daemon

### P2 · 运维收尾债务

- **tailscaled 僵尸 extension 未清理**：brew tailscaled 已 launchd 持久化跑通（今天验证 KeepAlive 自愈），但 Tailscale.app 官方 system extension 仍卡在 `NoState` 僵尸态，不影响当前功能，占用系统扩展槽位，建议下次重启机器时顺手清理或重装 Tailscale.app
- **AetherForge 生产部署落后 dev**：pinned 部署 `aetherforge-final-ae3570f` 落后 dev 若干 commit（含 socket 路径修复），是否升级是发布决策，非阻塞但持续累积漂移
- **`omlxc doctor` 观察到三后端同时 inventory_drop**（mac-mini 45→19、MBP omlx-app 38→16、y7000p 44→19）：本次是单次快照观察，未确认是探测层新的残留问题还是恰好撞上其他后端正忙的巧合，列为监控项，下次复现时应抓取更细粒度 timeline 再定性

---

## 三、优先级路线图

**立即可做（低风险高收益）**
- [ ] 修 `full-status.sh` 内存口径，回填 `safe_audit.py` 已验证的公式
- [ ] y7000p LM Link 配对问题：等你确认是否现在处理（涉及改动 Windows 机器状态）

**本周内（中等改动量）**
- [ ] MBP 常驻策略扩展：挑 1-2 个高频模型（如 `coding`/`vision`）从 `resident=false` 改 `true`，复刻今天在 mac-mini 上验证过的常驻收益
- [ ] `legacy_extensions_json` 拆解为独立 TOML section 或独立文件，结束「过渡态即永久态」

**需要专门评估的架构级改动**
- [ ] 探针取消机制（涉及 LM Studio 侧生成任务的主动中止协议）
- [ ] 跨后端内存预算协调层
- [ ] 真正原子的热重载（对象图整体替换 + 不打断在途 job）

---

## 四、给你的直接结论：Windows (y7000p) 现状

Tailscale 和 LM Studio 都在正常运行、可达（局域网直连，6-14ms）。它自己端口 1234 的 LM Studio 服务器活着，也确实挂着一批真实模型（`qwen/qwen3.5-9b`、OCR、whisper、kokoro 等）。**但它的 `lms` 命令行控制通道当前被远程配对到了 mac-mini**——这是今天深度审计时才挖出来的，光看界面看不出来。这也解释了一个历史疑点：即便 y7000p 之前长期离线，`config.toml` 里给它配置的受控加载策略事实上从未在它自己身上真正生效过，因为控制通道从一开始就没对准过自己。
