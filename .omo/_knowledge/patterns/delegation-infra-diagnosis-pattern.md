---
lifecycle: pattern
owner: governance-team
last_updated: 2026-08-07
related:
  - ../../../docs/operations/delegation-infra-config.md
  - p71-baseline-recovery-pattern.md
  - p78-triple-axis-diagnostic-pattern.md
---

# Delegation Infra Diagnosis Pattern — 子代理委托基础设施四层故障诊断 Runbook

> **Generated**: 2026-08-07 (post delegation-infra-reliability P3a)
> **SSOT**: `docs/operations/delegation-infra-config.md` (修复后固定状态) + `bin/delegation-alias-check.py` (P1a 漂移校验) + `bin/delegation-preflight.py` (P2 会话前健康检查)
> **Purpose**: 抽象子代理委托基础设施故障的标准诊断流程, 防"盲目换 category 重试 11 次无效"的失败模式

## 1. 模式识别 (4 层故障症状分类)

委托基础设施故障**必须分层**, 症状不同根因不同。本次会话四层全踩:

| 层 | 典型症状 | 根因 | 案例 (2026-08-07 实测) |
|----|----------|------|------------------------|
| **账户层** | 子代理返回 `Insufficient Balance` / 请求 402 / 余额错误 | agent 模型绑定到无余额的 provider | `opencode-go-b/deepseek-v4-flash` 余额不足 |
| **注册层** | `Model not found: omlxc/triage` | 模型别名未在目标端点注册 | `omlxc/triage`、`omlxc/mid-local` 在网关 `model_list` 无路由 |
| **网关路由层** | 子代理"只叙述不落盘" (narrate but never edit) | 端点返回**空 content** — 网关无路由 / 路由到无响应后端 | 网关把 `mid-local` 路由到 mac-mini Ollama 返回 reasoning-only；或 opencode 有别名但 litellm-config.yaml 无对应路由 |
| **调度器覆盖** | 手动编辑 opencode.json 在 PEAK/OFF-PEAK 切换后消失 | `~/.config/opencode/` 是 git 仓库, 由 `dynamic-router.py` 定时重写 | 手动修复被调度器覆盖回旧配置 |

**关键判读**:
- "只叙述不落盘" = **模型路由故障强信号** (空 content / 错误端点), 不是模型偷懒, 不是换 category 能解决的。
- "模型名出现在 `provider.omlxc.models`" ≠ 可用 — **路由注册 + model 字段兼容是两道独立门槛**。
- 别一上来就重试子代理; 先跑 §2 诊断顺序, 再动手。

## 2. 诊断顺序 (proven sequence)

按此顺序从配置到服务逐层收敛, **不要盲目重试**:

```
① 症状确认
   subagent "只叙述不落盘" / 余额错误 / Model not found
② 检查 opencode.json provider + agent model 绑定
   读 provider.omlxc 与各 agent 的 model 字段
③ curl 目标模型端点冒烟
   对比 omitted-model vs with-model (8000 与 8092 行为不同, 见 §5)
④ 检查网关路由
   grep litellm-config.yaml model_list 与 opencode 别名对照
⑤ 跑 bin/delegation-alias-check.py + bin/delegation-preflight.py
   工具化确认漂移与可解析性
⑥ 若配置被改回 → 检查调度器
   git -C ~/.config/opencode log 看 dynamic-router.py 重写痕迹
```

### ② 检查配置绑定

```bash
# 读 opencode.json 的 provider.omlxc 与 agent 绑定 (只读)
python3 -c "
import json
d = json.load(open('$HOME/.config/opencode/opencode.json'))
print('baseURL:', d.get('provider', {}).get('omlxc', {}).get('options', {}).get('baseURL'))
print('omlxc.models:', sorted((d.get('provider', {}).get('omlxc', {}).get('models') or {}).keys()))
for name, cfg in (d.get('agent') or {}).items():
    print(f'agent {name}: {cfg.get(\"model\")}')
"
# 期望: explore/reviewer/scribe = deepseek/deepseek-v4-flash (云, 已验证)
#        coder = omlxc/coder (唯一本地绑定, 已知例外)
```

### ③ curl 端点冒烟

