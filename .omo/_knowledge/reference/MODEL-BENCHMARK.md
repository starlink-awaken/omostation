---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史能力/过程/治理/参考/愿景文档批量归档, 当前活跃文档以各面 INDEX/SSOT 为准"
---
# Model Benchmark — 2026-05-21

> 注：用户指定的 OntoDerive 路径 `/engine/engine/formal/entity.py`、`facts.py`、`relation.py` 在当前工作区不存在；本基准改用当前实际模型定义文件 `ontoderive/engine/foundation/models.py`，并补充 `reasoners/reasoner_formal.py` 中的 `FormalConclusion`。

## Eidos types

### Relation (knowledge_card.py)
**Methods:** no `to_dict/from_dict/validate`

| Field | Type | Default | Required |
|-------|------|---------|----------|
| target_id | str | — | yes |
| relation_type | str | — | yes |
| label | str | "" | no |

### KnowledgeCard
**Methods:** `to_dict`, `from_dict`, `validate`

| Field | Type | Default | Required |
|-------|------|---------|----------|
| id | str | — | yes |
| title | str | — | yes |
| content | str | — | yes |
| source | str | — | yes |
| source_type | str | — | yes |
| schema_type | str | — | yes |
| tags | list[str] | [] | no |
| relations | list[Relation] | [] | no |
| created_at | str | "" | no |
| updated_at | str | "" | no |

### OntologyNode
**Methods:** `to_dict`, `from_dict`, `validate`

| Field | Type | Default | Required |
|-------|------|---------|----------|
| id | str | — | yes |
| name | str | — | yes |
| node_type | str | — | yes |
| parent | str | "" | no |
| properties | dict | {} | no |
| aliases | list[str] | [] | no |
| description | str | "" | no |

### Fact
**Methods:** `to_dict`, `from_dict`, `validate`

| Field | Type | Default | Required |
|-------|------|---------|----------|
| id | str | — | yes |
| subject | str | — | yes |
| predicate | str | — | yes |
| object | str | — | yes |
| confidence | float | 1.0 | no |
| source_card_id | str | "" | no |
| derived_from | str | "" | no |

### Relation
**Methods:** `to_dict`, `from_dict`, `validate`

| Field | Type | Default | Required |
|-------|------|---------|----------|
| id | str | — | yes |
| source_id | str | — | yes |
| target_id | str | — | yes |
| relation_type | str | — | yes |
| meta_relation | MetaRelationType | MetaRelationType.STRUCT | no |
| weight | float | 1.0 | no |
| properties | dict[str, Any] | {} | no |

### InferenceRule
**Methods:** `to_dict`, `from_dict`, `validate`

| Field | Type | Default | Required |
|-------|------|---------|----------|
| id | str | — | yes |
| name | str | — | yes |
| rule_type | str | — | yes |
| premises | list[str] | — | yes |
| conclusion | str | — | yes |
| confidence | float | 1.0 | no |
| metadata | dict[str, Any] | {} | no |

### StateTransition
**Methods:** `to_dict`

| Field | Type | Default | Required |
|-------|------|---------|----------|
| from_state | str | — | yes |
| to_state | str | — | yes |
| trigger | str | — | yes |
| guard | str | "" | no |

### StateMachine
**Methods:** `to_dict`, `from_dict`, `validate`

| Field | Type | Default | Required |
|-------|------|---------|----------|
| id | str | — | yes |
| name | str | — | yes |
| states | list[str] | — | yes |
| transitions | list[StateTransition] | — | yes |
| initial_state | str | — | yes |
| metadata | dict[str, Any] | {} | no |

## OntoDerive foundation

### Fact (`foundation/models.py`)
**Methods:** none

| Field | Type | Default | Required |
|-------|------|---------|----------|
| fid | str | — | yes |
| description | str | — | yes |
| value | str | "" | no |
| source | str | "" | no |
| confidence | float | 0.95 | no |
| type | str | "data" | no |

### Entity (`foundation/models.py`)
**Methods:** none

| Field | Type | Default | Required |
|-------|------|---------|----------|
| eid | str | — | yes |
| name | str | — | yes |
| entity_type | str | — | yes |
| role | str | "" | no |
| count | str | "" | no |
| facts_ref | List[str] | [] | no |

### Inference (`foundation/models.py`)
**Methods:** none

