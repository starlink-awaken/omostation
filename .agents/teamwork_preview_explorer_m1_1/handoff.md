# Handoff Report — M1 里程碑跨层调用重构分析

## 1. Observation (观测事实)

*   **O1: ECOS Swarm 后端命令直调细节**
    *   文件路径：`projects/ecos/src/ecos/workflow/backends/swarm.py`
    *   `_CLI_PATHS` 备用路径（第 26-33 行）：
        ```python
        _CLI_PATHS: list[list[str]] = [
            ["uv", "run", "--package", "aetherforge", "python", "-m", "aetherforge.swarm"],
            [sys.executable, str(Path.home() / "Workspace" / "projects" / "aetherforge" / "packages" / "swarm" / "src" / "swarm_engine" / "cli.py")],
            [str(Path.home() / "bin" / "aetherforge"), "swarm"],
        ]
        ```
    *   执行命令（第 94-100 行）：
        ```python
        cmd = [*cli_cmd, "run", "--goal", goal, "--json"]
        r = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=120, cwd=Path.home(),
        )
        ```
    *   Mock兜底（第 114-120 行）：若全部 CLI 不可用，直接返回 mock 字典。

*   **O2: 已存在的 Agora MCP HTTP 调用实现**
    *   文件路径：`projects/ecos/src/ecos/workflow/agora_mcp_backend.py`
    *   Agora HTTP 终点定义（第 17 行）：
        ```python
        _AGORA_MCP_URL = "http://127.0.0.1:7422"
        ```
    *   `httpx` 的 `resolve_bos_uri` 工具请求形式（第 64-78 行）：
        ```python
        resp = httpx.post(
            f"{_AGORA_MCP_URL}/v1/tools/call",
            json={
                "name": "resolve_bos_uri",
                "arguments": {
                    "uri": bos_uri,
                    "arguments": {
                        "task": params.get("task", ""),
                        "context": params.get("context", ""),
                        "agent_role": agent_role,
                    },
                },
            },
            timeout=timeout,
        )
        ```

*   **O3: Agora 端的工具响应与服务注册配置**
    *   文件路径：`projects/agora/src/agora/server/tools_bos.py`
    *   `resolve_bos_uri` 工具定义（第 252 行）：
        ```python
        async def resolve_bos_uri(uri: str, arguments: dict | str = "{}") -> dict:
        ```
    *   当成功时（第 299-306 行），通过 `_ok` 返回：
        ```python
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "uri": uri,
                "source": source,
                "result": result,
            }
        )
        ```
        其中 `_ok` 函数（`projects/agora/src/agora/server/_response.py` 第 12-14 行）将结果组装为：
        ```python
        def _ok(data: dict) -> dict:
            return {"status": "ok", **data}
        ```

*   **O4: Agora BOS 服务静态注册表**
    *   文件路径：`projects/agora/etc/bos-services.yaml`
    *   用于声明式地注册所有 `bos://` 路由（例如 `bos://governance/metaos/decide` 采用 stdio 模式调用子进程）。

---

## 2. Logic Chain (逻辑链条)

1.  根据 **O1**，`swarm.py` 中 `_execute_step_swarm` 函数通过 `subprocess.run` 直调本地 `aetherforge` 子进程。我们需要在它的最前端引入基于 HTTP 的网格 RPC 调用。
2.  根据 **O2**，`ecos` 库里具有成熟的 `httpx` 调用模板，且配置了 `_AGORA_MCP_URL = "http://127.0.0.1:7422"`。我们可以将此模式复用到 `swarm.py` 中。
3.  根据 **O3**，RPC 调用的成功返回具备结构 `{"status": "ok", "result": {...}}`，我们可以解析 `data.get("result")` 以提取实际的数据载荷，并通过结构 `{"ok": True, "data": result}` 返回，完美契合 `execute` 接收的返回值约束。
4.  根据 **O1** 与 **O2**，如果 RPC 网络不可达（如捕获 `httpx.ConnectError` 等）或返回的状态表明存在业务错误（`status != "ok"`），则仅产生 `logger.warning` 警告，不执行 `return`，使得调用流程顺畅地进入 `_CLI_PATHS` 循环，从而完美实现 Subprocess 作为 Fallback 降级。
5.  根据 **O4**，为了能让网格解析此服务，需要在 `bos-services.yaml` 中静态注册 `bos://capability/swarm/run`，指向 `aetherforge.swarm` 执行命令行。

---

## 3. Caveats (局限与盲点)

*   No caveats. 重构涉及的代码位置与交互参数在 codebase 中都是确定且直接可用的。

---

## 4. Conclusion (明确的结论)

通过 Agora MCP 网格 BOS 协议进行 RPC 调用重构 Swarm 执行命令是完全可行的。重构方案实现了：
1.  **高内聚与控制面解耦**：通过 `resolve_bos_uri` 将物理依赖收敛至唯一的 HTTP 网格。
2.  **防御性架构设计**：采用三级降级链路设计（网格 RPC -> 本地 CLI Subprocess -> Mock 数据兜底），即使网格挂掉，系统依然能无损降级回原机制，具有高度的架构安全性。

---

## 5. Verification Method (如何独立验证)

1.  **服务注册校验**：检查 `projects/agora/etc/bos-services.yaml` 是否正确添加了 `bos://capability/swarm/run` 的 stdio 配置。
2.  **降级链路单测校验**：在不启动 Agora 网格（或故意写错端口）的开发状态下运行 ECOS 的测试用例：
    ```bash
    cd projects/ecos && uv run pytest tests/ -q
    ```
    预期：打印 `Swarm backend: RPC failed/unreachable. Falling back to subprocess execution.` 的 Warning 日志，单元测试全部顺利跑通。
3.  **网格联合集成校验**：启动 Agora MCP（`:7422` 端口），运行工作流测试，确认有请求进入 Agora 路由，子进程未被 ecos 自身唤起，而是由 Agora 的 stdio adapter 托管执行。
