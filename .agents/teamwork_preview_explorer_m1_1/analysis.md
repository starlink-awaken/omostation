# ECOS 跨层调用重构分析报告 — M1 里程碑

## ⚡️ Superpowers Activated
- **Architect Planning**: 跨层通信架构设计与依赖收敛分析。
- **Defensive Design**: 稳态落盘与多级降级安全网保障设计。
- **BMAD Flattening**: 对全局跨层调用（L0 ↔ I0 ↔ L2）的解耦治理。

---

## 💡 创意与分析
### 1. 为什么要进行这次重构？（架构痛点与价值）
- **紧耦合痛点**：目前 `ecos`（L0 协议与工作流层）直调 `aetherforge/swarm`（I0 网格/引擎层）是通过本地的 `subprocess.run` 命令行进程直接唤起。这造成了 eCOS 框架在执行环境上的强物理依赖，严重影响了架构的弹性伸缩与多机分布式部署能力。
- **路由收敛价值**：将直调重构为 Agora MCP 网格 BOS 协议（通过 `resolve_bos_uri` 请求 `bos://capability/swarm/run`）后，`ecos` 仅需与唯一的 HTTP 入口 `Agora Gateway (:7422)` 交互。实际执行 `swarm` 任务的节点位置、调用协议（stdio 或是后续演进的 socket/http 远程 RPC）对 `ecos` 完全透明，达成 **逻辑解耦** 与 **控制面收敛**。

### 2. 核心架构决策
- **三层隔离**：`ecos`（L0）↔ `agora`（I0 路由）↔ `aetherforge`（L2/I0 引擎）。
- **三级降级保护**：引入网格 RPC 后，本地 subprocess 不能简单丢弃，而应沉降为二级 Fallback 降级防线。当网格服务因重启、网络抖动等原因不可达时，能够无缝切回本地子进程运行，最终通过 Mock 状态兜底，确保核心工作流的最高可用性（High Availability）。

---

## 🗺️ 规划与设计

### 1. 数据链路与接口契约
#### 1.1 Agora 网格服务注册契约
在 `projects/agora/etc/bos-services.yaml` 中，以 stdio transport 模式注册该 URI 路由：
```yaml
  - uri: "bos://capability/swarm/run"
    domain: capability
    action: "run"
    transport: stdio
    package: "aetherforge"
    command: ["uv", "run", "--package", "aetherforge", "python", "-m", "aetherforge.swarm", "run"]
    description: "AetherForge Swarm 任务执行入口"
```

#### 1.2 HTTP MCP JSON-RPC 请求契约
- **HTTP 接口**：`POST http://127.0.0.1:7422/v1/tools/call`
- **Request Payload**：
```json
{
  "name": "resolve_bos_uri",
  "arguments": {
    "uri": "bos://capability/swarm/run",
    "arguments": {
      "goal": "任务目标描述",
      "params": {}
    }
  }
}
```

#### 1.3 接口响应与解包契约
正常响应（HTTP 200）：
```json
{
  "status": "ok",
  "format_version": "agora-v1",
  "uri": "bos://capability/swarm/run",
  "source": "stdio",
  "result": {
    "task_id": "swarm-12345",
    "status": "completed",
    "output": "执行结果文本/JSON"
  }
}
```
错误响应（HTTP 200 / 500）：
```json
{
  "status": "error",
  "error": "错误原因说明",
  "format_version": "agora-v1"
}
```

---

## 💻 代码实现方案

### 1. `swarm.py` 中执行命令的现有细节定位
在 `projects/ecos/src/ecos/workflow/backends/swarm.py` 中：
- **CLI 入口集合**（26-33 行）：`_CLI_PATHS` 包含 3 组备用命令行列表。
- **参数组合**（94 行）：`cmd = [*cli_cmd, "run", "--goal", goal, "--json"]`。
- **子进程调用**（97-100 行）：
  ```python
  r = subprocess.run(
      cmd, capture_output=True, text=True,
      timeout=120, cwd=Path.home(),
  )
  ```
- **输出解析与 Mock 兜底**（101-120 行）：如果执行成功，进行 `json.loads` 解析并以 `{"ok": True, "data": ...}` 返回；若全部 CLI 路径尝试失败，返回 Mock 伪数据。