| Field | Type | Default | Required |
|-------|------|---------|----------|
| iid | str | — | yes |
| title | str | — | yes |
| derives_from | List[str] | [] | no |
| confidence | float | 0.85 | no |
| raw_confidence_label | str | "inference" | no |
| text | str | "" | no |
| tags | List[str] | [] | no |

### Scheme (`foundation/models.py`)
**Methods:** none

| Field | Type | Default | Required |
|-------|------|---------|----------|
| sid | str | — | yes |
| title | str | — | yes |
| assertions | List[str] | [] | no |
| facts_refs | List[str] | [] | no |
| inferences_refs | List[str] | [] | no |
| file_path | str | "" | no |

### CheckResult (`foundation/models.py`)
**Methods:** none

| Field | Type | Default | Required |
|-------|------|---------|----------|
| pid | str | — | yes |
| name | str | — | yes |
| passed | bool | — | yes |
| severity | str | — | yes |
| detail | str | — | yes |
| fixes | List[str] | [] | no |
| file | str | "" | no |
| line | int | 0 | no |

### DeriveSnapshot (`foundation/models.py`)
**Methods:** none

| Field | Type | Default | Required |
|-------|------|---------|----------|
| timestamp | str | — | yes |
| facts | int | 0 | no |
| entities | int | 0 | no |
| inferences | int | 0 | no |
| scheme_files | int | 0 | no |
| metrics | Optional[dict] | None | no |

### FormalConclusion (`reasoners/reasoner_formal.py`)
**Methods:** none

| Field | Type | Default | Required |
|-------|------|---------|----------|
| conclusion | str | — | yes |
| certainty | str | — | yes |
| method | str | — | yes |
| derives_from | List[str] | [] | no |
| confidence | float | 0.90 | no |

## Minerva knowledge

### Entity
**Methods:** none

| Field | Type | Default | Required |
|-------|------|---------|----------|
| id | str | — | yes |
| type | str | — | yes |
| name | str | — | yes |
| aliases | list[str] | [] | no |
| properties | dict | {} | no |
| valid_from | str | None | no |
| valid_until | str | None | no |
| superseded_by | str | None | no |
| source_ids | list[str] | [] | no |
| confidence | str | "MEDIUM" | no |
| recorded_at | str | None | no |
| last_verified | str | None | no |

### Relation
**Methods:** none

| Field | Type | Default | Required |
|-------|------|---------|----------|
| id | str | — | yes |
| subject_id | str | — | yes |
| predicate | str | — | yes |
| object_id | str | — | yes |
| valid_from | str | None | no |
| valid_until | str | None | no |
| confidence | str | "MEDIUM" | no |
| source_ids | list[str] | [] | no |
| recorded_at | str | None | no |

## Cross-project field mapping

| Concept | Eidos | OntoDerive | Minerva |
|---------|-------|-----------|---------|
| id | `id: str` | `fid/eid/iid/sid/pid: str` or `id: str` | `id: str` |
| name/title | `title/name` | `name/title` | `name: str` |
| type | `source_type/schema_type/node_type/relation_type/rule_type` | `type/entity_type/raw_confidence_label` | `type: str` |
| subject | `subject` / `source_id` / `from_state` | `derives_from` (list) | `subject_id` |
| object/target | `object` / `target_id` / `to_state` | `facts_ref` / `inferences_refs` / `assertions` (by context) | `object_id` / `predicate` |
| confidence | `confidence: float` or `weight: float` | `confidence: float` | `confidence: str` |
| source refs | `source_card_id` / `derived_from` / `source` | `facts_ref`, `facts_refs`, `source` | `source_ids` |
| timestamps | `created_at`, `updated_at` | `recorded_at` / `timestamp` | `valid_from`, `valid_until`, `recorded_at`, `last_verified` |

## Migration Scope

Number of files to modify:
- eidos/types/: 6 files ✅ (already MetaType / current model definitions)
- ontoderive/engine/formal/: 3 requested files not present; current model definitions found in `engine/foundation/models.py` + `engine/reasoners/reasoner_formal.py`
- minerva/knowledge/: 1 file

## Notes

- Eidos has the richest per-model lifecycle API (`to_dict/from_dict/validate`) across all current definitions.
- OntoDerive foundation models are pure dataclasses without serialization/validation helpers in `foundation/models.py`.
- Minerva uses a graph/storage-oriented schema; `confidence` is categorical (`HIGH|MEDIUM|LOW`) rather than numeric.
