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

#### 债务 #1：y7000p 的 SSH 控制通道被错误配对到 mac-mini（今日新发现，**已修复**）

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

**处置记录**（用户确认后执行，同一会话内完成）：

1. `ssh xia@100.64.43.36 'lms link disable'` — 解除 LM Link 配对
2. `lms link disable` 未立即生效（CLI 有缓存的连接状态），`lms server stop` + `lms server start` 重启后 `lms ps` 才回归本机真实状态（`No models are currently loaded`）
3. **意外副作用**：`lms server start` 默认 `--bind 127.0.0.1`（仅本机回环），而此前（LM Link 配对期间）server 是监听 `0.0.0.0`（对外可访问）。重启后外部 HTTP 全部超时（`netstat` 确认只监听 `127.0.0.1:1234`）。补充 `lms server start --bind 0.0.0.0` 后恢复对外监听
4. **顺带发现并清理**：解除配对后 `lms ls` 显示 y7000p 真实本地只有 10 个模型（39.23GB），此前 HTTP `/v1/models` 看到的 19 个模型里有一半是 LM Link 跨设备合并视图的假象（来自 mac-mini/MBP）。`config.toml` 里 y7000p 的 3 个 placement 中，`embed-bge-m3--y7000p...`（指向不存在的 `bge-m3-mlx`）和 `baai-bge-reranker...--y7000p...`（指向不存在的 `baai-bge-reranker-v2-m3-mlx`）是从 mac-mini 抄错的死配置，已删除；`mythos-fast--y7000p...` 的 `backend_model_id` 修正为真实存在的 `qwythos-9b-claude-mythos-5-1m`（原来多了个不存在的 `-mlx` 后缀）

**端到端验证**：`lms ps` 显示 DEVICE 从 `MacMini-M4` 变为 `Local`，context/TTL 精确匹配下发参数；`mythos-fast--y7000p-rtx4070-8g-lm_studio` placement 探测转绿；直接对 y7000p 真实 chat 请求 200 + 正确生成内容；全程确认 mac-mini 状态零干扰。

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
- [x] 修 `full-status.sh` 内存口径，回填 `safe_audit.py` 已验证的公式
- [x] y7000p LM Link 配对问题：已解除配对 + 修正 config.toml 死配置，端到端验证通过

**本周内（中等改动量）**
- [ ] MBP 常驻策略扩展：挑 1-2 个高频模型（如 `coding`/`vision`）从 `resident=false` 改 `true`，复刻今天在 mac-mini 上验证过的常驻收益
- [ ] `legacy_extensions_json` 拆解为独立 TOML section 或独立文件，结束「过渡态即永久态」

**需要专门评估的架构级改动**
- [ ] 探针取消机制（涉及 LM Studio 侧生成任务的主动中止协议）
- [ ] 跨后端内存预算协调层
- [ ] 真正原子的热重载（对象图整体替换 + 不打断在途 job）

---

## 四、Windows (y7000p) 现状：已修复

Tailscale 和 LM Studio 都在正常运行、可达（局域网直连，6-14ms）。它自己端口 1234 的 LM Studio 服务器活着，真实本地有 10 个模型（39.23GB）。控制通道被远程配对到 mac-mini 的问题已解除，`config.toml` 里从 mac-mini 抄错的死配置已修正为 y7000p 真实拥有的模型 ID，端到端真实推理验证通过（RTX4070 8GB 上跑 9B 模型，~19s 完成一次短生成，符合预期）。

## 五、附：本次修复过程中反复出现的仓库异常（需要你关注）

处理这次修复期间，`omlxc` 本地仓库连续两次被静默 checkout 到旧提交（`main → e3cec15 → main → e3cec15 → 7615b5c`），文件内容一度回退到早于本次会话所有改动的状态。两次都确认 `origin/main` 完好、无数据丢失，`git checkout main` 即可恢复。

reflog 显示这个模式很规律（在两个特定提交间反复横跳，且间隔很短），同时 `ps aux` 里有一个常驻的 `oh-my-claudecode` 插件桥接进程（`bridge/mcp-server.cjs`），`.omc/` 目录下的状态文件也在持续变化。**怀疑是这个插件的某个后台功能在做仓库快照/对比时误 checkout 了 omlxc**，但这超出本次审计范围，未深入排查插件内部逻辑。建议你留意：如果之后还遇到"改动莫名消失"的情况，先检查 `git reflog` 和 `origin/main`（大概率数据都还在，只是本地检出指针被挪动了），必要时可以考虑暂时关闭该插件观察是否复现。
