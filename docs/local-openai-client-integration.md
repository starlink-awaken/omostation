# 让 OpenCode、Pi、oh-my-pi、Kilo Code 接入 AetherForge + omlxc

本指南面向 OpenCode、Pi、oh-my-pi、Kilo Code、aider、Continue、桌面聊天客户端和自研脚本这类**支持 OpenAI Chat Completions 与自定义 base URL** 的本地工具。目标是让它们安全地使用本机算力，而不暴露节点拓扑、私有 Unix socket 或后端端口。

> **一条规则：客户端只连接 AetherForge 的 OpenAI 兼容门面；绝不直连 `omlxcd`。**

`omlxcd` 是私有控制/数据平面，使用 Unix socket，负责模型驻留、容量、节点授权和后端选择。AetherForge 是经过鉴权的公开门面，负责逻辑模型别名、调用策略及统一的 OpenAI 兼容响应。跳过它会绕开这些边界，也会让客户端与内部实现强耦合。

```mermaid
flowchart LR
    C["OpenCode 或其他本地客户端"]
    G["AetherForge\nOpenAI-compatible facade"]
    D["omlxcd\nprivate Unix socket"]
    P["本地受信任算力后端"]

    C -->|"Bearer auth · /v1"| G
    G -->|"typed UDS request"| D
    D -->|"placement / capacity / residency"| P
```

## 1. 接入前检查

你需要具备以下条件：

1. AetherForge 已由受管服务以 `active` 模式运行；不要在客户端项目里自行再起一个代理。
2. `omlxcd` 已就绪。对本机执行平面做无副作用检查：

   ```bash
   omlxc status --json
   ```

   输出应表示 daemon 已就绪且未降级。日常客户端接入不需要、也不应使用会探测远端的诊断命令。

3. 你有 AetherForge 的获准访问凭据。**不要因为门面只绑定 loopback 就假定它无需 key**：是否要求 Bearer 认证由受管服务配置决定；只要目录请求返回 `401`，就必须从获准的本地密钥来源注入凭据。
4. 客户端支持 OpenAI 兼容的 `baseURL` 与 Chat Completions。OpenCode 的自定义 provider 正符合这一模式。

不要把内部 socket 文件、节点地址、后端原始端口或私有配置复制进客户端配置。

## 2. 公开接口与边界

把以下 base URL 放进客户端配置。默认本机门面示例为：

```text
http://127.0.0.1:9290/v1
```

如果你的受管部署使用了不同的本机端口或绑定地址，**只**从服务运维说明获取对应 base URL；不要猜测或扫描端口。

| 接口 | 用途 | 客户端应如何使用 |
| --- | --- | --- |
| `GET /health` | 仅检查门面进程是否存活 | 可在启动前做一次只读检查；它不证明某个模型可生成。 |
| `GET /v1/models` | 列出当前可选的逻辑模型 ID | 用返回的 `data[].id` 填 OpenCode 的 `models` 键。不要手写物理后端名。 |
| `POST /v1/chat/completions` | 非流式和 SSE 流式聊天 | 这是编码助手的主接口。`stream: true` 使用标准 SSE。 |
| `POST /v1/embeddings` | 文本向量 | 仅在模型列表与实际策略允许 embedding 时使用。 |

当前公开契约不要求客户端直接调用内部路由规划、加载、卸载或作业接口；这些是 `omlxc` 的受控运维面。客户端请求会由 AetherForge 与 `omlxcd` 共同决定是否存在合格、本地且有容量的 placement。

### 本地优先与模型选择

- AetherForge 接收**逻辑模型 ID**，并在受管策略内解析它；`omlxc` 才决定实际 placement。
- 普通客户端请求默认采用 `local` 路由模式。若你的 SDK 能发送扩展 body，可显式传递 `routing_mode: "local"`；不要把 `hybrid` 或 `cloud` 当作无意的兜底。
- 模型可用性是动态的。每次启动客户端或修改 provider 前，都以 `GET /v1/models` 的实际返回值为准。
- 不把请求体里的模型 ID 当作节点或后端标识，也不要把内部 placement ID 写入项目配置。

