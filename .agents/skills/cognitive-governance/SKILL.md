---
type: ssot
name: cognitive-governance
description: V2.0 Cognitive OS & Sovereign Governance Skill. Enables agents to deconstruct vague human intents into structured execution DAGs, bind regulatory policies, warm KV cache snapshots (0ms TTFT), mount vertical domain cartridges, and run adversarial shadow challenge with auto-patching before final delivery.

last-reviewed: 2026-08-26
owner: governance-team
---

# 🧠 Cognitive Governance & Adversarial QA Skill (ADR-0195 - ADR-0199)

## 📌 When to Activate
Activate this skill whenever:
1. The user asks to draft, analyze, or review complex industry proposals, project applications, or government filings (especially in Healthcare IT `work-weijian` or Tech Transfer `work-transfer`).
2. The user's request is high-level or ambiguous and requires decomposing into structured Policy-as-Code rules, 14-day SLA fact dependencies, and multi-agent roles.
3. Generating code or documents that must undergo multi-angle red-team adversarial inspection (Audit Bureau, Cyber-security MLPS Level 3, or Tech Transfer team reward ratios).
4. Running the full-lifecycle governed workflow (`omo.workflow start --profile cognitive-governance-delivery`).

---

## 🛠️ Tool & Command Reference

### 1. Intent Deconstruction (Sage / 意图解构)
- **FastMCP Tool**: `runtime_intent_compile(prompt: str, domain: str = "auto")`
- **Cockpit CLI**:
  ```bash
  cockpit intent "<prompt>" [--domain <domain>] [--json]
  ```
- **Output**: Returns `IntentExecutionSpec` with bound `policy_requirements`, `fact_requirements`, `agent_dag` (Sage, Builder, Keeper, Devil), and compute budget.

---

### 2. Sovereign Fabric & KV Snapshots (Builder / 主权算力与快照)
- **Cockpit CLI**:
  ```bash
  cockpit fabric snapshot list
  cockpit fabric snapshot warm --name mof-governance-v3
  cockpit fabric speculative-eval "<prompt>"
  ```
- **Impact**: Provides 0ms TTFT pre-warmed system state and routes 90% routine AST/triage tasks to local sovereign silicon.

---

### 3. Vertical Domain Cartridges (Keeper / 长尾领域卡带)
- **FastMCP Tool**: `runtime_cartridge_list()`, `runtime_cartridge_inspect(cartridge_id: str)`
- **Cockpit CLI**:
  ```bash
  cockpit cartridge list
  cockpit cartridge export cartridge-weijian-v1 --output ./weijian.yaml
  cockpit cartridge validate ./weijian.yaml
  ```
- **Built-in Cartridges**:
  - `cartridge-weijian-v1`: 卫健委信息化立项论证、信创基础软硬件、等保三级、医疗互联互通标准。
  - `cartridge-transfer-v1`: 科技成果赋权、作价入股、研发团队收益分配 ≥70%、TRL ≥ 6 产业化成熟度。

---

### 4. Shadow Challenger Loop (Devil / 影子红蓝对抗审查与自愈)
- **FastMCP Tool**: `runtime_shadow_challenge(text_or_file: str, domain: str = "auto", auto_patch: bool = True)`
- **Cockpit CLI**:
  ```bash
  cockpit challenge "<proposal_path_or_text>" --domain <domain> --auto-patch [--strict]
  ```
- **Mechanism**:
  - Simulates Audit Bureau (budget > 500w without expert review).
  - Simulates Cyber-Security Bureau (clinical data without MLPS Level 3 / GM cryptography).
  - Simulates Tech Transfer Legal (team profit split < 70%).
  - Automatically synthesizes and appends certified compliance clauses (`Auto-Patch`).

---

### 5. Governed Lifecycle Workflow (ADR-0203 / ADR-0204)
- **Start Workflow**:
  ```bash
  python3 bin/agent-workflow.py start --profile cognitive-governance-delivery --claim <task_id>
  ```
- **Deterministic Phases**:
  1. `phase-1-intent-spec` -> 2. `phase-2-compute-triage` -> 3. `phase-3-cartridge-mount` -> 4. `phase-4-dual-plane-draft` -> 5. `phase-5-shadow-challenge` -> 6. `phase-6-facts-closeout`.
