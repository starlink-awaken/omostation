---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-07
related:
  - STRAT-P77-strategic-roadmap.md
  - ../../../../../bin/check-cross-repo-consistency.py
  - ../../../../../tests/test_cross_repo_consistency.py
  - 0162-p76-phase8-real-engineering.md
supersedes: []
---

# ADR-0164: P77 Phase 1 — 跨仓一致性 detector (CR-CROSS-REPO-CONSISTENT)

> **For agentic workers**: 本 ADR 是 ACCEPTED 状态 (2026-07-07), 是 P77 路线图 (STRAT-P77) 启动 phase 1 的实施收口。

## 0. TL;DR

| 交付 | 状态 | 关键产物 |
|------|:---:|---------|
| **跨仓一致性 detector** | ✅ | `bin/ssot/check-cross-repo-consistency.py` (165 行) |
| **8 单元测试** | ✅ | `tests/test_cross_repo_consistency.py` 全 PASSED |
| **GaC 规则** | ✅ | CR-CROSS-REPO-CONSISTENT (X3, advisory) |

## 1. 决策 (WHY/WHAT/NEXT)

### 1.1 WHY

STRAT-P77 §1.2: 系统债扫描出**跨仓一致性**为最高优先级 (RICE 12). 表现:
- agora BOS SSOT: 117 URI 已注册
- 项目源码: 58+ URI 引用
- 重叠/不一致: 52 unregistered (referenced but not in SSOT), 5 orphan (zombie)

根因: 跨仓代码改动 (aetherforge / c2g 等) 新增 BOS URI, 但忘了在 agora 注册 → runtime "找不到服务". 修本需自动 verifier.

### 1.2 WHAT — detector 设计

`bin/ssot/check-cross-repo-consistency.py`:

```python
# 数据流:
#   1. 读 projects/agora/etc/bos-services.yaml → registered set (SSOT)
#   2. 扫 projects/*/src/ 真 bos:// 引用 → referenced set (排 test/fixture)
#   3. unregistered = referenced - registered
#   4. orphan = registered - referenced
#   5. 输 unregistered + orphan 报告, threshold 默认 20
#   6. exit 0 if unregistered ≤ threshold else 1
```

豁免:
- `bos://custom/path` (c2g test fixture)
- `bos://example/` (docstring example pattern)
- `tests/` / `__pycache__/` 目录

### 1.3 阈值策略

| 阶段 | threshold | 期望 unregistered 数 |
|------|-----------|---------------------|
| Phase 1 (W1-2 启动) | **20** (default) | 52 (当前, > 20 = fail) |
| Phase 3 (W5-6 治本) | 10 | <10 |
| Phase 3 收口 | 0 | 0 |

治本路径: 统一 referrer 与 SSOT 注册表 — aetherforge 3 URI + 各仓 NS 入口 → 全部登记。

### 1.4 NEXT — Phase 2 入口

| 候选 | ROI |
|------|-----|
| 演化护栏 catalog (P76-1..9A-5 沉淀 → 5 新 GaC rules) | 高 |
| 跨仓 violations 治本 (Phase 3 启动) | 中 |
| Foundry web dashboard (推迟 P78) | 低 |

## 2. 沉淀原则 (P77-1)

| # | 原则 | 含义 |
|---|------|------|
| P77-1 | **consistency-by-tool** | 跨仓一致性靠自动 verifier 守护, 不靠 review memory |

## 3. 不在本 ADR 范围

- ❌ threshold=20 强制为 0 (Phase 3 治本才动)
- ❌ port-registry 跨仓冲突扫描 (Phase 2 续)
- ❌ docstring / comment 智能识别 (当前 regex 过滤已够)

## 4. 验证清单

- [x] `bin/ssot/check-cross-repo-consistency.py` 创建 (165 行)
- [x] 8 单元测试 PASSED (test_cross_repo_consistency.py)
- [x] CR-CROSS-REPO-CONSISTENT 规则注册 (164 rules total)
- [x] M1 instance 同步 (164 ↔ 164, 0/0/0)
- [x] 实际运行: 52 unregistered / 5 orphan 检测到

## 5. 关联

- STRAT-P77-strategic-roadmap.md (Phase 1 启动依据)
- ADR-0162 (P76 Phase 8 跨仓代码改动源头)
- ADR-0163 (Phase 9A commit-assist — 同一 epoch)
- bin/gac/knowledge-foundry-cron.py (radar_cron 可调本 detector)

---

*最后更新: 2026-07-07 · P77 Phase 1 跨仓一致性 detector 收口 · ACCEPTED*