### 上下文与输出预算：目录不等于固定容量

`GET /v1/models` 回答的是“哪些逻辑模型 ID 可以由门面公布”，**不**公布实时的
context window、显存余量或最终 placement。一个逻辑模型可以映射到多个 placement；
它们的 context limit 可能不同。请求到达后，`omlxc` 才按授权、可用性、能力、上下文、
内存和并发条件选择候选。没有合格候选时会返回 typed `409`，而不是把超长输入截断或
偷偷切到物理后端。

因此，`/v1/models` 不公布实时 context window，客户端也不应把“目录中有此模型”
理解成每次都保证相同的输入容量。下表中的数值是**保守客户端预算**：它们适合当前
本机常用逻辑模型的正常使用，而不是服务端对每一个 placement 的硬承诺。

- 默认把单次输入控制在 **16K token** 以内；这会给工具结果、系统提示词和输出留出余量。
- 只有在调用方能接受 typed `409` 并重新缩短上下文时，才把请求提高到 **32K token**。
- `max_tokens` 是期望输出上限；输入加输出仍必须落在实际获选 placement 的 context limit 内。
- 需要稳定长上下文时，在客户端做摘要、检索或分段，而不要设置无限请求超时。

## 3. 安全地准备环境变量

把地址和凭据放在终端会话、受管 secret store 或系统钥匙串导出的环境变量中；不要把 key 写进仓库、`opencode.json`、shell history、截图或 issue。

```bash
export AETHERFORGE_BASE_URL="http://127.0.0.1:9290/v1"
test -n "${AETHERFORGE_BASE_URL}"
```

如果部署启用了认证，再从获准的本地密钥来源注入 key：

```bash
export AETHERFORGE_API_KEY="从获准的本地密钥来源读取的值"
test -n "${AETHERFORGE_API_KEY}"
```

上例的 key 文本只是占位符，不能原样使用。是否可无 key 仅由受管服务的认证策略决定，而不是由绑定地址决定；仍建议在客户端配置中保留环境变量引用，便于策略变化后不改项目文件。

若要把环境变量长期交给客户端启动器，使用操作系统的 secret 管理机制或权限为 `0600` 的、本机私有的环境文件。不要把 `.env` 加入版本控制。

### 本机已验证的快速启动方式

本机受管部署把凭据保存在系统钥匙串。只在准备启动客户端的当前 shell 中读取，既不打印也不写回配置：

```bash
export AETHERFORGE_BASE_URL="http://127.0.0.1:9290/v1"
export AETHERFORGE_API_KEY="$(security find-generic-password -s aetherforge-gateway -w)"
test -n "${AETHERFORGE_API_KEY}"
```

随后可先检查客户端目录解析：

```bash
opencode models omlxc
pi --list-models omlxc
```

本机已登记的常用逻辑模型限制如下。它们是保守的客户端起步预算，不代表每次请求
一定有合格 placement，也不是所有候选的固定 context window；最终仍以 typed HTTP
结果为准。

| 逻辑 ID | 输入上下文 | 最大输出 | 用途 |
| --- | ---: | ---: | --- |
| `coding` | 16384 | 2048 | 通用编码 |
| `coding-fast` | 16384 | 2048 | 低延迟小任务 |
| `coding-next` | 16384 | 4096 | 多轮工具任务首选 |
| `mythos-fast` | 16384 | 2048 | 快速文本任务 |
| `reasoning-lite` | 16384 | 2048 | 轻量分析 |
| `vision` | 16384 | 2048 | 需要图像能力的请求 |

## 4. 先做无推理连通性验证

先验证门面和模型目录，再发真实请求。以下命令不会执行推理：

```bash
set -o pipefail

auth_header=()
if [[ -n "${AETHERFORGE_API_KEY:-}" ]]; then
  auth_header=(-H "Authorization: Bearer ${AETHERFORGE_API_KEY}")
fi

curl --fail --silent --show-error \
  "${AETHERFORGE_BASE_URL%/v1}/health" | jq .

curl --fail --silent --show-error \
  "${auth_header[@]}" \
  "${AETHERFORGE_BASE_URL}/models" \
  | jq -r '.data[] | .id'

# 私有控制面采用统一 envelope；列表位于 data.items，不是 data.models。
omlxc models list --json | jq -e '.data.items | length > 0'
```

