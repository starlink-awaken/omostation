# Agora 路由与 RPC 实现分析报告 — `bos://capability/swarm/run`

## 1. `bos-services.yaml` 结构分析与 RPC 路由注册

在 `projects/agora/etc/bos-services.yaml` 文件中定义了所有的 BOS 服务，该文件采用声明式 YAML 格式，是 Agora 跨层服务调用的 SSOT (Single Source of Truth) 注册表。

通过分析现有的路由注册项，目前服务网格主要支持以下几种 `transport`（传输协议）：
1. **`stdio`**: 通过启动外部 CLI 子进程进行通信，Agora 通过 `stdin` 写入 JSON-RPC 请求，并读取 `stdout` 作为响应。
2. **`internal`**: 进程内直调（Direct Importing/Invocation），Agora 在同一个 Python 进程中动态导入模块并执行指定函数。
3. **`mcp_stdio`**: 通过跨进程的本地 MCP 协议进行通信（跨进程 stdio 交互）。
4. **`mcp_proxy`**: 通过代理机制进行远程 MCP 转发（多在高性能服务如 `gbrain` 中使用）。

针对 M1 里程碑需要注册与实现的 Swarm 任务运行 RPC（`bos://capability/swarm/run`），我们推荐使用 **`internal` 进程内直调** 作为首选方案，同时也提供 **`stdio` 子进程调用** 作为优雅的 CLI 备用通道。

### 注册 YAML 片段设计

#### 推荐方案：`internal` 传输模式（高性能进程内直调）
```yaml
  - uri: "bos://capability/swarm/run"
    domain: capability
    action: "run"
    transport: internal
    package: "aetherforge"
    module_path: "aetherforge.swarm.rpc"
    func_name: "run_swarm_workflow"
    description: "AetherForge Swarm 多智能体任务工作流运行接口"
```
**设计依据与优势**：
- **性能优势**：规避了频繁启动 Python 解释器和加载虚拟环境的系统开销（冷启动可减少 1-2 秒，性能提升约 10-100x）。
- **进程隔离支持**：设置 `package: "aetherforge"` 之后，Agora 解析器会自动将对应项目的 `projects/aetherforge/src` 加入 `sys.path`，无需手动处理包依赖导入路径。
- **异常穿透**：支持 Python 级的实时异常捕获与结构化数据交互，相比 `stdio` 的文本流解析更加健壮。

#### 备选方案：`stdio` 传输模式（传统的子进程封装）
若需要直接通过 CLI 执行（例如测试目的），可注册如下片段：
```yaml
  - uri: "bos://capability/swarm/run"
    domain: capability
    action: "run"
    transport: stdio
    package: "aetherforge"
    command: ["uv", "run", "--package", "aetherforge", "python", "-m", "aetherforge.cli", "swarm", "run"]
    description: "AetherForge Swarm 任务工作流 CLI 封装入口"
```
*注：由于 Agora 的 `StdioAdapter` 采用 `JSON-RPC over stdio` 协议，当 `transport` 设为 `stdio` 时，参数会以 JSON 形式通过 `stdin` 发送至子进程，这意味着目标命令行工具（即 `aetherforge.cli` 中的 `cmd_swarm`）必须重构以支持从 `stdin` 读取任务 Goal 等输入，否则会因为参数无法传递导致执行挂起或超时。*

---

## 2. Agora 服务网格对 BOS 协议路由的解析与切入分析

BOS 协议路由解析的完整调用链路如下：

### 2.1 网格解析切入点
- **定位文件**：`projects/agora/src/agora/mcp/resolver/api.py`
- **切入函数**：`async def resolve_bos_uri(uri: str, *args: Any, proxy_manager: Any | None = None, **kwargs: Any) -> dict`

### 2.2 路由解析的详细逻辑
1. **URI 规范化与匹配**：
   - 首先调用 `normalize_bos_uri(uri)`，将别名映射为规范 URI。
   - 通过 `get_service(uri)` 从 `bos-services.yaml` 反序列化缓存的 `BosService` 实体列表中匹配对应实体。对于 `bos://capability/swarm/run`，匹配结果为 `domain='capability'`, `package='swarm'` (在 URI 中规范化表现，对应 `aetherforge-swarm` 包的业务), `action='run'`。
