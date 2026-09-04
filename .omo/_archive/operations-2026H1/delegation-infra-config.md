---
lifecycle: contract
owner: governance-team
last_updated: 2026-08-18
title: OpenCode 委托基础设施配置 — delegation-infra-config
type: doc
---
# OpenCode 委托基础设施配置 — delegation-infra-config

> 固化 2026-08-07 委托基础设施（delegation infra）故障修复后的**固定状态**，让修复可存活、可回滚、可复现。
> 故障现象：11 条委托路由失败，子代理"只叙述不落盘"（空 content）。
> 本文档是操作事实记录（当前状态 + 恢复步骤），不是设计文档；所有路径、备份名、命令均为实测。

---

## ⚠️ 调度器是权威写入者（Authoritative Writer）— 2026-08-07 执行中发现

> **重要**：本文档 §1「当前固定状态」是**瞬态手工应用状态**，不是持久事实。`~/.config/opencode/` 下存在自动调度器，会按时间窗重写 `opencode.json` —— 任何手工编辑都是临时的，调度器在下一次切换时覆盖。

### 0.1 已核实事实（实测命令，非推断）

1. **`~/.config/opencode/` 是一个 git 仓库**，调度器的每次切换都留提交：

   ```bash
   git -C ~/.config/opencode log --oneline -5
   ```

   实测 reflog（`.git/logs/refs/heads/main`）含 `chore(model): <PEAK|OFF-PEAK> (<HH>:00) schedule -> <model>` 提交，例如：
   - `chore(model): PEAK (9:00) schedule -> deepseek/deepseek-v4-flash`
   - `chore(model): OFF-PEAK (23:00) schedule -> zhipuai-coding-plan/glm-4.7-flash`

2. **调度器 = `scripts/model-scheduler.sh`**（launchd `com.omo.model-scheduler.plist`，每小时 :05 触发，`RunAtLoad=true`）：
   - **PEAK（09:00–23:59）**：`opencode.json` 顶层 `model` → `deepseek/deepseek-v4-flash`（`small_model` → `zhipuai-coding-plan/glm-4.5-flash`）
   - **OFF-PEAK（00:00–08:59）**：`model` → `zhipuai-coding-plan/glm-4.7-flash`
   - 同时重写 `~/.omo/omo.jsonc` 的 flash-tier agents（hephaestus/explore/librarian/atlas/sisyphus-junior）primary + fallback
   - 写后校验 JSON，成功则 `git commit -m "chore(model): ..."`；校验失败则 `git checkout --` 还原
   - **`dynamic-router.py` 是模型池/评分引擎（生成 `oh-my-openagent-dynamic.json`），不直接写 `opencode.json`**

3. **模型池 `dynamic-router.py` L101–107** 含 `omlxc/coder|coder-fast|reasoner|mid-local|mini-9b|vision|triage`；omlxc 网关探活 `local_gateway_ok()`（docstring 标注 10s 缓存，L28）。

4. **含义**：任何手工编辑 `opencode.json` 都是瞬态的 —— 修复要么在调度器下次切换后**重新应用**，要么修调度器的模型池生成（本计划默认超出范围）。

5. **P1b 删除 mid-local/triage 方向正确（网关无路由 → 空响应），但已被覆盖**。当前 live 状态（2026-08-07 实测 `~/.config/opencode/opencode.json`）：
   - `provider.omlxc.options.baseURL = "http://127.0.0.1:8000/v1"`（L742）
   - `agent.coder.model = "omlxc/coder"`（L19）
   - `provider.omlxc.models` 又出现 `mid-local`（L722；`triage` 本次未回，但模型池仍含，随时可能回来）

6. **端口事实**（两个本机 MLX 服务语义不同）：
   - **8000 = omlx-server**（omlxc 官方服务）：接受 `model` 字段，服务真实模型 id（如 `Qwen3.6-27B-MLX-4bit`），对 `omlxc/coder` 别名返回 `not_found`
   - **8092 = mlx_lm**：拒绝 `model` 字段（提供任意 model → 404 并按 HF 仓库名解析）—— 见 §5

### 0.2 对本文档的读法

§1「当前固定状态」与 §3「恢复/回滚步骤」只对**手工应用的那一刻**成立；持久权威是调度器（`model-scheduler.sh`）。执行任何修复后用 §6 校验，并接受调度器可能再次覆盖 —— 若需长效修复，必须改模型池/调度器生成（超出本计划范围）。

---

## 1. 当前固定状态（瞬态 — 手工应用时点，2026-08-07 实测）

> ⚠️ 本节是 **P1b 修复手工应用瞬间**的状态快照（baseURL=8092 / 5 模型 / deepseek 绑定），**不是当前 live 状态，也不是持久事实**。live 状态与持久权威见 §0（调度器每次切换覆盖手工编辑）。本节保留用于说明修复内容与回滚基线。

### 1.1 `provider.omlxc`（`~/.config/opencode/opencode.json`）

