# Handoff Report — `bos://capability/swarm/run` RPC 重构分析

## 1. Observation (观察)

我们在只读状态下对整个工作区的关联代码进行了完整检索和审查，观察到以下核心物理事实：

1. **BOS 服务注册表形式**：
   `projects/agora/etc/bos-services.yaml` 采用声明式 YAML。存在 `internal` 传输类型的注册项，例如：
   ```yaml
     - uri: "bos://capability/bus/data"
       domain: capability
       action: "data"
       transport: internal
       package: "bus-foundation"
       module_path: "bus_foundation.facade.data"
       func_name: "emit"
   ```
2. **Agora 服务端解析器实现**：
   `projects/agora/src/agora/mcp/resolver/api.py` 的第 130-141 行：
   ```python
               if service.package and service.package != "agora":
                   pkg_path = str(Path(_WS) / "projects" / service.package / "src")
                   if pkg_path not in sys.path:
                       sys.path.insert(0, pkg_path)
   ```
   它动态加载 package 路径，然后使用 `importlib.import_module(service.module_path)` 加载模块。
3. **MCP 参数透传链路**：
   `projects/agora/src/agora/server/tools_bos.py` 第 252 行定义的 MCP 工具 `resolve_bos_uri`：
   ```python
       async def resolve_bos_uri(uri: str, arguments: dict | str = "{}") -> dict:
   ```
   第 276 及 290 行：
   ```python
               args = json.loads(arguments) if isinstance(arguments, str) else arguments
               ...
               result, source = await _resolve_with_router(
                   uri, proxy_manager=_get_proxy_manager(), **args
               )
   ```
   这表明外界传递的字典参数会最终以 `**kwargs` 形式透传给 RPC 目标函数。
4. **子包路径隐患**：
   `projects/aetherforge/src/aetherforge/swarm/__init__.py` 第 3-5 行：
   ```python
   from swarm_engine import __version__
   from swarm_engine.graph_workflow import GraphWorkflow
   ```
   而真实 `swarm_engine` 包的代码实际保存在 `projects/aetherforge/packages/swarm/src` 中。

---

## 2. Logic Chain (逻辑链)

1. **API 自动路由逻辑**：
   因为 Agora 服务端通过 `resolve_bos_uri` 内置了通用的 `internal` 反射加载机制（Observation-2），只要在 `bos-services.yaml` 中为 `bos://capability/swarm/run` 注册 `transport: internal`，指定模块为 `aetherforge.swarm.rpc`（Observation-1），其调用请求就会自动路由到对应的 Python 函数。
2. **参数转发的可行性**：
   通过 MCP 调用的参数 `arguments` 会在 `tools_bos.py` 中被解构为字典并解包传入（Observation-3），因此，我们的目标 Python 函数接收签名 `run_swarm_workflow(goal: str, **kwargs: Any)` 能够顺利接收参数。
3. **ModuleNotFoundError 的成立与避免**：
   当 `agora` 进程内调导入 `aetherforge.swarm` 时，因 `sys.path` 仅被追加了 `projects/aetherforge/src`，无法寻找到 `swarm_engine`（Observation-4）。因此，我们逻辑推导出必须在 `rpc.py` 内部引入动态补齐 `sys.path` 的操作，才能避免报错，并安全导入 `GraphWorkflow` 执行。

---

## 3. Caveats (注意事项)

1. **环境依赖一致性**：
   `internal` 模式在 `agora` 进程同进程内执行，如果 `aetherforge` 后端依赖的第三方库与 `agora` 的虚拟环境不同步，可能会抛出包导入异常。对此应确保根依赖使用 `uv` workspace 锁定。
2. **只读声明**：
   本次分析是在 `Read-only` 状态下完成，因此所有的修改（如 `analysis.md` 中的 `rpc.py` 伪代码和 `bos-services.yaml` 配置）均未在运行时执行修改或真实加载验证。

---

## 4. Conclusion (结论)

BOS 路由 RPC 方案设计成熟：
- **注册 YAML**：已在 `analysis.md` 中提供，采用 `internal` 直调。
- **Agora 服务端路由**：直接由 `resolver/api.py` 的 `resolve_bos_uri` 通用处理，无需修改 Agora 核心。
- **AetherForge 后端转发**：需在 `projects/aetherforge/src/aetherforge/swarm/` 下新建 `rpc.py`，实现带有路径自我补全功能的 `run_swarm_workflow` 转发工具，详细代码见 `analysis.md`。

---

## 5. Verification Method (验证方法)

代码由 Implementer 落地后，可按以下方式进行验证：

1. **单元与集成测试**：
   在 `projects/agora` 中运行其测试集，确保网格没有因为 YAML 格式错误崩溃：
   ```bash
   cd projects/agora && uv run pytest tests/
   ```
2. **API 发现状态**：
   调用 `omo bos discover` 命令行或使用 `bos_list()` MCP 工具，确认 `bos://capability/swarm/run` 已经被列入服务注册表。
3. **直接解析调用验证**：
   在 Python 脚本或 `agora` 调试控制台中执行以下代码，验证是否能正常返回工作流步骤和 `result` 字典且不抛出 `ModuleNotFoundError`：
   ```python
   import asyncio
   from agora.mcp.resolver.api import resolve_bos_uri

   async def test():
       res = await resolve_bos_uri("bos://capability/swarm/run", goal="测试分布式蜂群工作流")
       print(res)

   asyncio.run(test())
   ```
