# Handoff Report

## 1. Observation (观测事实)

* **R1: ECOS Subprocess 进程直调**
  * 定位文件：`projects/ecos/src/ecos/workflow/backends/swarm.py`
  * 命令行路径 `_CLI_PATHS` (第 26-33 行): 
    * `["uv", "run", "--package", "aetherforge", "python", "-m", "aetherforge.swarm"]`
    * `[sys.executable, str(Path.home() / "Workspace" / "projects" / "aetherforge" / "packages" / "swarm" / "src" / "swarm_engine" / "cli.py")]`
    * `[str(Path.home() / "bin" / "aetherforge"), "swarm"]`
  * 命令行执行与传参 `_execute_step_swarm` 函数 (第 94 行):
    * `cmd = [*cli_cmd, "run", "--goal", goal, "--json"]`
    * `goal` 的取值: `step.get("description") or step.get("name") or action or "task"`

* **R2: Swarm 遗留事件与兼容 Stub**
  * 遗留兼容 Stub：`projects/aetherforge/packages/swarm/src/swarm_engine/_compat.py`
  * 孵化事件发布 `projects/aetherforge/packages/swarm/src/swarm_engine/_events.py` 的 `_emit_hatcher_event` 函数 (第 11-20 行):
    * 依赖本地伪 EventBus (`.event_bus`)，调用 `EventBus.get_instance().publish(event)`。
  * 生命周期事件发布 `projects/aetherforge/packages/swarm/src/swarm_engine/lifecycle_events.py` 的 `SwarmEventEmitter.emit` 函数 (第 58-85 行):
    * 尝试调用 `kairon_events.get_global_event_bus().publish(make_event(...))`，失败则静默捕获。
  * 现有的 `bus-foundation` 包及 API：
    * 路径：`projects/bus-foundation/src/bus_foundation/`
    * 统一发布入口 `bus_foundation/__init__.py`: `publish(envelope: BusEnvelope) -> str` (第 45-68 行)；
    * 统一订阅装饰器 `bus_foundation/__init__.py`: `subscribe(pattern: str)` (第 71-79 行)；
    * 统一信封格式 `bus_foundation/envelope.py` (第 27-122 行): `BusEnvelope` (又名 `OmniEnvelope`)，参数包含 `plane`, `topic`, `source_uri`, `payload` 等。

* **R3: Mesh 动态反馈与 Omo 稳态落盘闭环**
  * 底层 Mesh 检测到节点变更发布的地方：`projects/aetherforge/packages/mesh/src/compute_mesh/topology/registry.py` 的 `NodeRegistry` 类的 `register` (第 36-46 行) 与 `unregister` (第 48-58 行) 函数，其内部在修改字典结构后会调用 `self._notify("registered" / "updated" / "unregistered", node)`。
  * `NodeRegistry.add_listener`（第 106-112 行）可添加变化通知回调。
  * 上层 Omo 写入元模型的安全写回机制与落盘 API：
    * `projects/omo/src/omo/omo_ingress.py` 中 `write_system_projection_fields` (第 780-845 行) 通过 POSIX 文件锁 `fcntl_lock` (第 803 行) 保证写入并发，并通过 `write_yaml_atomic` (原子文件替换机制，定义在 `omo_io.py`) 将最新状态写回到 `state/system.yaml` 中，产生 `record_audit` (第 831 行) 审计日志以及 `_record_trail` (第 838 行) 轨迹记录，禁止 ad-hoc 直写行为。
    * 反向同步及物化工具：`projects/ecos/src/ecos/ssot/tools/mof-state-bridge.py` 内部，通过调用 `from omo.omo_io import write_yaml_atomic` 将状态安全写入 M1 元配置中（如 `compute_engine/` 或 `omo_layer/` 目录下的 `.yaml` 稳态文件）。

---

## 2. Logic Chain (逻辑链条)