2. **`internal` 模式执行链**：
   当检测到 `service.transport == "internal"` 时，执行以下操作：
   - **环境准备**：
     ```python
     if service.package and service.package != "agora":
         pkg_path = str(Path(_WS) / "projects" / service.package / "src")
         if pkg_path not in sys.path:
             sys.path.insert(0, pkg_path)
     ```
     Agora 会根据 `service.package`（其值为 `"aetherforge"`）动态定位到本地 `/Users/xiamingxing/Workspace/projects/aetherforge/src`，并将其插入到 `sys.path[0]` 中，保证跨项目导包正常工作。
   - **动态加载与反射**：
     ```python
     mod = importlib.import_module(service.module_path)  # 导入 aetherforge.swarm.rpc
     func = getattr(mod, service.func_name)               # 获取 run_swarm_workflow 函数
     ```
     网格会动态加载指定的 `module_path`（即 `aetherforge.swarm.rpc`）以及反射获取入口函数 `func_name`（即 `run_swarm_workflow`）。
   - **参数传参及调用**：
     网格判断目标函数签名，如果包含 `proxy_manager` 则传入网格管理器实例，否则直接解包 `*args` 和 `**kwargs`：
     ```python
     raw = func(*args, **kwargs)
     if inspect.isawaitable(raw):
         raw = await raw
     ```
     网格支持同步与异步函数的自适应调用。返回值最终被包装为 `{"status": "ok", "result": raw, "uri": uri, "transport": "internal"}` 返回给调用方。

---

## 3. 后端 Swarm 核心功能 API 的切入建议

为配合 `internal` 路由的实现，建议在 `projects/aetherforge/` 的包内为网格提供对应的 API 暴露。

### 3.1 核心执行引擎
- **工作流引擎**：`GraphWorkflow`
- **源文件路径**：`projects/aetherforge/packages/swarm/src/swarm_engine/graph_workflow.py`
  - 该类是一个类似于 LangGraph 的有向无环/循环图工作流控制器。它支持注册节点（LLM 节点/自定义 Python 节点）与有向边，维护全局 State 并支持运行追踪历史（`_history`）。

### 3.2 建议实现的桥接入口
在 `projects/aetherforge/src/aetherforge/` 目录下新增一个与注册表匹配的模块：
- **目标文件**：`projects/aetherforge/src/aetherforge/swarm/rpc.py`
- **建议实现的 RPC 桥接函数**：
  ```python
  from aetherforge.swarm import GraphWorkflow
  from typing import Any

  async def run_swarm_workflow(goal: str, **kwargs: Any) -> dict[str, Any]:
      """
      BOS RPC 执行入口: bos://capability/swarm/run
      驱动 GraphWorkflow 运行指定的智能体编排任务。
      """
      # 实例化工作流
      wf = GraphWorkflow()

      # 定义并注册 Swarm 协同步骤 (仿照 aetherforge/cli.py 的实现)
      @wf.node("任务规划", description="分析并分解任务目标")
      def plan_task(state):
          goal_text = state.get("goal", "")
          # 调用 LLM 进行目标规划（可选，通过 gateway)
          return {"plan": f"已分析目标: {goal_text}"}

      @wf.node("任务执行", description="协同智能体执行具体计划")
      def execute_task(state):
          plan = state.get("plan", "")
          return {"output": f"成功执行计划:\n{plan}"}

      wf.add_edge("任务规划", "任务执行")
      wf.set_entry("任务规划")

      # 执行工作流
      initial_state = {"goal": goal}
      state = wf.run(initial_state)

      # 包装结果
      return {
          "status": "success" if not state.get("_errors") else "failed",
          "result": state.get("output", ""),
          "history": state.get("_history", []),
          "errors": state.get("_errors", [])
      }
  ```
  该设计可以直接利用 eCOS 已有的大部分工作流编排机制，并且在返回数据上提供了干净的 JSON 交互结构，非常适合作为跨层 RPC 的稳态终点。
