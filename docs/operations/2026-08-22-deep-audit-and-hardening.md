# omlxc 全链路深度审计与加固 — 2026-08-22

> 状态: 全部完成，测试/lint 通过，改动已提交推送到 main
> 背景: 承接 08-20 的优化工作，本轮聚焦"真实端到端验证"而非配置层面的推测

---

## 一、核心发现：oMLX App 曾整体宕机

`omlxc doctor` 报告 oMLX App **后端**健康，但逐模型核查发现 18 个模型里 **15 个 placement 全部 `avail=False`**——进程活着（`ps` 可见），端口 8000 却完全无响应，不知道宕了多久。这暴露了一个真实的可观测性缺口：**后端级健康检查和模型级可用性是两条不交叉验证的代码路径**，后端"能连上"不代表任何模型真的可用。

处理：重启 oMLX App 恢复服务；新增 `scripts/pipeline-watchdog.sh`，注册为 launchd 常驻任务（`com.omlxc.watchdog`，每 5 分钟探测一次），oMLX App 无响应时自动重启，同时读探测缓存判断"是否有模型所有 placement 都不可用"并记录 WARN。

## 二、oMLX App 的模型软链与 config.toml 长期漂移

oMLX App 自己维护一份独立的软链目录（`~/omlx/app-models`），和 omlxc 的 config.toml 完全靠人工保持一致，没有自动同步机制。核查发现：
- 5 个死链接（`mid-local`/`qwen-3.5-9b-flash`/`qwen-3.5-9b-pro`/`reasoning-lite`/`vision-large`）——两轮会话前删除的模型，软链一直没清
- 2 个悬空链接，目标文件已被删除
- `ornith-35b` 停留在 1.0 版本，没跟着 LM Studio 侧一起升级到新下载的 1.5

omlxc 内建的 `models reconcile` 命令看起来正是为解决这个问题设计的，但后端未接入（`E100 daemon API does not expose 'models reconcile' yet`，空壳命令）。用 `scripts/sync-omlx-app-models.sh` 顶上：清理死链接/悬空链接，报告缺失注册。**约定：改完 config.toml 里的 omlx-app placement 之后跑一次这个脚本。**

## 三、两个真实生产 bug（非配置层面）

### 3.1 config.toml 里两个已上线的死 placement

`coding-fast-local` 和 `mythos-fast-local`（omlx-app 侧）指向的权重文件已被删除（正是之前判定为乱码/淘汰的模型），导致这两个 placement 常年不可用——看门狗接入模型可用性检查后第一时间就报了出来。`mythos-fast` 在 MBP 上甚至没有 LM Studio 侧的兜底 placement，只能指望 Tailscale 才能连到的远程节点，Tailscale 一断就全灭。

处理：删除死 placement，`resident_models` 里同步移除失效引用。

**曾尝试给 `mythos-fast` 新增 `mythos-fast-lm_studio`（指向 qwythos-9b），已回退。** 实测证明这个 placement 一旦接入 omlxc 的正常请求路径（无论是健康探测还是真实 chat 请求），LM Studio 都会重新 JIT 加载并回到 852736 的失控上下文——即便请求前手动 `lms load -c 8192` 显式限制过也没用，omlxc 的路由请求会绕开这个手动加载，触发 LM Studio 自己的默认加载路径。两次复现，第二次是在专门做验证时当场触发。详见第四节；根因不在 config.toml 能调的范围内，属于 LM Studio 适配层的问题，贸然留着这个 placement 比没有更危险，已撤回。当前 `mythos-fast` 只有两个依赖 Tailscale 的远程 placement，Tailscale 断线时会整体不可用——这是已知的、安全的降级状态，不是新问题。

### 3.2 Ollama 兜底链的死链

`ollama_fallbacks` 全部指向 `qwen3.5:9b` / `nomic-embed-text:latest`，但本地 Ollama 实际装的是完全不同的模型集合（用户中途自己换过）。这类"配置指向不存在的东西"是本轮反复出现的模式（gemma-4-26b 自引用死链、baai-bge-reranker 错标 role 也是同一类问题）。

