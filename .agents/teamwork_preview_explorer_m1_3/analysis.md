# M1 里程碑探索 - 验证机制与降级策略分析报告

本报告针对 M1 里程碑在重构 `aetherforge/swarm` 子进程调用为 Agora 网格 RPC 调用时的**验证脚本设计**、**RPC 调用监控**以及 **Agora 故障时的无缝降级策略**进行了深入分析，并提供了具体的方案规划。

---

## 一、 子进程拦截验证脚本的设计与实施

为了在重构中彻底切断 `ecos workflow run` 时针对 `aetherforge` 的 `subprocess` 直调，必须在 CI/CD 或本地测试套件中引入针对子进程生成的拦截校验。由于 Python 所有的子进程派生（如 `subprocess.run`, `subprocess.call` 等）在底层都会调用 `subprocess.Popen`，因此在测试层面对 `subprocess.Popen` 实施拦截和参数断言是最高效、最可靠的手段。

### 1. 验证脚本设计方案

我们建议在 `projects/ecos/tests` 目录下设计一个专用的集成验证测试（例如 `tests/test_swarm_no_subprocess.py`），通过 pytest 机制执行，同时可在 `pre-commit` 阶段运行。

该脚本的核心逻辑如下：
1. **统一拦截点**：使用 `unittest.mock.patch` 全局 Mock `subprocess.Popen`。
2. **命令行黑名单过滤**：当拦截到任何 `Popen` 实例化时，对传入的 `args` 数组或命令行字符串进行正则匹配。
3. **触发异常**：一旦检测到命令中包含 `aetherforge`、`swarm_engine/cli.py` 等与 AetherForge 引擎直调相关的关键字，立即抛出 `AssertionError`，并打印出违规的调用栈。
4. **RPC 交互匹配断言**：模拟 Agora 处于健康状态并正常响应，同时利用 Mock 记录 `httpx.post` 的调用历史，断言其确实向 Agora Gateway 发送了针对 `resolve_bos_uri` 的 RPC 请求，且 URI 为映射后的 Swarm 服务地址。

### 2. 验证脚本具体代码设计 (Sketch)

```python
import pytest
from unittest.mock import patch, MagicMock
import subprocess
import httpx
from ecos.workflow.executor import execute_m1_workflow

def test_ecos_workflow_no_aetherforge_subprocess():
    """验证在执行带有 Swarm 步骤的工作流时，绝不会产生 direct subprocess 调用"""
    
    # 1. 备份并包装原始的 Popen
    original_popen = subprocess.Popen
    detected_violations = []

    def mock_popen(args, *pargs, **kwargs):
        # 将 args 转化为字符串进行分析
        cmd_str = " ".join(args) if isinstance(args, list) else str(args)
        
        # 2. 检查是否命中了 AetherForge 遗留子进程调用的黑名单
        if any(keyword in cmd_str for keyword in ["aetherforge", "swarm_engine/cli.py", "swarm_engine.cli"]):
            violation_msg = f"检测到违规的子进程直调: {cmd_str}"
            detected_violations.append(violation_msg)
            raise AssertionError(violation_msg)
            
        return original_popen(args, *pargs, **kwargs)

    # 3. 构造 Mock M1 工作流定义
    # 模拟包含 aetherforge 步骤的工作流节点
    mock_workflow_node = {
        "type": "Workflow",
        "id": "workflow-swarm-test",
        "name": "Swarm Test Workflow",
        "domain": "capability",
        "layer": "L0",
        "bos_uri": "bos://ecos/workflow/swarm-test",
        "execution": {
            "backend": "swarm",  # 执行后端为 swarm
            "mode": "sequential",
        },
        "steps": [
            {
                "order": 1,
                "name": "Execute-Agent-Research",
                "action": "research",
                "output": ["bos://analysis/minerva/research"]
            }
        ]
    }

    # 4. Mock 外部 HTTP 调用与系统 Popen
    with patch("httpx.get") as mock_get, \
         patch("httpx.post") as mock_post, \
         patch("subprocess.Popen", side_effect=mock_popen), \
         patch("ecos.workflow.executor.load_workflow", return_value=mock_workflow_node):

        # Mock Agora 网格健康检查响应
        mock_get.return_value = MagicMock(status_code=200)
        
        # Mock Agora 成功路由 RPC 响应
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "success": True,
                "status": "ok",
                "result": {"output": "Swarm RPC executed successfully via Agora"}
            }
        )

        # 5. 执行工作流
        result = execute_m1_workflow("workflow-swarm-test")

        # 6. 断言结果
        # 确保没有发生任何 subprocess 违规直调
        assert len(detected_violations) == 0, f"发现子进程直调违规:\n" + "\n".join(detected_violations)
        assert result["failed"] == 0
        assert result["passed"] == 1
        
        # 确保 RPC 调用确实被发送到了 Agora Gateway
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        post_json = call_kwargs.get("json", {})
        
        # 校验 RPC 请求的工具名与传参格式
        assert post_json.get("name") == "resolve_bos_uri"
        assert post_json.get("arguments", {}).get("uri") == "bos://analysis/minerva/research"
```