### 2. 重构设计方案（拟修改方案 Diff）

为了在 `ecos/workflow/backends/swarm.py` 中完美融入 RPC 调用及 Fallback 降级，方案设计如下：

```python
<<<<
# 21 行之后新增导入
import httpx

_AGORA_MCP_URL = "http://127.0.0.1:7422"
====
# 保持原样
>>>>
def _execute_step_swarm(
    step_name: str, action: str, agent_role: str,
    step: dict[str, Any], params: dict[str, Any],
) -> dict[str, Any]:
    """Execute a single step via swarm subprocess."""
    goal = step.get("description") or step.get("name") or action or "task"

    # 尝试每个 CLI 入口
    for cli_cmd in _CLI_PATHS:
====
def _execute_step_swarm(
    step_name: str, action: str, agent_role: str,
    step: dict[str, Any], params: dict[str, Any],
) -> dict[str, Any]:
    """Execute a single step via swarm MCP first, then fallback to subprocess."""
    goal = step.get("description") or step.get("name") or action or "task"

    # ── 第一防线：尝试通过 Agora MCP 发起 RPC 路由调用 ──
    logger.info("Swarm backend: Attempting RPC call via Agora MCP: %s", goal)
    try:
        # 1. 快速健康检查，避免网格不可达时的长时挂起
        health_resp = httpx.get(f"{_AGORA_MCP_URL}/health", timeout=2)
        if health_resp.status_code == 200:
            # 2. 发送工具调用请求
            resp = httpx.post(
                f"{_AGORA_MCP_URL}/v1/tools/call",
                json={
                    "name": "resolve_bos_uri",
                    "arguments": {
                        "uri": "bos://capability/swarm/run",
                        "arguments": {
                            "goal": goal,
                            "params": params,
                        },
                    },
                },
                timeout=120, # 与子进程超时保持对齐
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "ok":
                    result = data.get("result", {})
                    logger.info("Successfully executed swarm task via Agora MCP RPC")
                    # 返回结构对齐 execute()
                    return {"ok": True, "data": result}
                else:
                    logger.warning(
                        "Agora MCP call succeeded but returned business error: %s",
                        data.get("error", "Unknown error")
                    )
            else:
                logger.warning("Agora MCP endpoint returned HTTP status %d", resp.status_code)
        else:
            logger.warning("Agora MCP health check failed with HTTP %d", health_resp.status_code)
    except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError) as e:
        logger.warning("Agora MCP RPC call failed or timeout: %s", e)

    # ── 第二防线：优雅降级为本地 CLI Subprocess 直调 ──
    logger.warning("Swarm backend: RPC failed/unreachable. Falling back to subprocess execution.")
    for cli_cmd in _CLI_PATHS:
>>>>
```

---

## ✅ 验收与提交

### 1. 独立验证路径（Verification Steps）
1. **Agora 注册态验证**：
   在 Agora 服务启动后，通过 `resolve_bos_uri` 手动触发以验证配置是否生效：
   ```bash
   # 手动调用 resolve_bos_uri 来验证 bos://capability/swarm/run
   # 预期：Agora 顺利唤起 aetherforge swarm 进程并正确返回 JSON 结果
   ```
2. **重构代码集成验证**：
   在不启动 Agora 容器或关闭 `127.0.0.1:7422` 的情况下，运行 `ecos` 的工作流测试，验证其正确打印 `Falling back to subprocess` 日志并运行通过：
   ```bash
   cd projects/ecos && uv run pytest tests/ -q
   ```
3. **网格联合测试验证**：
   启动 Agora MCP 网格服务：
   ```bash
   cd projects/agora && make run
   ```
   然后运行 ECOS Workflow step，观察 Agora 终端日志，确认有请求流入 `v1/tools/call` 并成功触发了 `resolve_bos_uri` 对 `bos://capability/swarm/run` 的路由调用。

### 2. 治理与一致性保障（Anti-Drift）
- **无 RAW IO 写入原则**：重构仅涉及网络 RPC 交互与子进程 fallback，不得包含任何对 `.omo` 文件或稳态配置的直接改写逻辑。
- **Ruff Lint 门禁校验**：
  ```bash
  make kairon-lint
  ```