- `provider.omlxc.options.baseURL = "http://127.0.0.1:8092/v1"` — 指向**本机 mlx_lm**（非 LiteLLM 网关 4000 端口）。
- `provider.omlxc.models` 现只含 **5 个**别名，全部与网关路由同步（`IN_BOTH`）：

| opencode 别名 | 网关路由 (model_name) | 后端 |
| --- | --- | --- |
| `coder` | `coder` | MBP MLX · devstral (127.0.0.1:9000/coding) |
| `coder-fast` | `coder-fast` | MBP MLX · holo3 MoE (127.0.0.1:9000/coding-fast) |
| `mini-9b` | `mini-9b` | mac-mini Ollama · qwen3.5:9b |
| `reasoner` | `reasoner` | MBP MLX · GLM-4.7-Flash (127.0.0.1:9000/reasoning) |
| `vision` | `vision` | MBP MLX · Qwen3-VL-8B (127.0.0.1:9000/vision) |

**已删除**：`mid-local`、`triage`。两者在网关 `model_list` 中**没有对应路由**，请求发到网关后无路可走 → 返回空内容（子代理表现为"只叙述不落盘"）。

### 1.2 agent 模型绑定（explore / reviewer / scribe）

| agent | 当前模型（已修复） | 修复前（见 `.bak-omlxfix`） |
| --- | --- | --- |
| `explore` | `deepseek/deepseek-v4-flash` | `opencode-go-b/deepseek-v4-flash` |
| `reviewer` | `deepseek/deepseek-v4-flash` | `opencode-go-b/deepseek-v4-flash` |
| `scribe` | `deepseek/deepseek-v4-flash` | `opencode-go-b/deepseek-v4-flash` |

修复原因：`opencode-go-b` 账号余额不足（Insufficient Balance），改用 `deepseek` 直连（API key 在 `~/.config/opencode/keys/deepseek.txt`）。

> 其余 agent：`coder` → `omlxc/coder`（唯一本地绑定）；`build` / `plan` / `researcher` → `deepseek/deepseek-v4-flash`。

### 1.3 备份文件（`~/.config/opencode/`）

| 备份文件 | 语义 | 关键内容（实测） |
| --- | --- | --- |
| `opencode.json.bak-omlxfix` | **修复前**完整状态 | `baseURL=http://100.96.126.35:4000/v1`；explore/reviewer/scribe = `opencode-go-b/deepseek-v4-flash`；**含** `mid-local`/`triage` |
| `opencode.json.bak-omlxfix-2022` | **删模型前**状态（baseURL + 绑定已修复） | `baseURL=http://127.0.0.1:8092/v1`；绑定 = `deepseek/deepseek-v4-flash`；**仍含** `mid-local`/`triage` |

语义区分：`.bak-omlxfix` 先于 baseURL/绑定修复；`.bak-omlxfix-2022`（HHMM = 20:22）先于模型删除。列表以 `ls -la ~/.config/opencode/opencode.json.bak-*` 为准。

### 1.4 同步校验现状（`bin/delegation-alias-check.py`）

```bash
# 从 worktree（delegation-infra-reliability）运行：
cd <worktree>/delegation-infra-reliability
uv run --with pyyaml python bin/delegation-alias-check.py --json
```

2026-08-07 实测结果：`IN_OPENCODE_ONLY = []`（无路由缺口，修复目标达成）；`IN_BOTH = [coder, coder-fast, mini-9b, reasoner, vision]`；`IN_LITELLM_ONLY = [embed, embed-bge, fast, mid, mini-chat, mythos, ocr, rerank, vision-lite]`（9 条网关有、opencode 未暴露 —— **未使用容量，不是故障**，脚本因此 exit 1，属预期）。

---

## 2. 根因（为什么是这三个修复）

三层故障要分层，本次全踩：

| 层 | 故障 | 表现 | 修复 |
| --- | --- | --- | --- |
| 账户层 | `opencode-go-b` Insufficient Balance | 请求 402/余额错误 | agent 绑定改 `deepseek/deepseek-v4-flash` |
| 注册层 | `omlxc/triage`（及 `mid-local`）未在网关 `model_list` 注册 | Model not found / 无路由 | 从 `provider.omlxc.models` 删除 |
| 网关路由层 | 网关无 `mid-local` 路由 / 路由到无响应的后端 | **空 content** → 子代理"只叙述不落盘" | baseURL 改指本机 `127.0.0.1:8092` + 删除无路由别名 |

诊断顺序应为：`opencode.json` provider 配置 → 目标模型 curl 可达性 → 服务状态 → 账户余额，而非盲目换 category 重试（此前重试 11 次无效）。

---

## 3. 恢复 / 回滚步骤

> 回滚前先备份当前状态，回滚后**重启 opencode 会话**使配置生效。

### 3.1 完整回滚到修复前（baseURL + 绑定 + mid-local/triage 全部还原）

