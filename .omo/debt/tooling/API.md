# omo-debt API Reference

> **Pattern 09 v2.1**: Programmatic Technical Debt Assessment

---

## Table of Contents

1. [Installation](#installation)
2. [Core Modules](#core-modules)
3. [Stage Identification](#stage-identification)
4. [Scoring (v2.0)](#scoring-v20)
5. [Honesty Assessment (v2.1)](#honesty-assessment-v21)
6. [Models & Data Classes](#models--data-classes)
7. [CLI Integration](#cli-integration)
8. [Examples](#examples)

---

## Installation

### From Source

```bash
git clone https://github.com/your-org/omo-debt.git
cd omo-debt
uv sync
```

### Import in Python

```python
from omo_debt.core.stage import identify_project_stage
from omo_debt.core.scoring import calculate_score_v2
from omo_debt.honesty.core import calculate_honesty_score
```

---

## Core Modules

### Module Structure

```
omo_debt/
├── core/
│   ├── stage.py          # Project stage identification
│   └── scoring.py        # Debt scoring (v2.0)
├── honesty/
│   ├── core.py           # Honesty scoring coordinator
│   ├── completeness.py   # Completeness dimension
│   ├── consistency.py    # Consistency dimension
│   └── verifiability.py  # Verifiability dimension
├── models.py             # Data classes
└── cli.py                # CLI commands
```

---

## Stage Identification

### `identify_project_stage()`

Automatically detect project development stage from Git history.

**Signature**:
```python
def identify_project_stage(
    project_path: str = ".",
    months: int = 6
) -> StageInfo
```

**Parameters**:
- `project_path` (str): Path to Git repository (default: current directory)
- `months` (int): Number of months to analyze (default: 6)

**Returns**: `StageInfo` object with:
- `stage` (str): One of `"rapid_evolution"`, `"stable_growth"`, `"maintenance"`, `"unknown"`
- `commit_count` (int): Total commits in time period
- `avg_commits_per_month` (float): Average monthly commits
- `confidence` (str): `"high"`, `"medium"`, `"low"`, or `"unknown"`

**Example**:
```python
from omo_debt.core.stage import identify_project_stage

# Auto-detect stage
stage_info = identify_project_stage(project_path="/path/to/repo", months=6)

print(f"Stage: {stage_info.stage}")
print(f"Commits/month: {stage_info.avg_commits_per_month:.1f}")
print(f"Confidence: {stage_info.confidence}")
# Output:
# Stage: rapid_evolution
# Commits/month: 37.3
# Confidence: high
```

**Stage Thresholds**:
```python
rapid_evolution:  avg_commits_per_month > 30
stable_growth:    10 <= avg_commits_per_month <= 30
maintenance:      avg_commits_per_month < 10
```

**Confidence Levels**:
```python
high:    not near boundaries (>3 commits away)
medium:  near boundaries (1-3 commits away)
low:     very few commits (<5 total)
unknown: not a Git repo or error
```

---

## Scoring (v2.0)

### `calculate_score_v2()`

Calculate debt priority score using Pattern 09 v2.0 algorithm.

**Signature**:
```python
def calculate_score_v2(
    impact: float,
    frequency: float,
    cost: float,
    stage: str = "stable_growth",
    custom_weights: Optional[Dict[str, float]] = None
) -> ScoringResult
```

**Parameters**:
- `impact` (float): Impact score 1-10
- `frequency` (float): Frequency score 1-10
- `cost` (float): Cost score 1-10
- `stage` (str): Project stage (auto-detected or manual)
- `custom_weights` (dict, optional): Override default weights

**Returns**: `ScoringResult` object with:
- `base_score` (float): Weighted score before normalization
- `normalized_score` (float): Final score after normalization
- `priority` (str): `"P0"` (≥7.5), `"P1"` (5.0-7.5), or `"P2"` (<5.0)
- `stage` (str): Stage used for calculation
- `weights` (dict): Applied weights
- `normalization_factor` (float): Applied normalization

**Example**:
```python
from omo_debt.core.scoring import calculate_score_v2

# Basic scoring
result = calculate_score_v2(
    impact=9,
    frequency=8,
    cost=7,
    stage="rapid_evolution"
)

print(f"Base score: {result.base_score:.2f}")
print(f"Normalized: {result.normalized_score:.2f}")
print(f"Priority: {result.priority}")
# Output:
# Base score: 8.30
# Normalized: 8.30
# Priority: P0
```

**Stage-Specific Weights**:
```python
rapid_evolution:  impact=0.50, frequency=0.30, cost=0.20
stable_growth:    impact=0.40, frequency=0.35, cost=0.25
maintenance:      impact=0.35, frequency=0.25, cost=0.40
```

**Custom Weights**:
```python
result = calculate_score_v2(
    impact=8, frequency=7, cost=6,
    stage="stable_growth",
    custom_weights={"impact": 0.5, "frequency": 0.3, "cost": 0.2}
)
```

---

## Honesty Assessment (v2.1)

### `calculate_honesty_score()`

Calculate overall honesty score from three sub-dimensions.

**Signature**:
```python
def calculate_honesty_score(
    completeness: float,
    consistency: float,
    verifiability: float,
    evidence_commits: Optional[List[str]] = None,
    evidence_issues: Optional[List[str]] = None,
    evidence_refs: Optional[List[str]] = None
) -> HonestyScore
```

**Parameters**:
- `completeness` (float): Completeness score 0-10
- `consistency` (float): Consistency score 0-10
- `verifiability` (float): Verifiability score 0-10
- `evidence_commits`, `evidence_issues`, `evidence_refs`: Optional evidence metadata

**Returns**: `HonestyScore` object with:
- `score` (float): Overall honesty score 0-10
- `completeness_score` (float): Completeness sub-score
- `consistency_score` (float): Consistency sub-score
- `verifiability_score` (float): Verifiability sub-score
- `status` (str): `"excellent"`, `"high"`, `"medium"`, `"low"`, or `"poor"`

**Example**:
```python
from omo_debt.honesty.core import calculate_honesty_score

honesty = calculate_honesty_score(
    completeness=6.8,
    consistency=7.5,
    verifiability=7.3
)

print(f"Overall: {honesty.score:.1f}/10")
print(f"Status: {honesty.status}")
# Output:
# Overall: 7.2/10
# Status: high
```

### `calculate_completeness()`

Assess debt inventory completeness.

**Signature**:
```python
def calculate_completeness(
    project_path: str,
    debt_files: Optional[List[str]] = None,
    disclosed_issues: Optional[List[str]] = None
) -> CompletenessResult
```

**Parameters**:
- `project_path` (str): Project root directory
- `debt_files` (list, optional): Paths to debt YAML files
- `disclosed_issues` (list, optional): Known issue IDs

**Returns**: `CompletenessResult` with:
- `score` (float): 0-10
- `code_coverage` (float): Fraction of codebase covered
- `key_area_coverage` (float): Critical areas covered
- `history_coverage` (float): Historical issues documented

### `calculate_consistency()`

Assess objectivity and stability.

**Signature**:
```python
def calculate_consistency(
    self_rating: float,
    peer_avg: Optional[float] = None,
    historical_scores: Optional[List[float]] = None,
    similar_project_scores: Optional[List[float]] = None
) -> ConsistencyResult
```

**Parameters**:
- `self_rating` (float): Current debt assessment score
- `peer_avg` (float, optional): Average score from peers
- `historical_scores` (list, optional): Past scores for same debt
- `similar_project_scores` (list, optional): Scores from similar projects

**Returns**: `ConsistencyResult` with score and sub-scores.

### `calculate_verifiability()`

Assess evidence support.

**Signature**:
```python
def calculate_verifiability(
    has_impact_evidence: bool = False,
    has_frequency_evidence: bool = False,
    has_cost_evidence: bool = False,
    evidence_commits: Optional[List[str]] = None,
    evidence_issues: Optional[List[str]] = None,
    evidence_refs: Optional[List[str]] = None,
    total_claims: int = 1
) -> VerifiabilityResult
```

**Parameters**:
- `has_impact_evidence`, `has_frequency_evidence`, `has_cost_evidence`: Boolean flags
- `evidence_commits`, `evidence_issues`, `evidence_refs`: Evidence references
- `total_claims`: Number of claims in description

**Returns**: `VerifiabilityResult` with score and sub-scores.

### `adjust_score_with_honesty()`

Apply honesty adjustment to base score.

**Signature**:
```python
def adjust_score_with_honesty(
    base_score: float,
    honesty_score: float
) -> float
```

**Parameters**:
- `base_score` (float): Pattern 09 v2.0 score
- `honesty_score` (float): Honesty dimension score 0-10

**Returns**: Adjusted score (±25% range)

**Formula**:
```python
adjustment_factor = 1 + (honesty_score - 5.0) / 20.0
adjusted_score = base_score * adjustment_factor
```

**Examples**:
```python
adjust_score_with_honesty(8.0, 10.0)  # → 9.0 (+12.5%)
adjust_score_with_honesty(8.0, 5.0)   # → 8.0 (no change)
adjust_score_with_honesty(8.0, 0.0)   # → 6.0 (-25%)
```

---

## Models & Data Classes

### `StageInfo`

```python
@dataclass
class StageInfo:
    stage: str                    # "rapid_evolution", "stable_growth", "maintenance", "unknown"
    commit_count: int             # Total commits in period
    avg_commits_per_month: float  # Average monthly commits
    confidence: str               # "high", "medium", "low", "unknown"
    months_analyzed: int          # Number of months analyzed
```

### `ScoringResult`

```python
@dataclass
class ScoringResult:
    impact: float
    frequency: float
    cost: float
    stage: str
    base_score: float
    normalized_score: float
    priority: str                 # "P0", "P1", "P2"
    weights: Dict[str, float]
    normalization_factor: float
```

### `HonestyScore`

```python
@dataclass
class HonestyScore:
    score: float                  # Overall 0-10
    completeness_score: float
    consistency_score: float
    verifiability_score: float
    status: str                   # "excellent", "high", "medium", "low", "poor"
    evidence_count: int
    adjustment_factor: float      # For priority adjustment
```

---

## CLI Integration

### Programmatic CLI Execution

```python
import subprocess

# Run identify-stage
result = subprocess.run(
    ["uv", "run", "python", "-m", "omo_debt.cli", 
     "identify-stage", "--project-path", "/path/to/repo"],
    capture_output=True, text=True
)
print(result.stdout)

# Run score
result = subprocess.run(
    ["uv", "run", "python", "-m", "omo_debt.cli",
     "score", "--impact", "9", "--frequency", "8", "--cost", "7"],
    capture_output=True, text=True
)
print(result.stdout)
```

---

## Examples

### Full Workflow

```python
from omo_debt.core.stage import identify_project_stage
from omo_debt.core.scoring import calculate_score_v2
from omo_debt.honesty.completeness import calculate_completeness
from omo_debt.honesty.consistency import calculate_consistency
from omo_debt.honesty.verifiability import calculate_verifiability
from omo_debt.honesty.core import calculate_honesty_score, adjust_score_with_honesty

# 1. Identify stage
stage_info = identify_project_stage("/path/to/project", months=6)
print(f"Detected stage: {stage_info.stage}")

# 2. Basic scoring (v2.0)
result = calculate_score_v2(
    impact=9, frequency=8, cost=7,
    stage=stage_info.stage
)
print(f"Base score: {result.normalized_score:.2f}, Priority: {result.priority}")

# 3. Honesty assessment (v2.1)
completeness_result = calculate_completeness(
    project_path="/path/to/project",
    debt_files=["debt.yaml"]
)

consistency_result = calculate_consistency(
    self_rating=result.normalized_score,
    peer_avg=None
)

verifiability_result = calculate_verifiability(
    has_impact_evidence=True,
    has_frequency_evidence=True,
    has_cost_evidence=False
)

honesty = calculate_honesty_score(
    completeness=completeness_result.score,
    consistency=consistency_result.score,
    verifiability=verifiability_result.score
)

print(f"Honesty: {honesty.score:.1f}/10 ({honesty.status})")

# 4. Adjust priority
adjusted_score = adjust_score_with_honesty(
    result.normalized_score,
    honesty.score
)
print(f"Adjusted score: {adjusted_score:.2f}")
```

### Batch Processing

```python
debts = [
    {"impact": 9, "frequency": 8, "cost": 7},
    {"impact": 7, "frequency": 9, "cost": 6},
    {"impact": 6, "frequency": 5, "cost": 8},
]

stage = identify_project_stage(".").stage

for i, debt in enumerate(debts, 1):
    result = calculate_score_v2(**debt, stage=stage)
    print(f"Debt {i}: {result.normalized_score:.2f} ({result.priority})")
```

---

## See Also

- [TUTORIAL.md](TUTORIAL.md) - Comprehensive user guide
- [README.md](README.md) - Quick start
- [examples/](examples/) - Real-world examples

---

**omo-debt v0.2.0** | Pattern 09 v2.1 | OMO v3.0