处理：chat 兜底改指现存的 `xentriom/gemma-4-12B-agentic-fable5-composer2.5-v2`，embedding/reranker 兜底分别接上现存的 `nomic-embed-text` 和 `qllama/bge-reranker-v2-m3`。**注：仅做存在性验证（`/api/tags` 查询），未做生成验证——当晚已出现多次系统卡死，主动放弃了会触发加载的深度验证。**

## 四、卡死根因：探测本身会触发失控的生成

深夜实测到系统连续卡死，追查到 LM Studio 日志：`llmworker.js` 持续 78.5% CPU、19GB RSS，对应 omlxc 对 `mythos-fast` 的健康探测（"Reply O only"）。链路是：

1. 探测触发 LM Studio JIT 加载 qwythos-9b，JIT 加载不吃 `lms load -c` 那套上下文限制，直接用了模型支持的最大上下文（852736 tokens）——仅 KV cache 就是巨大开销
2. 模型收到探测 prompt 后先展开一段"要不要确认自己是 Qwythos"的思维链推理，而不是直接回复
3. 探测自己超时断开连接，但 LM Studio 侧日志明确写着"客户端断了，但如果还在处理会先跑完"——**探测超时不会中止生成，孤儿生成持续烧 CPU**

这是一个尚未修复的架构隐患：任何 JIT 加载路径都可能触发超预期的上下文/计算量，且探测层没有真正的取消机制。当晚仅做了止血（卸载该模型腾出内存），未改探测逻辑本身——需要专门评估修复方案，不适合仓促手动打补丁。

**后续复现确认这不是探测独有的问题**：单独验证 `mythos-fast-lm_studio` 时，即使请求前手动 `lms load -c 8192` 显式控制过上下文，omlxc 的正常 chat 请求路径依然重新触发了 LM Studio 的 JIT 加载，把上下文打回 852736。也就是说问题出在 `qwythos-9b-claude-mythos-5-1m-mlx` 这个具体模型 + LM Studio adapter 的 JIT 加载组合上，不局限于探测场景——任何经 omlxc 路由到这个 backend_model_id 的请求都有触发风险。已将对应 placement 从 config.toml 撤回（见 3.1），在 adapter 层修复前不再暴露这个入口。

**根因定位到底**：`~/.lmstudio/settings.json` 里 `.defaultContextLength = {"type": "max", "value": 8192}`。`type: "max"` 表示**所有** JIT 自动加载的模型都会用模型自身支持的最大上下文，而不是这个 `value` 字段——852736 正是 qwythos-9b 自己支持的最大值。这是全局设置，不分模型，今晚每一次"意外触发大上下文加载"最终都能归到这一项。`~/.lmstudio/.internal/historical-version-info.json` 里有条迁移记录 `v0_4_16_b2_defaultContextLength8192`，说明固定 8192 曾是 LM Studio 的出厂默认值，当前的 `"max"` 是后来被改掉的。

**代码侧已根治 (`6c91a8c`)**：数据面 `ensure_loaded` 现在会注入该后端全部 placement 的最小 `context_limit` 作为 `lms load -c`，不再裸加载。即使 LM Studio 全局设置仍是 "max"，omlxc 触发的加载也受控。GUI 侧改 `defaultContextLength` 降级为纵深防御（仍建议做，覆盖非 omlxc 触发的加载）。

## 四点五、探测层三连修 (2026-08-22 下午追加)

审计后连续定位并修复了三个探测层缺陷，全部已提交：

