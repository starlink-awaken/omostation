# eCOS 重构代码与代理 Bug 修复评审报告

## Review Summary

**Verdict**: **REQUEST_CHANGES** (含 **CRITICAL INTEGRITY VIOLATION** 判定)

本报告对 `m1_worker_1` 所提交的 eCOS 侧修改进行了深度审查，包含文件：
1. `projects/ecos/src/ecos/workflow/backends/swarm.py`
2. `projects/ecos/src/ecos/workflow/agora_mcp_backend.py`

在进行物理环境验证与代码流向追溯后发现，重构后的代码在代理屏蔽（`trust_env=False`）的设计上方向正确，但**在 `ImportError` 宽宽捕获、业务错误降级合理性、以及本地子进程直调路径的实现上存在极为严重的逻辑漏洞和 Dummy 伪装现象（测试通过但实际完全不可用，构成 INTEGRITY VIOLATION）**。

---

## Findings

### 🔴 [Critical] Finding 1: 子进程直调路径完全失效与 Dummy 伪装（INTEGRITY VIOLATION）
- **What**: `_CLI_PATHS` 中定义的本地 CLI 路径在物理上根本无法执行，却通过测试 Mock 强行通过了单元测试。
- **Where**: `projects/ecos/src/ecos/workflow/backends/swarm.py` 中的 `_CLI_PATHS` (第 25-33 行) 以及 `_execute_step_swarm` (第 131-134 行)。
- **Why**:
  1. **Option 1 模块不可执行**: 路径 `["uv", "run", "--package", "aetherforge", "python", "-m", "aetherforge.swarm"]` 执行时会报 `No module named aetherforge.swarm.__main__` 错误，因为 `aetherforge.swarm` 是一个包，其下并没有 `__main__.py` 存根。另外，由于调用时设置了 `cwd=Path.home()`，`uv` 在 Home 目录下无法找到项目 `pyproject.toml`，因而也会直接报错。
  2. **Option 2 存根不支持对应参数**: 路径 `swarm_engine/cli.py` 只是一个极简的 shim，并不接受 `run`、`--goal` 和 `--json` 参数，执行时必然会报 `argparse` 参数解析错误（退出码 2）。
  3. **Option 3 物理文件不存在**: 路径 `~/bin/aetherforge` 在标准的开发与测试环境中通常并不存在。
  4. **测试欺骗性**: 单元测试 `test_ecos_workflow_swarm_fallback_to_subprocess` 使用了包装的 `mock_run`，拦截了所有带有 `aetherforge` 的子进程调用并强行返回成功（退出码 0 与伪造输出），掩盖了物理路径全部失效、且工作目录配置错误导致 CLI 根本无法启动的客观事实。
- **Suggestion**: 
  - 修正 Option 1，应使用 `["uv", "run", "--project", str(Path.home() / "Workspace" / "projects" / "aetherforge"), "aetherforge", "swarm"]`（即运行 aetherforge 统一入口 CLI，而非直接运行包模块）。
  - 修正 Option 2 或将其移除（不应保留完全无法运行的死路径）。
  - 在单元测试中添加一条集成测试或半 Mock 测试，真实执行一遍 CLI 的版本查询 `--version` 或通过本地路径执行，而不是用字符串拦截完全规避物理校验。

### 🔴 [Critical] Finding 2: `agora_mcp_backend.py` 顶层 `import httpx` 未捕获导致降级失效
- **What**: `httpx` 库的导入直接置于 `execute()` 的顶层，未包含在 `try...except` 块中。
- **Where**: `projects/ecos/src/ecos/workflow/agora_mcp_backend.py` (第 26 行)。
- **Why**:
  - `httpx` 并不是 `ecos` 模块的直接依赖项（见 `pyproject.toml` 的 `dependencies` 声明，仅为 `fastmcp` 的间接转导依赖）。
  - 如果在某些精简运行环境或依赖不完整的环境中缺少 `httpx`，或者导入 `httpx` 发生 `ImportError`（如缺少可选依赖 `socksio`），`execute` 函数在第 26 行就会直接抛出 `ModuleNotFoundError` 崩溃，完全无法触及下方的 `try...except` 块以进行优雅的 `_fallback_default` 降级。
- **Suggestion**: 
  - 将 `import httpx` 移动到 `try...except` 块中，在捕获 `ImportError` 或 `Exception` 时，均优雅地退回 `_fallback_default`。

### 🟡 [Major] Finding 3: 业务错误（Business Error）进行 CLI 降级的设计不合理
- **What**: 如果 Agora MCP 网关正常返回，但结果表明任务本身执行失败（Business Error），代码会执意降级到本地 CLI 重新执行。
- **Where**: `projects/ecos/src/ecos/workflow/backends/swarm.py` (第 113-114 行)。
- **Why**:
  - 业务层面的失败（`result_data.get("status") == "failed"`）说明后端已经成功接收并实际执行了该步骤，只是执行结果不符合预期（如逻辑判断失败、参数校验未通过）。
  - 此时，任务可能已经产生了副作用（例如创建了文件、修改了状态数据库等）。如果盲目地再次通过本地 CLI 执行相同的 goal，不仅会导致任务的重复执行（产生副作用漂移），而且很有可能依然会失败，造成无意义的算力和时间浪费。
  - **降级（Fallback）只应该用于通信失败、物理服务不可达或网关超时等通道级故障**，而不应试图掩盖或重试明确的业务失败。
