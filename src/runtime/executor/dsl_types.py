from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class DSLNodeType(StrEnum):
    AGENT = "agent"
    INPUT = "input"
    OUTPUT = "output"
    TOOL = "tool"
    CAPABILITY = "capability"
    STEP = "step"
    CONDITIONAL_STEP = "conditional_step"
    CONDITION = "condition"
    LOOP = "loop"
    PARALLEL = "parallel"
    TRY_CATCH = "try_catch"
    VARIABLE = "variable"
    LITERAL = "literal"
    BINARY_OP = "binary_op"
    UNARY_OP = "unary_op"
    PROPERTY_ACCESS = "property_access"
    FUNCTION_CALL = "function_call"
    TEMPLATE_STRING = "template_string"
    ARRAY_LITERAL = "array_literal"
    CONDITIONAL_EXPRESSION = "conditional_expression"


@dataclass
class SourceLocation:
    file: str = "<unknown>"
    line: int = 1
    column: int = 1
    snippet: str | None = None


@dataclass
class DSLNode:
    type: DSLNodeType = DSLNodeType.LITERAL
    loc: SourceLocation | None = None


@dataclass
class DSLInput(DSLNode):
    name: str = ""
    data_type: str = "string"
    description: str = ""
    required: bool = True
    default: Any = None


@dataclass
class DSLOutput(DSLNode):
    name: str = ""
    data_type: str = "string"
    description: str = ""


@dataclass
class DSLTool(DSLNode):
    name: str = ""
    alias: str = ""


@dataclass
class DSLCapability(DSLNode):
    capability_type: str = ""
    level: str = "intermediate"


@dataclass
class DSLRetry:
    max_attempts: int = 3
    backoff_ms: int = 1000


@dataclass
class DSLExpression(DSLNode): ...


@dataclass
class DSLVariable(DSLExpression):
    name: str = ""


@dataclass
class DSLLiteral(DSLExpression):
    value: Any = None


@dataclass
class DSLBinaryOp(DSLExpression):
    operator: str = "+"
    left: DSLExpression | None = None
    right: DSLExpression | None = None


@dataclass
class DSLUnaryOp(DSLExpression):
    operator: str = "!"
    operand: DSLExpression | None = None


@dataclass
class DSLPropertyAccess(DSLExpression):
    object: DSLExpression | None = None
    property: str = ""


@dataclass
class DSLFunctionCall(DSLExpression):
    function: str = ""
    arguments: list[DSLExpression] = field(default_factory=list)


@dataclass
class DSLTemplateString(DSLExpression):
    parts: list[str | DSLExpression] = field(default_factory=list)


@dataclass
class DSLArrayLiteral(DSLExpression):
    elements: list[DSLExpression] = field(default_factory=list)


@dataclass
class DSLConditionalExpression(DSLExpression):
    test: DSLExpression | None = None
    consequent: DSLExpression | None = None
    alternate: DSLExpression | None = None


@dataclass
class DSLCall:
    type: str = "agent"
    name: str = ""
    skill_id: str = ""


@dataclass
class DSLStep(DSLNode):
    name: str = ""
    call: DSLCall | None = None
    inputs: dict[str, DSLExpression] = field(default_factory=dict)
    outputs: dict[str, str] = field(default_factory=dict)
    retry: DSLRetry | None = None


@dataclass
class ConditionalBranch:
    if_expr: DSLExpression | None = None
    then_call: DSLCall | None = None
    else_call: DSLCall | None = None


@dataclass
class DSLConditionalStep(DSLNode):
    name: str = ""
    branches: list[ConditionalBranch] = field(default_factory=list)
    inputs: dict[str, DSLExpression] = field(default_factory=dict)
    outputs: dict[str, str] = field(default_factory=dict)


@dataclass
class DSLCondition(DSLNode):
    test: DSLExpression | None = None
    consequent: list[DSLNode] = field(default_factory=list)
    alternate: list[DSLNode] = field(default_factory=list)


@dataclass
class DSLLoop(DSLNode):
    loop_type: str = "while"
    variable: str = ""
    collection: DSLExpression | None = None
    test: DSLExpression | None = None
    body: list[DSLNode] = field(default_factory=list)


