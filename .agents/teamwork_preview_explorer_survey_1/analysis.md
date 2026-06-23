# 项目全局代码探测与重构方案调研报告

本报告对当前代码库中涉及的三个重构任务进行了详细调研与分析，定位了相关代码的具体位置、实现逻辑、API 依赖，并给出了具体的重构方案建议。

---

## 1. 【R1: ECOS 跨层 subprocess 调用】

### 1.1 现状定位与依赖分析
在 ECOS 工作流中，直接使用进程级 `subprocess` 命令行调用 AetherForge Swarm 引擎的代码位于：
* **文件路径**: `projects/ecos/src/ecos/workflow/backends/swarm.py`
* **关键变量**: `_CLI_PATHS` (第 26-33 行) 定义了被调用的三种命令行/脚本路径优先级：
  1. `["uv", "run", "--package", "aetherforge", "python", "-m", "aetherforge.swarm"]`
  2. `[sys.executable, str(Path.home() / "Workspace" / "projects" / "aetherforge" / "packages" / "swarm" / "src" / "swarm_engine" / "cli.py")]`
  3. `[str(Path.home() / "bin" / "aetherforge"), "swarm"]`
* **调用方式与传参**: 
  在 `_execute_step_swarm` 函数（第 84-120 行）中，构建命令参数并同步执行：
  ```python
  cmd = [*cli_cmd, "run", "--goal", goal, "--json"]
  ```
  其中 `goal` 的取值为 `step.get("description") or step.get("name") or action or "task"`。执行成功后获取 stdout 并将其反序列化为 JSON 格式返回；若执行出错或所有 CLI 均不可用，则降级为 Mock 记录行为。

### 1.2 跨层调用机制
当前 ECOS 作为一个 L0 协议层，遵循不直接 `import` L2 包的原则，因此跨层交互采用了 CLI 命令行 `subprocess` 直调的过渡方案。这在性能、跨平台和可观测性上存在限制，有必要收敛至 I0 Agora 统一路由。

### 1.3 方案建议与重构切入点
1. **Agora 侧 BOS 路由注册**:
   在 `projects/agora/etc/bos-services.yaml` 注册新路由：
   ```yaml
   - uri: "bos://capability/swarm/run"
     domain: capability
     action: "run"
     transport: internal
     module_path: "agora.mcp.swarm"  # 或是 aetherforge 内部模块
     func_name: "run_swarm_task"
     description: "执行 aetherforge 蜂群任务 (RPC 方式)"
   ```
   并在 Agora 中实现对应的 `run_swarm_task` 函数，将目标 `goal` 及参数转发给 AetherForge Swarm 引擎。
2. **ECOS Swarm Backend 重构**:
   重构 `projects/ecos/src/ecos/workflow/backends/swarm.py` 中的 `_execute_step_swarm` 方法。参考 `ecos/workflow/agora_mcp_backend.py`，改为通过 `httpx` 向 Agora Gateway (`http://127.0.0.1:7422/v1/tools/call`) 发起工具调用：
   * **Tool Name**: `resolve_bos_uri`
   * **Arguments**:
     ```json
     {
       "uri": "bos://capability/swarm/run",
       "arguments": {
         "goal": goal,
         "params": params
       }
     }
     ```
   如果 Agora 连接失败或返回错误，可以原样保留现有的 `_CLI_PATHS` subprocess 命令行调用和 Mock 机制作为降级（Fallback）方案，从而确保重构过程的平滑过渡。

---

## 2. 【R2: Swarm 底层事件总线替换】

### 2.1 Swarm 底层事件桩 (Stub) 现状
在 `packages/swarm/src/swarm_engine/` 中存在大量与 SharedBrain 遗留资产兼容的 Stub 定义，主要集中在以下文件：
* `_compat.py`: 桩定义，包括 `TaskType`, `WorkerState`, `Priority`, `GovernanceAction`, `GovernanceState`, `GovernanceEvent`, `BOSEventStub` 等。
* `dispatch_compat.py` & `ext/_compat.py`: 其他遗留交互的兼容适配。
* `event_bus.py`: 本地伪 EventBus 实现（行号 87-263）。在未检测到全局 `kairon_events` 依赖时（行号 44-77），回退至利用内部 `deque` 限制大小为 500 的本地事件派发桩。
* **主要事件发布入口**:
  1. `_events.py` 中定义的 `_emit_hatcher_event`（第 11-20 行）:
     ```python
     def _emit_hatcher_event(event_type: str, source: str, payload: dict | None = None) -> None:
         from .event_bus import EventBus, make_event
         # ...
         bus.publish(event)
     ```
     该函数主要被 `hatcher_core.py` 引用，用于在 Swarm 孵化器（Hatcher）对 Worker 节点进行初始化或回收时发送事件通知。
  2. `lifecycle_events.py` 中定义的 `SwarmEventEmitter.emit`（第 58-85 行）:
     调用 `kairon_events.get_global_event_bus().publish`，发出 Swarm 节点自身的运行生命周期事件。

### 2.2 `bus-foundation` 模块与 API 现状
* **模块路径**: `projects/bus-foundation/src/bus_foundation/`
* **核心接口** (`bus_foundation/__init__.py`):
  * `publish(envelope: BusEnvelope) -> str`: 发布事件的唯一物理入口，默认走 `eventbus` 后端。
  * `subscribe(pattern: str)` (装饰器): 订阅具有特定 pattern 的事件。