---

## 二、 Agora 网格 RPC 调用监控与审计体系

重构完成后，所有的跨层调用都将收敛到 I0 层（Agora 网格）。为了防止 RPC 调用成为“黑盒”，必须在网格两端（客户端与网格代理端）实施立体化的监控与审计记录，主要包括结构化日志、不可变审计链以及异常自愈立项。

### 1. 监控与审计架构设计

在本项目中，RPC 调用的监控设计可以深度复用和扩展现有的 `mof_agora_hook.py` 和 SSB 签名链机制：

```
+------------------+                   +--------------------+                  +------------------------+
|   ECOS Client    | --(BOS RPC)-->    |   Agora Gateway    | --(BOS Router)-> |   Target Service (L2)  |
| (agora_backend)  |                   | (tools_bos/server) |                  |     (e.g., Swarm)      |
+------------------+                   +--------------------+                  +------------------------+
         |                                       |
         |                                       | (post_audit Hook)
         v                                       v
   [l0_audit] Log                       +----------------------------------+
   (Operation logs)                     |       mof_agora_hook.py          |
                                        +----------------------------------+
                                                 |
                       +-------------------------+-------------------------+
                       |                         |                         |
                       v                         v                         v
               [BOS Audit Log]           [SSB Client (L0)]          [CARDS Database]
             (bos-audit.jsonl)         (Immutable Chain Log)      (Cards.db - Auto Debt)
```

### 2. 具体监控维度与实现建议

1. **分布式请求调用追踪（分布式 Trace ID）**
   - **设计**：在 ECOS 客户端侧发起 `httpx.post` 请求调用 `resolve_bos_uri` 时，在 arguments 的 `context` 字典中自动注入一个全局唯一的 `trace_id`（由 UUID 生成）。
   - **监控价值**：无论请求在网格中如何跳转（例如从 ECOS -> Agora -> MetaOS -> Swarm），全链路日志都会携带该 `trace_id`，极大地方便了分布式系统的联调与排障。

2. **结构化网格日志监控**
   - **设计**：在 Agora 的 `resolve_bos_uri` 路由处理器中（`projects/agora/src/agora/server/tools_bos.py`），对请求和响应的耗时记录结构化日志。
   - **实现细节**：
     ```python
     logger.info(
         "bos_uri_resolved",
         uri=uri,
         status="ok",
         latency_ms=duration_ms,
         source=source,
         trace_id=trace_id
     )
     ```

3. **双重审计记录链（本地 JSONL 审计 + SSB 密码学链）**
   - **本地异步审计日志**：扩展复用 `mof_agora_hook.py`。每次 RPC 调用完成，触发 `post_audit`，将事件（包含时间戳、BOS URI、状态码、响应时间）以 JSONL 形式安全追加至用户目录下的 `~/.ecos/bos-audit.jsonl` 中。
   - **SSB 不可变审计链**：在 `post_audit` 中，通过 `SSBClient().publish()` 将 BOS 审计条目以 `SIGNAL` 类型发布到本地 SSB 不可变散列链表中。通过密码学手段，确保网格上的每一次跨层 RPC 路由都有永久、防篡改的存证记录。

