---
schema_version: specification/v1
spec_version: 1.0.0
title: Semantica 嵌入式图引擎内核集成与 BOS 决策网格设计
bet_id: BET-Y1Q4-T6-26
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-09-12
value_indicator_policy: false
---

# T6-26 — Semantica Graph Kernel & BOS Decision Mesh 设计

## 1. 问题

当前 kairon 的知识图谱能力依赖外部 Neo4j/Neptune 等云端图数据库，存在三个核心缺陷：

1. **无本地图存储**：所有图查询必须经过网络请求，延迟高且违反 Local-First 原则。
2. **无决策因果追溯**：Resident Agent 的决策记录散落在日志中，无法追溯 CAUSED/INFLUENCED
   因果链，无法回答"为什么做出这个决策"。
3. **无 Datalog 确定性推理**：规则推理依赖外部引擎，无法保证结果的可重复性。

## 2. 非目标（与 ledger non_goals 一致）

- 不引入外部云端托管图数据库（如云端 Neo4j/Neptune）。
- 不替代 gbrain 现有的双链工作记忆与个人笔记。
- 不修改底层的 Merkle 账本格式。

## 3. 设计

### 3.1 Semantica Kernel（`src/kairon/graph/semantica_kernel.py` 新建）

嵌入式图引擎内核，支持双后端（Oxigraph 优先，SQLite fallback）：

```python
class SemanticaKernel:
    """嵌入式图引擎内核 — Oxigraph 优先，SQLite fallback."""

    def __init__(self, backend: str = "auto") -> None:
        """
        backend:
        - "auto": 尝试 Oxigraph，失败则降级 SQLite
        - "oxigraph": 强制 Oxigraph
        - "sqlite": 强制 SQLite
        """
        ...

    def add_triple(self, subject: str, predicate: str, object_: str) -> None:
        """添加 RDF 三元组到图中."""
        ...

    def query(self, pattern: str) -> list[dict[str, str]]:
        """执行 SPARQL 查询，返回匹配结果."""
        ...

    def reason_datalog(self, rules: list[str]) -> list[dict[str, str]]:
        """执行 Datalog 确定性推理，返回推导事实."""
        ...

    def export_rdf(self) -> bytes:
        """导出图为 RDF/XML 格式."""
        ...

    @property
    def backend_name(self) -> str:
        """当前使用的后端名称."""
        ...
```

**Oxigraph 集成**: 使用 `oxigraph` Python 包（纯 Rust 实现的嵌入式 RDF 存储引擎，
零依赖、零网络）。若 Oxigraph 不可用，自动降级为 SQLite 实现（简单的三元组表）。

### 3.2 Causal Tracer（`src/kairon/decision/causal_tracer.py` 新建）

决策因果链追溯引擎：

```python
@dataclass
class DecisionRecord:
    """决策记录"""
    decision_id: str
    timestamp: datetime
    agent: str
    action: str
    confidence: float
    inputs: list[str]
    outcome: str | None = None

class CausalTracer:
    """决策因果链追溯器 — CAUSED/INFLUENCED 关系."""

    def __init__(self, kernel: SemanticaKernel) -> None:
        self._kernel = kernel

    def record_decision(self, record: DecisionRecord) -> None:
        """记录决策到因果图."""
        ...

    def trace_causes(self, decision_id: str) -> list[dict[str, Any]]:
        """追溯指定决策的完整因果祖先链."""
        ...

    def trace_effects(self, decision_id: str) -> list[dict[str, Any]]:
        """追溯指定决策的下游影响面."""
        ...

    def link_cause(self, cause_id: str, effect_id: str, relation: str) -> None:
        """建立 CAUSED/INFLUENCED 关系."""
        ...
```

**因果关系类型**:
- `CAUSED`: 直接因果关系（强）
- `INFLUENCED`: 间接影响关系（弱）

### 3.3 BOS 路由注册

在 `bos-services.yaml` 追加 5 条路由:
- `bos://decision/record` — 记录决策
- `bos://decision/trace-causes` — 追溯因果祖先
- `bos://decision/trace-effects` — 追溯下游影响
- `bos://graph/query` — SPARQL 查询
- `bos://graph/reason` — Datalog 推理

### 3.4 测试

- `projects/knowledge/kairon/tests/test_semantica_kernel.py`:
  - 图引擎: 三元组添加/查询/导出
  - Datalog 推理: 传递闭包/规则链
  - 因果追溯: CAUSED 链/INFLUENCED 链/循环检测
  - Fallback: Oxigraph → SQLite 降级
  - BOS 路由: 5 条路由在册

## 4. 完成判据映射

| done_when | 落点 |
|---|---|
| kairon 集成嵌入式 Oxigraph + 单测覆盖 | §3.1 SemanticaKernel + §3.4 测试 |
| bos-services.yaml 注册 bos://decision/* + bos://graph/* | §3.3 5 条路由 |
| 决策记录、因果链追溯、Datalog 推理示例 | §3.2 CausalTracer + §3.1 reason_datalog |
| AetherForge 端点联调 | §3.1 本地推理（AetherForge 为后续扩展） |

## 5. 风险与回滚

- 所有新增模块均为新增文件，回滚 = revert 单 PR。
- `pyproject.toml` 仅新增 `oxigraph` 可选依赖，不修改现有依赖。
- SemanticaKernel 默认 `backend="auto"`，Oxigraph 不可用时自动降级 SQLite，
  核心流程不阻塞。
- CausalTracer 不修改任何现有决策记录格式，仅新增因果图索引。

## 6. 关键约束

- **数据本地化**: 图存储全量在本地（Oxigraph 嵌入式 / SQLite 本地文件），
  严禁通过 HTTP POST 将图数据发送到外部 API。
- **确定性推理**: Datalog 推理结果必须可重复（相同输入 → 相同输出）。
- **熔断降级**: Oxigraph 初始化失败时自动降级 SQLite（与 T6-25 共享降级模式）。
