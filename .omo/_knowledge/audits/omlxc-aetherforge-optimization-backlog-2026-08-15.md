# omlxc / oMLX App / AetherForge 联动调优台账 — 2026-08-15

> **触发**: 用户要求"对 omlxc 和 omlx app 做全面调优，配置做最优解…结合 AetherForge 做好适配和联动优化"，
> 授权范围"全面铺开，你自主判断优先级"。
> **执行约束（本轮实测）**: 诊断 agent 的 Bash 沙箱屏蔽了几乎所有 socket/网络操作
> （Unix socket connect / loopback TCP connect / git 走的本地代理 127.0.0.1:7890 /
> tailscale CLI 读本地 daemon 偏好），本轮拿到的任何"实时探测"结果（daemon RPC、
> tailscale status、backend probe）都不可信，只有**纯文件读取**的结论可信。
> 因此本轮只做了静态配置审计 + 已落地的 1 处代码修复，其余项列为待办，标注了
> "需要真终端复核"的项不要直接采信之前 `omlxc doctor --direct` 里的 tailscale/backend
> 失败结论——那很可能也是同一个沙箱假阳性（app-models resolve E200 已经实锤过一次）。

## 已完成

| 项 | 状态 | 证据 |
|---|---|---|
| app-models 扁平投影塌陷 (release 切版本后无人重建) | 已定位根因 + 代码修复就绪，待用户在真终端 `app sync --apply` 落地 | `.omo/_knowledge/audits/omlxc-model-discovery-current-state-2026-08-15.md`；修复见 [projects/omlxc/bin/omlx](../../../projects/omlxc/bin/omlx) `_app_projection_health` + [README.md](../../../projects/omlxc/README.md) 新增"Legacy release cutover"节 |

## 待办（按老王自主排序，优先级从高到低）

### P0 — 需要用户在真终端复核，不要信这轮的沙箱结果

1. **`omlxc doctor --direct` 报的 `tailscale: identity check failed` + 4 个远端 backend `read-only probe failed`（mac-mini/y7000p 的 lm_studio/ollama）是否真实。**
   - 静态审计：`~/.config/omlxc/config.toml` 里 mac-mini / y7000p 的 `[nodes.tailscale]` 段（peer_id / public_key / magic_dns_name / allowed_ips / allowed_http_ports / allowed_ssh_users）**字段齐全，格式看起来正常**，没有发现明显配置错误。
   - 但本轮 `tailscale status --json` 在这个沙箱里直接报 `Failed to load preferences`（读本地 daemon 偏好失败），跟 unix socket / TCP 被拦的模式完全一致——大概率也是沙箱假阳性，不是真故障。
   - **动作**：用户自己跑一遍 `omlxc doctor --direct --json`，如果 tailscale/backend 仍然失败，再具体查 peer_id/public_key 是否与两台机器当前的 `tailscale status` 输出一致（key 轮换、机器重装过 tailscale 都会导致 public_key 漂移）。

### P1 — 静态审计已确认健康，无需改动

2. **AetherForge 别名层**（[aliases.yaml](../../../projects/aetherforge/packages/gateway/src/llm_gateway/aliases.yaml)）：设计成熟，`coder/coder-fast/coder-next → coding/coding-fast/coding-next` 等映射与 omlxc `models.json` 键完全对齐，fallback 链（App → LM Link → Ollama）文档化清楚，`unsupported` 段如实记录未覆盖项而非假装齐了。**不需要动。**
3. **oMLX App 请求默认值**（`models.json` → `omlx_app.request_defaults`）：`chat_template_kwargs.enable_thinking=false` + `thinking_budget=0` 已经是关闭思考链省 token 的合理默认，跟各模型条目里 `chat_template_args.enable_thinking=false` 一致，没有冲突。

### P2 — 需要更多信息才能判断，下一轮再深入

4. **`engine_policy.nodes.*.primary/fallback` 排序是否是当前三机负载下的最优解**——需要用户实际的模型体积/显存/延迟数据，不能瞎猜"最优"。目前 mbp 是 `omlx_app` 主力，macmini/y7000p 是 `lmstudio` 主力 + `ollama` 兜底，这个分层本身合理，但没有实测数据支撑"是不是最优"。
5. **`models.json` 里 23 个模型的 `params`（temp/kv_bits/max_tokens）是否需要按角色重新调**——这属于"使用体验最优解"，涉及具体使用场景（编码 vs 推理 vs 视觉），需要用户明确几个高频场景的具体诉求（比如 `coding-next` 51G 巨型仓库是不是常驻内存合适、要不要收紧 `max_tokens` 4096）。

## 下一步建议

P0 复核完、P1 确认无误后，P2 两项需要用户提供更具体的"最优"定义（哪个场景优先延迟/哪个优先吞吐/内存预算上限），否则会变成瞎调。建议用户复核完 P0 后开一个新的、聚焦的调优 session，带着实测数据来，而不是这轮基于静态审计的空转猜测。
