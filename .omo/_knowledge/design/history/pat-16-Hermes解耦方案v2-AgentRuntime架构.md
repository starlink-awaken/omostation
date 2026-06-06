# Hermes 解耦方案 v2：Agent Runtime 架构

> 思路转变：不再试图替代 Hermes，而是重新定义它的角色。
> Hermes 退化为纯 IM 通信层 + 定时触发器。
> 所有"智能"由我们自建的 Agent Runtime 提供。

---

## 一、架构对比

### 旧方案：替代 Hermes 4 个能力

```
Hermes 替代计划
  ├─ WeChat 接收   → 自建 gateway (复杂, 数周)
  ├─ WeChat 发送   → weixin_send.py (curl iLink)
  ├─ Cron 调度器   → 系统 crontab
  └─ Agent 循环    → Agent Runtime ~500 LOC
```

问题：花了大量精力在 WeChat 上，不是我们的核心价值。

### 新方案：Hermes 做 IM，Agent Runtime 做智能

```
用户 (微信)
  ↓  iLink REST API (Hermes 维护)
┌─────────────────────────────────┐
│  Hermes Gateway (仅 IM 层)      │
│  收消息 → 转发                  │
│  接结果 → 推送                  │
│  Cron 调度 → 触发 → 回调       │
└──────────┬──────────────────────┘
           ↓ HTTP / MCP
┌─────────────────────────────────┐
│  Agent Runtime (我们的)         │
│  聊天: 解释意图 + 编排工具      │
│  Cron: 执行 prompt + 调用工具   │
│  固定模型: DeepSeek V4          │
└──────────┬──────────────────────┘
           ↓ MCP
┌─────────────────────────────────┐
│  KOS / Agora / Minerva / ……     │
│  能力层 (不变)                   │
└─────────────────────────────────┘
```

---

## 二、调研关键发现

### 1. iLink 是独立 REST API

从 `gateway/platforms/weixin.py` 确认：

```python
ILINK_BASE_URL = "https://ilinkai.weixin.qq.com"
EP_SEND_MESSAGE = "ilink/bot/sendmessage"     # POST 发消息
EP_GET_UPDATES = "ilink/bot/getupdates"       # GET long-poll 收消息
EP_SEND_TYPING = "ilink/bot/sendtyping"
EP_GET_CONFIG = "ilink/bot/getconfig"
```

**可被 curl 直接调用**，但我们不用在 WeChat 上花精力——Hermes 继续维护它。

### 2. Hermes Gateway 有 API Server 平台

`gateway/platforms/api_server.py` — Hermes gateway 内置了一个 REST API 服务，提供：
- `/v1/chat/completions` — 类 OpenAI API
- `/v1/runs` — 运行 Agent 任务
- 可以直接作为我们桥接的入口

### 3. Gateway 有 builtin_hooks 扩展点

`gateway/builtin_hooks/` — 空目录，是 Hermes 预留的"始终注册的钩子"。
我们可以在这里加一个 hook：收到消息 → 转发到 Agent Runtime API。

### 4. Hermes Cron 支持 no_agent 脚本

每个 LLM cron 可以改为：
```
原来: cron prompt → Hermes AIAgent 执行
改为: cron no_agent 脚本 → curl 调 Agent Runtime API → 结果写 stdout → Hermes 推微信
```

这样 Hermes cron **完全不需要动**，只需要改 job 配置。

---

## 三、Agent Runtime 架构设计

### 核心接口

```python
# Agent Runtime — 无状态 HTTP 服务
POST /run-task     # 执行单个任务（用于 cron）
  Body: {prompt: str, tools: [str], context: {…}}
  Response: {result: str, tool_calls: [...], tokens: int}

POST /chat         # 聊天对话（用于消息接收）
  Body: {message: str, session_id: str, history: [...]}
  Response: {reply: str, tool_calls: [...]}

GET  /health       # 健康检查
```

### 核心循环（~500 LOC）