* **R1 subprocess 重构**: 依据 **Observation 1** 确定 `ecos/workflow/backends/swarm.py` 为唯一直接产生 subprocess 命令直调 AetherForge Swarm 引擎的地方。因其功能单一（即执行工作流 step）、参数规则明确，可以直接在 `_execute_step_swarm` 入口处引入 `httpx` 连接 Agora Gate 统一路由，以 RPC 方式取代 `subprocess.run`。原有的 CLI 命令行执行仅作优雅回退降级（Fallback）之用，逻辑上是自洽且平滑的。
* **R2 事件总线替换**: 根据 **Observation 2**，Swarm 底层发布 Hatch/Lifecycle 事件时，强依赖了本地桩实现 `event_bus.py` 或可能缺失的全局 `kairon_events`。而 `bus-foundation` 模块已经成熟且暴露了标准的 `publish` 接口与 `BusEnvelope` 包装器。通过直接替换 `_emit_hatcher_event` 和 `SwarmEventEmitter.emit` 内部的逻辑，将事件统一以 `BusEnvelope` 打包并由 `bus_foundation.publish` 分发，从而能够彻底在物理层和逻辑层中下线 Swarm 本地冗余事件总线桩，消除了代码库的兼容坏味道。
* **R3 Mesh-Omo 稳态闭环**: 根据 **Observation 3**，Mesh 网格节点状态变动在 `NodeRegistry._notify` 中是确定可捕获的。配合 **Observation 2** 提供的 `bus-foundation`，在此处调用发布变更事件是最佳切入点。当 Omo 后台接收到此事件后，可以通过 Ingress 的 `write_system_projection_fields` 在锁和审计的双重保护下安全落盘到 `state/system.yaml`，并借由 `write_yaml_atomic` 写回到 M1 的 YAML 静态配置中，从而闭环实现了 “**动态变动捕捉 -> 事件推送 -> 校验控制 -> 审计原子写回**” 的整套流程。

---

## 3. Caveats (局限与盲点)

* 调研完全基于只读代码审计。部分与 Agora Gateway 或是 Omo 远程通信所需要的详细 arguments 格式定义，可能需要实际联调时根据协议 Schema 做适当微调。
* 本地 EventBus.py 在下线前，需要全面排查在 `projects/aetherforge/packages/swarm/` 中是否有其他地方的 listener 注册。若存在，需要同时迁移到 `bus-foundation` 订阅端。

---

## 4. Conclusion (明确的结论)

本调研证明，上述三项重构在当前代码库中切入点非常精准且清晰：
1. **R1** 切入点为 `ecos/workflow/backends/swarm.py` 的 `_execute_step_swarm`，将 subprocess 调用替换为 Agora MCP `resolve_bos_uri` RPC 调用。
2. **R2** 切入点为 `packages/swarm/src/swarm_engine/` 中的 `_events.py` 与 `lifecycle_events.py`，统一用 `bus-foundation` 代替本地 EventBus 桩。
3. **R3** 切入点为 `compute_mesh/topology/registry.py` 的 `NodeRegistry._notify` 处利用事件总线发布更新通知，并由 Omo 监听该事件后，经 `omo_ingress.py` 的 `write_system_projection_fields` 与 `write_yaml_atomic` 完成原子审计的 YAML 稳态落盘闭环。

---

## 5. Verification Method (如何独立验证)

1. **R1 校验**: 
   运行 ecos 的 workflow 测试确保当前机制无损：
   ```bash
   cd projects/ecos && uv run pytest tests/ -q
   ```
2. **R2 校验**: 
   在修改总线后运行 aetherforge/swarm 包的测试：
   ```bash
   cd projects/aetherforge/packages/swarm && uv run pytest tests/ -q
   ```
3. **R3 校验**: 
   使用 Omo 自身的单元测试和 Ingress 校验测试，确保 system.yaml 和 M1 双向同步流程正确性：
   ```bash
   cd projects/omo && uv run pytest tests/test_omo_ingress.py -q
   ```
