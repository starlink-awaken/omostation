---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R1: Phase 1-13 历史执行计划归档, 当前阶段/状态以 .omo/state/system.yaml + .omo/goals/current.yaml 为准"
---
# Phase 6 Wave 1 execution plan

> Status: execution-ready packet
>
> Goal: `G6.1` durable + governance runtime core

## Objective

Turn the pre-gate hardening baseline into a real runtime core without breaking OMO's single-source control flow.

## What Wave 1 must land

1. **Durable execution substrate**
   - durable step/checkpoint recorder in `scripts/omo_worker.py`
   - reclaim/resume semantics that survive interruption
   - queue discipline and watchdog/heartbeat visibility
2. **Governance mutation path**
   - proposal-governed truth mutation path
   - explicit approval/apply lifecycle
   - no direct-write escape hatch for governed operations
3. **Audit and verification continuity**
   - proposal/run/verification/delivery artifacts stay linkable
4. **Scheduler convergence boundary**
   - new runtime execution is OMO-owned
   - Hermes remains ingress/memory compatibility only

## Packet scope

This packet is the **only** execution-ready Phase 6 packet. Discovery/templates and skill federation stay gated until this packet closes with GO.

## Evidence packet

1. runtime checkpoint/resume evidence
2. governance approval/apply evidence
3. verification trace continuity evidence
4. scheduler de-ownership evidence

## Verification

1. `python3 scripts/omo_worker.py task validate --all-active`
2. `python3 scripts/sync_omo_state.py --omo-dir .omo`
3. `python3 -m pytest .omo/tests -q`
4. `python3 scripts/omo_worker.py worker status`

## Exit judgment

Wave 1 is complete only when the repository has one real governed runtime path for execution, recovery, mutation approval, and delivery evidence.

