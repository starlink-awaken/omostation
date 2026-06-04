# omo-debt Examples

This directory contains real-world examples of technical debt assessment using Pattern 09 v2.0/v2.1.

## Example Files

| File | Project | Stage | Description |
|------|---------|-------|-------------|
| `example-gbrain.yaml` | gbrain | rapid_evolution | TypeScript type definitions debt |
| `example-omostation.yaml` | omostation | stable_growth | Test coverage debt |
| `example-minimal.yaml` | minimal | - | Minimal required fields example |

## Running Examples

### Example 1: gbrain Assessment

```bash
# Basic scoring (v2.0)
uv run python -m omo_debt.cli score \
  --impact 7 \
  --frequency 8 \
  --cost 5 \
  --stage rapid_evolution

# With honesty dimension (v2.1)
uv run python -m omo_debt.cli score \
  --impact 7 \
  --frequency 8 \
  --cost 5 \
  --enable-honesty \
  --project-path /path/to/gbrain \
  --debt-files examples/example-gbrain.yaml
```

**Expected Result**:
- Base score: 6.90 (rapid_evolution: 0.50×7 + 0.30×8 + 0.20×5)
- Normalization: ×1.0
- Priority: P1
- With honesty: ~7.2 (medium honesty → +4% boost)

### Example 2: omostation Assessment

```bash
# Basic scoring
uv run python -m omo_debt.cli score \
  --impact 8 \
  --frequency 6 \
  --cost 8 \
  --stage stable_growth

# With honesty
uv run python -m omo_debt.cli score \
  --impact 8 \
  --frequency 6 \
  --cost 8 \
  --enable-honesty \
  --project-path /path/to/omostation \
  --debt-files examples/example-omostation.yaml
```

**Expected Result**:
- Base score: 7.40 (stable_growth: 0.40×8 + 0.35×6 + 0.25×8)
- Normalization: ×1.1 = 8.14
- Priority: P0
- With honesty: ~8.5 (medium honesty → +4% boost)

### Example 3: Minimal Example

```bash
uv run python -m omo_debt.cli score \
  --impact 9 \
  --frequency 5 \
  --cost 3 \
  --stage maintenance
```

**Expected Result**:
- Base score: 6.45 (maintenance: 0.35×9 + 0.25×5 + 0.40×3)
- Normalization: ×1.2 = 7.74
- Priority: P1

## Honesty Assessment Examples

### Assess Completeness

```bash
uv run python -m omo_debt.cli assess-honesty \
  --project-path /path/to/project \
  --debt-files examples/example-gbrain.yaml \
  --output table
```

### Compare Honesty Across Projects

```bash
# gbrain
uv run python -m omo_debt.cli assess-honesty \
  --project-path /path/to/gbrain \
  --debt-files examples/example-gbrain.yaml

# omostation
uv run python -m omo_debt.cli assess-honesty \
  --project-path /path/to/omostation \
  --debt-files examples/example-omostation.yaml
```

## Creating Your Own Examples

1. Copy `example-minimal.yaml` as a template
2. Fill in your debt details:
   - `id`: Unique identifier (e.g., "PROJ-D001")
   - `title`: Short descriptive title
   - `description`: Detailed explanation
   - `impact`, `frequency`, `cost`: Scores 1-10
   - `evidence`: Optional but recommended for v2.1

3. Run assessment:
   ```bash
   uv run python -m omo_debt.cli score \
     --impact X --frequency Y --cost Z \
     --enable-honesty \
     --project-path . \
     --debt-files your-debt.yaml
   ```

## Tips

- **Start simple**: Use `example-minimal.yaml` format for quick assessments
- **Add evidence**: Include commits/issues for better honesty scores
- **Calibrate**: Compare multiple debts to establish scoring baseline
- **Iterate**: Refine descriptions as understanding deepens

## See Also

- [TUTORIAL.md](../TUTORIAL.md) - Comprehensive usage guide
- [README.md](../README.md) - Quick start and overview
- [RELEASE_NOTES_v0.2.0.md](../RELEASE_NOTES_v0.2.0.md) - v2.1 features

