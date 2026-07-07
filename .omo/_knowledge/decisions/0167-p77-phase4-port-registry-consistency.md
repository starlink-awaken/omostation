---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-07
related:
  - 0164-p77-phase1-cross-repo-consistency.md
  - 0165-p77-phase2-evolution-guardrails.md
  - 0166-p77-phase3-cross-repo-remediation.md
  - STRAT-P77-strategic-roadmap.md (Phase 4 收口)
  - ../../../../../bin/check-cross-repo-consistency.py
  - ../../../../../tests/test_cross_repo_consistency_phase4.py
supersedes: []
---

# ADR-0167: P77 Phase 4 — 跨仓 port-registry 一致性 (bug 修复 + 6 端口对齐)

> **For agentic workers**: 本 ADR 是 ACCEPTED 状态 (2026-07-07), 是 P77 STRAT § 2 Phase 4 收口.

## 0. TL;DR

| 交付 | 状态 | 关键产物 |
|------|:---:|---------|
| **port-registry 加载 bug 修复** | ✅ | `load_ecos_ports` 实际加载 0→9 ports (top-level 误读 → ports: 段) |
| **YAML inline comment strip** | ✅ | `_strip_yaml_comment()` helper, 6 conflict → 6 duplicate |
| **6 端口名对齐** | ✅ | 8080 (agora-api-gateway→ontoderive-web), 9290 (llm-gateway-http→llm-gateway) |
| **port 冲突扫描** | ✅ | `find_port_conflicts()` 区分 duplicate vs conflict |
| **7 phase-4 单元测试** | ✅ | `tests/test_cross_repo_consistency_phase4.py` 全 PASSED |
| **33/33 cross-repo tests** | ✅ | phase 1 (8) + phase 3 (8) + phase 4 (7) + p76 (10) = 33/33 |

## 1. 决策 (WHY/WHAT/NEXT)

### 1.1 WHY

STRAT-P77 § 2 Phase 4 入口: Phase 3 unregistered 治本完成, 转向 port-registry 一致性. ADR-0164 § 1.2 占位 "跨仓 port-registry 冲突扫描" — Phase 3 实现占位 (port_count: 0) 但未实施. Phase 4 治本.

根因:
- `load_ecos_ports` 误读 `data.items()` (top-level) 而非 `data["ports"].items()` → 永远返回 0 ports
- YAML parser 不 strip inline comment (`'name  # comment'` 整串返回) → 6 conflict false positive
- 2 真冲突: 8080 (agora-api-gateway 已移除, 重用为 ontoderive-web) + 9290 (命名不一致)

### 1.2 WHAT — detector 升级

```python
# 修 (Phase 4):
def load_ecos_ports() -> dict[int, str]:
    data = load_yaml(f) or {}
    ports = data.get("ports", {}) if isinstance(data, dict) else {}
    return {int(k): _strip_yaml_comment(str(v)) for k, v in ports.items() if str(k).isdigit()}

def _strip_yaml_comment(value: str) -> str:
    if "  #" in value:
        return value.split("  #", 1)[0].strip()
    if "\t#" in value:
        return value.split("\t#", 1)[0].strip()
    return value.strip()
```

效果:
- `load_ecos_ports` 实际加载 9 ports (从 0)
- 6 conflict → 6 duplicate (YAML comment 误判)
- 0 真冲突 (port 8080 + 9290 已对齐)

### 1.3 WHAT — 6 端口对齐

| Port | ecos (前) | protocols | 治本后 (统一) |
|------|-----------|-----------|---------------|
| 7422 | agora-mcp-http | agora-mcp-http | agora-mcp-http (duplicate, ✓) |
| 7431 | agora-mcp-sse | agora-mcp-sse | agora-mcp-sse (duplicate, ✓) |
| 8080 | **agora-api-gateway** | ontoderive-web/health-dashboard | **ontoderive-web** (aligned) |
| 8090 | cockpit-dashboard | cockpit-dashboard | cockpit-dashboard (duplicate, ✓) |
| 9190 | omo-dashboard | omo-dashboard | omo-dashboard (duplicate, ✓) |
| 9290 | **llm-gateway-http** | llm-gateway | **llm-gateway** (aligned) |

### 1.4 NEXT — Phase 5 入口

| 候选 | ROI |
|------|-----|
| LLM-assisted commit 端到端验收 (aetherforge tier 真跑) | 中 |
| Foundry v2 web dashboard | 低 |
| 端口硬编码扫描 (code uses port=1234 not via registry) | 中 |

## 2. 沉淀原则 (P77-4)

| # | 原则 | 含义 |
|---|------|------|
| P77-4-1 | **yaml-comment-strip** | YAML parser 不 strip inline comment, detector 必须手动 strip (`  #` 分割) |
| P77-4-2 | **registry-uniq-by-name** | duplicate (同号同名) 是信息, conflict (同号不同名) 是错误 — 区分 severity |
| P77-4-3 | **ssot-by-canonical-name** | 跨仓 registry 冲突时, 取 protocols/port-registry.yaml 为 SSOT (I0 > L0) |
| P77-4-4 | **aligned-comment-padding** | 端口名对齐后, 注释对齐 (`name  # comment` 保持 2-space 分隔) |
| P77-4-5 | **multi-ssot-warning** | 多 SSOT 同一数据是技术债 — 治本 = 砍掉一个 (或显式声明 deprecation), 不能光留 duplicate |

## 3. 不在本 ADR 范围

- ❌ 端口硬编码扫描 (Phase 5 入口, 留给后续)
- ❌ orphan 28 全治本 (有的是 planned features, 不需补)
- ❌ 6 duplicate 砍掉 (multi-SSOT 治理是 larger refactor, 留作 P78)

## 4. 验证清单

- [x] `load_ecos_ports` 加载 9 ports (从 0)
- [x] `_strip_yaml_comment` helper
- [x] 6 conflict → 6 duplicate
- [x] 0 真 port conflicts
- [x] 端口 8080 + 9290 对齐
- [x] 7 phase-4 测试 PASSED
- [x] 33/33 cross-repo tests passed
- [x] ADR-0167 ACCEPTED + INDEX

## 5. 关联

- STRAT-P77 § 2 Phase 4 (12-week plan W7-8 节点)
- ADR-0166 (Phase 3 unregistered 治本, P77-4 延用 strict-regex 思路)
- ADR-0164 (Phase 1 detector 起点, port_count 字段是 P77-1 占位)
- P77-3-1 (strict-regex-by-boundary 思路延伸到 yaml-comment-strip)

---

*最后更新: 2026-07-07 · P77 Phase 4 跨仓端口一致性收口 · 6 duplicate + 0 conflict · ACCEPTED*
