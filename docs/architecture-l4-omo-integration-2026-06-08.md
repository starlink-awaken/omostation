# L4 Kernel · OMO 强制流程集成

**2026-06-08 · 治理闭环设计**

---

## 一、核心原则

```
所有 L4 操作，无论入口 (Agent/MCP/CLI/HTTP)，都必须:

1. 需求/目标    → OMO Phase 管理
2. 任务/执行     → OMO Task 跟踪
3. 债务/缺陷     → OMO Debt 注册
4. Bug/异常      → OMO Debt 注册 + CARDS 自动创建
5. 变更/修改     → OMO Audit 记录
```

---

## 二、OMO 强制流程模型

```
                    ┌─────────────────────────┐
                    │     OMO 治理中枢          │
                    │                         │
                    │  Phase ─→ Task ─→ Debt   │
                    │    │        │       │    │
                    │    │        │       │    │
                    │  目标管理  执行跟踪  问题注册│
                    └────┬───────┬───────┬─────┘
                         │       │       │
         ┌───────────────┼───────┼───────┼───────────────┐
         │               │       │       │               │
         ▼               ▼       ▼       ▼               ▼
    ┌─────────┐    ┌─────────┐ ┌─────────┐ ┌─────────┐
    │ Agent   │    │  MCP    │ │  CLI    │ │  Cron   │
    │ 入口    │    │ 入口    │ │ 入口    │ │ 入口    │
    └────┬────┘    └────┬────┘ └────┬────┘ └────┬────┘
         │              │           │           │
         └──────────────┴───────────┴───────────┘
                        │
                    ┌───▼───────────────────────────┐
                    │  L4 Kernel · 业务执行          │
                    │  12 场景 · 43 tools            │
                    └───────────────────────────────┘
```

---

## 三、强制规则矩阵

### 3.1 操作类型 → OMO 机制 映射

| 操作类型 | OMO 机制 | 触发时机 | 强制执行 |
|---------|---------|---------|:---:|
| 创建新域 | Phase goal 更新 | 域创建时 | ✅ |
| 修改 STATE.md | Task 跟踪 | 修改时 | ✅ |
| 发现 Schema violation | Debt 注册 | KemsValidator 检测到 error | ✅ |
| 发现新鲜度问题 | Debt 注册 | DomainHealth 检测到 ⚠️🔴 | ✅ |
| CARDS 状态变更 | Task 状态同步 | 卡片 status 变更时 | ✅ |
| 信号 🔴 未闭环 | Debt 注册 | 48h 未处理 | ✅ |
| 跨域场景执行 | Task 创建 + 跟踪 | 场景启动时 | ✅ |
| Agent 会话 | Phase context 注入 | 会话开始时 | ✅ |
| 配置变更 | Audit 记录 | 变更前后 | ✅ |
| 域删除/归档 | Phase milestone | 操作时 | ✅ |

### 3.2 入口强制规则

| 入口 | 强制要求 |
|------|---------|
| **Agent** | 会话开始→读取 Phase context; 操作前→cards_check; 操作后→OMO audit |
| **MCP** | 写操作前→cards_check; 写操作后→signal emit; error→debt register |
| **CLI** | 同 MCP |
| **Cron** | 结果→signal emit; 异常→debt register |
| **HTTP** | 同 MCP |

---

## 四、12 场景 OMO 集成

### 场景 1: 研究→归档→CARDS

```
Step 0 · OMO Phase context 注入
  └─ 读取当前 Phase 目标

Step 1-7 · 业务执行 (原有)

Step 8 · OMO Task 跟踪
  ├─ 如研究关联 CARDS → 更新 Task 状态
  └─ 如无关联 CARDS → 创建 Task "研究归档: {topic}"

Step 9 · OMO Debt 检查
  └─ 如 vault 有 Schema violation → 注册 Debt
```

### 场景 2: 信号→诊断→修复

```
Step 0 · OMO Debt 注册 (自动)
  └─ KemsValidator error → omo debt register

Step 1-7 · 业务执行 (原有)

Step 8 · OMO Debt 关闭
  └─ 修复验证通过 → omo debt resolve

Step 9 · OMO Task 完成
  └─ 修复完成 → task status=done
```

### 场景 3: 周度全局治理

```
Step 0 · OMO Phase review
  └─ 检查 Phase 进展

Step 1-8 · 业务执行 (原有)

Step 9 · OMO Debt 扫描
  └─ 扫描所有域的 Schema violation
  └─ 自动注册未处理的 Debt

Step 10 · OMO Task 同步
  └─ 同步 CARDS 与 Task 状态
```

---

## 五、实现

### 5.1 l4-kernel 新增 omo.py

