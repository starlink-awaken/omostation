# Phase 2: Eidos 适配器层 — OntoDerive + Minerva + Agora

## TL;DR

> **Quick Summary**: 打通 Eidos 的 Schema 体系到 OntoDerive（推理引擎）、Minerva（研究系统）、Agora（服务路由），实现三层架构的端到端闭环。
>
> **Deliverables**:
> - OntoDerive Eidos Adapter — Fact/Entity ↔ Eidos KnowledgeCard/Fact/OntologyNode 映射
> - Minerva Eidos Adapter — ResearchResult ↔ Eidos KnowledgeCard 输出
> - Agora Eidos Service Registration — 把 Eidos 注册为 Agora 可路由服务
> - 端到端集成测试: Eidos → KOS → OntoDerive
>
> **Estimated Effort**: Medium (3 Wave)
> **Parallel Execution**: YES — Wave 1 双线并行
> **Critical Path**: Wave 1 (OntoDerive + Minerva) → Wave 2 (Agora) → Wave 3 (Integration)

---

## Context

### Current State (Post Phase 1)

```
┌─────────────────────────────────────────────────────┐
│  Eidos (Schema/Definition)           ✅ Phase 1      │
│  - Schema/SchemaField/FieldType                       │
│  - KnowledgeCard/Fact/OntologyNode concrete types     │
│  - Validator + CLI (validate/list)                    │
│  - 23 tests passing                                   │
├─────────────────────────────────────────────────────┤
│  KOS (Storage/Retrieval)            ✅ Phase 1        │
│  - ingest command (46k files indexed)                 │
│  - Optional Eidos validation                          │
│  - search/query commands                              │
├─────────────────────────────────────────────────────┤
│  OntoDerive (Reasoning)             ❌ No Eidos link  │
│  - v3.5.0, zero external deps                         │
│  - Formal: Fact/Entity/Inference/Scheme dataclasses   │
│  - Symbolic: SymbolicFact/SymbolicEntity              │
│  - FormalPipeline for reasoning                       │
│  - ecosystem/ adapters: minerva.py, sophia.py, agora  │
│  - CLI: init/derive/check/toolforge                   │
├─────────────────────────────────────────────────────┤
│  Minerva (Research)                 ❌ No Eidos link  │
│  - v0.11.0, Entity/Relation in SQLiteKnowledgeStore   │
│  - ResearchResult for pipeline output                 │
│  - No existing KOS/Eidos integration                  │
├─────────────────────────────────────────────────────┤
│  Agora (Service Hub)                ❌ No Eidos link  │
│  - v1.5.0, MCP registry/discovery/router              │
│  - CLI: register/list/discover/route/pipeline         │
└─────────────────────────────────────────────────────┘
```

### Research Findings

**OntoDerive Formal Data Models**:
- `engine/engine/formal/facts.py`: `Fact(id, index, weight, tags, data, features, meta)`
- `engine/engine/formal/entity.py`: `Entity(id, node_type, tags, data, weight)`
- `engine/engine/formal/inference.py`: `Inference(id, name, data, tags, meta)`
- `engine/engine/formal/scheme.py`: `Scheme` (rule/framework)
- `engine/engine/formal/__init__.py`: `FormalKnowledge` container
- `engine/engine/ecosystem/`: Existing adapters for minerva, sophia, agora, ecos
- Pipeline: `engine/engine/pipeline.py` — FormalPipeline

**Minerva Knowledge Models**:
- `src/minerva/knowledge/`: `Entity(name, type, description, relations)`, `Relation(target, relation_type, description)`
- SQLiteKnowledgeStore for persistence
- Research pipeline → ResearchContext / ResearchResult

**Eidos Schema Mapping**:

| Eidos Type | OntoDerive Formal | Minerva Knowledge | Purpose |
|-----------|------------------|-------------------|---------|
| KnowledgeCard | — | ResearchResult | 知识卡片/研究产出 |
| Fact | FormalFact | — | 三元组事实 |
| OntologyNode | FormalEntity | Entity | 本体节点/实体 |

---

## Work Objectives

