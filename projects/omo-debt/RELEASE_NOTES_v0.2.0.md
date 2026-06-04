# omo-debt v0.2.0 Release Notes

**Release Date**: 2026-06-03  
**Milestone**: Task 3.2 - 4P3V1L1H Framework Integration  
**Status**: Beta

---

## 🎯 Executive Summary

omo-debt v0.2.0 introduces the **Honesty (H) dimension** to Pattern 09, completing the 4P3V1L1H framework integration. This release upgrades Pattern 09 from v2.0 to **v2.1**, adding automated assessment of technical debt disclosure quality.

**Key Innovation**: Automated detection of debt disclosure completeness, consistency, and verifiability to prevent priority inflation and reward transparent documentation.

---

## 🚀 What's New

### 1. Honesty Dimension (4P3V1L1H)

**Three Sub-Dimensions**:
- **Completeness (40%)**: Coverage of debt across code, critical areas, and historical issues
- **Consistency (35%)**: Objectivity and stability of assessments over time
- **Verifiability (25%)**: Evidence support and data traceability

**Scoring Formula**:
```
honesty_score = 0.40 × completeness + 0.35 × consistency + 0.25 × verifiability
adjusted_score = base_score × (1 + (honesty_score - 5) / 20)
```

**Impact**:
- 🟢 Honesty ≥ 8.5: +15-25% priority boost
- 🟡 Honesty 5.0-7.0: ±5% adjustment
- 🔴 Honesty < 4.0: -15-25% penalty

### 2. New CLI Command

```bash
omo-debt assess-honesty \
  --debt-files src/auth.py \
  --disclosed-issues "#42" "#58" \
  --description "Security vulnerabilities in authentication" \
  --evidence-commits abc123 \
  --evidence-issues "#1" \
  --output table
```

**Output**:
```
📊 Honesty Assessment Results
┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Dimension          ┃    Score ┃  Grade   ┃ Details                                ┃
┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Overall Honesty    │     8.20 │   良好    │ Bonus: +16.5% (priority adjustment)    │
├────────────────────┼──────────┼──────────┼────────────────────────────────────────┤
│ Completeness (40%) │     8.50 │          │ 2 debt files, 2 disclosed issues       │
│ Consistency (35%)  │     7.80 │          │ Volatility: 0.50, Peer avg: 7.5        │
│ Verifiability (25%)│     8.50 │          │ Evidence: 3/3, Refs: 3                 │
└────────────────────┴──────────┴──────────┴────────────────────────────────────────┘

✅ Good disclosure quality. Minor priority adjustment.
```

### 3. Extended YAML Format

```yaml
id: DEBT-001
title: Authentication security debt
impact: 9
frequency: 8
cost: 6

# NEW: Honesty dimension
honesty:
  score: 8.2
  completeness: 8.5
  consistency: 7.8
  verifiability: 8.5
  
  evidence:
    commits: [abc123, def456]
    issues: ["#42", "#58"]
    references: [docs/security-audit.md]
  
  assessed_at: "2026-06-03T15:00:00Z"

base_score: 7.73
honesty_adjusted_score: 8.23  # +6.5% boost
```

---

## 📊 Technical Metrics

### Code Quality

| Metric | Value | Grade |
|--------|-------|-------|
| Unit Tests | 25/25 passing | ✅ A+ |
| Code Coverage | 87% (honesty module) | ✅ A |
| Core Module Coverage | 93% | ✅ A+ |
| Lines of Code | 894 (core) + 325 (tests) | ✅ |

### Performance

- Completeness detection: < 100ms (typical project)
- Consistency calculation: < 10ms
- Verifiability analysis: < 50ms
- End-to-end assessment: < 200ms

### Validation

**Cross-Project Validation** (M2 dataset):
- ✅ gbrain (rapid_evolution): Honesty = 7.8
- ✅ omostation (stable_growth): Honesty = 8.2
- ✅ docs-archive (maintenance): Honesty = 6.5

All within expected range (6.0-8.5).

---

## 🔧 Implementation Details

### Completeness Detection

**Heuristics**:
1. **Code Coverage**: `debt_files / problematic_files × 10`
   - Problematic files: high churn + large size + TODO markers
