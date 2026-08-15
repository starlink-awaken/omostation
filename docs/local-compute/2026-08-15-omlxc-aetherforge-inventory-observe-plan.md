---
status: active
lifecycle: plan
owner: architecture-team
last-reviewed: 2026-08-15
review-state: grilled
---

# omlxc × AetherForge 库存观测落地规划

> Grill-me Q1–Q8 已锁（均为推荐项 A）。  
> 调查：`.omo/_knowledge/audits/omlxc-model-discovery-current-state-2026-08-15.md`  
> omlxc 已合：`omostation-omlxc#28` → `214d038`（3.0.15）  
> 主仓指针已合：`omostation#1515`

## 0. 一句话

3.0.15 已经会在 adapter 库存悬崖时打 `inventory_drop`；本计划只做两件事：**把本机 daemon 换成会告警的版本**，以及 **让 AetherForge 只读看见这条警告**，不改存活探针、不上云政策、不改聊天错误体。

## 1. 已锁契约

| # | 决定 |
|---|---|
| Q1 | 范围 = 运维收口 + AF 只读转发 `warnings` + 文档一句。不做 set-diff、`models reconcile`、T1-20 |
| Q2 | 两本手册：这台机先升级；可疑空库机先改 App 目录再启 3.0.15 |
| Q3 | `GET /health` 一字不改。新面 `GET /v1/compute`。9290 不因库存变红 |
| Q4 | 不改 hybrid 云 fallback |
| Q5 | omlxcd 不可达时 `/v1/compute` 仍 200，`warnings: []`，`omlxc: unavailable` |
| Q6 | 两段串行：段 1 升级验收；段 2 一个 AetherForge PR |
| Q7 | 段 2 不改 `/v1/chat/completions` / SSE 错误体 |
| Q8 | `/v1/compute` 鉴权与 `/v1/models` 相同（有 key 要 Bearer；无 key 的 loopback 放行） |

硬约束（沿用调查，不重开）：不扫盘、不改 App 配置、不新公共端口、不绕过 AetherForge、CLI 不读 daemon SQLite、`doctor --direct` 不看高水位。

## 2. 现状（2026-08-15 实测）

| 面 | 事实 |
|---|---|
| omlxc origin/main / 主仓 gitlink | `13d240d`（#29 投影告警，含 3.0.15 / #28） |
| 本机 `omlxc --version` + LaunchAgent | **v3.0.15**（`~/.local/bin/omlxcd`） |
| `omlxc status --json` | `status=ready`，**`warnings: []`**（满库，高水位已种子） |
| `omlx app sync --apply` | 目标 23 · 需更新 0 · 需清理 0 |
| `models list` / `app-models/` | 同一组 23 个逻辑 ID（含 `coding` / `coding-fast` / `coding-next` / `deepseek-v4-*`） |
| `127.0.0.1:9290/health` | `{"status":"ok","service":"aetherforge-openai-proxy"}` |
| `OmlxcClient` | `route_plan` / `list_models` / chat / embed / **`health()`**（段 2） |
| `ModelGateway.health()` | 扫旧 per-port `/v1/models`，不是 omlxcd |
| `/health` 中间件 | 与 `/` 一起免鉴权；Pi / OMP 准入认这个身份 |

根因链（已修代码、未修运行）：App `app-models/` 是 gitignore 的本机投影；cutover 后若不跑 `omlx app sync --apply`，adapter `list_models()` 仍成功但条数塌缩；`models list` 仍是配置规范名所以别名还在。3.0.15 用高水位条数悬崖告警；**没装上就等于没修。**

## 3. 目标架构（本增量之后）

```
消费者 / 脚本
  → GET 127.0.0.1:9290/health     身份：门面活着（不变）
  → GET 127.0.0.1:9290/v1/compute 观测：omlxc 可达性 + warnings
  → POST /v1/chat/completions     推理：政策不变

AetherForge OmlxcClient.health()
  → UDS GET /api/v1/health
  → 只转发 allowlist 字段

omlxcd CatalogProbe
  → 成功 list_models 比高水位
  → health()["warnings"]
```

`/v1/compute` 成功体（建议）：

```json
{
  "omlxc": "ok",
  "omlxc_mode": "active",
  "warnings": [
    {
      "code": "inventory_drop",
      "node_id": "…",
      "backend_id": "…",
      "baseline": 10,
      "current": 6
    }
  ]
}
```

`omlxc` 取值：`ok` | `unavailable` | `timeout` | `invalid`。daemon 挂了：`omlxc=unavailable`，`warnings=[]`，HTTP 200。只转发 `code=inventory_drop` 且仅上述四字段；丢弃未知键和模型名。