@dataclass
class DSLParallel(DSLNode):
    branches: list[list[DSLNode]] = field(default_factory=list)
    max_concurrency: int | None = None


@dataclass
class DSLTryCatch(DSLNode):
    try_block: list[DSLNode] = field(default_factory=list)
    catch_variable: str = ""
    catch_block: list[DSLNode] = field(default_factory=list)
    finally_block: list[DSLNode] = field(default_factory=list)


@dataclass
class DSLGovernance:
    first_principles_check: bool = False
    red_team_threshold: str = "medium"
    quality_gate_enabled: bool = False
    max_retries: int = 3
    token_budget: int = 100000


@dataclass
class DSLMetadata:
    author: str = ""
    version: str = "1.0"
    license: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass
class AgentDSL(DSLNode):
    name: str = ""
    description: str = ""
    agent_type: str = "worker"
    layer: str = "L3"
    domain: str = ""
    inputs: list[DSLInput] = field(default_factory=list)
    outputs: list[DSLOutput] = field(default_factory=list)
    tools: list[DSLTool] = field(default_factory=list)
    capabilities: list[DSLCapability] = field(default_factory=list)
    body: list[DSLNode] = field(default_factory=list)
    governance: DSLGovernance = field(default_factory=DSLGovernance)
    metadata: DSLMetadata = field(default_factory=DSLMetadata)


@dataclass
class ParseResult:
    success: bool = False
    ast: AgentDSL | None = None
    errors: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class CompileResult:
    success: bool = False
    output: str = ""
    errors: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ExecutionStats:
    total_duration_ms: float = 0.0
    agent_calls: int = 0
    skill_calls: int = 0
    tool_calls: int = 0
    total_tokens: int = 0
    successful_calls: int = 0
    failed_calls: int = 0


@dataclass
class TraceEntry:
    timestamp: float = 0.0
    statement_type: str = ""
    location: SourceLocation | None = None
    status: str = "success"
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionResult:
    success: bool = True
    value: Any = None
    trace: list[TraceEntry] = field(default_factory=list)
    errors: list[Exception] = field(default_factory=list)
    outputs: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionOptions:
    max_iterations: int = 10000
    max_nesting_depth: int = 100
    enable_tracing: bool = True
    max_concurrency: int | None = None


@dataclass
class ExecutionContext:
    input: dict[str, Any] = field(default_factory=dict)
    locals: dict[str, Any] = field(default_factory=dict)
    results: dict[str, Any] = field(default_factory=dict)
    trace_id: str = ""
    depth: int = 0
    stats: ExecutionStats = field(default_factory=ExecutionStats)
    parent: ExecutionContext | None = None
    trace: list[TraceEntry] = field(default_factory=list)
    options: ExecutionOptions = field(default_factory=ExecutionOptions)


def create_execution_context(
    input_data: dict[str, Any] | None = None,
    parent: ExecutionContext | None = None,
) -> ExecutionContext:
    return ExecutionContext(
        input=input_data or {},
        trace_id=parent.trace_id if parent else uuid.uuid4().hex[:32],
        depth=(parent.depth + 1) if parent else 0,
        stats=ExecutionStats(),
        parent=parent,
        options=parent.options if parent else ExecutionOptions(),
    )


@dataclass
class RetryConfig:
    max_retries: int = 3
    base_delay_ms: int = 1000
    max_delay_ms: int = 10000
    backoff_multiplier: float = 2.0
    jitter: bool = True


@dataclass
class CallResult:
    success: bool = True
    data: Any = None
    error: str = ""
    duration_ms: float = 0.0
    tokens_used: int = 0
    retry_count: int = 0
    outputs: dict[str, Any] = field(default_factory=dict)


@dataclass
class CallTrace:
    trace_id: str = ""
    parent_trace_id: str = ""
    step_name: str = ""
    call_type: str = "agent"
    target: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    duration_ms: float = 0.0
    success: bool = True
    error: str = ""
    tokens_used: int = 0
    retry_count: int = 0
    input_summary: dict[str, Any] = field(default_factory=dict)
    output_summary: dict[str, Any] = field(default_factory=dict)


@dataclass
class CallConfig:
    type: str = "agent"
    name: str = ""
    skill_id: str = ""
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, str] = field(default_factory=dict)
    retry: RetryConfig | None = None
    timeout: int = 0
