---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-07
related:
  - 0164-p77-phase1-cross-repo-consistency.md
  - 0165-p77-phase2-evolution-guardrails.md
  - 0166-p77-phase3-cross-repo-remediation.md
  - 0167-p77-phase4-port-registry-consistency.md
  - STRAT-P77-strategic-roadmap.md (Phase 5 收口)
  - ../../../../../bin/check-hardcoded-ports.py
  - ../../../../../tests/test_hardcoded_ports.py
supersedes: []
---

# ADR-0168: P77 Phase 5 — 跨仓端口硬编码扫描 (硬门 + 5 port 补登)

> **For agentic workers**: 本 ADR 是 ACCEPTED 状态 (2026-07-07), 是 P77 STRAT § 2 Phase 5 收口.

## 0. TL;DR

| 交付 | 状态 | 关键产物 |
|------|:---:|---------|
| **硬编码端口 detector** | ✅ | `bin/ssot/check-hardcoded-ports.py` (140 行) |
| **4 unregistered 补登** | ✅ | protocols/port-registry.yaml: 28 → **32** ports |
| **7 port-context patterns** | ✅ | PORT = NNNN / port=NNNN / --port / host:port / localhost / 127.0.0.1 / 0.0.0.0 |
| **5 LEGACY_OK_PORTS** | ✅ | 1234 (LM Studio) / 3000+3001 (family-hub) / 4318 (otel) / 5173 (vite) |
| **10 单元测试** | ✅ | `tests/test_hardcoded_ports.py` 全 PASSED |
| **43/43 cross-repo+port tests** | ✅ | phase 1 (8) + phase 3 (8) + phase 4 (7) + p76 (10) + phase 5 (10) = 43/43 |

## 1. 决策 (WHY/WHAT/NEXT)

### 1.1 WHY

STRAT-P77 § 2 Phase 5 入口: P77-4 port-registry 治本完成, 转向"代码硬编码 vs SSOT 注册" 检测. 修真修真:

- 7430 (agora internal): 16 sites in code, 0 in SSOT → 16 修真修真反模式
- 9876 (runtime L1): 3 sites in code, 0 in SSOT → 3 修真修真反模式
- 7420 (BOS API): 2 sites in code, 0 in SSOT
- 7432 (ecos event listener): 1 site in code, 0 in SSOT

反模式: 端口在代码里硬编码, 没在 SSOT 注册 → 跨仓 port 冲突 / 部署漂移 / port 治理盲区.

### 1.2 WHAT — detector 设计

```python
# 数据流:
#   1. 读 projects/ecos/port-registry.yaml + protocols/port-registry.yaml → registered union
#   2. 扫 projects/*/src/ 真代码 (非 test, 非 docstring) 7 种 port-context 模式
#   3. 排除 LEGACY_OK_PORTS (外部标准 / 工具)
#   4. unregistered = hardcoded_keys - registered - legacy_ok
#   5. 输出 violations table + threshold (默认 0)
#   6. exit 0 if unregistered ≤ threshold else 1
```

7 种 port-context 模式 (修真修真覆盖):
- `PORT = NNNN` (常量)
- `port=NNNN` / `port: NNNN` (配置)
- `--port NNNN` (CLI)
- `host:port/path` (URL)
- `localhost:port` / `127.0.0.1:port` / `0.0.0.0:port` (开发/部署)

### 1.3 WHAT — 4 port 补登

| Port | 名称 | 用法 | sites |
|------|------|------|-------|
| 7420 | bos-api | BOS API service (agora tools_proxy, ecos watchdog) | 2 |
| 7430 | agora-internal | agora internal dashboard / instance / worker_dispatch | 16 |
| 7432 | ecos-event-listener | ecos workflow event_listener SSE | 1 |
| 9876 | runtime-l1 | runtime L1 service (cockpit dashboard) | 3 |

### 1.4 WHAT — LEGACY_OK_PORTS (5 外部豁免)

| Port | 名称 | 理由 |
|------|------|------|
| 1234 | LM Studio | 本地 LLM (OpenAI compatible) |
| 3000 | family-hub dashboard | 外部仓 (projects/family-hub) |
| 3001 | family-hub api | 外部仓 |
| 4318 | OpenTelemetry OTLP | 行业标准 |
| 5173 | Vite dev server | 工具默认 |

### 1.5 NEXT — Phase 6 入口

| 候选 | ROI |
|------|-----|
| LLM-assisted commit 端到端验收 (aetherforge tier 真跑) | 中 |
| Foundry v2 web dashboard | 低 |
| 端口硬编码 → env var 重构 (修真修真) | 中 (慢) |

## 2. 沉淀原则 (P77-5)

| # | 原则 | 含义 |
|---|------|------|
| P77-5-1 | **port-registration-mandatory** | 任何 service 端口必须先在 SSOT 注册, 否则 hard fail |
| P77-5-2 | **legacy-external-allowlist** | 外部服务 (otel/vite/lm-studio/family-hub) 允许硬编码 + 显式 LEGACY_OK_PORTS |
| P77-5-3 | **environment-variable-preferred** | 优先用 env var, 而不是字面量 — 修真修真 (Phase 6 入口) |
| P77-5-4 | **port-context-pattern** | detector 必须用 7+ port-context 模式覆盖 (PORT= / port= / --port / host:port / localhost / 127.0.0.1 / 0.0.0.0) |
| P77-5-5 | **detector-evolution-via-catalog** | detector 升级必须先有测试断言新行为 (P77-2-3 + P77-3-5 沿用) |

## 3. 不在本 ADR 范围

- ❌ 端口硬编码 → env var 重构 (Phase 6, 慢)
- ❌ LLM-assisted commit 端到端验收 (独立 entry, 留作 Phase 6.x)
- ❌ Foundry v2 web dashboard (低优先级)

## 4. 验证清单

- [x] `bin/ssot/check-hardcoded-ports.py` 创建 (140 行)
- [x] 7 port-context 模式覆盖
- [x] 5 LEGACY_OK_PORTS (1234/3000/3001/4318/5173)
- [x] 4 unregistered 全补登 SSOT (32 total)
- [x] unregistered = 0 (实际 run 验证)
- [x] 10 phase-5 测试 PASSED
- [x] 43/43 cross-repo+port tests passed
- [x] ADR-0168 ACCEPTED + INDEX
- [x] M1 sync (no new GaC rules)

## 5. 关联

- STRAT-P77 § 2 Phase 5 (12-week plan W9-10 节点)
- ADR-0167 (P77-4 port-registry 一致性, Phase 5 是其延伸)
- ADR-0166 (P77-3 unregistered 治本, port 是 unregistered 的一种)
- P77-4-3 (ssot-by-canonical-name, protocols 是 I0 SSOT)
- P77-2-3 (rule-per-principle, detector 必加测试)
- P77-3-5 (tool-evolution-via-tests, 沿用)

---

*最后更新: 2026-07-07 · P77 Phase 5 端口硬编码扫描收口 · 4 unregistered 全治本 · ACCEPTED*
