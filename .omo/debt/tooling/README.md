# omo-debt

Pattern 09 v2.0: Project lifecycle stage-aware technical debt scoring CLI tool.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)

## 📖 Overview

`omo-debt` is a CLI tool that implements **Pattern 09 v2.0**, a lifecycle-aware technical debt scoring model. It automatically adjusts debt priorities based on project maturity stages:

- **Rapid Evolution** (>30 commits/month): Frequency-focused (weights 0.35/0.40/0.25, norm 1.0)
- **Stable Growth** (10-30 commits/month): Balanced approach (weights 0.40/0.30/0.30, norm 1.1)
- **Maintenance** (<10 commits/month): Impact-prioritized (weights 0.50/0.20/0.30, norm 1.2)

## 🚀 Quick Start

### Installation

```bash
pip install omo-debt
```

### Basic Usage

```bash
# Identify project stage
omo-debt identify-stage /path/to/project

# Score a debt item
omo-debt score --impact 9 --frequency 8 --cost 7 --stage rapid_evolution

# Compare multiple debt items
omo-debt compare debt1.yaml debt2.yaml debt3.yaml

# Analyze project health
omo-debt analyze /path/to/project --debt-file debts.yaml
```

## 📋 Commands

### 1. `identify-stage` - Project Stage Identification

Analyzes Git commit history to determine project lifecycle stage.

```bash
omo-debt identify-stage /path/to/project [--months 6] [--verbose]
```

### 2. `score` - Debt Scoring

Calculates weighted debt score using Pattern 09 v2.0 algorithm.

```bash
omo-debt score --impact 9 --frequency 8 --cost 7 --stage rapid_evolution
```

### 3. `compare` - Multi-Debt Comparison

Compares multiple debt items and ranks by priority.

```bash
omo-debt compare debt1.yaml debt2.yaml debt3.yaml [--format table|json|yaml]
```

### 4. `analyze` - Project Health Analysis

Generates comprehensive debt health report.

```bash
omo-debt analyze /path/to/project --debt-file debts.yaml [--output report.md]
```

See [USAGE.md](docs/USAGE.md) for detailed documentation.

## 🧮 Pattern 09 v2.0 Algorithm

### Scoring Formula

```python
base_score = impact × w_impact + frequency × w_freq + cost × w_cost
normalized_score = base_score × normalization_factor
priority = "P0" if score ≥ 7.0 else "P1" if score ≥ 5.0 else "P2"
```

See [ALGORITHM.md](docs/ALGORITHM.md) for full details.

## 📊 Examples

See [examples/](examples/) directory for:
- Sample debt YAML files
- Health report output
- Multi-project comparisons

## 🏗️ Development

```bash
# Install with uv
uv sync

# Run tests
uv run pytest tests/unit/ -v

# Run linter
uv run ruff check .
```

## 📄 License

MIT License

## 📧 Contact

- Author: starlink-awaken
- Part of OMO v2.0 → v3.0 evolution

---

**Created as M3 milestone deliverable (2026-06-03)**


## Pattern 09 v2.1: Honesty Dimension (4P3V1L1H)

### Overview

Version 0.2.0 introduces the **Honesty dimension** to Pattern 09, extending the framework from 4P3V1L to **4P3V1L1H**:

- **4P**: Four Planes (Control/Truth/Knowledge/Delivery)
- **3V**: Three Dimensions (Value/Velocity/Visibility)
- **1L**: One Layer (Layered Architecture)
- **1H**: One Honesty dimension (NEW)

### Honesty Scoring

The Honesty dimension measures the quality of technical debt disclosure across three sub-dimensions:

| Sub-dimension | Weight | Description |
|---------------|--------|-------------|
| **Completeness** | 40% | Coverage of debt disclosure (code/areas/history) |
| **Consistency** | 35% | Objectivity and stability of assessments |
| **Verifiability** | 25% | Evidence support and data traceability |

**Formula**:
```
honesty_score = 0.40 × completeness + 0.35 × consistency + 0.25 × verifiability

adjusted_score = base_score × (1 + honesty_bonus)
where honesty_bonus = (honesty_score - 5) / 20
```

**Impact**:
- Honesty = 10 → +25% priority boost (excellent disclosure)
- Honesty = 5 → No change (average)
- Honesty = 0 → -25% penalty (poor disclosure)

### CLI Usage

#### Assess Honesty Dimension

