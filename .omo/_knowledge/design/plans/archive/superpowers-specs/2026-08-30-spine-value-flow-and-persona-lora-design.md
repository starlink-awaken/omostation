---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-30
last-reviewed: 2026-08-30
bet_id: BET-Y1Q3-T10-105
risk_level: L1
human_gate: true
type: ssot
last_updated: 2026-09-03
---

# Spine Value Flow & Persona LoRA Distillation v1 Design Specification

## 1. Objective
Enable end-to-end flow from real external signal ingestion to Cockpit Spine draft generation, human signing diff recording, reservoir-sampled experience replay accumulation (target >= 30 samples), and on-device LoRA distillation on Mac mini M4 to produce adapter-xiamingxing-v1.

## 2. Architecture & Components
- Draft Generator: cockpit.commands.spine.draft calling local omlxc / AetherForge inference with DFlash 2 speculative acceleration.
- Diff Broker: cockpit.commands.spine.sign computing structured character/semantic diffs between model draft and human signed copy.
- Experience Replay Buffer: omlxc.dataplane.experience_replay implementing 30% historical replay / 70% fresh batch mixing to avoid catastrophic forgetting.
- On-device Distillation: cockpit.commands.spine.distill executing parameter-efficient LoRA fine-tuning on Mac mini M4.

## 3. Verification Criteria
- lora-replay-buffer.jsonl contains >= 30 valid signed diff samples.
- Distillation generates hot-swappable LoRA adapter without catastrophic forgetting.
- Evaluated alignment improvement >= 25% on historical test cases.