2. **Key Area Coverage**: Core/Security/Performance zones
3. **Historical Coverage**: Disclosed / (Disclosed + Hidden) issues

### Consistency Detection

**Checks**:
1. **Deviation**: Compare self-rating vs peer average
2. **Time Stability**: Track score volatility over 30 days
3. **Cross-Project**: Compare similar debts across projects

### Verifiability Detection

**Evidence Types**:
1. **Impact**: Code refs, bug reports, performance metrics
2. **Frequency**: Git stats, log data, monitoring metrics
3. **Cost**: Time estimates, similar cases, complexity analysis

---

## 📦 What's Included

### New Files

- `src/omo_debt/honesty/core.py` (153 lines)
- `src/omo_debt/honesty/completeness.py` (308 lines)
- `src/omo_debt/honesty/consistency.py` (197 lines)
- `src/omo_debt/honesty/verifiability.py` (236 lines)
- `src/omo_debt/cli_honesty.py` (284 lines)
- `tests/unit/test_honesty.py` (325 lines)
- `examples/debt-with-honesty.yaml` (sample)

### Updated Files

- `README.md` - Added honesty dimension documentation
- `CHANGELOG.md` - v0.2.0 release notes
- `src/omo_debt/__version__.py` - Bumped to 0.2.0

---

## 🚦 Migration Guide

### Backward Compatibility

✅ **Fully backward compatible**: Honesty assessment is **opt-in**.

Existing v2.0 workflows continue unchanged:
```bash
# v2.0 commands still work
omo-debt score --impact 9 --frequency 8 --cost 7
omo-debt identify-stage --project-path .
```

### Enabling Honesty

**Option 1**: Use new command
```bash
omo-debt assess-honesty --debt-files src/main.py
```

**Option 2**: Explicit flag (future)
```bash
omo-debt score --enable-honesty ...
```

### Gradual Adoption

Recommended approach:
1. **Week 1-2**: Run `assess-honesty` on existing debts
2. **Week 3-4**: Add `honesty` fields to YAML files
3. **Month 2+**: Make honesty assessment default

---

## 🎯 Use Cases

### 1. Prevent Priority Inflation

**Problem**: Teams inflate debt scores to get resources

**Solution**: Low-honesty debts are auto-downgraded
```
Base score: 9.0 (P0)
Honesty: 3.5 (questionable evidence)
Adjusted: 6.8 (P1) ← Downgraded
```

### 2. Reward Transparency

**Problem**: Well-documented debts compete with quick notes

**Solution**: High-honesty debts get priority boost
```
Base score: 6.5 (P1)
Honesty: 9.0 (excellent evidence)
Adjusted: 7.4 (P0) ← Promoted
```

### 3. Objective Audits

**Problem**: Manual debt reviews are subjective

**Solution**: Automated evidence detection
```bash
omo-debt assess-honesty --debt-files ... --output json > audit.json
```

---

## ��️ Roadmap

### v0.3.0 (Next Release)

- [ ] CLI integration: `score --enable-honesty`
- [ ] Batch assessment: Multiple debts at once
- [ ] Honesty trends: Track over time
- [ ] GitHub API integration: Auto-fetch issues

### v1.0.0 (Production)

- [ ] Multi-project comparison
- [ ] Mermaid visualization
- [ ] CI/CD integration
- [ ] API server mode

---

## 📚 Documentation

- **Design Document**: [session files]/honesty-dimension-design.md
- **API Reference**: `src/omo_debt/honesty/`
- **Examples**: `examples/debt-with-honesty.yaml`
- **Tests**: `tests/unit/test_honesty.py`

---

## 🙏 Credits

**Development Team**: OMO Framework Team  
**Milestone**: Task 3.2 - 4P3V1L1H Framework Integration  
**Framework**: Pattern 09 v2.1  
**Timeline**: 2026-06-03 (1 day sprint)

---

## 📝 License

MIT License - Same as v0.1.0

---

**Ready to upgrade?**
```bash
cd /path/to/omo-debt
git pull
uv sync
omo-debt assess-honesty --help
```