```bash
cd ~/.config/opencode
cp opencode.json opencode.json.pre-rollback      # 先留当前状态
cp opencode.json.bak-omlxfix opencode.json
```

还原后：`baseURL=100.96.126.35:4000`、explore/reviewer/scribe=`opencode-go-b/deepseek-v4-flash`、`mid-local`/`triage` 重新出现（此状态会复现原故障）。

### 3.2 仅回滚模型删除（保留 8092 baseURL 与 deepseek 绑定）

```bash
cd ~/.config/opencode
cp opencode.json.bak-omlxfix-2022 opencode.json
```

还原后：`mid-local`/`triage` 回到 `provider.omlxc.models`，其余修复保留。**注意**：此时仍未注册网关路由，子代理仍可能拿空内容 —— 见 §5 限制。

### 3.3 精确重新添加 `mid-local`（仅在网关路由注册后）

必须**同时**改两个源（双源同步规则，见 §4）：

1. 网关 `/Volumes/Model/omlx/gateway/litellm-config.yaml` 的 `model_list` 增加路由（`mid-local` 曾路由到 mac-mini Ollama 无响应，重加必须确认后端真实可用）：

```yaml
  - model_name: mid-local
    litellm_params:
      model: openai/<真实后端模型名>
      api_base: http://<可达后端>/v1
      api_key: <对应 key>
```

2. opencode.json `provider.omlxc.models` 增加别名（旧条目格式）：

```json
"mid-local": {
  "id": "/Volumes/Model/LMStudio/lmstudio-community/Qwen3.6-27B-MLX-4bit",
  "name": "omlxc Mid-Local (Qwen3.6-27B-MLX-4bit)"
}
```

3. 校验：`uv run --with pyyaml python bin/delegation-alias-check.py --json` → `mid-local` 出现在 `IN_BOTH`，且 `IN_OPENCODE_ONLY` 为空。

> ⚠ 即便如此，本地 MLX 后端的 model 字段限制仍可能让它对 opencode 子代理不可用 —— 见 §5。

---

## 4. 双源同步规则（实为三源 — 含调度器模型池）

**任何新模型必须注册在三处**，否则就会出现"opencode 有别名、网关无路由"的空响应故障；且若未同步第三源（调度器模型池），调度器重建/回带会把已删别名重新写回 `opencode.json`：

| 源 | 文件 | 字段 |
| --- | --- | --- |
| ① opencode 侧 | `~/.config/opencode/opencode.json` | `provider.omlxc.models`（别名键） |
| ② 网关侧 | `/Volumes/Model/omlx/gateway/litellm-config.yaml` | `model_list[].model_name` |
| ③ 调度器模型池 | `~/.config/opencode/dynamic-router.py` | `MODEL_POOL` L101–107（`omlxc/*` 项） |

调度器模型池定位命令（实测 L101–107 含 `omlxc/coder|mid-local|mini-9b|triage` 等）：

```bash
grep -n "omlxc/" ~/.config/opencode/dynamic-router.py | head
```

校验：`bin/delegation-alias-check.py`（worktree 内）做双向交叉检查 —— `IN_OPENCODE_ONLY` 非空 = 路由缺口（必须修）；`IN_LITELLM_ONLY` 非空 = 未使用容量（可接受，不用清空）。改名/删路由同样要同步三处（含模型池，否则调度器可能回带）。

---

## 5. 已知限制（勿重新"发现"）

- **本地 MLX（mlx_lm @ 127.0.0.1:8092）只响应省略 model 字段的请求**；提供任意 model 值 → 404 且按 HF 仓库名去解析。
- **opencode 总是发送 model 字段** → `omlxc/*` 本地模型**对 opencode 子代理不可靠**。
- 因此当前唯一被验证可行的子代理路径是 **deepseek 云模型绑定**（`deepseek/deepseek-v4-flash`）；`coder` 保留 `omlxc/coder` 属已知例外（若空响应，按 §3.2 思路处理）。
- 不要因为"模型名出现在 `provider.omlxc.models`"就认为可用 —— 路由注册 + model 字段兼容是两道独立门槛。

---

## 6. 验证记录（2026-08-07）

| 检查 | 命令 | 结果 |
| --- | --- | --- |
| 别名同步（worktree） | `uv run --with pyyaml python bin/delegation-alias-check.py --json` | `IN_OPENCODE_ONLY=[]`；`IN_BOTH` 5 项 |
| 文档 SSOT（基线，主工作区） | `cd /Users/xiamingxing/Workspace && uv run --with pyyaml python bin/ssot/doc-ssot-lint.py --json` | `ok:true, conflicts:0, files_scanned:174, findings:[]` |
| 文档 SSOT（本文件单文件） | `uv run --with pyyaml python bin/ssot/doc-ssot-lint.py --file docs/operations/delegation-infra-config.md --json` | 0 冲突（无新增失败） |
