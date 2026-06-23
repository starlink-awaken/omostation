## 2026-06-23T02:57:14Z
【任务：M1 里程碑 - Agora I0 MCP 跨层通信重构代码实现】
你是一个全栈开发智能体（teamwork_preview_worker）。
你的身份是：m1_worker_1。
你的工作目录是：/Users/xiamingxing/Workspace/.agents/teamwork_preview_worker_m1_1/。

请阅读项目全局设计文件 PROJECT.md、详细计划 plan.md 以及以下 3 个 Explorer 提交的方案报告：
- ECOS 客户端调用设计：/Users/xiamingxing/Workspace/.agents/teamwork_preview_explorer_m1_1/analysis.md
- Agora 服务注册与路径补全：/Users/xiamingxing/Workspace/.agents/teamwork_preview_explorer_m1_2_gen2/analysis.md
- 降级与特异性环境处理：/Users/xiamingxing/Workspace/.agents/teamwork_preview_explorer_m1_3/analysis.md

你的具体任务：
1. 【修改 Agora 路由注册】
   在 `projects/agora/etc/bos-services.yaml` 中注册 `bos://capability/swarm/run`。推荐使用 `internal` 高性能传输模式，指向 `aetherforge.swarm.rpc` 模块中的 `run_swarm_workflow` 函数。

2. 【实现 Agora RPC 桥接处理】
   在 `projects/aetherforge/src/aetherforge/swarm/rpc.py` 处新建文件，实现 `run_swarm_workflow(goal: str, **kwargs: Any) -> dict[str, Any]`。
   - 必须在文件头部加入动态 `sys.path` 补全逻辑（将 `projects/aetherforge/packages/swarm/src` 加入 `sys.path`），解决 `swarm_engine` 的 `ModuleNotFoundError`。
   - 反射并调用底层的 `GraphWorkflow` 执行多智能体 Swarm 工作流任务并返回标准 JSON-RPC 字典，参照前任报告中的 Sketch 设计。

3. 【重构 ECOS 跨层调用与降级】
   修改 `projects/ecos/src/ecos/workflow/backends/swarm.py`。
   - 重构 `_execute_step_swarm` 函数，首先尝试使用 `httpx` 向 Agora Gateway (`http://127.0.0.1:7422/v1/tools/call` 或合适端点) 触发 `resolve_bos_uri` 来调用 `bos://capability/swarm/run`。
   - 在客户端请求中必须显式设置 `trust_env=False` 强行忽略系统代理，防止 SOCKS5 代理导致探测失败。
   - 使用宽泛的异常捕获（包含 `ImportError`、`ConnectError` 等），在 Agora 不可用或返回 business 错误时，打印 fallback 降级日志，并优雅切入本地原有的 subprocess 直调逻辑作为兜底防线。

4. 【编写与运行验证测试】
   - 在 `projects/ecos/tests/` 目录下编写单元集成测试（如 `test_swarm_no_subprocess.py`），利用 Popen Mock 机制，验证在执行工作流时决不产生针对 `aetherforge` CLI 命令的子进程，同时验证 Agora 成功路由 RPC 响应。
   - 运行项目相关的测试集验证：
     - 运行 ecos 单元测试：在 `projects/ecos/` 运行 pytest；
     - 运行 swarm 单元测试：在 `projects/aetherforge/packages/swarm/` 运行 pytest；
     - 记录测试输出，以确保代码编译与功能无损。

5. 【提交说明】
   - 任务完成后，在你的工作目录下写入 `changes.md` 说明你的修改细节，以及 `handoff.md`。
   - 严格遵循 “修改后立即 git commit” 的机制。
   - 完成后，使用 send_message 向我报告（Conversation ID: d6d08efc-a7bd-44e1-8861-e985ac7a8c92）。

【MANDATORY INTEGRITY WARNING】
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.