4. **度量指标（Metrics）与网格健康态可视化**
   - **监控指标**：跟踪每个 BOS URI 的调用次数、成功率、以及响应时间的分位数（p50/p95/p99）。
   - **命令行感知**：管理员和开发智能体可以通过 `omo bos status` 实时查看调用指标，使用 `omo bos health` 获得网格的端点健康报告。

5. **异常卡片自动立项机制（CARDS 债务闭环）**
   - **闭环设计**：在 `mof_agora_hook.py` 的后置审计中，当 RPC 调用返回 `status_code >= 500`（系统异常）或发生熔断、访问拒绝时，系统自动拦截并连接 to `data/cards/cards.db`。
   - **立项卡片**：在 cards 数据库中自动插入一张 `type='debt', status='identified'`（技术债务）或 `type='issue'` 的卡片（例如 `DEBT-BOS-xxxx`），将 RPC 异常在任务看板上立项，确保基础设施的故障和债务能够被跟踪、修复。

---

## 三、 Agora 网格故障时的无缝降级策略

为了防范由于网格异常、端口被占用或 Agora Gateway 未启动等故障导致工作流执行彻底崩溃，ECOS 需要具备弹性设计的“无缝降级”策略。系统必须建立一套双轨（RPC 与 Subprocess）自适应运行链路。

### 1. 降级链路架构设计

在 `ecos.workflow.backends.swarm` 中，将原有的单一 `subprocess` 直调改写为自适应降级流程：

```
                     +---------------------------------------+
                     | ECOS Step Execution (backends.swarm)  |
                     +---------------------------------------+
                                         |
                                         v
                         /-------------------------------\
                        <   Is Agora Gateway reachable?   >
                         \-------------------------------/
                                    /         \
                             (Yes) /           \ (No / Timeout)
                                  v             v
                     +------------------+    [FALLBACK TRIGGERED]
                     |  Agora RPC Route |    logger.warning("Degrading...")
                     +------------------+               |
                              |                         v
                              |              +----------------------+
                              | (Fail)       | Subprocess Direct    |
                              +------------> | aetherforge CLI      |
                                             +----------------------+
                                                        |
                                                        | (Fail)
                                                        v
                                             +----------------------+
                                             | Mock Fallback        |
                                             | (Graceful OK Record) |
                                             +----------------------+
```

### 2. 降级具体实现设计规范（含真实环境踩坑优化）

在实际的环境运行调试中（例如测试用例 `TestAgoraBackend.test_agora_execute_fallback_on_unreachable`），我们发现由于本地宿主机可能配置了全局的 **SOCKS 代理**，导致 `httpx` 客户端在尝试探测 Agora 服务健康时（默认读取系统代理）抛出 `ImportError: Using SOCKS proxy, but the 'socksio' package is not installed.`，这直接绕过了针对 `ConnectError` 等常规网络异常的捕获，导致降级机制失效。

为了实现真正的无缝、鲁棒性降级，具体的实现需要遵循以下关键点：

1. **显式忽略系统代理 (Ignore trust_env)**：
   在用于探测健康或发送 RPC 的 `httpx` 客户端中，**必须**显式设置 `trust_env=False`。
   这样可以保证本地回路（`127.0.0.1`）的网络连通性测试绝对不受系统全局环境变量代理（如 `ALL_PROXY`, `HTTP_PROXY`）的干扰，也消除了对可选第三方包（如 `socksio`）的物理依赖。

2. **防御性异常捕获 (Broad Exception Catching)**：
   除捕获标准的 `httpx.RequestError` 之外，还需要拦截例如 `ImportError`（缺少socksio等导致）、`RuntimeError` 以及各种底层网络模块抛出的不可预期异常。

3. **零延迟健康嗅探（状态缓存与 TTL）**：
   维护一个本地健康状态缓存，并配置 5 秒的 TTL。只有当缓存失效时，才使用 `trust_env=False` 及 500ms 的短超时做 GET 探测，避免每个工作流步骤由于多次探测导致明显的性能损耗。

4. **自适应降级执行器伪代码 (backends/swarm.py)**：