`curl --fail` 与 `set -o pipefail` 不能省略。否则 `401` 的错误 body 可能被下游
解析器当作空数组，最终被误报成“0 个模型”。同理，`omlxc models list --json`
返回的是版本化 envelope；只读取不存在的 `.data.models` 也会制造一个假的零值。

记录其中一个返回的模型 ID，以下用 `<model-id-from-models>` 表示。没有任何模型时，不要伪造 model ID 或让客户端直接连接后端；先由运维面处理容量、授权或库存问题。

### 模型目录的判定表

这一步经常被误读。按下表处理，**不要**因为目录暂时不可用就绕过 AetherForge：

| 现象 | 正确结论 | 下一步 |
| --- | --- | --- |
| `GET /v1/models` 返回 `401` | 门面要求认证；这不是“没有模型”。 | 从获准本地密钥来源注入变量后，重新做一次只读目录请求。 |
| 返回 `200`，但 `data` 为空 | 门面当前没有可安全公布的逻辑模型；不能用猜测的 model ID。 | 停止客户端接入，检查受管服务状态并交给运维面处理。 |
| 返回非空目录，但 OpenCode/Pi/omp 看不到对应选择项 | 客户端配置未解析、别名写错，或工具缓存仍是旧配置。 | 做本指南中对应工具的离线配置检查；不要刷新/扫描内部后端目录。 |
| 返回 `503` 或 `504` | 本地目录或执行平面暂不可用。 | 记录状态码与时间，停止重试；不要让客户端驱动 load/unload。 |

active 模式的公开目录应只公布 `omlxcd` 已知的逻辑模型 ID。它与内部的私有控制目录不是让客户端直接依赖的第二套 API；后者只是 AetherForge 用来保持“目录能列出什么”与“实际能执行什么”一致的受控来源。

## 5. OpenCode 配置

当前 OpenCode 的正式配置使用 `provider` 结构；这台机器也已经有名为 `omlxc` 的 provider。**增量修改这个 provider，不要并行新增第二个指向相同门面的 provider，也不要覆写既有的其它 provider。** 这样能保持既有 alias 与权限策略不变。