* **数据结构** (`bus_foundation/envelope.py`):
  * `BusEnvelope` (即 `OmniEnvelope`): 统一的消息信封。包含 `plane` (默认为 "EVENT")、`topic` (即 event_type)、`source_uri` (事件来源 URI)、`payload` 等核心字段。

### 2.3 替换方案建议
1. **替换 `_emit_hatcher_event`**:
   移除 `_events.py` 对本地桩 `.event_bus` 的依赖，直接引入 `bus-foundation`，将事件信封标准化：
   ```python
   from bus_foundation import publish, BusEnvelope, OmniPlane

   def _emit_hatcher_event(event_type: str, source: str, payload: dict | None = None) -> None:
       try:
           envelope = BusEnvelope(
               plane=OmniPlane.EVENT,
               topic=event_type,
               source_uri=source,
               payload=payload or {}
           )
           publish(envelope)
       except Exception as e:
           _log.debug("[HatcherEvents] Failed to emit hatcher event: %s", e)
   ```
2. **替换 `SwarmEventEmitter.emit`**:
   同样使用 `bus-foundation` 统一发布接口，替代可能不存在的 `kairon_events`。
3. **下线本地 `event_bus.py`**:
   在将所有事件生产端替换为 `bus-foundation` 后，可彻底删除 Swarm 中冗余的 `event_bus.py` 以及 `_compat.py` 内部的部分事件桩定义，完成总线层面的去耦与收敛。

---

## 3. 【R3: Mesh 动态反馈与 Omo 稳态落盘闭环】

### 3.1 Mesh 状态变更捕捉与发布
* **位置定位**: `projects/aetherforge/packages/mesh/src/compute_mesh/topology/registry.py` 中的 `NodeRegistry`。
* **变更逻辑**: 
  在 `register` (行号 36-46) 和 `unregister` (行号 48-58) 时，分别根据操作结果触发 `_notify("registered" / "updated" / "unregistered", node)`。
* **事件发布重构建议**:
  可以在 `_notify` 函数（第 119-125 行）中，利用 `bus-foundation` 实时发布节点状态改变的通知事件：
  ```python
  from bus_foundation import publish, BusEnvelope, OmniPlane

  def _notify(self, event: str, node: ComputeNode) -> None:
      # 1. 触发原有的本地 listener 逻辑
      for listener in self._listeners:
          try:
              listener(event, node)
          except Exception:
              _log.exception("NodeRegistry listener failed")
      
      # 2. 动态向事件总线广播节点状态变化
      try:
          envelope = BusEnvelope(
              plane=OmniPlane.EVENT,
              topic=f"mesh:node:{event}",  # 产生 mesh:node:registered, mesh:node:updated 等事件
              source_uri=f"mesh://node/{node.node_id}",
              payload=node.to_dict()
          )
          publish(envelope)
      except Exception as e:
          _log.warning("Failed to publish node change event: %s", e)
  ```

### 3.2 Omo 稳态落盘与安全审计逻辑
当 Omo 治理引擎接收到 Mesh 节点的变动事件时，执行安全校验并写回 M1 配置的闭环需要使用以下两个关键机制：

1. **Omo Ingress 安全校验与系统更新** (`projects/omo/src/omo/omo_ingress.py`):
   * `write_system_projection_fields` (行号 780-846) 是更新全局 `state/system.yaml` 的 Ingress 入口。
   * 它使用了 POSIX 文件锁 `fcntl_lock`（第 803 行）对写操作加锁以防止并发冲突，并通过 `write_yaml_atomic` 实现原子的临时文件写入与替换。
   * 同时它会强制调用 `record_audit` (行号 831) 和 `_record_trail` (行号 838) 写入 Ingress 审计日志，保证操作满足审计合规性，完全杜绝 ad-hoc 任意直写引起的一致性破坏。
2. **M1 YAML 稳态落盘机制** (`projects/ecos/src/ecos/ssot/tools/mof-state-bridge.py`):
   * Omo 通过 `omo_io.py`（以及重构后的 `omo._shared.append_only_log`）提供了 `write_yaml_atomic` 和 `AppendOnlyLog` 的原子读写 API。
   * `mof-state-bridge.py` 内部在处理 M1 配置写回时，会通过 `write_yaml_atomic(path, data)` 原子写入到对应的 M1 `.yaml` 配置文件中（如 `projects/ecos/src/ecos/ssot/mof/m1/omo_layer/` 或是 `compute_engine/` 下）。

### 3.3 闭环链路方案建议
1. **订阅组件**: 在 Omo 治理端（例如 L4 Kernel 的后台服务）通过 `bus_foundation.subscribe("mesh:node:*")` 注册事件监听。
2. **安全审计与白名单校验**: 
   收到事件后，从 payload 取出 `ComputeNode` 数据。检查其是否符合 L0 层的合规要求（即 `projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml` 约束），并比对变更是否经过授权。
3. **M1 与 System 状态写回**:
   * 调用 `write_system_projection_fields` 将状态同步并物化更新至 `.omo/state/system.yaml`，以此更新 Omo 本地稳态状态。
   * 利用 `write_yaml_atomic` 写回到 M1 对应的节点定义 YAML 中（例如 `projects/ecos/src/ecos/ssot/mof/m1/compute_engine/{node_id}.yaml`），以确保元配置与物理层的一致。由此在不需要人工介入的情况下，完成 “**Mesh 检测状态变更 -> 总线通知 -> Omo 校验拦截 -> Ingress 原子锁写回 -> 审计落盘记录**” 的稳态闭环。
