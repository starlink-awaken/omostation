# Handoff Report

## 1. Observation (观测事实)

*   **O1: `ecos/workflow/backends/swarm.py` 中遗留的子进程直调**
    *   定位文件：`projects/ecos/src/ecos/workflow/backends/swarm.py`
    *   命令行路径 `_CLI_PATHS` (第 26-33 行): 
        ```python
        _CLI_PATHS: list[list[str]] = [
            ["uv", "run", "--package", "aetherforge", "python", "-m", "aetherforge.swarm"],
            [sys.executable, str(Path.home() / "Workspace" / "projects" / "aetherforge" / "packages" / "swarm" / "src" / "swarm_engine" / "cli.py")],
            [str(Path.home() / "bin" / "aetherforge"), "swarm"],
        ]
        ```
    *   命令行直调函数 `_execute_step_swarm` (第 97-100 行):
        ```python
        r = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=120, cwd=Path.home(),
        )
        ```
*   **O2: `agora_mcp_backend.py` 内部 RPC 发送与映射机制**
    *   定位文件：`projects/ecos/src/ecos/workflow/agora_mcp_backend.py`
    *   RPC 终端地址 (第 17 行): `_AGORA_MCP_URL = "http://127.0.0.1:7422"`
    *   RPC 请求构造 (第 64-78 行) 使用 `httpx.post` 发送 `resolve_bos_uri` 工具请求：
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
*   **O3: 现有 RPC 监控审计 Hook 与闭环机制**
    *   定位文件：`projects/ecos/src/ecos/ssot/tools/mof_agora_hook.py`
    *   审计日志路径 (第 42 行): `AUDIT_LOG = HOME / ".ecos" / "bos-audit.jsonl"`
    *   不可变链同步 (第 185-215 行): 使用 `SSBClient().publish` 将 `BOS_AUDIT` 信号发布至不可变签名链。
    *   异常自愈建卡 (第 220-240 行): 当 `status_code >= 500` 且 `cards.db` 存在时，通过 `conn.execute` 自动向看板卡片数据库写入 `debt` 类型的卡片。
*   **O4: 现有的 workflow 单元测试对子进程的 Mock 覆盖**
    *   定位文件：`projects/ecos/tests/test_workflow.py`
    *   `TestExecuteStep` 包含了针对 `subprocess.run` 的多处 Mock 示例 (例如第 227 行 `@patch("ecos.workflow.actions.subprocess.run")`)。
*   **O5: SOCKS 代理依赖异常导致降级失效的现象**
    *   在测试任务（ID: `ffa1937b-121f-4ef4-9fd4-1a13b59aafd1/task-57`）中，测试用例 `TestAgoraBackend.test_agora_execute_fallback_on_unreachable` 执行失败：
        ```
        E  ImportError: Using SOCKS proxy, but the 'socksio' package is not installed. 
        E  Make sure to install httpx using `pip install httpx[socks]`.
        ```
    *   出错栈定位在 `httpx.get` 调用系统代理解析过程（`trust_env=True` 且环境存在 socks5 代理设置时），这抛出了 `ImportError`，导致原来的 `except (httpx.ConnectError, httpx.TimeoutException)` 无法捕获该异常，导致降级机制崩溃。

---

## 2. Logic Chain (逻辑链条)