```python
class AgentRuntime:
    def __init__(self, model="deepseek-v4-flash"):
        self.model = model          # 固定模型！
        self.mcp_clients = {...}    # KOS, Agora, Minerva 的 HTTP MCP 客户端
        self.terminal = Terminal()  # subprocess 执行器

    def run_task(self, prompt: str, tools: list[str], context: dict) -> str:
        """简化版任务循环：LLM → 工具调用 → 结果 → 输出"""
        system_prompt = self._build_system_prompt(tools)
        messages = [{"role": "system", "content": system_prompt}]
        if context:
            messages.append({"role": "user", "content": json.dumps(context)})
        messages.append({"role": "user", "content": prompt})
        
        for _ in range(MAX_TOOL_TURNS):
            response = self._call_llm(messages)
            if response.tool_calls:
                for tc in response.tool_calls:
                    result = self._execute_tool(tc.name, tc.args)
                    messages.append({"role": "tool", ...})
            else:
                return response.content
        
        return "Max tool turns reached"
```

### 需要的工具

| 工具类型 | 实现方式 | 覆盖哪些 cron |
|---------|---------|-------------|
| `terminal.run` | subprocess | WF-006/007/008/009/010 |
| `mcp.kos.*` | HTTP → KOS :7420 | WF-001/002 |
| `mcp.agora.*` | HTTP → Agora :7430 | — |
| `mcp.minerva.*` | HTTP → Minerva :8765 | WF-002 |
| `file.read` | Python open() | WF-005/009 |
| `file.write` | Python open() | WF-005 |
| `python.import` | importlib | codexbar-quota |

---

## 四、集成方案（Hermes ↔ Agent Runtime）

### 方式 A：Cron 任务集成（立即能做）

每个 LLM cron 改为 no_agent 脚本：

```bash
# ~/.hermes/scripts/run-agent-task.sh
#!/bin/bash
# 通用 Agent Runtime 调用脚本
# 用法: run-agent-task.sh WF-003
source ~/.zshrc
WORKDIR="${WORKDIR:-/Users/xiamingxing/Workspace}"

# 1. 查找对应的 prompt 定义
PROMPT_FILE="$WORKDIR/.omo/agent-tasks/$1.json"
if [ ! -f "$PROMPT_FILE" ]; then
    echo "[ERROR] Task $1 not defined"
    exit 1
fi

# 2. 调用 Agent Runtime
RESULT=$(curl -s -m 180 -X POST \
    -H "Content-Type: application/json" \
    -d @"$PROMPT_FILE" \
    http://localhost:9876/run-task)

# 3. 输出结果 → Hermes cron 投递到微信
echo "$RESULT"
exit 0
```

Hermes cron job 配置改为：

```json
{
  "id": "wf-003",       // 原 ID 不变
  "name": "WF-003 系统健康检查",
  "script": "run-agent-task.sh",
  "args": ["WF-003"],
  "no_agent": true,     // 改为 no_agent！
  "schedule": "0 10 * * *"
}
```

### 方式 B：实时消息集成（后续做）

在 Hermes gateway 中增加 builtin_hook：

```python
# gateway/builtin_hooks/agent_runtime_bridge.py
"""收到消息 → 转发到 Agent Runtime"""

async def on_message(platform, message, session):
    if message.text.startswith("/"):  # slash command 走原有逻辑
        return None
    
    # 转发到 Agent Runtime
    resp = await http_client.post(
        "http://localhost:9876/chat",
        json={"message": message.text, "session_id": session.id}
    )
    
    # 返回响应 → Hermes 自动推送到 WeChat
    return resp.json()["reply"]
```

**但是**，这种方式需要改 Hermes gateway 代码（虽然只有几行）。更干净的方式：

**方式 C：Hermes API Server 作为桥梁**

Hermes gateway 已经自带 API Server（`gateway/platforms/api_server.py`），我们可以在 WeChat 收到消息后，通过 API Server 路由到我们的 Agent Runtime。但这一步不太需要——目前通过微信跟系统交互的需求并不迫切，cron 推送已经覆盖 90% 使用场景。

---

## 五、Task 拆解（简化版）

### Phase 0: Agent Runtime 基础（3-5 天）

| Task | 内容 | 估计 |
|------|------|------|
| T0.1 | `agent_runtime.py` 核心循环 — LLM 调用 + 工具编排 | 2天 |
| T0.2 | MCP Client — HTTP 调用 KOS/Agora/Minerva | 1天 |
| T0.3 | Terminal Executor — subprocess 调用 | 半天 |
| T0.4 | HTTP 服务 — Flask/FastAPI 暴露 `/run-task` 接口 | 半天 |
| T0.5 | 定义 cron task prompts 文件格式（`.omo/agent-tasks/*.json`） | 半天 |
| T0.6 | E2E 测试 — 手动跑一个 cron prompt 验证链路 | 半天 |

