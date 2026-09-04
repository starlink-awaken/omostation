---
lifecycle: contract
owner: governance-team
last_updated: 2026-08-18
last_updated: 2026-09-03
type: ssot
---
# ADR-0195: Intent-to-Spec Compiler Architecture

## Status
Accepted

## Context
As LLM workloads evolve from simple conversational agents to complex multi-agent orchestrations, raw natural language prompts often lack structured policy bindings, fact dependency definitions, and compute budgets. Without a formal deconstruction step, agents suffer from hallucinated constraints, missing context dependencies, and unbudgeted GPU/VRAM consumption.

## Decision
1. Introduce `IntentSpecCompiler` in `ecos.ssot.compiler.intent_compiler`.
2. Compile unstructured human prompts into an immutable `IntentExecutionSpec` containing:
   - `detected_domain`: Automatic domain inference (`work-weijian`, `work-transfer`, `engineering`, `general`).
   - `policy_requirements`: Regulatory bindings (`E-POL-WJ-001/002`, `E-POL-TF-001/002`).
   - `fact_requirements`: Specific YAML fact entity patterns and 14-day freshness SLA bounds.
   - `agent_dag`: Structured multi-agent collaboration graph (Sage, Builder, Keeper, Devil).
   - `compute_budget`: Estimated context tokens and local 14B vs cloud frontier allocation.
3. Expose via CLI `ecos-constraint intent compile "<prompt>"` and FastMCP `runtime_intent_compile`.

## Consequences
- Agents can deterministically ground vague human requests into executable, compliant DAGs.
- Eliminates ungrounded agent execution and bounds compute costs.
