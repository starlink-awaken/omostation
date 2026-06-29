# 全面重构 aetherforge swarm 与对齐 ecos workflow

## 0.1 竞品与现状调研 (Research & Benchmarking)
1. **系统内部代码与组件现状**：
   * **Swarm 引擎遗留问题**：经过我们使用 Python 虚拟机对 14 个在 `packages/swarm/MERGE-NOTES.md` 中标记为遗留导入错误的模块进行物理诊断，发现实际上只有 5 个模块在导入时会引发致命异常，另外 9 个已可正常导入。
   * **缺失的依赖链**：目前 `packages/swarm` 下缺少原版 SharedBrain 的 `organs` 和 `nucleus` 子系统，以及 hatcher 相关的 `_events` 常量和发射工具。
   * **CLI & 编排断链**：`ecos workflow` 中的 `swarm` 后端尝试通过 `subprocess` 调用 `aetherforge swarm run --goal <goal> --json`。但在主 CLI `src/aetherforge/cli.py` 中，此命令目前只是一个 Mock（返回 `not yet implemented`），导致 `ecos` 的 Swarm 工作流调用全部 fallback 降级为 mock passed，并未真正执行。
2. **为什么必须自研与修复**：
   * 为了实现 eCOS v5/v6 架构下 L0 蜂群引擎对上层 L3 cockpit 和 L0 ecos 编排的真实算力与协同支撑，必须打通 CLI 执行链路，救活被遗留导入错误“冻结”的 Swarm 多智能体组件，保证 100% 模块可安全导入与调用。

## 0.2 关键决策对齐 (Critical Decisions)
1. **[决策点1] 如何救活由于缺少 organs/nucleus 模块而无法导入的 Swarm 遗留文件？**
   - AI推荐: 在 `packages/swarm/src/swarm_engine/_compat.py` 中新增 `AgentProfile`、`IntentParticle`、`MetabolicStage`、`VisionParser` 等 Stub，并将对应文件导入路径重定向到 `._compat`，最大程度保持 `[LIBRARY-ONLY]` 的精简与自闭环。
   - 您的选择: AI推荐 (使用 _compat.py 进行 Stub 适配，解耦旧 nucleus 依赖)。
2. **[决策点2] 如何打通与 ecos workflow 的连接，避免 mock fallback？**
   - AI推荐: 重新实现 `aetherforge` 的 Swarm CLI 接口，使其支持 `run --goal <goal> --json`。在内部通过实例化 `GraphWorkflow` 对接 LLM 驱动的 agent，来接收并真实执行工作流分步任务。
   - 您的选择: AI推荐 (支持真实 run 命令对接，支持 GraphWorkflow 实例化调用)。
3. **[决策点3] ils_engine 中的多继承 Python 语法错误（TypeError）如何修复？**
   - AI推荐: 废弃将 `ShieldMixin` 和 `WitnessMixin` 直接作为 `object` 的做法（这会导致 `class ImmuneLawSystem(object, object)` 的多重 object 报错），改为定义局部空的 `class ShieldMixin: pass` 与 `class WitnessMixin: pass` 以保持完美的继承树。
   - 您的选择: AI推荐。

---

## 1. 方案细化与定型 (Solution Refinement)
1. **Swarm 兼容垫片修补**：
   * 在 `_compat.py` 中创建所需的模型 Stub，并将 `nks_task_planner.py`、`universal_worker.py` 和 `vision_metabolizer.py` 中的 `from .organs import ...` 替换为 `from ._compat import ...`。
2. **hatcher 常量与事件总线注入**：
   * 创建 `_events.py`，实现 `_DEFAULT_HATCH_TIMEOUT_S = 60.0` 和 `_PROCESS_POLL_INTERVAL_S = 0.5`，并在 `_emit_hatcher_event` 中桥接 `swarm_engine.event_bus` 实例向总线发布事件，恢复 `hatcher_core.py` 导入。
3. **真实 CLI 驱动**：
   * 在 `src/aetherforge/cli.py` 中，编写 `cmd_swarm` 的真实命令处理逻辑。当执行 `aetherforge swarm run --goal <goal> --json` 时，通过 `aetherforge.gateway` 的 LLM 实例去解决给定的 `--goal` 目标，并以 JSON 格式打印标准输出，完全满足 `ecos workflow` 的 subprocess 调用要求。

## 2. 可行性与必要性审查 (Feasibility & Necessity)
* **ROI 分析**：该方案不引入外部第三方重量级框架，只利用 Python 内置标准库与 `_compat.py` 修补机制，即可救活 5 个核心协同组件并打通跨层调用，修改成本极低，投资回报率（ROI）极高。

## 3. 架构审查 (Architecture Review)
* 符合 **BOS 域映射** 约束。`aetherforge-swarm` 仅在 L0 协议层下作为一个 `[LIBRARY-ONLY]` 的底层能力库，不直接挂载 HTTP 端口。跨层交互严格经过 `aetherforge CLI` 这一标准化入口。

## 4. 治理审查 (Governance Review)
* 本次修改不增加任何外部未授权端口。符合 `projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml` 下对横切蜂群组件的规则约束，不引入新的 OMO Debt。

## 5. 红队分析 (Red Team Analysis)
1. **输入 goal 极其庞大导致 LLM 崩溃**：需要限制 `--goal` 输入文本的长度并作异常拦截，如果执行失败，CLI 必须返回非 0 退出码及 stderr 以让 `ecos workflow` 识别。
2. **并发运行冲突**：由于 CLI 委托给 python 解释器执行，应保证其为 stateless（无状态），临时运行不冲突。

## 6. 用户视角审查 (User Perspective)
* 用户通过统一入口 `aetherforge swarm run` 调试，能清晰观察到智能体如何对具体目标进行分解和执行。

## 7. 质量保障 (Quality Assurance)
### 7.1 测试计划 (Test Plan)
* 将 `test_swarm_engine_imports.py` 中本被排除的 5 个遗留冷文件重新加入测试集，运行并确保 `make test` 100% 通过。
### 7.2 验收证据 (Evidence Required)
* `make test` 测试全部通过日志。
* 运行 `aetherforge swarm run --goal "test task" --json` 不报错并返回合法的 JSON payload。

---

## 🎯 任务拆解 (GSD Action Items)
- [x] 任务1: 更新 `packages/swarm/src/swarm_engine/_compat.py`，加入 `AgentProfile`、`IntentParticle`、`MetabolicStage`、`VisionParser` 兼容 Stub，定义 `WORKER_REGISTRY` 与 `get_worker_profile`。
- [x] 任务2: 创建 `packages/swarm/src/swarm_engine/_events.py`，实现 timeout/poll 常量定义及 `_emit_hatcher_event` 函数。
- [x] 任务3: 修改 `packages/swarm/src/swarm_engine/ils_engine.py`，改写 `ShieldMixin` 和 `WitnessMixin` 局部类定义以修复继承 TypeError。
- [x] 任务4: 修改 `hatcher_core.py`、`nks_task_planner.py`、`universal_worker.py`、`vision_metabolizer.py`，更新其 `.organs` 及 `._events` 导入指向。
- [x] 任务5: 修改 `packages/swarm/tests/test_swarm_engine_imports.py`，把原本不包含的 5 个模块从遗留黑名单中移出并加入 `MERGED_MODULES`，运行测试。
- [x] 任务6: 重新实现 `src/aetherforge/cli.py` 里的 `cmd_swarm`，使其打通并支持 `aetherforge swarm run --goal ... --json` 命令行接口。