*   **验证无子进程渗透的逻辑链条**：根据 **O1** 可知，遗留子进程调用全部通过 Python 内置的 `subprocess` 模块派生。结合 **O4** 现有的单元测试编写风格，若想确保 `ecos workflow run` 执行时绝对不产生针对 `aetherforge` CLI 进程的调用，最直接、无害的验证方式是在测试框架中全局 Mock `subprocess.Popen`。通过参数匹配拦截对 `aetherforge` 或其具体 Python 入口路径的调用，触发 AssertionError 即可对重构是否彻底进行断言校验，无需引入外部系统级监控工具（例如 `DTrace` 或 `auditd`）。
*   **可观测性审计链路闭环的逻辑链条**：由 **O2** 可知，工作流执行被重构为跨层调用，进入 Agora 的 RPC 网格。由 **O3** 可知，项目已经提供了一个完备的审计钩子适配器 `mof_agora_hook.py`，其实现了内存缓存路由（< 1ms 延迟）、本地结构化 JSONL 记录、SSB 密码学防篡改签名链以及向 SQLite 看板自动登记故障债务（CARDS）的完整流水线。通过在 Agora `resolve_bos_uri` 工具处理器成功或失败的分支中均调用该钩子，即可完美建立对 RPC 调用的高可观测性审计链路。
*   **无缝降级策略设计的逻辑链条**：由 **O2** 可知，跨层 RPC 严重依赖位于本机的 Agora 服务（`http://127.0.0.1:7422`）。基于 **O5** 的调试事实，常规的网络连接异常捕获不足以覆盖因全局代理引发的依赖包缺失错误。因此，我们在降级策略设计中，逻辑上推导出：**在 httpx 探测客户端中必须显式设置 `trust_env=False` 规避代理干扰，并引入包含 `ImportError` 在内的宽口径异常捕获**。通过这种优化，可以在网格不可达或探测中断时，稳健且无缝地 fallback 到 **O1** 定义的 `_execute_step_swarm` 子进程直调甚至 Mock 执行轨道，并且由本地 `bus-foundation` 机制补发事件，以保证系统状态一致。

---

## 3. Caveats (局限与盲点)

*   验证脚本运行前，需确保 Mock 机制完整，否则可能会由于未启动真实的本地 `aetherforge` CLI 环境而导致降级测试轨道不通过。
*   降级探测缓存的 TTL（如设为 5 秒）如果设置过长，可能会在网格短时间内重启恢复时引起执行器的延迟感知；若设置过短，高频探测会带来一定的本地请求开销。

---

## 4. Conclusion (明确的结论)

本调研与分析证明，M1 里程碑下的验证机制与自适应降级方案在当前代码库下是完全可行且具备基础设施支撑的：
1. **验证脚本**：可以通过在 `test_workflow_e2e.py` 中基于 `unittest.mock.patch("subprocess.Popen")` 全局 Hook 并解析参数关键字进行断言阻断来实施。
2. **RPC 监控**：可以通过在网格端整合 `mof_agora_hook.py` 实现结构化日志记录、SSB 签名链的不可变存证，并在出现网格级错误时自动写入 `cards.db` 完成卡片立项。
3. **降级策略**：在 `backends/swarm.py` 中引入健康嗅探与双轨（RPC 与本地直调）回退机制，在网格挂掉或连接异常时无缝降级到本地直调并调用 `bus-foundation` 分发事件以保障单机一致性。针对本地 SOCKS 代理带来的特异性崩溃，须使用 `trust_env=False` 绕过系统代理干扰。

---

## 5. Verification Method (如何独立验证)

1. **手动审查分析文档**：
   直接使用 `view_file` 阅读位于工作目录下的 `analysis.md`，确认其覆盖了三个核心问题的具体架构与设计伪代码。
2. **运行现有测试套件**：
   运行现有 ECOS 的工作流测试以确保原有的执行链路正确无误：
   ```bash
   cd projects/ecos && uv run pytest tests/test_workflow.py -q
   ```
3. **运行 Agora 与 Hook 验证测试**：
   运行相关 hook 的单元测试以证明审计链与 SSB 的调用可行性：
   ```bash
   cd projects/ecos && uv run pytest tests/test_mof_agora_hook.py -q
   ```

---

## 6. Remaining Work (剩余工作 - 供 Implementer 接续)

1. **实现拦截测试**：在 `projects/ecos/tests/test_workflow_e2e.py` 中实际引入 Mock 拦截校验的 pytest 用例，作为重构前的门禁。
2. **重构 Swarm Backend 执行器**：按照 `analysis.md` 中的“降级具体实现设计规范”，修改 `projects/ecos/src/ecos/workflow/backends/swarm.py`，引入健康缓存嗅探、`httpx` RPC 调用与自适应的子进程回退捕获。同时，**必须在 httpx 客户端中加入 `trust_env=False`** 以绕过本地 socks 代理异常。
3. **网格端集成 Hook**：确保 Agora Server 在执行 `resolve_bos_uri` 时，始终导入并正确运行 `ecos.ssot.tools.mof_agora_hook` 中的 `pre_check` 与 `post_audit`，以闭环监控链路。