```bash
# 省略 model 字段 (mlx_lm 8092 只响应这种)
curl -s http://127.0.0.1:8092/v1/models | head -c 2000

# 带 model 字段 (opencode 总是发送; 8000 omlx-server 接受真实 id, 拒绝 omlxc/coder 别名)
curl -s http://127.0.0.1:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"Qwen3.6-27B-MLX-4bit","messages":[{"role":"user","content":"hi"}]}' | head -c 2000

# 网关 (litellm) 全模型列表
curl -s http://100.96.126.35:4000/v1/models | head -c 2000
```

### ④ 检查网关路由

```bash
# 网关 model_list 与 opencode 别名对照 (双源同步规则见 §3 网关层)
grep -n "model_name" /Volumes/Model/omlx/gateway/litellm-config.yaml
python3 -c "
import json
d = json.load(open('$HOME/.config/opencode/opencode.json'))
print(sorted((d.get('provider', {}).get('omlxc', {}).get('models') or {}).keys()))
"
```

### ⑥ 检查调度器 (配置被改回时)

```bash
# ~/.config/opencode/ 是 git 仓库; 看谁改回了配置
git -C ~/.config/opencode log --oneline -10
git -C ~/.config/opencode diff HEAD~1 -- opencode.json | head -c 3000
# PEAK/OFF-PEAK 切换后 manual 修复消失 = dynamic-router.py 重写, 见 §3 调度器层
```

## 3. 各层修复命令

> 修复前**先备份当前状态**, 修复后**重启 opencode 会话**使配置生效 (与 delegation-infra-config.md §3 一致)。

### 账户层 — 换绑到有余额的 provider

```bash
cd ~/.config/opencode
cp opencode.json opencode.json.pre-<fix-tag>        # 备份当前状态
# 编辑 opencode.json: explore/reviewer/scribe 的 agent.model
#   opencode-go-b/deepseek-v4-flash  →  deepseek/deepseek-v4-flash  (已验证可用)
#   (deepseek API key 在 ~/.config/opencode/keys/deepseek.txt)
```

验证: 重启会话后子代理可正常落盘; 余额类错误消失。

### 注册层 — 注册模型 或 删除别名

- 目标端点**能注册** → 在端点注册该模型 (本机 MLX 后端见 §5 端口图)。
- 端点**不能/不该注册** → 从 `provider.omlxc.models` **删除别名** (2026-08-07 实测: 删除 `mid-local`/`triage`, 二者网关无路由, 请求发出后无路可走 → 空 content)。

```bash
cd ~/.config/opencode
cp opencode.json opencode.json.pre-del-model        # 备份
# 编辑 opencode.json, 删除无路由别名后保存
```

### 网关路由层 — 双源同步 (two-source rule)

**任何新模型必须注册在两处**, 否则出现"opencode 有别名、网关无路由"的空响应:

| 源 | 文件 | 字段 |
|----|------|------|
| ① opencode 侧 | `~/.config/opencode/opencode.json` | `provider.omlxc.models` (别名键) |
| ② 网关侧 | `/Volumes/Model/omlx/gateway/litellm-config.yaml` | `model_list[].model_name` |

```bash
# 网关 model_list 增加路由 (例: mid-local; 重加必须确认后端真实可用)
#   /Volumes/Model/omlx/gateway/litellm-config.yaml
#   - model_name: mid-local
#     litellm_params:
#       model: openai/<真实后端模型名>
#       api_base: http://<可达后端>/v1
#       api_key: <对应 key>

# opencode.json provider.omlxc.models 增加别名
#   "mid-local": { "id": "/Volumes/Model/LMStudio/lmstudio-community/Qwen3.6-27B-MLX-4bit", ... }

# 双向校验 → mid-local 出现在 IN_BOTH, IN_OPENCODE_ONLY 为空
cd <worktree>/delegation-infra-reliability
uv run --with pyyaml python bin/delegation-alias-check.py --json
```

### 调度器层 — 理解它是权威, 记录而非对抗