```python
import logging
import httpx
import time
import sys
from pathlib import Path
from ecos.workflow.backends.swarm import _execute_step_swarm

logger = logging.getLogger("ecos.workflow.backends.swarm")

# 缓存 Agora 的健康状态，避免高频探测
_AGORA_HEALTH_CACHE = {"healthy": True, "last_checked": 0.0}
CACHE_TTL_SEC = 5.0
AGORA_URL = "http://127.0.0.1:7422"

def is_agora_available() -> bool:
    """带缓存的 Agora 健康状态快速嗅探，集成代理规避与防御性异常捕获"""
    now = time.time()
    if now - _AGORA_HEALTH_CACHE["last_checked"] < CACHE_TTL_SEC:
        return _AGORA_HEALTH_CACHE["healthy"]
        
    _AGORA_HEALTH_CACHE["last_checked"] = now
    try:
        # 1. trust_env=False 显式忽略全局 SOCKS/HTTP 代理，避免 socksio 缺包导入报错
        with httpx.Client(trust_env=False, timeout=0.5) as client:
            r = client.get(f"{AGORA_URL}/health")
            is_ok = (r.status_code == 200)
            _AGORA_HEALTH_CACHE["healthy"] = is_ok
            return is_ok
    except Exception as e:
        # 2. 宽口径捕捉包含 ImportError、Timeout、Connection 在内的所有异常
        logger.debug("Agora health check failed (will degrade): %s", e)
        _AGORA_HEALTH_CACHE["healthy"] = False
        return False

def execute(m1_node: dict, params: dict | None = None) -> dict:
    """双轨降级 Swarm 后端执行器"""
    steps = m1_node.get("steps", [])
    params = params or {}
    results = {"steps": [], "passed": 0, "failed": 0}
    
    if not steps:
        return results

    # 1. 优先轨道：利用 Agora RPC 执行
    if is_agora_available():
        try:
            logger.info("Executing swarm backend steps via Agora RPC route")
            return _execute_via_agora_rpc(m1_node, params)
        except Exception as rpc_err:
            logger.warning(
                "[FALLBACK] Agora RPC execution failed: %s. Degrading to local subprocess.", 
                rpc_err
            )
            # 进入降级轨道
            
    # 2. 降级轨道：本地直调 Subprocess 
    logger.info("Running under fallback: executing swarm steps via subprocess")
    for i, step in enumerate(steps):
        step_name = step.get("name", f"step-{i + 1}")
        action = step.get("action", "")
        agent_role = step.get("agent_role", "default")
        
        # 调用原有的本地子进程直调逻辑
        result = _execute_step_swarm(step_name, action, agent_role, step, params)
        
        if result.get("ok", False):
            results["steps"].append({
                "name": step_name,
                "status": "ok",
                "result": result.get("data", {}),
                "fallback_mode": "subprocess"
            })
            results["passed"] += 1
        else:
            results["steps"].append({
                "name": step_name,
                "status": "failed",
                "error": result.get("error", "Unknown error"),
                "fallback_mode": "subprocess"
            })
            results["failed"] += 1
            
            # 失败中断策略
            execution = m1_node.get("execution", {})
            on_failure = step.get("on_failure") or execution.get("on_failure") or "continue"
            if on_failure == "abort":
                break
                
    return results

def _execute_via_agora_rpc(m1_node: dict, params: dict) -> dict:
    """通过 Agora HTTP MCP 发送 RPC (需要 trust_env=False 以防代理干扰)"""
    # 实现在 client 里设置 trust_env=False 
    # with httpx.Client(trust_env=False) as client:
    #     client.post(...)
    # ...
    pass
```

5. **单机状态一致性与事件补发**
   - **本地总线分发**：直调 `aetherforge` 时，Swarm 引擎必须在本地基于 `bus-foundation` 分发 Hatch/Lifecycle 事件，使本地守护进程依然能捕获节点变动。
   - **原子审计日志落盘**：降级执行的结果最终必须由 `mof-state-bridge.py` 或 Ingress 通过本地原子写方式写入 `.omo/state/system.yaml`，保障单机状态与审计链的物理一致性。