### Phase 1: Cron 迁移（3-5 天）

| Task | 内容 | 估计 |
|------|------|------|
| T1.1 | `run-agent-task.sh` 通用调用脚本 | 1天 |
| T1.2-12 | 逐个迁移 11 个 LLM cron（WF-001 ~ WF-015） | 各半天 |
| T1.13 | E2E — 关掉 Hermes AIAgent，所有 cron 通过 Agent Runtime 运行 | 1天 |

### Phase 2: 对话集成（可选，后续）

| Task | 内容 | 估计 |
|------|------|------|
| T2.1 | 调查是否需要在微信上回消息 | 1天 |
| T2.2 | 如果需要：Hermes builtin_hook 或 API Server 桥接 | 2天 |

### 总计

```
Phase 0: Agent Runtime 核心 ── 3-5天
Phase 1: Cron 迁移 ── 3-5天
Phase 2: 对话集成 (可选) ── ~3天
                          ──
总计: 1.5-3 周 (比旧方案少了 WeChat 部分，快了约 50%)
```

---

## 六、与旧方案对比

| 维度 | 旧方案（替代 Hermes） | 新方案（Agent Runtime） |
|------|---------------------|----------------------|
| 开发量 | ~30 tasks, 4-5周 | ~20 tasks, 1.5-3周 |
| WeChat 风险 | 🔴 iLink 未知 | ✅ 不动 Hermes，零风险 |
| Arch 干净度 | Hermes 完全移除 | Hermes 做 IM，职责分明 |
| 可替换性 | 高（无 Hermes） | 中（Hermes 作为 IM 层） |
| 回退难度 | 高（全链路） | 低（切回 Hermes AIAgent 即可） |
| 未来扩展 | 需要重写 gateway | 加新的 Agent 前端即可 |

---

## 七、红队分析（新方案）

| # | 攻击 | 影响 | 优先级 |
|---|------|------|--------|
| A1 | Agent Runtime 的 **模型必须固定** | 输出不稳定 | P0 |
| A2 | SILENT 协议在 no_agent 脚本中需自行实现 | 故障被掩盖 | P1 |
| A3 | cron prompt 硬编码了 `mcp_kos_*` 工具名 | Agent Runtime 需要工具名映射 | P1 |
| A4 | Agent Runtime 可用性 — 如果挂了，所有 cron 停摆 | 全线瘫痪 | P1 |
| A5 | 无执行历史 — 不像 Hermes 有 last_status追踪 | 运维困难 | P2 |

### 缓解措施

- **P0**: Agent Runtime 构造函数中固定 `self.model`，不跟随任何默认配置
- **P1**: cron wrapper 检查 exit code，非零退出直接告警
- **P1**: Agent Runtime 中做工具名映射：`mcp_kos_*` → KOS MCP server 的原始工具名
- **P1**: 启动 launchd 守护 Agent Runtime（`KeepAlive=true`），自动重启
- **P2**: Agent Runtime 自身写 SQLite 执行日志

---

## 八、文件结构

```
# 新增文件
~/Workspace/agent-runtime/
├── server.py             # HTTP 服务 (FastAPI)
├── runtime.py            # AgentRuntime 核心类
├── mcp_client.py         # MCP 工具调用封装
├── terminal_exec.py      # 终端执行
├── task_definitions/     # Cron task prompt 定义
│   ├── WF-001.json       # KOS每日索引
│   ├── WF-003.json       # 系统健康检查
│   ├── ...
├── pyproject.toml
└── README.md

# 新增/修改
~/.hermes/scripts/
├── run-agent-task.sh     # 通用 Agent Runtime 调用脚本 (新增)
├── common_paths.py       # 已有，不变

# 新增
~/.hermes/cron/agent-tasks/   # Hermes cron 配置引用
```

---

## 九、结论

**新方案比旧方案好 50%。** 核心变化：

1. 不碰 WeChat — Hermes 继续做它做得最好的事
2. 只建 Agent Runtime — 我们的核心价值（LLM 推理 + 工具编排）
3. 集成极简 — cron 改为 no_agent 脚本，一行 curl 调 Agent Runtime
4. 可逆 — 任何时候切回 Hermes AIAgent 只需改 cron 配置

**先做 T0.1: 建 Agent Runtime 核心循环。** 有它就能跑通整个链路。
