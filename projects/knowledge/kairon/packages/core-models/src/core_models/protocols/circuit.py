"""CircuitProtocol — 回路状态机执行

回路是声明式的协调状态机，定义多个服务间的信号传递路径。
回路定义使用YAML格式（.circuit文件），由CircuitEngine解析和执行。

YAML Schema:
  name: string              # 回路名称
  version: string           # 语义化版本
  trigger: string           # 触发器: api.X.Y | event.X.Y | schedule.X
  sla:
    p99_ms: int            # P99延迟目标
    timeout_ms: int         # 超时时间
  steps:
    - id: string            # 步骤ID
      neuron: string        # 神经元名称
      action: string        # 动作名
      depends_on: [string]  # 依赖步骤
      condition: string     # 可选执行条件
      on_failure: enum      # reject|retry|skip
      fire_and_forget: bool # 是否不等待结果
      retry: {max_attempts, backoff_ms}
      params: dict          # 步骤参数
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, runtime_checkable


class FailureAction(StrEnum):
    REJECT = "reject"
    RETRY = "retry"
    SKIP = "skip"


@dataclass
class CircuitStep:
    """回路步骤"""

    id: str
    neuron: str = ""
    action: str = ""
    depends_on: list[str] = field(default_factory=list)
    condition: str = ""
    on_failure: FailureAction = FailureAction.REJECT
    fire_and_forget: bool = False
    retry_max_attempts: int = 0
    retry_backoff_ms: int = 100
    params: dict = field(default_factory=dict)


@dataclass
class CircuitDefinition:
    """回路定义"""

    name: str
    version: str = "1.0"
    description: str = ""
    trigger: str = ""
    sla_p99_ms: int = 100
    sla_timeout_ms: int = 1000
    steps: list[CircuitStep] = field(default_factory=list)


@dataclass
class CircuitRun:
    """回路执行实例"""

    run_id: str
    circuit_name: str
    status: str = "pending"  # pending|running|completed|failed
    current_step: str = ""
    started_at: float = 0.0
    completed_at: float = 0.0
    error: str = ""


@runtime_checkable
class CircuitProtocol(Protocol):
    """回路协议"""

    async def execute_circuit(self, circuit: CircuitDefinition, context: dict) -> CircuitRun:
        """执行回路定义并返回执行实例"""
        ...

    async def get_run_status(self, run_id: str) -> CircuitRun:
        """查询回路执行状态"""
        ...

    async def cancel_run(self, run_id: str) -> bool:
        """取消回路执行"""
        ...
