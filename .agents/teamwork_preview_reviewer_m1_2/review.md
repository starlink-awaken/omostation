# M1 里程碑 - Agora 路由与反射桥接评审报告

## Review Summary

**Verdict**: REQUEST_CHANGES

## Findings

### 🔴 [Critical] Finding 1: 动态 `sys.path` 补全位置错误导致 `ModuleNotFoundError`
- **What**: AetherForge 桥接模块 `rpc.py` 内部所做的局部 `sys.path` 补全未能生效，导致在 internal 模式直调时导入失败。
- **Where**: `projects/aetherforge/src/aetherforge/swarm/rpc.py` 第 8-14 行
- **Why**: 当 Agora 试图通过反射导入 `aetherforge.swarm.rpc` 时，Python 的模块加载机制会优先导入父包 `aetherforge.swarm`。而 `aetherforge/swarm/__init__.py` 头部直接导入了 `swarm_engine`。由于此时 `rpc.py` 的补全逻辑还未执行，`sys.path` 缺失 `packages/swarm/src`，因此在加载父包时就会触发 `ModuleNotFoundError: No module named 'swarm_engine'`，导入流程提前崩溃。
- **Suggestion**: 应该将对 `packages/swarm/src`、`packages/gateway/src` 以及 `packages/mesh/src` 的 `sys.path` 补全逻辑统一移至 AetherForge 项目的主入口 `projects/aetherforge/src/aetherforge/__init__.py` 中。这样任何 `aetherforge.*` 子模块被加载时都会先触发主包的初始化，从而确保全局 sys.path 的一致性。

### 🟡 [Major] Finding 2: `sys.path` 补全不完整导致 `llm_gateway` 导入失败
- **What**: 即使解决了父包 `__init__.py` 的导入问题，`rpc.py` 在执行到 `from aetherforge.gateway import create_provider` 时，会因为 `sys.path` 缺失 `packages/gateway/src` 而在加载 `aetherforge/gateway/__init__.py` 时再次抛出 `ModuleNotFoundError: No module named 'llm_gateway'`。
- **Where**: `projects/aetherforge/src/aetherforge/swarm/rpc.py` 第 18 行
- **Why**: 补全设计中漏掉了 `llm_gateway` 和 `compute_mesh` 的路径。对于 `aetherforge` 这样通过 `uv workspace` 管理的多子包项目，在 internal 反射运行时其整体的 `sys.path` 应该统一进行完整补齐，而不仅仅是补齐 `swarm` 一个包。
- **Suggestion**: 与 Finding 1 建议一致，在 AetherForge 主入口一次性补齐所有的 packages 路径。

### 🟡 [Major] Finding 3: 任务规划节点过度吞异常导致“假成功”
- **What**: `run_swarm_workflow` 中的 `plan_task` 节点中对 Gateway 执行异常做了全量捕获（`try...except Exception`）且仅打印 warning，没有将异常状态透传。
- **Where**: `projects/aetherforge/src/aetherforge/swarm/rpc.py` 第 46-60 行
- **Why**: 当本地 Gateway 实际配置错误或 API 熔断导致规划失败时，虽然工作流在规划节点中优雅降级为 raw 字符串，但对外输出的最终状态仍为 `status: success`。这在 RPC 语义上是不健壮的，外界无法感知其实底层核心大模型规划已经失败。
- **Suggestion**: 在捕获到规划阶段异常时，应在 `state` 树中写入降级状态或错误记录（例如累加到 `_errors` 中），使得最终返回的 status 能客观反映执行链路的真实健康度。

### 🟢 [Minor] Finding 4: llm_gateway 模块中存在 asyncio 事件循环冲突风险
- **What**: `llm_gateway` 内部模块在加载时遇到了 `asyncio.run() cannot be called from a running event loop` 警告。
- **Where**: `llm_gateway.mcp_server.py` 第 28 行
- **Why**: 导入或初始化时调用了同步风格的 `asyncio.run()`，在有已有事件循环的 Agora 同进程反射直调时会触发冲突警告，导致 M1 nodes 初始化失败。
- **Suggestion**: 应该将该初始化动作重构为异步初始化或懒加载，规避静态导入时的同步事件循环占用。

---

## Verified Claims

- **BOS 路由注册准确性** → 审查 `projects/agora/etc/bos-services.yaml` → **PASS**。符合 internal transport 注册规范，配置参数无误。
- **Swarm 单元测试通过性** → `cd projects/aetherforge/packages/swarm/ && uv run pytest tests/` → **PASS**。65 个测试用例全数通过。
- **AetherForge 整体测试通过性** → `cd projects/aetherforge/ && uv run pytest` → **PASS**。86 个测试用例全数通过。
- **动态 `sys.path` 补全设计是否能彻底规避 `ModuleNotFoundError`** → 模拟测试验证 → **FAIL**。因为导入时父包 `aetherforge.swarm.__init__.py` 率先抛出 `No module named 'swarm_engine'`，且由于 gateway 子包缺失，随后还会触发 `No module named 'llm_gateway'`。
- **internal 模式反射执行 GraphWorkflow 是否符合设计意图** → 手动补齐 `sys.path` 后运行 `bos_resolver` 反射直调 → **PASS**。能够成功初始化 `GraphWorkflow`，按拓扑先后执行“任务规划”和“任务执行”节点并返回标准的序列化结果。

---

## Coverage Gaps

- **本地 Gateway 实体的多智能体协同（如 CrewAI 的具体交互逻辑）**
  - *风险等级*: 低
  - *建议*: 接受风险，目前 M1 milestone 为路由反射和桥接机制打通，局部 gateway 降级机制已就绪。
- **Agora 跨进程 stdio 通道下的性能损耗**
  - *风险等级*: 中
  - *建议*: 后续在集成测试中开展 benchmark 评估。