`omlxc_mode` 为 `legacy`/`shadow` 时仍读 UDS（观测与路由模式正交）。读失败走同一降解，不把 9290 打红。

## 4. 段 1 — 本机升级验收（无代码）

### 4.1 手册甲：这台机（库目前是满的）

1. 确认当前：`omlxc --version` 为 3.0.14；`omlxc models list` 条数正常。  
2. 把 **3.0.15** 装进 LaunchAgent 真正执行的 `~/.local/bin/omlxcd`（以及同前缀的 `omlxc`）。不要只改 git checkout 却让 LaunchAgent 继续跑旧二进制。安装来源：omlxc `214d038` 打的 wheel / `uv sync` 后拷到 `~/.local/bin`。  
3. `omlxc daemon restart --yes --confirm-impact`（R2）。  
4. 验收：
   - `omlxc --version` → `3.0.15`
   - `omlxc status --json` 的 `data` 含 `warnings`（本机满库时期望 `[]`）
   - `status` / `degraded` 仍表示存储健康，不因空 `warnings` 变红
   - `curl -sS http://127.0.0.1:9290/health` 仍是原身份 JSON  
5. **必须**确认 `~/omlx/app-models` 是 live 投影，不是 `releases/v3.0.14/app-models` 空目录。`omlx app sync --apply` 覆盖 `models.json` 里**全部**有有效 `models-active` 软链的键（本机实测 23/0，0 个被跳过）。omlxc #29 已在每次非 `app` 命令上警告投影塌陷，但仍不自动改写 App 目录。

### 4.2 手册乙：可疑 / 已知空库机

**先修目录，再启 3.0.15。** 否则第一次成功探测会把偏低条数写成高水位，这次误指永远不告警。

1. 看 App 实际模型目录；cutover 后补：`python3 ~/omlx/bin/omlx app sync --apply`。  
2. 确认 App / adapter 库条数恢复。  
3. 再走手册甲的安装与重启。  
4. 不要在已知空库上先起 3.0.15「等它自己告警」——它不会。

### 4.3 段 1 完成定义

- 本机 CLI + 正在跑的 `omlxcd` 都是 3.0.15。  
- `status --json` 有 `warnings`。  
- 9290 `/health` 未变。  
- 手册乙适用的机器：sync/改目录发生在**第一次** 3.0.15 成功探测之前。

## 5. 段 2 — AetherForge 观测 PR（一个 PR）

仓库：`omostation-aetherforge`（子模块 `projects/aetherforge`）。**不改 omlxc。**

### 5.1 改动面

| 文件 | 做什么 |
|---|---|
| `packages/gateway/src/llm_gateway/omlxc_client.py` | `OmlxcHealth` + `async def health()` → `GET /api/v1/health`。socket/超时报 `OmlxcError`（调用方捕获后降解，本方法保持 typed） |
| `packages/gateway/src/llm_gateway/openai_proxy.py` | `GET /v1/compute`；`create_app` 注册；模块头注释补一行。**不要**把 path 加入免鉴权名单 |
| `packages/gateway/src/llm_gateway/gateway.py` | 薄封装：调 client、裁剪 warnings、映射 `omlxc` 状态；**不要**改 `ModelGateway.health()` 的旧 per-port 语义 |
| `packages/gateway/tests/` | `/health` 形状回归；`/v1/compute` ok / unavailable / 转发 / 鉴权 |
| `docs/ARCHITECTURE.md` | 一句：库存观测走 `/v1/compute`，存活仍是 `/health` |
| `docs/local-compute/omlx-cluster-architecture.md`（omostation） | 可靠性节补一句 inventory-drop + `/v1/compute`。可与 AF PR 同轮或紧随的 omostation 文档 commit，**不要**和 AF 代码混在一个 submodule+指针 PR 里 |

### 5.2 明确不改

- `handle_health` / `GET /`  
- `cloud_fallback_allowed` 与 hybrid 分支  
- `_openai_error_payload`、SSE 错误  
- 新 BOS URI、新端口、读 omlxc SQLite、扫盘、改 App 路径  
- `AETHERFORGE_OMLXC_MODE` 的路由语义  

### 5.3 段 2 测试最低集

1. `GET /health` 仍精确为 `status=ok` + `service=aetherforge-openai-proxy`，且无 `warnings`。  
2. omlxcd 返回悬崖时，`GET /v1/compute` → 200，`omlxc=ok`，一条 `inventory_drop`，无模型名。  
3. 无 socket / 超时时 → 200，`omlxc=unavailable|timeout`，`warnings=[]`。  
4. 配了 API key：无 Bearer → 401；`/health` 仍免鉴权。  
5. 未知 warning `code` 或多余键被丢掉。

### 5.4 段 2 完成定义