### Core Objective
Build Eidos adapter bridges for OntoDerive, Minerva, and Agora, enabling end-to-end: **Define (Eidos) → Store (KOS) → Reason (OntoDerive) → Route (Agora)**

### Concrete Deliverables

| # | Deliverable | Files |
|---|-------------|-------|
| 1 | OntoDerive Eidos Adapter | `ontoderive/engine/ecosystem/eidos_adapter.py`, `ontoderive/tests/test_eidos_adapter.py` |
| 2 | OntoDerive CLI `eidos` subcommand | `ontoderive/src/ontoderive/cli.py` (edit) |
| 3 | Minerva Eidos Adapter | `minerva/src/minerva/knowledge/eidos_adapter.py`, `minerva/tests/test_eidos_adapter.py` |
| 4 | Agora Eidos Service Registration | `agora/tests/test_eidos_service.py` |
| 5 | Integration test | `.omo/tests/test_phase2_integration.py` |

### Definition of Done
 [x] OntoDerive adapter: OntoDerive Fact → Eidos Fact, Eidos Fact → OntoDerive FormalFact
 [x] OntoDerive CLI: `ontoderive derive --eidos` flag for Eidos-aware reasoning
 [x] Minerva adapter: ResearchResult → Eidos KnowledgeCard export
 [x] Agora Eidos service: `agora register eidos` protocol
 [x] Integration: Eidos schema → KOS → OntoDerive derive → Agora route
 [x] All tests pass

### Must Have
- Bidirectional mapping: OntoDerive ⇄ Eidos data models
- Minerva research output can be exported as Eidos KnowledgeCards
- Agora can route Eidos validation requests
- Zero new external dependencies

### Must NOT Have (Guardrails)
- No changes to KOS core storage layer
- No changes to OntoDerive FormalPipeline reasoning logic
- No changes to Minerva research pipeline logic
- No Eidos-to-OntoDerive hard dependency (adapters are optional)

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: YES (pytest in all projects)
- **Automated tests**: Tests-after (adapter tests + integration tests)
- **Framework**: pytest

### QA Policy
Every task includes agent-executed QA scenarios:
- Adapter import: PYTHONPATH=src python3 -c "import adapter_module"
- CLI verification: `ontoderive derive --eidos --help`
- Roundtrip: Create Eidos object → convert to OntoDerive → convert back → verify

---

## Execution Strategy

```
Wave 1 (Start Immediately — parallel, no conflicts):
├── Task 1: OntoDerive Eidos Adapter [deep]
└── Task 2: Minerva Eidos Adapter [deep]

Wave 2 (After Wave 1 — Agora + CLI integration):
├── Task 3: Agora Eidos Service Registration [quick]
├── Task 4: OntoDerive CLI `derive --eidos` flag [quick]
└── Task 5: Minerva CLI `research --eidos-output` flag [quick]

Wave 3 (After Wave 2 — end-to-end):
├── Task 6: Integration test [deep]
└── Task 7: Documentation + demo [writing]

Wave FINAL (After ALL):
├── F1: Scope fidelity check (oracle)
├── F2: Code quality review (oracle)
├── F3: E2E verification (oracle)
└── F4: Final QA (oracle)

Critical Path: Task 1 → Task 4 → Task 6 → F1-F4

```

---

## TODOs

---

### Wave 1 — Parallel (OntoDerive + Minerva adapters)