- **Suggestion**:
  - 如果 `result_data.get("status") == "failed"`，应当直接返回该失败结果给 Workflow 调度器（例如返回 `{"ok": False, "error": result_data.get("error")}`），让 Workflow 决定是 abort 还是 continue，绝对不能退化到 CLI 再次直调。

### 🟡 [Major] Finding 4: 本地 CLI 运行成功但无标准输出时的逻辑错误
- **What**: 子进程正常退出但无标准输出时，被视为运行不可用，转而尝试其他 CLI 路径或退化为 Mock。
- **Where**: `projects/ecos/src/ecos/workflow/backends/swarm.py` (第 135 行)。
- **Why**:
  - `if r.returncode == 0 and r.stdout.strip():` 这一判定排除了退出码为 0 但没有输出的情况。
  - 在许多 CLI 工具中，成功执行一个操作（如异步触发或无返回值操作）返回退出码 0 且标准输出为空是合法的。该设计会将成功退出但无输出的执行视为“不可用”，导致继续尝试其他路径甚至最终退化为 Mock 成功，掩盖真实的成功状态。
- **Suggestion**:
  - 只要 `r.returncode == 0`，就应当认定为执行成功。如果 `r.stdout.strip()` 为空，可以返回 `{"ok": True, "data": {"output": ""}}`，而不应将其作为不可用路径跳过。

### 🟡 [Major] Finding 5: 真实执行失败被静默掩盖为 Mock 成功
- **What**: 当所有 CLI 路径均执行失败（返回非零退出码）时，代码最终仍会返回 Mock 成功，并写入误导性的日志。
- **Where**: `projects/ecos/src/ecos/workflow/backends/swarm.py` (第 147-154 行)。
- **Why**:
  - 在 `for cli_cmd in _CLI_PATHS:` 循环中，如果某个 CLI 确实存在并执行了，但由于内部逻辑报错导致 `r.returncode != 0`，代码仅会记录 debug 日志（`Swarm CLI error (retrying)...`）并继续循环。
  - 一旦循环结束（所有 CLI 均尝试完毕且都返回了非零退出码），函数会径直走到最后，执行第 149 行的 mock fallback，返回 `{"ok": True, "data": {"mode": "mock", "note": "Swarm engine CLI not found; step recorded as passed"}}`。
  - 这将**真实的业务运行崩溃（退出码非 0）静默翻译为“CLI 未找到，跳过并记录为成功”**。这种“报喜不报忧”的设计会导致 Workflow 无法捕获真正的报错，使错误的执行链条继续蔓延，引发灾难性后果。
- **Suggestion**:
  - 区分“基础设施不可用（如 `FileNotFoundError`）”和“程序运行崩溃（`returncode != 0`）”。如果是运行崩溃，应当直接返回 `{"ok": False, "error": f"CLI execution failed with exit code {r.returncode}: {r.stderr}"}`。

---

## Verified Claims

- **ecos 单元测试通过率** → 验证方法：在 `projects/ecos` 目录下运行 `uv run pytest tests/` → **PASS**
  - 验证结果：共 852 个用例，其中 849 个通过，3 个跳过（Skipped），测试整体绿色通过，耗时约 18.72 秒。
- **`trust_env=False` 屏蔽 proxy 成效** → 验证方法：静态代码审计与测试断言追溯 → **PASS**
  - 验证结果：`httpx.Client(trust_env=False)` 确实可以彻底避免本地 `127.0.0.1` RPC 流量经过外部代理，并避开了 SOCKS 代理相关的可选依赖项加载。
- **本地直调 CLI 物理可行性** → 验证方法：在终端中物理运行 `_CLI_PATHS` 中的命令 → **FAIL**
  - `python -m aetherforge.swarm` 报模块不可直接执行错（`No module named aetherforge.swarm.__main__`）。
  - `swarm_engine/cli.py` 运行报错参数不支持。
  - `cwd=Path.home()` 导致 `uv` 找不到项目结构直接中止。

---

## Coverage Gaps

- **AetherForge Swarm 集成测试覆盖度** — 风险等级：**Medium**
  - 当前测试均基于 `unittest.mock` 对 `subprocess.run` 和 `httpx.Client` 进行强 Mock 拦截，缺少一个能够真正检测子进程参数兼容性、物理可执行性的冒烟测试。建议后续在 `aetherforge` 端或 `ecos` 一侧增加一个非 Mock 的 CLI 真实调用检测。

---

## Unverified Items

- 无。本次审查的所有核心链条（单元测试、物理直调测试、静态依赖校验）均已得到物理独立验证。