- `~/.config/opencode/` 是 git 仓库, `dynamic-router.py` 在 PEAK/OFF-PEAK 切换时**重写 opencode.json** — 它是配置的**权威源**, 手动修复会被覆盖, 这不是 bug。
- 应对: ① 记录该行为 (本 runbook); ② 需要持久的手动修复 → 改 `dynamic-router.py` 的模型池 (超出默认 scope, 需专门任务); ③ 临时修复 → 每次调度切换后**重跑 §2 诊断顺序**确认配置存活。
- 别试图"锁住" opencode.json 对抗调度器 — 只会引入下一轮漂移。

## 4. 预防 (Prevention)

| 时机 | 动作 | 命令 |
|------|------|------|
| **每次编排会话前** | 跑 preflight 健康检查 | `uv run --with pyyaml python bin/delegation-preflight.py --json` (4 项 critical, exit 0 = 可委托) |
| **任何模型配置改动后** | 跑 alias 漂移校验 | `uv run --with pyyaml python bin/delegation-alias-check.py --json` (IN_OPENCODE_ONLY 非空 = 路由缺口, 必须修) |
| 调度器切换后 | 复查配置存活 | `git -C ~/.config/opencode log --oneline -3` + §2 ② |

`bin/delegation-preflight.py` 六项检查 (四项 critical: `opencode_config_exists` / `provider_omlxc_configured` / `agent_bindings_resolvable` / `omlxc_endpoint_reachable`; 两项 informational: `local_mlx_alive` / `gateway_models_available`)。其中 `gateway_models_available` 对本机 mlx_lm (8092) 报 **WARN 而非 FAIL** — 已知限制, 勿为绕过而改动配置。

## 5. 端口图 (2026-08-07 实测)

| 端口 | 服务 | model 字段行为 |
|------|------|----------------|
| **8000** | omlx-server | **接受** model 字段, 但只认真实 id (`Qwen3.6-27B-MLX-4bit` 等); **拒绝** `omlxc/coder` 别名 |
| **8092** | mlx_lm | **拒绝** model 字段 (提供任意值 → 404 按 HF 仓库名解析); opencode 总发 model 字段 → 本地 omlxc/* 对子代理不可靠 |
| **100.96.126.35:4000** | LiteLLM 网关 | 统一 OpenAI 兼容入口 (仅 tailnet) |
| **8183** | embedding (omlx) | — |
| **11434** | Ollama | — |

**推论**: 当前唯一验证可行的子代理路径是 **deepseek 云模型绑定** (`deepseek/deepseek-v4-flash`); `coder` 保留 `omlxc/coder` 属已知例外 (若空响应, 按注册层思路处理)。

## 6. 验证记录 (2026-08-07)

| 检查 | 命令 | 结果 |
|------|------|------|
| 别名同步 | `uv run --with pyyaml python bin/delegation-alias-check.py --json` | `IN_OPENCODE_ONLY=[]`; `IN_BOTH` 5 项 (coder/coder-fast/mini-9b/reasoner/vision) |
| 文档 SSOT 基线 (主工作区) | `cd /Users/xiamingxing/Workspace && uv run --with "pyyaml" python bin/ssot/doc-ssot-lint.py --json` | `ok:true, conflicts:0, files_scanned:173, findings:[]` |

## 7. 复用清单 (诊断时 Checklist)

```markdown
- [ ] 症状归类: 余额 / Model not found / 空 content / 配置被改回 → 对应 §1 哪层
- [ ] 按 §2 顺序诊断, 不盲目重试
- [ ] 修复前备份 ~/.config/opencode/opencode.json
- [ ] 修复后重启 opencode 会话
- [ ] 改模型后跑 alias-check 确认 IN_OPENCODE_ONLY=[]
- [ ] 编排会话前跑 preflight
- [ ] 调度器切换后复查配置存活
- [ ] 双源同步: opencode.json models ↔ litellm-config.yaml model_list
```

## 8. 失败模式 (反模式)

- ❌ 子代理"只叙述不落盘"时换 category 重试 — 本次实测重试 11 次无效, 浪费整个会话。
- ❌ 认为"模型名出现在 provider.omlxc.models"就可用于子代理 — 路由注册 + model 字段兼容两道门槛。
- ❌ 手工对抗 dynamic-router.py 重写 — 调度器是权威, 对抗只会引入下一轮漂移。
- ❌ 改动配置后不跑 alias-check / preflight — 修复"存活"需要工具化验证 (P74 常态化精神)。