```bash
# Basic assessment
omo-debt assess-honesty \
  --debt-files src/main.py \
  --disclosed-issues "#42" "#58"

# Full assessment with evidence
omo-debt assess-honesty \
  --debt-files src/auth.py --debt-files src/session.py \
  --disclosed-issues "#1" "#2" \
  --description "Authentication module has security vulnerabilities" \
  --evidence-commits abc123 \
  --evidence-issues "#1" \
  --peer-avg 7.5 \
  --output table
```

#### Output Formats

```bash
# Rich table output (default)
omo-debt assess-honesty ... --output table

# JSON output
omo-debt assess-honesty ... --output json

# YAML output
omo-debt assess-honesty ... --output yaml
```

### YAML Format with Honesty

```yaml
id: DEBT-001
title: Example debt
impact: 9
frequency: 8
cost: 7

# Honesty dimension (Pattern 09 v2.1)
honesty:
  score: 8.2
  completeness: 8.5
  consistency: 7.8
  verifiability: 8.5
  
  evidence:
    commits: [abc123, def456]
    issues: ["#42", "#58"]
    references: [docs/arch.md]
  
  assessed_at: "2026-06-03T15:00:00Z"

# Adjusted scoring
base_score: 7.73
honesty_adjusted_score: 8.23  # Boosted by +6.5% due to high honesty
```

### Priority Adjustment Rules

Pattern 09 v2.1 introduces honesty-based priority adjustment:

| Base Priority | Honesty Score | Action |
|---------------|---------------|--------|
| P0 (≥7.0) | < 6.0 | ⚠️ Downgrade to P1 (low confidence) |
| P1 (≥5.0) | < 4.0 | ⚠️ Downgrade to P2 (questionable) |
| P2 (< 5.0) | ≥ 8.0 | ✅ Potential upgrade (well-documented) |

### Benefits

1. **Prevents Priority Inflation**: Low-honesty debts are automatically downgraded
2. **Rewards Transparency**: Well-documented debts receive priority boost
3. **Objective Assessment**: Automated evidence detection reduces bias
4. **Continuous Improvement**: Tracks disclosure quality over time

### Migration Guide

**Backward Compatibility**: Honesty assessment is **opt-in** by default. Existing v2.0 workflows continue unchanged.

To enable honesty dimension:

```bash
# Option 1: Explicit flag
omo-debt score --impact 9 --frequency 8 --cost 7 --enable-honesty

# Option 2: Use assess-honesty command
omo-debt assess-honesty --debt-files ...
```

### Technical Details

For detailed algorithm design, see:
- Design document: [session files]/honesty-dimension-design.md
- Source code: `src/omo_debt/honesty/`
- Unit tests: `tests/unit/test_honesty.py` (25 tests, 100% pass rate)


## Pattern 09 v2.1: Honesty Dimension

**New in v0.2.0**: Assess technical debt disclosure quality.

### Quick Start

```bash
# Pattern 09 v2.0 (basic scoring)
omo-debt score --impact 9 --frequency 8 --cost 7 --stage rapid_evolution

# Pattern 09 v2.1 (with honesty dimension)
omo-debt score --impact 9 --frequency 8 --cost 7 \
  --project-path . \
  --enable-honesty \
  --debt-files debt.yaml
```

### Honesty Scoring

The honesty dimension evaluates debt disclosure quality across three sub-dimensions:

1. **Completeness (40%)**: Coverage of all problematic areas
2. **Consistency (35%)**: Objectivity and stability of assessments
3. **Verifiability (25%)**: Evidence support and traceability

**Priority Adjustment**:
- High honesty (≥8.5): +15-25% boost → may upgrade priority
- Low honesty (<4.0): -15-25% penalty → may downgrade priority
- Neutral (5.0): no adjustment

### Example Output

```
债务评分结果 (Pattern 09 v2.1)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
影响分数              9.0
频繁度分数            8.0
成本分数              7.0
项目阶段              rapid_evolution
基础分数              8.10
归一化系数            1.0
────────────────────────────────
诚实度分数            7.2/10 (✅ 高)
  - 完整性           6.8/10
  - 一致性           7.5/10
  - 可验证性         7.3/10
诚实度加成            +11.0%
调整后分数            8.99
优先级                P0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Migration from v2.0 to v2.1

**Backward Compatible**: v2.1 is fully backward compatible with v2.0.
- Default behavior: Pattern 09 v2.0 (no honesty dimension)
- Opt-in: Use `--enable-honesty` flag to activate v2.1

No changes required to existing workflows.

