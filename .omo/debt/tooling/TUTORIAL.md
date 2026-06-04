# omo-debt Tutorial

> **Pattern 09 v2.1**: Technical Debt Prioritization with Honesty Dimension

Complete guide to using omo-debt for technical debt assessment and prioritization.

---

## Quick Start

```bash
# Install dependencies
cd omo-debt && uv sync

# Identify project stage
uv run python -m omo_debt.cli identify-stage --project-path .

# Score a technical debt (v2.0)
uv run python -m omo_debt.cli score --impact 8 --frequency 7 --cost 6

# Score with honesty dimension (v2.1)
uv run python -m omo_debt.cli score \
  --impact 8 --frequency 7 --cost 6 \
  --enable-honesty \
  --project-path . \
  --debt-files debt.yaml
```

## Core Concepts

### Project Stages

| Stage | Commits/Month | Priority Focus |
|-------|---------------|----------------|
| rapid_evolution | >30 | Speed (Impact 50%, Frequency 30%, Cost 20%) |
| stable_growth | 10-30 | Balance (Impact 40%, Frequency 35%, Cost 25%) |
| maintenance | <10 | Stability (Impact 35%, Frequency 25%, Cost 40%) |

### Three-Factor Scoring

- **Impact** (1-10): Business/user impact
- **Frequency** (1-10): How often encountered
- **Cost** (1-10): Effort to fix

### Honesty Dimension (v2.1)

Three sub-dimensions:
- **Completeness** (40%): Coverage of all issues
- **Consistency** (35%): Objectivity and stability
- **Verifiability** (25%): Evidence support

**Priority Adjustment**: ±25% based on honesty score

## Command Reference

### identify-stage

```bash
uv run python -m omo_debt.cli identify-stage \
  --project-path /path/to/project \
  --months 6
```

### score

```bash
# Basic (v2.0)
uv run python -m omo_debt.cli score \
  --impact 9 --frequency 8 --cost 7

# With honesty (v2.1)
uv run python -m omo_debt.cli score \
  --impact 9 --frequency 8 --cost 7 \
  --enable-honesty \
  --project-path . \
  --debt-files debt.yaml
```

### assess-honesty

```bash
uv run python -m omo_debt.cli assess-honesty \
  --project-path . \
  --debt-files debt1.yaml debt2.yaml
```

## Examples

See `examples/` directory for real-world cases:
- `example-gbrain.yaml`: TypeScript type definitions
- `example-omostation.yaml`: Test coverage debt
- `example-minimal.yaml`: Minimal template

## Best Practices

1. Always identify stage first
2. Use honesty dimension for new inventories
3. Document evidence proactively
4. Calibrate scores with team
5. Track priority changes over time

## See Also

- [API.md](API.md) - Programmatic usage
- [CONTRIBUTING.md](CONTRIBUTING.md) - Development guide
- [examples/](examples/) - Real-world examples

---

**omo-debt v0.2.0** | Pattern 09 v2.1
