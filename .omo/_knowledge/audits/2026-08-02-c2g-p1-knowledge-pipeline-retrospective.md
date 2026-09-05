---
last-reviewed: 2026-08-25
lifecycle: history
owner: unassigned
type: ephemeral
status: archived
---

# C2G 预测性结果至知识图谱发布管线 (P1) —— 深度复盘与迭代优化报告

> **日期**: 2026-08-02  
> **会话**: C2G P1 全面落地 (PR #750 Follow-up & ADR-0296)  
> **相关组件**: `projects/c2g`, `projects/omo`, `bin/ssot/ssot-guardian.py`  
> **合规基线**: SharedBrain 核心基因指令（真实、客观、严谨、公正）、ADR-0203/0204

---

## 1. 任务目标与背景

随着 C2G 预测性引擎（PredictiveEngine, ADR-0185）的构建，系统能够输出基于 EMA 与线性回归对任务及 Pitch 成功率的长期预测和战略风险热力图。为了打通与 Omostation 决策控制层（Cockpit）与知识中枢（Agora / KOS / LanceDB）的闭环，我们需要将 C2G 评估生成的策略报告转换成规范的“知识卡片（Knowledge Cards）”并通过事件总线进行持续分发。

本轮迭代通过落地 **ADR-0296 (C2G Predictive Outcomes to Knowledge Graph Pipeline)**，完成了数据生产者与知识处理器的端到端衔接，并在实战中进行了深层的系统优化与技术固化。

---

## 2. 核心技术痛点与迭代优化实践

### 2.1 优化点一：叶子层级隔离与双通道零阻塞降级 (Dual-Channel Resilient Delivery)
- **痛点与约束**：
  根据分层依赖契约，`projects/c2g` 属于纯粹的策略与分析叶子层（Zero-dependency leaf layer），严禁反向引用 `projects/cockpit` 或 `projects/agora` 等运行时具体服务实现，否则将导致循环依赖与分层违纪。
- **优化落地**：
  在 `projects/c2g/src/c2g/knowledge_publisher.py` 中实现了纯 HTTP API 通信与优雅降级控制：
  1. **主通道 (Agora MCP)**：默认优先调用 `http://127.0.0.1:8001/v1/tools/call` 的 `publish_event` 接口，发布标准事件 `bos://brain/events/card_updated`。
  2. **次通道 (Cockpit HTTP)**：一旦 Agora 不可达或抛出连接异常，无缝 fallback 至 Cockpit 知识存储接口 `http://127.0.0.1:8100/api/knowledge/put`。
  3. **离线高可用降级 (Offline Degradation)**：若本地无任何图谱服务在启动状态，请求绝不阻塞或抛出连接错误而中断 C2G 命令行报告的输出，而是自动封装完整知识 Payload 结构，并在报告中标记 `status: degraded_offline`。使得 CLI 在纯单机环境下具备 100% 稳定性。

### 2.2 优化点二：上下文管理器模式下 HTTP 客户端 Mock 固化策略 (Context Manager Mocking Pattern)
- **痛点发现**：
  在编写对 `knowledge_publisher` 的单测时，一开始直接针对 `httpx.Client.post` 进行了 `@patch.object(httpx.Client, "post")`，但在单元测试运行中始终返回 `degraded_offline`。
- **根因追溯**：
  真实业务代码使用的是上下文管理器模式：
  ```python
  with httpx.Client(timeout=timeout) as client:
      resp = client.post(...)
  ```
  直接 mock 方法类对象没有模拟 `__enter__` 与 `__exit__` 协议对实例作用域的创建，导致 mock 被绕过。
- **最佳实践固化**：
  对于 Python 中包含 Context Manager 的第三方对象，统一使用模块类拦截策略：
  ```python
  @patch("c2g.knowledge_publisher.httpx.Client")
  def test_publish_outcome_card_mock_agora(mock_client_cls):
      mock_client = MagicMock()
      mock_client_cls.return_value.__enter__.return_value = mock_client
      mock_resp = MagicMock()
      mock_resp.status_code = 200
      mock_resp.json.return_value = {"status": "ok", "event_id": "evt-123"}
      mock_client.post.return_value = mock_resp
      # ...
  ```
  通过直接控制 `__enter__.return_value`，成功将 6/6 个新单测完全通过，避免后续出现假阳性/假阴性。

### 2.3 优化点三：彻底根除 OMO 任务统计真理层口径漂移 (SSOT Drift Root-Cause Fix)
- **痛点发现**：
  在执行完整门禁守门员 `ssot-guardian.py` 时，反复出现 `task_count_drift (high)` 报错：
  ```
  system: {'completed': '0', 'planned': '3', 'active': '0', 'total': '3'}
  actual: {'active': 0, 'planned': 3, 'done': 225, 'total': 228}
  ```
  即使运行 `omo state sync-tasks`，写入 `system.yaml` 的 `completed_tasks` 依然是 `0`。
- **深层元认知诊断**：
  通过比对统计架构代码：
  - `ssot-guardian.py` 中的 `_count_tasks()` 计算完成数量时，额外聚合了 `tasks/archived/done/*.yaml`（本工作区共有 225 个归档完成任务）。
  - 而 `projects/omo/src/omo/omo_state.py` 中的计数逻辑未将 `archived/done` 加入遍历范围，导致写入状态文件的值错配。
- **架构级对齐**：
  在 `projects/omo/src/omo/omo_state.py` 补充统一计算公式：
  ```python
  archived_done = omo_dir / "tasks" / "archived" / "done"
  archived_count = len(list(archived_done.glob("*.yaml"))) if archived_done.exists() else 0
  counts["done"] += archived_count
  ```
  经实际验证，任务统计在 CLI、YAML 真源与检测规则之间实现了真正的零漂移闭环。

---

## 3. 经验固化清单 (Solidified Takeaways)

1. **对外部服务网络请求的容错规范**：任何无上游强耦合依赖的分析层、报告层，网络通信须具备非阻塞和结构化负载保留的降级逻辑。
2. **SSOT 口径对齐准则**：在多工具共享同一状态投影（如 `system.yaml`）时，生产工具与监控审计工具的数据采集口径必须对齐到底层物理目录的统一枚举，防止“工具间内部标准互斥”。
3. **流程控制纪律**：任何需求变更均严格遵从 `agent-workflow.py` 声明（Claim）、单测覆盖（Coverage）、多维审计（Verify & Guardian）后再完成提交或并入的主仓控制红线。