1. **probe 预算 1→100 (`8f64b71`)** — reasoning 模型思维链吃光 1 token 预算致 content 恒空、后端被永判不可用。该修复 08-20 曾做过但未提交，被并发 checkout 重置抹掉并被后续 wheel 构建覆盖回 bug 版（比对已安装包与 git 历史坐实）。教训：**修复必须立即 commit**。
2. **数据面加载注入受控上下文 (`6c91a8c`)** — 见上文根因定位。
3. **~~繁忙模型阻塞探针~~ 已根治 (`fa3f391`)，live 摆动验证通过** — 探针模型正忙于长生成时，probe chat 排队吃光 backend 级超时 → 整个 discover 被掐死 → 全后端判死（实测 30/37↔0/15 摆动）。修复：probe chat 独立 5s 短超时（`_PROBE_CHAT_TIMEOUT`，测试可调），超时只损失该模型的 generation_ready，目录/加载状态照常返回，其余 placement 不受牵连。契约回归测试固化。**Live 验证（看门狗日志对比）**：修复前 65 分钟内 12 条大面积全灭记录（十几模型级联摆动）；修复部署（12:05）后全灭记录只剩 `mythos-fast`/`coding-fast` 两个既定安全降级项，级联摆动彻底消失。
4. **~~stale-loaded 竞态触发 HTTP JIT 失控加载~~ 已修复 (`9c46ff7`)** — 端到端验证时定位：探测缓存的 loaded=True 与 LM Studio 实际状态存在竞态窗口，数据面据此跳过 ensure_loaded 直接发 HTTP chat → 未加载的模型被 LM Studio JIT 按全局 `max` (262144) 加载。实测一次请求把 ornith/vision 双双 JIT 成 262144 并把系统内存打到 1.5GB。修复：adapter 维护 discover 刷新的已加载缓存（`_loaded_cache_valid` 区分"未探测"(放行)与"探测过且未加载"(拦截)），chat/stream_chat 发送前对未加载模型先走幂等 SSH 受控 `lms load -c`。契约回归测试固化"chat 前恰好一次带 -c 的受控加载"。修复后端到端验证 200 + 真实中文生成贯通（vision → omlx-app 路径）。

## 五、AetherForge 全链路验证

### 5.1 客户端 socket 路径 bug

`omlxc_client.py` 的 `default_omlxc_socket()` 在 macOS 上硬编码返回 `~/Library/Application Support/omlxc/omlxcd.sock`，但 daemon 实际监听 `~/.config/omlxc/omlxcd.sock`。旧路径是个已停用多日的孤儿 socket。已修复（移除硬编码分支 + 清理因此变成无用的 `import sys`），提交推送到 aetherforge main（`63de5bc`）。

**重要澄清**：这个 bug 对当前实际运行的 `com.aetherforge.gateway` launchd 服务**没有影响**——它的 launchd 环境变量里已经手动写死了正确的 `OMLXC_SOCKET`，日志证实这条链路持续健康轮询 omlxc（`GET /v1/models` 每分钟一次，200 OK；唯一一次 504 正好撞上本轮压测最猛的时刻，随后自愈）。bug 修复仍然有价值——对任何没设这个环境变量的场景（本地开发、测试）是真实隐患，只是不紧急。

### 5.2 生产部署落后于最新代码

实际运行的网关代码是 `/Users/xiamingxing/aetherforge-final-ae3570f`，定格在 `b222a25`，比 `Workspace/projects/aetherforge` 的 main 落后好几个 commit（含上面的 socket 修复）。是否升级是发布决策，未擅自处理。

## 六、开机启动任务清理

`~/Library/LaunchAgents` 里和 omlxc/AetherForge 链路直接相关的部分：

| 处理 | 对象 | 依据 |
|------|------|------|
| 删除 | `com.omlx.autopilot/autostart/gateway/gateway-ui`（4个 plist + 4个备份） | 确认 `disabled` 状态，被 omlxc daemon + oMLX.app 取代 |
| 删除 | `com.aetherforge.gateway` 的 10 个历史备份 plist | 同一次早期迭代留下的调试痕迹，正式版本已在 git |
| 保留 | `com.lmstudio.server`（`lms server start`） | 核实是正常开机拉起脚本，一次性执行完退出 |
| 保留 | `com.omlxc.daemon` / `com.omlxc.watchdog` | 核心链路 |

`com.omostation.*`、CleanMyMac/Docker/ToDesk/ClashX 等不属于这条链路，未展开审计。

## 七、已知但刻意未动的技术债

