---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-07
related:
  - 0164-p77-phase1-cross-repo-consistency.md
  - 0165-p77-phase2-evolution-guardrails.md
  - STRAT-P77-strategic-roadmap.md (Phase 3 收口)
  - ../../../../../bin/check-cross-repo-consistency.py
  - ../../../../../tests/test_cross_repo_consistency_phase3.py
supersedes: []
---

# ADR-0166: P77 Phase 3 — 跨仓 unregistered 治本 (threshold 20→0 + 升 hard)

> **For agentic workers**: 本 ADR 是 ACCEPTED 状态 (2026-07-07), 是 P77 STRAT § 2 Phase 3 治本收口.

## 0. TL;DR

| 交付 | 状态 | 关键产物 |
|------|:---:|---------|
| **detector 严格模式** | ✅ | BOS URI regex 升级 (边界匹配, 排除 substring 误判) |
| **17 unregistered 全治本** | ✅ | agora/etc/bos-services.yaml: 117 → **134** services |
| **threshold 默认 0** | ✅ | `bin/ssot/check-cross-repo-consistency.py --threshold` 默认 0 |
| **CR-CROSS-REPO-CONSISTENT 升 hard** | ✅ | enforcement: advisory → **error** |
| **CR-CROSS-REPO-CHECK 升 hard** | ✅ | enforcement: advisory → **error** |
| **8 phase-3 单元测试** | ✅ | `tests/test_cross_repo_consistency_phase3.py` 全 PASSED |
| **16/16 cross-repo tests passed** | ✅ | phase 1 (8) + phase 3 (8) = 16/16 |

## 1. 决策 (WHY/WHAT/NEXT)

### 1.1 WHY

STRAT-P77 § 2 Phase 3 治本: 跨仓 unregistered 56→0. 根因:
- 17 真 unregistered 缺注册 (代码引用但 SSOT 没记录 → runtime "找不到服务")
- 19 prefix patterns (URI 末尾 `/` 用作 startswith 前缀) 误判为 unregistered
- 1 test fixture (`bos://bad/foo/bar`) 误判

### 1.2 WHAT — detector 严格模式

```python
# 前 (Phase 1):
BOS_URI_RE = re.compile(r"bos://[a-z][a-z0-9_-]+(?:/[a-z0-9_-]+){1,3}")
# 误判: 'bos://memory/kos' 匹配 'bos://memory/kos/search' 的子串

# 后 (Phase 3):
BOS_URI_RE = re.compile(r'bos://[a-z][a-z0-9_-]+(?:/[a-z0-9_-]+){1,3}/?(?![a-z0-9_/-])')
# 严格: URI 边界 (后面不能跟 [a-z0-9_/-]), 可选 trailing / 表 prefix pattern
```

效果:
- 17 → 17 unregistered (no change for true cases)
- 56 → 17 unregistered 总数 (因 prefix pattern 排除)
- LEGACY_OK_URI_FRAGMENTS 加 `bos://bad/foo/bar` (omo BOS schema validation test fixture)
- 排除 trailing `/` URI (prefix pattern, routing config, not service URI)

### 1.3 WHAT — 17 unregistered 全补登

agora/etc/bos-services.yaml 新增 17 个 entry (117 → 134):

| # | URI | 类型 |
|---|-----|------|
| 1 | `bos://agora/metrics` | internal self-id |
| 2 | `bos://agora/registry` | @mcp.resource |
| 3 | `bos://agora/status` | @mcp.resource |
| 4 | `bos://capability/evaluator` | RBAC 域 |
| 5 | `bos://cockpit/tools/cards_status` | cockpit 工具 |
| 6 | `bos://cockpit/tools/test` | cockpit 工具 |
| 7 | `bos://domain/package` | mcp discovery |
| 8 | `bos://domain/package/action` | mcp discovery |
| 9 | `bos://ecos/events` | ecos SSE service |
| 10 | `bos://ecos/workflow` | ecos CLI |
| 11 | `bos://execution/workers/status` | mcp_protocol endpoint |
| 12 | `bos://forge/market/list` | agora market plugin |
| 13 | `bos://governance/protocols-layer/trigger` | mcp resolver |
| 14 | `bos://governance/roles/list` | mcp_protocol endpoint |
| 15 | `bos://kairon/minerva` | kairon integration |
| 16 | `bos://memory/docs/readme` | mcp_protocol endpoint |
| 17 | `bos://vault/_state` | ecos gateway |

### 1.4 WHAT — GaC rules 升 hard

| Rule | 前 | 后 |
|------|----|----|
| `CR-CROSS-REPO-CONSISTENT` | advisory | **error** (block) |
| `CR-CROSS-REPO-CHECK` | advisory | **error** (block) |

threshold 默认 20 → **0**.

### 1.5 NEXT — Phase 4 入口

| 候选 | ROI |
|------|-----|
| 跨仓端口冲突扫描 (Phase 3 占位) | 中 |
| LLM-assisted commit 默认开启 (aetherforge tier) | 高 |
| Foundry v2 web dashboard | 低 |

## 2. 沉淀原则 (P77-3)

| # | 原则 | 含义 |
|---|------|------|
| P77-3-1 | **strict-regex-by-boundary** | 检测器 regex 必须有 boundary 断言, 避免 substring 误判 |
| P77-3-2 | **prefix-pattern-allowed** | URI 末尾 `/` 表 routing prefix, 不需具体服务注册 |
| P77-3-3 | **remediation-over-suppression** | unregistered 治本 = 补登 SSOT, 而非放宽 threshold |
| P77-3-4 | **hard-only-after-zero** | enforcement: hard 仅在治本完成 (unregistered=0) 后启用, 避免 CI 永红 |
| P77-3-5 | **tool-evolution-via-tests** | detector 升级必须先有测试断言新行为 (P77-2-3 rule-per-principle) |

## 3. 不在本 ADR 范围

- ❌ 跨仓端口冲突深度扫描 (Phase 3 占位, 留给 P77-3.x)
- ❌ orphan 37 全治本 (有的是 planned features, 不需补)
- ❌ SSOT schema 升级 (加 `prefix: true` 字段, etc.)

## 4. 验证清单

- [x] detector 严格模式生效 (regex boundary 断言)
- [x] unregistered = 0 (实际 run 验证)
- [x] 17 unregistered 全补登 SSOT (134 total)
- [x] threshold 默认 0
- [x] CR-CROSS-REPO-CONSISTENT 升 hard (enforcement: error)
- [x] CR-CROSS-REPO-CHECK 升 hard (enforcement: error)
- [x] 16/16 cross-repo tests passed (8 phase 1 + 8 phase 3)
- [x] ADR-0166 ACCEPTED + INDEX
- [x] M1 sync (CR 规则 version 0.1→0.2)

## 5. 关联

- STRAT-P77 § 2 Phase 3 (12-week plan W5-6 节点)
- ADR-0164 (P77 Phase 1 detector 起点)
- ADR-0165 (P77 Phase 2 演化护栏, P77-3-4 hard-only-after-zero 原则)
- P77-2-2 catalog-SSOT (本 ADR 列入 P77-3-1..5 原则)

---

*最后更新: 2026-07-07 · P77 Phase 3 跨仓治本收口 · 17 unregistered 全治本 · ACCEPTED*