- [x] **1. OntoDerive Eidos Adapter**

  **What to do**:
  - Create `ontoderive/engine/ecosystem/eidos_adapter.py` — bridge between OntoDerive's formal data models and Eidos KnowledgeCard/Fact/OntologyNode
  - Implement `to_eidos_fact(onto_fact: FormalFact) -> Fact` converter
  - Implement `from_eidos_fact(eidos_fact: Fact) -> FormalFact` converter
  - Implement `to_eidos_ontology_node(onto_entity: FormalEntity) -> OntologyNode` converter
  - Implement `from_eidos_ontology_node(node: OntologyNode) -> FormalEntity` converter
  - Implement `batch_convert(onto_entities: list[FormalEntity]) -> list[OntologyNode]`
  - All converters must handle edge cases: empty data, missing fields, None values
  - Add EIDOS_AVAILABLE flag with try/except ImportError
  - Add helper: `is_eidos_available() -> bool`
  - Add helper: `list_available_schemas() -> list[str]`

  **Must NOT do**:
  - Do NOT modify OntoDerive FormalPipeline
  - Do NOT add Eidos as a dependency to OntoDerive pyproject.toml (adapter is optional)
  - Do NOT touch engine/engine/formal/*.py core logic

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Cross-project mapping requires understanding both OntoDerive's formal models and Eidos schema types
  - **Skills**: [] (no special skills needed)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Task 2)
  - **Blocks**: Task 4
  - **Blocked By**: None

  **References** (CRITICAL):
  - `ontoderive/engine/engine/formal/facts.py` — FormalFact dataclass
  - `ontoderive/engine/engine/formal/entity.py` — FormalEntity dataclass
  - `eidos/src/eidos/types/` — Eidos KnowledgeCard, Fact, OntologyNode
  - `eidos/src/eidos/schema.py` — Generic Schema/SchemaField system
  - `ontoderive/engine/ecosystem/minerva.py` — existing adapter pattern to follow

  **Acceptance Criteria**:

  **QA Scenarios**:

  ```
  Scenario: OntoDerive Fact → Eidos Fact conversion
    Tool: Bash
    Preconditions: OntoDerive and Eidos projects exist
    Steps:
      1. cd ontoderive && PYTHONPATH=eidos/src:ontoderive python3
      2. from engine.engine.formal.facts import Fact as OFact
      3. from eidos.types import Fact as EidosFact
      4. onto_fact = OFact(id="f1", index=0, weight=1.0, tags=["test"], data={"name": "test"}, features=[], meta={})
      5. from engine.ecosystem.eidos_adapter import to_eidos_fact
      6. eidos_fact = to_eidos_fact(onto_fact)
      7. assert eidos_fact.id == "f1"
      8. assert eidos_fact.validate() == []
    Expected Result: Bidirectional conversion works, no validation errors
    Evidence: .omo/evidence/task1-ontofact-roundtrip.txt

  Scenario: Eidos Fact → OntoDerive FormalFact
    Tool: Bash
    Preconditions: Same
    Steps:
      1. from engine.ecosystem.eidos_adapter import from_eidos_fact
      2. eidos_fact = EidosFact(id="f2", subject="s1", predicate="p1", object="o1")
      3. onto_fact = from_eidos_fact(eidos_fact)
      4. assert onto_fact.data.get("id") == "f2"
    Expected Result: Eidos Fact maps correctly to OntoDerive FormalFact format
    Evidence: .omo/evidence/task1-eidosfact-roundtrip.txt

  Scenario: EIDOS_AVAILABLE check
    Tool: Bash
    Steps:
      1. from engine.ecosystem.eidos_adapter import is_eidos_available
      2. Run without eidos in PYTHONPATH, expect False
      3. Run with eidos in PYTHONPATH, expect True
    Expected Result: Graceful fallback when Eidos not available
    Evidence: .omo/evidence/task1-available-check.txt
  ```

  **Evidence to Capture**:
   [x] All 3 scenarios run successfully
   [x] Import with and without Eidos both work

  **Commit**: YES (groups with Phase 2 Wave 1)
  - Message: `feat(ontoderive): add eidos adapter for formal model bridge`
  - Files: `engine/ecosystem/eidos_adapter.py`, `tests/test_eidos_adapter.py`

---

- [x] **2. Minerva Eidos Adapter**

  **What to do**:
  - Create `minerva/src/minerva/knowledge/eidos_adapter.py` — export Minerva research results as Eidos KnowledgeCards
  - Implement `research_result_to_card(result: ResearchResult) -> KnowledgeCard` — convert Minerva's research output into Eidos KnowledgeCard
  - Implement `entity_to_ontology_node(entity: Entity) -> OntologyNode` — convert Minerva Entity to Eidos OntologyNode
  - Implement `card_to_research_context(card: KnowledgeCard, source: str) -> dict` — import Eidos card back to Minerva context
  - Use try/except ImportError for `from eidos.types import KnowledgeCard, OntologyNode`
  - Add helper: `export_cards_to_json(cards: list[KnowledgeCard], path: str) -> int`
  - Add helper: `list_exported_cards(dir_path: str) -> list[str]`

  **Must NOT do**:
  - Do NOT modify Minerva's core knowledge store (SQLiteKnowledgeStore)
  - Do NOT add Eidos as a dependency to Minerva's pyproject.toml
  - Do NOT modify research pipeline logic

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Cross-project mapping requires understanding Minerva's knowledge model + Eidos types
  - **Skills**: [] (no special skills needed)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Task 1)
  - **Blocks**: Task 5
  - **Blocked By**: None

  **References**:
  - `minerva/src/minerva/knowledge/` — Entity, Relation dataclasses
  - `minerva/src/minerva/research.py` — ResearchResult, ResearchContext
  - `eidos/src/eidos/types/knowledge_card.py` — KnowledgeCard
  - `eidos/src/eidos/types/ontology_node.py` — OntologyNode
  - `ontoderive/engine/ecosystem/eidos_adapter.py` — follow same pattern

  **Acceptance Criteria**:

  **QA Scenarios**:

  ```
  Scenario: ResearchResult → KnowledgeCard conversion
    Tool: Bash
    Preconditions: Minerva and Eidos projects exist
    Steps:
      1. cd minerva && PYTHONPATH=src:eidos/src python3
      2. from minerva.knowledge.eidos_adapter import research_result_to_card
      3. result = {"title": "Test", "content": "Research findings", "source": "/tmp/test"}
      4. card = research_result_to_card(result)
      5. assert card.title == "Test"
      6. assert card.schema_type == "KnowledgeCard"
      7. assert card.validate() == []
    Expected Result: Research result converts to valid Eidos KnowledgeCard
    Evidence: .omo/evidence/task2-research-card.txt

  Scenario: Eidos available check
    Tool: Bash
    Steps:
      1. PYTHONPATH=src python3 -c "from minerva.knowledge.eidos_adapter import is_eidos_available; print(is_eidos_available())"
      2. Run with and without eidos in path
    Expected Result: Graceful fallback
    Evidence: .omo/evidence/task2-available-check.txt
  ```

  **Evidence to Capture**:
   [x] Research conversion works with valid data
   [x] Graceful fallback without Eidos

  **Commit**: YES
  - Message: `feat(minerva): add eidos adapter for research output`
  - Files: `src/minerva/knowledge/eidos_adapter.py`, `tests/test_eidos_adapter.py`

---

### Wave 2 — CLI Integration (after Wave 1)

- [x] **3. Agora Eidos Service Registration**

  **What to do**:
  - Create `agora/tests/test_eidos_service.py` — integration test verifying Eidos can be registered as an Agora service
  - Add Eidos protocol configuration to Agora registry
  - Test: register Eidos validate as an MCP endpoint via Agora
  - Test: `agora list` shows registered Eidos service

  **Must NOT do**:
  - Do NOT modify Agora's core routing logic
  - Do NOT add Eidos as a dependency to Agora's pyproject.toml

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple registration test, no complex logic
  - **Skills**: [] (no special skills needed)

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 4, 5)
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 6
  - **Blocked By**: None (wave-level dependency)

  **References**:
  - `agora/src/agora/registry.py` — Service registry
  - `agora/src/agora/cli.py` — CLI registration pattern
  - `agora/src/agora/_protocols.py` — Protocol definitions

  **Commit**: YES
  - Message: `test(agora): add eidos service registration test`
  - Files: `tests/test_eidos_service.py`

---

- [x] **4. OntoDerive CLI eidos flag**

  **What to do**:
  - Add `--eidos` flag to OntoDerive `derive` subcommand in `src/ontoderive/cli.py`
  - When `--eidos` is set: call `eidos_adapter.batch_convert()` on derivation results
  - Output: print Eidos objects alongside regular OntoDerive output
  - Graceful message if Eidos not available: "Eidos not available — skipping Eidos output"

  **Must NOT do**:
  - Do NOT change existing `derive` behavior without `--eidos` flag

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: [] (no special skills needed)

  **References**:
  - `ontoderive/src/ontoderive/cli.py` — existing CLI (find `derive` subcommand)
  - `ontoderive/engine/ecosystem/eidos_adapter.py` — adapter (from Task 1)

  **Commit**: YES
  - Message: `feat(ontoderive): add --eidos flag to derive command`
  - Files: `src/ontoderive/cli.py`

---

- [x] **5. Minerva CLI eidos-output flag**

  **What to do**:
  - Add `--eidos-output` flag to Minerva `research` subcommand
  - When set: export research results as Eidos KnowledgeCards to specified directory
  - Output: "Exported N KnowledgeCards to <path>"
  - Graceful message if Eidos not available

  **Must NOT do**:
  - Do NOT change existing research behavior

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: [] (no special skills needed)

  **References**:
  - `minerva/src/minerva/cli.py` — CLI entry point (find research command)
  - `minerva/src/minerva/knowledge/eidos_adapter.py` — adapter (from Task 2)

  **Commit**: YES
  - Message: `feat(minerva): add --eidos-output flag to research command`
  - Files: `src/minerva/cli.py`

---

### Wave 3 — Integration + Documentation

- [x] **6. Phase 2 Integration Test**

  **What to do**:
  - Create `.omo/tests/test_phase2_integration.py` — end-to-end test:
    1. Define an Eidos OntologyNode schema
    2. Convert to OntoDerive FormalEntity via adapter
    3. Run OntoDerive derive with --eidos
    4. Convert Minerva ResearchResult to Eidos KnowledgeCard
    5. Register Eidos service in Agora (test registration)
  - Tests require PYTHONPATH pointing to all 4 project src dirs
  - Each step is independent: test_ontoderive_adapter, test_minerva_adapter, test_agora_service

  **Must NOT do**:
  - Do NOT run actual kos ingest (too expensive for unit test)

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: [] (no special skills needed)

  **References**:
  - Tasks 1-5 outputs
  - `.omo/plans/knowledge-foundation-phase2.md` (this plan)

  **Commit**: YES
  - Message: `test: add phase2 e2e integration test`
  - Files: `.omo/tests/test_phase2_integration.py`

---

 [x] **7. Documentation + Demo**

  **What to do**:
  - Update `.omo/KNOWLEDGE_ARCH.md` with Phase 2 architecture updates
  - Write a demo script that shows: Eidos → Minerva research → OntoDerive reasoning → KnowledgeCard output
  - Update READMEs in eidos/, ontoderive/, minerva/ with cross-project reference

  **Must NOT do**:
  - Do NOT create verbose documentation

  **Recommended Agent Profile**:
  - **Category**: `writing`
  - **Skills**: [] (no special skills needed)

  **Commit**: YES
  - Message: `docs: add phase2 architecture docs and demo`
  - Files: `.omo/KNOWLEDGE_ARCH.md`, `README.md`

---

## Final Verification Wave

 [x] **F1. Scope Fidelity Check** — `oracle`
  Verify: Each Task 1-7 deliverable exists. Must Haves all present. Must NOT Haves absent.
  Output: `Tasks [N/7] | VERDICT: APPROVE/REJECT`

 [x] **F2. Code Quality Review** — `oracle`
  Review all new adapter code. Check: try/except ImportError pattern, no hard dependencies, clean conversion logic.
  Output: `Files [N clean/N issues] | VERDICT: APPROVE/REJECT`

 [x] **F3. E2E Verification** — `oracle`
  Run the integration tests. Verify all tasks pass end-to-end.
  Output: `Scenarios [N/N pass] | VERDICT: APPROVE/REJECT`

 [x] **F4. Final QA** — `oracle`
  Verify integrity of all changes. No scope creep. No regression in existing tests.
  Output: `All Checks Pass | VERDICT: APPROVE/REJECT`

---

## Commit Strategy

- **Task 1**: `feat(ontoderive): add eidos adapter for formal model bridge`
- **Task 2**: `feat(minerva): add eidos adapter for research output`
- **Task 3**: `test(agora): add eidos service registration test`
- **Task 4**: `feat(ontoderive): add --eidos flag to derive command`
- **Task 5**: `feat(minerva): add --eidos-output flag to research command`
- **Task 6**: `test: add phase2 e2e integration test`
- **Task 7**: `docs: add phase2 architecture docs and demo`