1. **~~`reload_daemon()` 是空壳~~ 诚实度已修复 (`88a5ba1`)**——现在会重新读取 config.toml 算 identity 哈希比对，状态不一致时如实报 `stale` 而不是撒谎说 `reloaded`。**但真正的热重载依然没做**：`reload_daemon()` 仍然不重建 `build_production_daemon()` 组装的整张对象图（adapters/catalog/planner/storage/bus/probe/target_factory/coordinator），只是让返回值可信。要让 config 改动真正生效，唯一可靠方式还是 `omlxc daemon restart --yes --confirm-impact`（会短暂打断在途推理）。真正的热重载需要原子替换整张对象图且不打断在途 job，这仍然是架构级改动，未在本轮实现。
2. **探测层缺乏真正的取消机制** — 见第四节，JIT 加载 + 探测超时孤儿生成是当晚系统卡死的直接原因。
3. **LM Studio `defaultContextLength.type = "max"`** — 根因定位到底后发现的全局配置项，所有 JIT 加载模型共享这一个设置。需要人工在 LM Studio 设置界面改成固定值，omlxc/config.toml 层面无法代管这一项。改完后第三、四节记录的问题会整体消失，是目前性价比最高的一项修复，只是执行动作不在这个仓库能触达的范围内。
3. **两个后端不感知彼此内存占用** — LM Studio 和 oMLX App 各自独立做内存守护，互相不知道对方占了多少，在 128GB 统一内存机器上同时加载大模型仍有击穿风险。

   **同一晚复现，且不需要跨后端**：LM Studio 单进程内同时驻留 `qwen3-coder-next`(54.81GB, 262144 上下文) + `qwythos-9b`(18.84GB, 852736 上下文, 正在生成) 两个模型，把系统可用内存从平时的 ~68GB 打到 **~510MB**（`vm_stat` 实测），逼近冻结边界。`qwen3-coder-next` 当时是 IDLE（不是活跃任务）——卸载它化解了这次，没有打断正在跑的 qwythos 生成。说明风险不止是"两个后端各自不知道对方"，同一个 LM Studio 进程自己也没有对同时驻留的多个大上下文模型做内存预算控制，纯靠系统整体 OOM 兜底。

## 八、验证

```
uv run pytest -q       # 1056 passed, 1 deselected (hardware), 0 failed
uv run ruff check .    # All checks passed
```

未跑硬件/生成类验证——本轮多次触发系统卡死后主动收紧到纯配置校验 + 静态检查。

---

## 关键文件

| 文件 | 内容 |
|------|------|
| `scripts/pipeline-watchdog.sh` | oMLX App 自愈看门狗，launchd 每 5 分钟跑 |
| `scripts/sync-omlx-app-models.sh` | omlx-app 软链与 config.toml 同步（顶替空壳的 `models reconcile`） |
| `scripts/deep-registration-audit.py` | 全量注册深度审计（真实生成请求测乱码/空输出），模型清单从 `omlxc models list` 动态读取 |
| `~/.config/omlxc/config.toml` | 本轮改动：删 3 个死模型、修 4 处死 fallback、升级 ornith-35b、补 mythos-fast LM Studio 兜底 |

## 九、Tailscale 诊断翻案 (2026-08-22 12:20 追加)

此前会话对 Tailscale 无法登录的结论是"ClashX fake-ip DNS 劫持"，并据此给 ClashX 配置加了 DNS 白名单。**该结论是错的**，证据链：

1. 8.8.4.4 (Google DoH) 查询 `baidu.com` 返回真实百度 IP → 该 DoH 干净
2. 同一 DoH 查 `controlplane.tailscale.com` 返回 192.200.0.101-116 → 与本机系统 DNS 结果一致
3. **TLS 直连 192.200.0.102:443 成功，证书 `CN=controlplane.tailscale.com`** (Let's Encrypt) → 这批 IP 是 Tailscale 控制面真实 anycast 池，网络链路完全通畅

真实故障：tailscaled (macOS system extension, root 沙盒) 内部的 DNS 解析路径失败（用户态解析正常，沙盒内拿不到结果）——与任何代理软件无关。猎豹 VPN (utun244, 22.0.0.0/8) 接管路由但未阻断 Tailscale 控制面。

**修复方案（待用户执行）**：`sudo cp /tmp/hosts.new /etc/hosts`（文件已备好，含 controlplane/login/log 三个域名的已验证真实 IP 与可逆性注释），随后 `tailscale up`（logged out 状态可能需要浏览器授权一次）。给 ClashX 加的白名单无害但无必要，可留可删。