OpenCode 的 provider 模板适用于任何 OpenAI 兼容服务：使用 `@ai-sdk/openai-compatible`、指定 `options.baseURL`，并把实际模型 ID 写入 `models`。不要混入来自旧教程、实验分支或第三方适配层的 `providers`、`package`、`settings` 或 `modelID` 键。配置语法始终以 [OpenCode Providers](https://opencode.ai/docs/providers/) 与 [OpenCode Config](https://opencode.ai/docs/config/) 的当前版本为准。

保留既有 `provider.omlxc` 的 `npm`、`options`、models 和所有其它 provider。需要新增或更新一个模型时，只在它的 `models` 对象内加入下列条目；`coding-next` 是 OpenCode 的选择名，`id` 才是发送给门面的逻辑模型 ID：

```json
{
  "provider": {
    "omlxc": {
      "npm": "@ai-sdk/openai-compatible",
      "options": {
        "baseURL": "{env:AETHERFORGE_BASE_URL}",
        "apiKey": "{env:AETHERFORGE_API_KEY}"
      },
      "models": {
        "coding-next": {
          "id": "coding-next",
          "name": "AetherForge local coding",
          "tool_call": true,
          "limit": {"context": 32768, "output": 4096}
        }
      }
    }
  },
  "agent": {
    "omlxc-local": {
      "model": "omlxc/coding-next",
      "tools": {"*": false, "read": true}
    }
  },
  "share": "disabled"
}
```

说明：

- `omlxc` 是已有 provider ID；不要改为物理后端或节点名。
- `{env:…}` 是 OpenCode 的环境变量替换语法。环境变量不存在时会展开为空，因此先做上一节的 `test -n`。
- `models` 的 key 是 OpenCode 本地选择名；其中的 `id` 必须与 `GET /v1/models` 返回的 `id` **完全一致**。模型列表变化后，只更新这一项的 `id`。
- `omlxc-local` 是低风险起步 agent：只开放 `read`，不会因为模型返回了 tool call 就自动获得编辑或 shell 权限。确认协议正常后，再按项目策略逐项开放。
- `permission.edit` 与 `permission.bash` 设为 `ask`，使编码助手的文件和命令操作逐次确认；模型可用不等于应自动执行本机命令。
- `share: "disabled"` 是适合本地工作区的保守默认值。按团队的合规要求单独调整它。

随后启动 OpenCode，通过 `/models` 选择 `omlxc/coding-next`；也可先运行 `opencode models omlxc` 只查看现有配置候选项。`opencode models omlxc` 展示的是客户端已配置子集，公共 `/v1/models` 展示的是门面逻辑目录；两者数量不同不等于注册链路断裂。

对现有配置做**无推理**校验：先备份用户配置，再运行下文的“迁移前只读预检”；它只输出 provider 是否存在和条目数量。不要在终端录屏、CI 日志或共享会话中运行 `opencode debug config`，因为该命令可能展示已解析的认证配置。

### 迁移前的只读预检

在修改配置前，先执行下列预检。它只输出条目数量，不输出 key、模型名、节点信息或内部地址：

```bash
python3 - <<'PY'
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

config_path = Path.home() / ".config/opencode/opencode.json"
if not config_path.exists():
    raise SystemExit("OpenCode user configuration was not found; do not create one automatically.")
config = json.loads(config_path.read_text())
models = config.get("provider", {}).get("omlxc", {}).get("models", {})
configured = {
    entry.get("id")
    for entry in models.values()
    if isinstance(entry, dict) and isinstance(entry.get("id"), str)
}
base_url = os.environ.get("AETHERFORGE_BASE_URL", "").rstrip("/")
if not base_url:
    raise SystemExit("AETHERFORGE_BASE_URL is not set; do not fall back to a private daemon endpoint.")
request = Request(f"{base_url}/models")
api_key = os.environ.get("AETHERFORGE_API_KEY")
if api_key:
    request.add_header("Authorization", f"Bearer {api_key}")
try:
    with urlopen(request, timeout=3.0) as response:  # noqa: S310 -- user-supplied local facade
        catalog = json.load(response)
except HTTPError as exc:
    raise SystemExit(f"public model directory returned HTTP {exc.code}; stop and fix access first.") from exc
except URLError:
    raise SystemExit("public model directory is unavailable; stop and fix the managed facade first.") from None
items = catalog.get("data") if isinstance(catalog, dict) else None
if not isinstance(items, list):
    raise SystemExit("public model directory response is malformed; do not use a private fallback.")
available = {
    item["id"]
    for item in items
    if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"]
}
print({
    "configured": len(configured),
    "still_available": len(configured & available),
    "needs_update": len(configured - available),
})
PY
```

只有 `needs_update` 为零时，既有映射才无需处理。若它大于零，先从**认证后的 AetherForge 公共目录**选择等价逻辑 ID，再对 `provider.omlxc.models` 的对应 `id` 做最小更新；不要删除整个 provider、不要批量替换所有模型、也不要把私有目录或物理后端 ID 写进 OpenCode。

### 只在当前项目生效

把 provider 放到项目级 `opencode.json` 可避免影响其他代码库。该文件不应包含真实 key，因而可以提交；真正的 secret 只通过环境变量注入。

如需限制 OpenCode 只显示该 provider，可按 OpenCode 当前版本的配置文档设置 provider allowlist。不要通过删除全局认证文件来达到隔离效果。

## 6. Pi

Pi 使用 `~/.pi/agent/models.json` 注册自定义 provider。该文件是用户私有配置；不要写进项目仓库。Pi 的模型条目直接向 API 传递 `id`，所以 `id` 必须替换为认证后 `GET /v1/models` 的一个逻辑 ID。AetherForge 当前是 Chat Completions 兼容面，使用 `openai-completions`，并明确关闭 Pi 可能附加的 reasoning 参数。

```json
{
  "providers": {
    "omlxc": {
      "baseUrl": "http://127.0.0.1:9290/v1",
      "api": "openai-completions",
      "apiKey": "$AETHERFORGE_API_KEY",
      "authHeader": true,
      "compat": {
        "supportsDeveloperRole": false,
        "supportsReasoningEffort": false
      },
      "models": [
        {
          "id": "coding-next",
          "name": "AetherForge local coding",
          "reasoning": false,
          "input": ["text"],
          "contextWindow": 32768,
          "maxTokens": 4096,
          "supportsTools": true
        }
      ]
    }
  }
}
```

Pi 的 `$AETHERFORGE_API_KEY` 是环境变量引用，缺失时 provider 会不可用；不要把真实 key 写成 JSON 字面量。首次运行后使用 `/model` 选择 `omlxc/coding-next`。Pi 会在每次打开 `/model` 时重新读取该配置，所以不需要重启守护进程。v3.0.11 接受 Pi/oh-my-pi 当前发送的 `max_completion_tokens`、`stream_options`、`store`、`parallel_tool_calls` 与 bounded `strict` 工具定义；每个请求最多 256 个工具、单个工具说明最多 128 KiB，完整请求仍受 1 MiB 总体上限保护。

如果 Pi 的默认会话长时间没有结束，先用纯净、只读模式区分“协议不可用”和
“本机旧扩展/上下文过重”。下面的探针仍保留 `read` 工具，但不会加载 ambient
扩展、skills、prompt templates 或项目上下文：

```bash
pi --provider omlxc --model coding \
  --mode json --no-session --tools read --thinking off \
  --no-extensions --no-skills --no-prompt-templates --no-context-files \
  --print "Read README.md with the read tool and return its title."
```

若纯净模式成功而默认模式长尾，问题在 Pi 本地启动面；逐项恢复扩展和上下文，
不要改 OMLXC 路由、直接连接物理后端或无限提高服务超时。

## 7. oh-my-pi

oh-my-pi（`omp`）的自定义 provider 放在 `~/.omp/agent/models.yml`。这是当前的 canonical 配置；旧的 `models.json` 仅作为迁移输入，不能同时手工维护两份。它把 `apiKey` 解析为“已存在的环境变量名或字面量”；`authHeader: true` 才会向门面发送 Bearer 认证头。因此，模板必须使用环境变量名，不能使用假的占位 key。

```yaml
providers:
  omlxc:
    baseUrl: http://127.0.0.1:9290/v1
    api: openai-completions
    apiKey: AETHERFORGE_API_KEY
    authHeader: true
    models:
      - id: coding-next
        name: AetherForge local coding
        contextWindow: 32768
        maxTokens: 4096
        supportsTools: true
```

启动前只需在受管 shell 或私有环境文件中提供 `AETHERFORGE_API_KEY`；不要用仓库内 `.env` 覆盖该值。选择 `omlxc/coding-next` 即可。若它提示 provider 未启用，检查 `disabledProviders` 中没有 `omlxc`；该数组在项目级配置中会整体覆盖全局数组，不能假定自动合并。`models.yml` 是 canonical 配置，兼容 `models.json` 只用于迁移或回退，不要长期双写两份不同值。

目录检查应返回 JSON，而不是“退出 0 但没有任何输出”：

```bash
omp models omlxc --json | jq -e '.models | length > 0'
```

旧版 OMP 可能在只读 `models` 命令中误加载 ambient hooks。若遇到空输出，先用
`omp models omlxc --json --no-extensions` 验证；它是有界诊断兜底，不应替代升级。
已安装包含 ambient-hook 隔离修复的版本后，两条命令应返回相同模型集合。

## 8. Kilo Code

Kilo Code 的终端版与 VS Code 扩展都支持 OpenAI-compatible provider。凭据引用只能放在可信的全局配置中：`~/.config/kilo/kilo.jsonc`。**不要**把带 `{env:AETHERFORGE_API_KEY}` 的 provider 提交到项目级 `kilo.json[c]`：Kilo 会为了防止项目窃取凭据而拒绝解析该引用。

在 Kilo 的 Providers UI 中选择 **Custom provider**、Provider API 选 **OpenAI Compatible**，填入 loopback base URL，并从认证后的 `/v1/models` 选择一个逻辑模型。UI 会写入当前版本支持的 provider 结构；若需手工维护全局 `kilo.jsonc`，使用官方的 `openai-compatible` 形状：

```jsonc
{
  "$schema": "https://app.kilo.ai/config.json",
  "model": "openai-compatible/local-coding",
  "provider": {
    "openai-compatible": {
      "options": {
        "apiKey": "{env:AETHERFORGE_API_KEY}",
        "baseURL": "http://127.0.0.1:9290/v1"
      },
      "models": {
        "local-coding": {
          "id": "coding-next",
          "name": "AetherForge local coding",
          "reasoning": false,
          "tool_call": true,
          "limit": {
            // Replace both caps with limits confirmed for the selected logical model.
            "context": 32768,
            "output": 4096
          }
        }
      }
    }
  },
  "privacy_mode": true
}
```

`tool_call: true` 只表示协议支持函数工具，不会替客户端批准文件或命令操作。Kilo 的文件与命令执行权限仍由客户端控制，应保持交互确认默认值。

当前 VS Code 扩展安装会附带 `kilo` CLI，但它未必自动加入 shell `PATH`。先在扩展的
`bin/kilo` 路径执行 `kilo --help` 确认版本，再按该版本实际提供的 `kilo models <provider>`
做**只读**目录检查；不要因为 shell 找不到 `kilo` 就全局安装第二份 CLI，也不要使用
`--refresh`（它会请求外部目录）。若已认证的 AetherForge 目录非空、Kilo 的 provider
筛选仍没有模型，先检查全局配置中的 provider ID、环境变量引用和模型 mapping，而不是
扫描后端或改动服务配置。

## 9. 统一实验流程

四个工具共用同一条规则：**先确认模型目录，后写配置，最后才做一次有界的非敏感推理实验。** 接入实验不应触发客户端驱动的模型 load/unload，也不应探测远端节点。

| 阶段 | OpenCode | Pi | oh-my-pi | Kilo Code |
| --- | --- | --- | --- | --- |
| 配置位置 | 既有用户级 `opencode.json` 的 `provider.omlxc` | `~/.pi/agent/models.json` | `~/.omp/agent/models.yml` | `~/.config/kilo/kilo.jsonc` |
| 认证来源 | `{env:AETHERFORGE_API_KEY}` | `$AETHERFORGE_API_KEY` | `AETHERFORGE_API_KEY` | `{env:AETHERFORGE_API_KEY}` |
| 模型选择 | `omlxc/<本地选择名>` | `omlxc/<逻辑 ID>` | `omlxc/<逻辑 ID>` | `openai-compatible/<本地选择名>` |
| 本机验证状态 | 目录、文本与 read 工具轮次通过 | 目录/取密通过；v3.0.7 请求形状已做契约测试 | 取密/请求形状已做契约测试 | 扩展自带 CLI 已发现；全局 provider 与凭据引用已做只读核验，待首次有界推理实验 |

对于任何工具：

1. 导出凭据时只检查变量是否为空，不能 `echo` 它。
2. 从已认证的 `GET /v1/models` 取得逻辑 ID，不把物理目录导入工具。
3. 全局私有配置权限保持为用户可读写；不要将 key、prompt、内部地址或模型驻留信息提交进仓库。
4. 初次推理仅用一个短的非敏感请求，明确超时和零重试；记录 HTTP 状态、客户端版本、请求是否流式，不记录正文、密钥或内部拓扑。
5. 若返回 409/503/504，停止而不是直接连接后端或让客户端执行 load/unload。

## 10. 其他 OpenAI 兼容客户端

任何支持自定义 base URL 的客户端都使用同一对环境变量。下面是 Python SDK 的最小示例；它只展示协议形状，不包含真实业务内容或凭据：

```python
import os

from openai import OpenAI

client = OpenAI(
    base_url=os.environ["AETHERFORGE_BASE_URL"],
    api_key=os.environ["AETHERFORGE_API_KEY"],
)

response = client.chat.completions.create(
    model="<model-id-from-models>",
    messages=[{"role": "user", "content": "Reply with OK."}],
    stream=False,
)
print(response.choices[0].message.content)
```

流式调用只需把 `stream` 改为 `True` 并按 SDK 的迭代方式消费事件。客户端取消流时，AetherForge 和 `omlxcd` 会收敛直属流资源；不要以断开连接代替显式的客户端取消处理。

### Tools、结构化输出与多模态

- 编码助手的文件读取、编辑与 shell 执行是**客户端能力**。把它们设置为需要确认，不要误以为模型服务会限制本机工具权限。
- v3.0.11 支持有界 function tools、`tool_choice`、assistant `tool_calls`、tool-result messages 与流式 tool-call delta；同时兼容 Pi/OMP 当前的 `max_completion_tokens` 和工具 schema。单个请求最多包含 256 个工具、单个工具说明最多 128 KiB，完整请求仍限于 1 MiB。模型是否真的选择某个工具仍取决于模型与上下文。
- `response_format` 等结构化输出字段尚不是本指南承诺的统一契约；需要 JSON 时优先让客户端做结构验证，不要假定所有物理后端都支持相同私有扩展。
- 图像消息会要求 vision 能力；embedding 请求会要求 embedding 能力。没有相应 placement 时，服务会拒绝请求，而不是把普通聊天模型伪装成对应能力。
- 优先选择客户端支持的 Chat Completions 流程；不要假定 `/v1/responses` 或厂商私有扩展存在。

## 11. 常见错误与正确处理方式

| HTTP 状态 | 含义 | 客户端侧处理 |
| --- | --- | --- |
| `400` | 请求格式或受支持参数不正确 | 检查 JSON、model ID 与客户端插件版本；不要重试原样坏请求。 |
| `401` | Bearer 凭据缺失或无效 | 重新从获准密钥来源注入变量；不要把 key 粘进配置文件或日志。 |
| `403` | 安全或策略拒绝 | 视为策略结果，保留最少元数据后联系运维方。 |
| `409` | 没有满足条件的本地容量或候选 | 等待资源恢复或选择模型目录中的另一逻辑模型；客户端不得直接 load/unload。 |
| `502` | 本地推理链内部失败 | 收集状态码、时间和安全的 request metadata；不要附带 prompt、key、节点信息或原始日志。 |
| `503` | 当前后端不可用 | 先检查 `/health`、`/v1/models` 与 `omlxc status --json`；不要扫描或直连后端。 |
| `504` | 在调用预算内未完成 | 适度提高客户端超时或缩短上下文；不要用无限重试掩盖容量问题。 |

`/health` 返回成功只表示门面进程存活；模型可用性仍以 `/v1/models` 与具体调用的 typed 结果为准。

若 Pi/OMP/Kilo 在旧版服务上反复得到 `400 invalid`，并且 AetherForge 到私有 UDS 显示 `422`，通常是 SDK 使用了 `max_completion_tokens`、超过 128 个工具，或超过旧 16 KiB 的工具说明而服务尚未升级。升级到 v3.0.11 或更高版本；不要用移除全部工具、无限重试或直连后端来掩盖协议不兼容。

## 12. 排障顺序

按这个顺序排查，既能缩小范围，也不会触发模型加载、卸载或远端探测：

1. 检查环境变量是否非空；不要打印 key。
2. `GET /health`：确认 AetherForge 门面进程存活。
3. `GET /v1/models`：确认至少一个逻辑模型 ID 可供客户端配置。
4. `omlxc status --json`：确认私有执行平面正常；用
   `omlxc models list --json | jq '.data.items | length'` 检查控制目录。
5. 仅用一个短、非敏感的聊天请求验证非流式；成功后再验证流式。
6. 若仍失败，报告时间、HTTP 状态、客户端版本、是否流式、是否使用图片/embedding；不要报告 prompt、密钥、Unix socket 路径、节点地址或完整日志。

不要把 `omlxc doctor --direct` 当作常规客户端排障命令。它属于运维诊断路径，可能触发额外的后端发现；本指南的接入检查只使用本机只读状态和门面接口。

## 13. 数据与安全实践

- 把 AetherForge 视为唯一信任边界：客户端只知道逻辑模型和公开兼容 API，不知道物理 placement。
- 使用 loopback 或部署批准的受控绑定；不要把门面随意绑定到局域网地址，更不要关闭非 loopback 暴露所需的认证。
- 不要在 OpenCode 的项目说明、共享会话、截图、shell history、错误报告或 git 配置中保存 key。
- 先为编码客户端启用 `edit: ask` 与 `bash: ask`；模型输出不是授权执行任意修改的依据。
- 将项目的密钥文件、构建产物、数据目录和生成缓存放进客户端的忽略规则，避免它们被自动收集进上下文。
- telemetry 只应使用安全的请求元数据；任何问题报告都应排除 prompt、内容正文、认证头、URL、身份与内部拓扑。

## 14. 运维分工

| 事项 | 负责人 | 客户端是否应处理 |
| --- | --- | --- |
| 逻辑模型、鉴权、请求策略 | AetherForge | 否；客户端只传逻辑 model ID。 |
| placement、容量、加载状态、后端选择 | omlxc | 否；客户端接受 typed 成功或拒绝。 |
| 本地文件、shell 与确认策略 | OpenCode 等客户端 | 是；通过客户端权限配置明确控制。 |
| 配置、服务生命周期、模型 load/unload | 受权运维流程 | 否；不要把这些命令封装进编码助手。 |

这层分工是可升级性的关键：更换后端、增加节点或调整容量时，客户端配置仍只需保持 AetherForge base URL、凭据和逻辑模型 ID。

## 15. 上线检查表

- [ ] AetherForge 使用受管的 active 门面，未在项目中启动旁路代理。
- [ ] `omlxc status --json` 表示 daemon 就绪、未降级。
- [ ] `/health` 成功，`/v1/models` 返回至少一个模型。
- [ ] 目录检查启用了认证、`curl --fail` 与 `pipefail`，没有把 `401` 当成空列表。
- [ ] `omlxc models list --json` 从 `.data.items` 读取，而不是猜测 envelope 字段。
- [ ] OpenCode 配置用 `{env:…}` 引用凭据，仓库中没有真实 key。
- [ ] 模型 ID 从 `/v1/models` 复制，而不是猜测或使用物理后端名。
- [ ] `permission.edit` 与 `permission.bash` 已设为 `ask` 或更严格的团队策略。
- [ ] 已用一次非敏感的非流式和流式请求验证，并按最少信息原则记录结果。
- [ ] 失败时先看 typed HTTP 状态，不做无限重试、直连后端或客户端驱动的模型生命周期操作。

## 16. 参考

- [OpenCode Providers](https://opencode.ai/docs/providers/)：自定义 OpenAI-compatible provider、`baseURL` 和模型映射。
- [OpenCode Config](https://opencode.ai/docs/config/)：环境变量替换、权限与分享设置。
- [Pi Custom Models](https://pi.dev/docs/latest/models)：`models.json`、OpenAI Completions provider、环境变量与兼容开关。
- [oh-my-pi Providers](https://github.com/can1357/oh-my-pi/blob/main/docs/providers.md)：`models.yml`、`apiKey` 解析和 `authHeader`。
- [Kilo Code Custom Models](https://kilo.ai/docs/code-with-ai/agents/custom-models)：自定义 OpenAI-compatible provider、可信配置中的环境变量与模型限制。
- [Kilo Code CLI configuration](https://kilo.ai/docs/code-with-ai/platforms/cli)：全局/项目级配置位置、模型和权限配置。
- [omlxc README](../README.md)：私有 daemon、CLI 和受控运维边界。