```python
# l4_kernel/omo.py (新增)

class OmoBridge:
    """L4 Kernel ↔ OMO 治理桥接。
    
    所有 L4 操作通过此桥接器与 OMO 机制联动。
    """
    
    def __init__(self, registry: DomainRegistry, omo_dir: Path | None = None):
        self.registry = registry
        self.omo_dir = omo_dir or Path.home() / "Workspace" / ".omo"
    
    # ── Phase 管理 ──
    def get_current_phase(self) -> dict:
        """读取当前 Phase 上下文。"""
    
    def check_phase_alignment(self, domain_id: str) -> dict:
        """检查域操作是否与当前 Phase 对齐。"""
    
    # ── Task 管理 ──
    def create_task(self, title: str, priority: str = "P2", 
                    domain: str = "l4-kernel", **kwargs) -> str:
        """创建 OMO Task。返回 task_id。"""
    
    def update_task_status(self, task_id: str, status: str) -> bool:
        """更新 Task 状态。"""
    
    # ── Debt 管理 ──
    def register_debt(self, domain_id: str, violation: dict) -> str:
        """注册 OMO Debt。返回 debt_id。"""
    
    def resolve_debt(self, debt_id: str) -> bool:
        """解决 Debt。"""
    
    # ── 强制流程 ──
    def pre_operation_check(self, domain_id: str, operation: str) -> dict:
        """操作前强制检查。
        
        检查:
        1. Phase 是否允许此操作
        2. CARDS 是否有冲突
        3. 是否有未解决的 Debt
        """
    
    def post_operation_audit(self, domain_id: str, operation: str, 
                             result: dict) -> None:
        """操作后审计。
        
        记录:
        1. OMO Audit 日志
        2. 如有 error → Debt 注册
        3. 如有 warning → Signal 发射
        """
```

### 5.2 MCP tools 强制检查

```python
# mcp_server.py 新增

def l4_omo_phase_context() -> str:
    """获取当前 OMO Phase 上下文 (所有 Agent 会话必须首先调用)。"""
    bridge = OmoBridge(_registry)
    return json.dumps(bridge.get_current_phase(), ensure_ascii=False)

def l4_omo_pre_check(domain_id: str, operation: str) -> str:
    """操作前 OMO 合规检查 (所有写操作必须首先调用)。"""
    bridge = OmoBridge(_registry)
    return json.dumps(bridge.pre_operation_check(domain_id, operation))

def l4_omo_task_create(title: str, priority: str = "P2", 
                       domain: str = "l4-kernel") -> str:
    """创建 OMO Task。"""
    bridge = OmoBridge(_registry)
    task_id = bridge.create_task(title, priority, domain)
    return json.dumps({"task_id": task_id})

def l4_omo_debt_register(domain_id: str, violation_type: str, 
                         detail: str) -> str:
    """注册 OMO Debt。"""
    bridge = OmoBridge(_registry)
    debt_id = bridge.register_debt(domain_id, {
        "type": violation_type,
        "detail": detail,
    })
    return json.dumps({"debt_id": debt_id})
```

### 5.3 入口强制流程伪代码

```python
# 所有 Agent 入口
def agent_session_start():
    phase = l4_omo_phase_context()     # 必须: 获取 Phase
    cards_check("")                     # 必须: 全局合规检查
    context = workspace_context()       # 必须: 获取上下文
    return {phase, cards, context}

# 所有写操作
def l4_any_write_operation(domain_id, operation, *args):
    pre = l4_omo_pre_check(domain_id, operation)  # 必须: 操作前检查
    if not pre["compliant"]:
        return {"error": "OMO pre-check failed", "violations": pre["violations"]}
    
    result = _execute_operation(*args)
    
    # 必须: 操作后审计
    if result["status"] == "error":
        l4_omo_debt_register(domain_id, "operation_error", str(result))
        l4_signal_emit(domain_id, "🔴", f"操作失败: {operation}")
    else:
        l4_signal_emit(domain_id, "✅", f"操作完成: {operation}")
    
    return result
```

---

## 六、实施计划

| Phase | 内容 | 文件 |
|-------|------|------|
| P1 | `omo.py` — OmoBridge 核心 | l4_kernel/omo.py |
| P1 | `mcp_server.py` — 新增 4 个 OMO tools | l4_kernel/mcp_server.py |
| P2 | 12 场景 Step 0 添加 OMO 检查 | l4_kernel/workflows.py |
| P2 | 入口强制流程 (Agent/MCP/CLI/Cron) | 各入口文件 |
| P3 | 自动 Debt 注册 (KemsValidator + DomainHealth) | l4_kernel/omo.py |

---

## 七、强制流程图

```
任何 L4 操作:

1. Agent 入口
   ├── l4_omo_phase_context()        ← 获取 Phase
   ├── l4_cards_check("")            ← 全局合规
   └── l4_omo_pre_check(domain, op)  ← 操作前检查
         │
         ├── 通过 → 2
         └── 不通过 → 返回 violation + 建议
               └── l4_omo_debt_register()  ← 自动注册 Debt

2. 业务执行
   └── 12 场景 / 43 tools

3. 操作后审计
   ├── 成功 → l4_signal_emit("✅")
   ├── 失败 → l4_signal_emit("🔴")
   │         └── l4_omo_debt_register()
   └── 变更 → l4_omo_task_create/update
```

开始实施 P1（omo.py + MCP tools）吗？