- AF PR 合入其 `main`。  
- 本机 9290 重启后：`/health` 不变；`/v1/compute` 在 3.0.15 满库时 `warnings: []` 且 `omlxc=ok`。  
- 人工或测试注入悬崖（测试替身即可，不必真把 App 目录砸空）能在 `/v1/compute` 看见 `inventory_drop`。

## 6. 节奏与验收闸

```
段 1（人 / 本机）          段 2（工程）
  装 3.0.15                 OmlxcClient.health
  restart omlxcd            GET /v1/compute
  status 见 warnings  ──►   测试 + 文档
  /health 未变              AF PR → 指针（若主仓要跟上）
```

段 1 不等段 2。段 2 不改 omlxc。主仓 AF 指针另走 `submodule-pointer-close`，不要和代码 PR 捆死。

现场联调（两段都完成后，可选）：

```bash
omlxc --version                    # 3.0.15
omlxc status --json                # data.warnings 存在
curl -sS http://127.0.0.1:9290/health
# 有 key 时带 Authorization
curl -sS http://127.0.0.1:9290/v1/compute
```

## 7. 风险

| 风险 | 处置 |
|---|---|
| 只更新了 git / CLI，LaunchAgent 仍跑旧 `~/.local/bin/omlxcd` | 段 1 以 `--version` + `status` 是否有 `warnings` 为准，不以 checkout 为准 |
| 空库机先启 3.0.15 | 手册乙；已种子偏低则人手修目录，本次不告警（已知 leftover） |
| 把 `/v1/compute` 误免鉴权 | 测试 4；中间件名单只保留 `/health` 与 `/` |
| 把 `inventory_drop` 当成 9290 不健康 | Q3/Q5；观测 200 + 字段，不 5xx |
| 改 OpenAI 错误形 | Q7；段 2 不做 |
| 共享工作区仍停在旧 omlxc 分支 | 段 2 在隔离 worktree / 独立 clone 改 AF，不要在共享树上切 omlxc |

## 8. 明确不做（下一份方案再 grill）

- 警告 JSON 里的模型名 / set-diff  
- `models reconcile`  
- `doctor --direct` 读高水位  
- hybrid 因 `inventory_drop` 禁云  
- `BET-Y1Q2-T1-20` 发版自动指针 PR  
- `BET-Y1Q4-T6-01` AetherForge 并入 runtime  
- 新探测循环、改 `models list` 为 adapter 原始 ID  

## 9. 「覆盖到所有本地模型」复审（2026-08-15，对照 #26/#29/#32）

「全部本地模型」= live `~/omlx/conf/models.json` 的 23 个键，**不是** AF 公共别名表，也不是仓库里那份已改名的 `projects/omlxc/conf/models.json`。

| 面 | 是否覆盖 23 | 证据 |
|---|---|---|
| `omlx app sync --apply` | 是，0 跳过 | 目标 23 / 更新 0 / 清理 0；`app-models/` 23 条软链 |
| 本机 TOML `*-omlx-app` placement | 是（+1 故意 fallback） | 24 条：23 个 `backend_model_id` 与 App id 1:1，外加 `coding-fast-local-fallback → coding` |
| `omlxc resolve coding / coding-fast / coding-next` | 是 | 三条都 `available=true` `ready=true`，本机 placement 各自指向自己的 App id |
| 仓库 `projects/omlxc/conf/models.json` | **分叉** | #26 把逻辑名改成 `qwen-3.5-9b-flash/pro`；本机仍是物理名 `deepseek-v4-flash/pro`。不要用仓库文件覆盖 live，否则 sync 会投影不存在的键 |
| AF `aliases.yaml` | 故意不全 | 只暴露意图名（`coder` / `triage` / `mid`…）。23 个 App id 走 omlxc catalog，不靠 AF 别名枚举 |
| AF #32 体积表 | 曾漏 live 名 | #32 把 fallback 体积键改成 `qwen-3.5-9b-*`。段 2 回补 `deepseek-v4-*`，双 ID 并存，MemoryGuard 两边都能准入 |

结论：sync 这条路径本来就覆盖全部 23 个 live 模型；方案原先「满库则不必 sync」是错的（#29 就是为这次 cutover 空投影写的）。AF 不必、也不该把 23 个物理 ID 做成公共别名。

## 10. 下一步

1. ~~段 1 手册甲~~ 已在本机完成（3.0.15 + sync 23/0 + resolve 三元）。  
2. 段 2 在 **aetherforge 隔离树** `feat/v1-compute-inventory-warnings` 落地后开 PR。  
3. 段 2 合入后再决定是否 bump 主仓 `projects/aetherforge` 指针。  
4. 仓库 vs live 的 `qwen-3.5-9b-*` / `deepseek-v4-*` 命名分叉另开方案，不在本增量改 live `models.json`。
