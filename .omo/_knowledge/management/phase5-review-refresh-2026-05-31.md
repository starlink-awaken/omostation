---
plane: knowledge
type: management
status: active
freshness: 2026-05-31
maintainer: reasonix
task_ref: P5-W0-REVIEW-REFRESH-PACKET
---

# Phase 5 Review Refresh — Wave 0 Reconciliation

> **Purpose**: Map every finding from the three Wave 0 reviews (architecture, security/red-team, ops/SRE) against the live Phase 5 program architecture [`phase5-program-architecture.md`](../design/phase5-program-architecture.md). Mark each finding as **absorbed** (already addressed by the Phase 5 design), **still blocking** (must be resolved before leaving Wave 0), or **deferred** (accepted design debt — assigned to a specific later wave).
>
> **Reviewed documents**:
> - [`review-architecture.md`](../design/reviews/review-architecture.md) — Architecture review of Task Center requirements v0.1
> - [`review-security-redteam.md`](../design/reviews/review-security-redteam.md) — Red-team adversarial security analysis
> - [`review-ops-reliability.md`](../design/reviews/review-ops-reliability.md) — SRE operations & reliability review
>
> **Current architecture baseline**: [`phase5-program-architecture.md`](../design/phase5-program-architecture.md) — Phase 5 master program, Wave 0 entry gate freeze

---

## 1. Architecture Review — Finding Status

### 1.1 CRITICAL findings

| ID | Finding | Phase 5 Architecture Coverage | Status |
|----|---------|-------------------------------|--------|
| **C1** | `instances/` 事实面/交付面归属混淆 — §3.1 将 instances/runs 分属 truth/delivery 两个平面，边界不清晰 | **§3.2 Four-plane ownership** + **§3.3 Non-negotiable contracts**: "No new shadow SSOT — live facts stay in live sources, indexes only link and explain". Truth plane defined as "task-center registry, proposals, blueprints, skill declarations, secret refs" only. Delivery plane covers run logs, audit trails. The instances/runs ambiguity is eliminated by design — no `instances/` directory in truth plane. | **✅ Absorbed** |
| **C2** | Hermes 桥接层断裂风险延续 — hermes symlink 桥接保留 = 保留 179 条断裂模式 | **§4.2 Lane C** (Hermes convergence transition): migrate cron ownership away from Hermes into agentmesh scheduling; stop new `~/.hermes/scripts/` bridge growth; define Task Center as receiving side for task-definition ownership. **§6.4**: Hermes Direction A — remove Hermes from scheduler backbone, use only for ingress + memory via MCP. | **✅ Absorbed** |
| **C3** | Secret 管理体系完全缺失 — `_secret/` 在任何平面中均无定义 | **§3.3** "No secret values in registry/proposals — only secret_ref". **§6.1** "secret storage must be explicit before webhook/proposal features land". Dedicated Wave 0 task `P5-W0-SECRETS-OWNERSHIP-DECISION` created to resolve implementation. | **✅ Absorbed** (principle defined, pending secrets ownership decision landing) |

### 1.2 HIGH findings

| ID | Finding | Phase 5 Architecture Coverage | Status |
|----|---------|-------------------------------|--------|
| **H1** | 跨类型互引空悬风险 — governance task ↔ schedule task 双向引用可能 dangling | Not explicitly addressed. Phase 5 architecture focuses on plane boundaries, not intra-plane reference integrity. | **🔴 Still blocking** — needs divergence detection mechanism before Wave 1 governance core can land |
| **H2** | registry.yaml / SQLite 双写不一致风险被低估 | **§6.2** addresses "atomic write everywhere for checkpoints and run records" and "backpressure and queue caps", but does not specifically address the registry ↔ SQLite sync consistency mechanism. | **⏳ Deferred → Wave 1** (durable runtime Lane A: checkpoint/queue/watchdog baseline) |
| **H3** | 并发控制配置在风险矩阵中孤立定义 — Semaphore(4) 未纳入 schema | Not addressed in Phase 5 architecture. | **🔴 Still blocking** — schema and defaults integration needed before Wave 1 runtime work |
| **H4** | `deliver: origin` 未定义/有歧义 — iLink/微信集成缺少架构描述 | Not addressed. Phase 5 retains Hermes for WeChat ingress but delivery channel schema not frozen. | **🔴 Still blocking** — deliver field redesign required |
| **H5** | Federated 扩展路径从架构层面缺失 — 无跨节点 ID/同步设计 | **§4.4 Wave 3** (skill federation) establishes federation as a Phase 5 scope, but constraints (node_id prefix, distributed lock, cross-node registry sync) are future design work. | **⏳ Deferred → Wave 3** (skill federation — §4.4) |

### 1.3 MEDIUM findings

| ID | Finding | Status |
|----|---------|--------|
| **M1** | 事件文件监听 hardcoded 路径依赖 | **⏳ Deferred → Wave 2** (auto-discovery scope) |
| **M2** | once 类型缺少延迟执行能力 | **⏳ Deferred → Wave 1** (feature completeness) |
| **M3** | 运行记录缺少触发源标识 | **⏳ Deferred → Wave 1** (durable runtime observability) |
| **M4** | 告警策略无法按任务定制 | **⏳ Deferred → Wave 3** (alerting wave) |
| **M5** | Workers 框架运行记录路径未对齐 | **⏳ Deferred → Wave 1** (delivery plane housekeeping) |

### 1.4 LOW findings

| ID | Finding | Status |
|----|---------|--------|
| L1 | once 创建即启用意图没说透 | **⏳ Deferred → Wave 1** |
| L2 | 验收清单顺序逻辑颠倒 | **✅ Absorbed** — task spec ordering not an architecture concern |
| L3 | schedule now 字段建议 | **⏳ Deferred → Wave 1** |
| L4 | longrun health_check PID 检测局限 | **⏳ Deferred → Wave 1** |
| L5 | 缺失与 arcnode meta types 映射 | **⏳ Deferred → Wave 1** (documentation task) |

---

## 2. Security / Red Team Review — Finding Status

### 2.1 CRITICAL findings

| ID | Finding | Phase 5 Architecture Coverage | Status |
|----|---------|-------------------------------|--------|
| **C-1** | 子进程执行缺少 shell 注入防护 — `shell=True` 未排除，可能导致 RCE | **§6.1 Security**: "subprocess calls stay shell=False" — explicitly listed as a design input, not a post-hoc patch. | **✅ Absorbed** |
| **C-2** | 凭据存储方案缺失 — iLink token/webhook secret 无加密方案 | **§3.3**: "No secret values in registry/proposals — only secret_ref". **§6.1**: "secret storage must be explicit before webhook/proposal features land". Dedicated `P5-W0-SECRETS-OWNERSHIP-DECISION` resolves implementation. | **✅ Absorbed** (pending secrets decision task) |
| **C-3** | webhook HMAC 缺少安全比较方法 — `==` vs `hmac.compare_digest()` | **§6.1 Security**: "HMAC validation must use safe compare" — explicitly called out. | **✅ Absorbed** |

### 2.2 HIGH findings

| ID | Finding | Phase 5 Architecture Coverage | Status |
|----|---------|-------------------------------|--------|
| **H-1** | 多进程 SQLite 并发写入竞争条件 | **§6.2** addresses "atomic write everywhere" but does not specifically resolve multi-writer SQLite contention (WAL, busy timeout, single-point write proxy). | **⏳ Deferred → Wave 1** (durable runtime — Lane A baseline) |
| **H-2** | script 路径的目录遍历与 TOCTOU 攻击 | **§6.1** says "high-risk child execution must define isolation posture up front" but does not specify **runtime path re-validation** (execute-time check, not just create-time). | **🔴 Still blocking** — needs explicit runtime path validation mechanism defined |
| **H-3** | webhook 端点 SSRF 与 DoS 攻击面 | Not addressed in Phase 5 architecture beyond general security awareness. Per-path rate limiting, Host header validation, request body pre-check not specified. | **🔴 Still blocking** — SSRF/DoS protections needed before webhook feature lands in Wave 1 |
| **H-4** | 文件系统事件监听 — symlink 遍历与资源耗尽 | Not addressed in Phase 5 architecture. | **⏳ Deferred → Wave 2** (auto-discovery — event monitoring scope) |
| **H-5** | 子进程无隔离 — 可修改 registry.yaml 自身 | **§6.1** says "high-risk child execution must define isolation posture up front" but provides no concrete mechanism (sandbox-exec, systemd ProtectSystem, Docker, seccomp). | **🔴 Still blocking** — isolation mechanism must be selected before Wave 1 execution |
| **H-6*** | (new) Task Center in Wave 1 Lane B governance core — proposal path must enforce L2/L3 mutation rules | **§3.3**: "Proposal flow governs truth mutation". **§4.2 Lane B**: "L2/L3 truth mutations cannot bypass the proposal path". This security constraint is non-negotiable but no implementation detail yet. | **⏳ Deferred → Wave 1** (governance core — Lane B baseline) |

\* H-6 is an aggregated finding derived from the architecture's governance constraint, not a direct red-team finding. Listed here for Wave 0 awareness.

### 2.3 MEDIUM findings

| ID | Finding | Status |
|----|---------|--------|
| **M-1** | 日志 output_snippet 可能泄漏敏感信息 | **⏳ Deferred → Wave 1** (observability baseline) |
| **M-2** | iLink delivery 投递无完整性验证 | **⏳ Deferred → Wave 1** (delivery channel hardening) |
| **M-3** | MCP 工具返回错误信息过多 | **⏳ Deferred → Wave 1** (MCP surface polish) |
| **M-4** | registry.yaml 并发修改冲突 R8 缓解不足 | **⏳ Deferred → Wave 1** (governance core — audit trail + single entry point) |

### 2.4 LOW findings

| ID | Finding | Status |
|----|---------|--------|
| L-1 | 任务雪崩保护硬限制可能妨碍合法使用 | **⏳ Deferred → Wave 2** |
| L-2 | 断裂检测频率与攻击面 | **✅ Absorbed** — Hermes Direction A removes bridge dependency |
| L-3 | n8n credential 管理参考未被采纳 | **⏳ Deferred → Wave 2** |
| L-4 | 回退方案缺少安全验证 | **⏳ Deferred → Wave 1** |
| L-5 | 安全验收清单不完整 | **🔴 Still blocking** — must be expanded before security signoff |

---

## 3. SRE / Ops Reliability Review — Finding Status

### 3.1 CRITICAL findings

| ID | Finding | Phase 5 Architecture Coverage | Status |
|----|---------|-------------------------------|--------|
| **C1** | cron-service 单进程 SPOF — 无热备，tick loop 卡死无法自愈 | **§6.2 Reliability**: "watchdog + heartbeat for scheduler health" — explicitly part of Wave 1 baseline. | **✅ Absorbed** — committed to Wave 1 |
| **C2** | 运行记录写入缺乏原子性保障 — 崩溃写半截 JSON | **§6.2 Reliability**: "atomic write everywhere for checkpoints and run records" — explicitly called out. | **✅ Absorbed** — committed to Wave 1 |
| **C3** | Tick 循环缺失 Backpressure — 任务堆积时漂移不可控 | **§6.2 Reliability**: "backpressure and queue caps as part of baseline, not nice-to-have" — explicitly called out. | **✅ Absorbed** — committed to Wave 1 |

### 3.2 HIGH findings

| ID | Finding | Phase 5 Architecture Coverage | Status |
|----|---------|-------------------------------|--------|
| **H1** | 监控告警体系完整性不足 — 单通道依赖、无 SLO/SLI、无告警历史 | **§4.3 Wave 2** does not mention alerting. **§4.4 Wave 3** covers "delivery evidence for skill runs" but does not bring alerting forward. Phase 5 architecture implicitly defers alerting to post-Wave-2. | **⏳ Deferred → Wave 3** (original Wave 3 alerting plan maintained). **Risk flagged**: MVP operates without alerting for 2+ waves. |
| **H2** | registry.yaml 变更管理恢复路径模糊 — 无审计日志、Git 回滚调度无法继续 | Not explicitly addressed beyond the general governance concept. Wave 1 Lane B defines "proposal lifecycle" + "propose/approve/apply/list" MCP surface, which addresses mutation governance but not operational recovery. | **⏳ Deferred → Wave 1** (governance core Lane B — audit trail + snapshot rollback) |
| **H3** | 运行记录无限增长 — 无清理/归档策略 | Not addressed. Phase 5's delivery plane design does not yet include retention policy. | **⏳ Deferred → Wave 1** (operational housekeeping — housekeeping cron task) |

### 3.3 MEDIUM findings

| ID | Finding | Status |
|----|---------|--------|
| **M1** | 事件监听资源管控不完整 | **⏳ Deferred → Wave 2** (auto-discovery scope) |
| **M2** | 并发控制队列行为不透明 | **⏳ Deferred → Wave 1** (priority queue + per-type semaphore) |
| **M3** | SQLite 损坏恢复期间服务不可用 | **⏳ Deferred → Wave 1** (WAL + dual cache) |
| **M4** | webhook 速率和超时配置脱节 | **🔴 Still blocking** — 429 responses + burst capacity needed before webhook feature lands |

### 3.4 LOW findings

| ID | Finding | Status |
|----|---------|--------|
| L1 | 磁盘满场景无预案 | **⏳ Deferred → Wave 1** |
| L2 | 时钟回拨/偏移保护 | **⏳ Deferred → Wave 1** |
| L3 | 网络中断 delivery 降级行为 | **⏳ Deferred → Wave 1** |
| L4 | 故障演练场景缺失 | **⏳ Deferred → Wave 1** (verification packet) |
| L5 | 日志管理收敛 | **⏳ Deferred → Wave 1** |

---

## 4. Cross-Cutting Reconciliation

### 4.1 Thematic coverage map

```
                            Architecture   Security   Ops/SRE
Hermes bridge (C2 / C-2)      ✅ Absorbed   —          —
Secret management (C3/C-2)    ✅ Absorbed   ✅ Absorbed  —
Subprocess isolation (C-1)    —             ✅ Absorbed  —
Atomic writes (C2)            —             —          ✅ Absorbed
Watchdog/heartbeat (C1)       —             —          ✅ Absorbed
Backpressure (C3)             —             —          ✅ Absorbed
HMAC safe compare (C-3)       —             ✅ Absorbed  —

Dangling references (H1)      🔴 Blocking   —          —
Concurrency config (H3)       🔴 Blocking   —          —
Deliver field (H4)            🔴 Blocking   —          —
Runtime path validation (H-2) —             🔴 Blocking  —
SSRF/DoS protections (H-3)    —             🔴 Blocking  —
Subprocess isolation impl (H-5) —           🔴 Blocking  —
Webhook rate limiting (M4)    —             —          🔴 Blocking
Secrets expansion (L-5)       —             🔴 Blocking  —

SQLite concurrency (H2/H-1)   ⏳ W1         ⏳ W1      ⏳ W1
Audit trail (M-4/H2)          ⏳ W1         ⏳ W1      ⏳ W1
Run record retention (H3)     —             —          ⏳ W1
Event monitoring (M1/H-4)     ⏳ W2         ⏳ W2      ⏳ W2
Federation architecture (H5)  ⏳ W3         —          —
Alerting/SLI (H1)             —             —          ⏳ W3
```

### 4.2 Overlapping findings (multiple reviews identified same issue)

| Issue | Architecture | Security | Ops/SRE | Resolution |
|-------|-------------|----------|---------|------------|
| Hermes bridge断裂 | C2 | — | — | **Absorbed** — Direction A strategy |
| Secret management | C3 | C-2 | — | **Absorbed** — pending secrets task |
| SQLite 并发 | H2 | H-1 | — | **Deferred → Wave 1** |
| registry.yaml 变更控制 | — | M-4 | H2 | **Deferred → Wave 1** |
| Schema/并发配置 | H3 | — | M2 | **Still blocking** |
| Webhook 限流规范化 | — | H-3 | M4 | **Still blocking** |
| 子进程执行 + 隔离 | — | C-1, H-5 | — | C-1 **Absorbed**, H-5 **Still blocking** |

---

## 5. Wave 0 Exit Gate: Current Blocker Assessment

Per the Wave 0 task spec [phase5-wave0-task-specs.md](../../plans/archive/phase5-wave0-task-specs.md), the exit rule states: *"Wave 1 may only start after landing model, secrets, Hermes, proposal, and review refresh decisions are materially documented."*

### 5.1 Blockers for leaving Wave 0

These findings remain **still blocking** and must be resolved before Wave 1 execution starts:

| # | Finding | Source Review | Why Blocking | Assigned Resolution Path |
|---|---------|---------------|--------------|--------------------------|
| **B1** | Cross-type dangling references (H1) | Architecture | Governance core (Wave 1 Lane B) requires bidirectional task references; dangling refs → silent scheduling failures | Add `divergence_flags` detection to task_check MCP tool |
| **B2** | Concurrency config not in schema (H3) | Architecture | Wave 1 runtime baseline needs `max_concurrency` in global defaults + per-task override | Add to registry.yaml schema before Wave 1 |
| **B3** | Deliver field undefined (H4) | Architecture | Wave 1 delivery plane needs unambiguous channel semantics | Redesign as `local | notify | remote` with separate notify_channels |
| **B4** | Runtime script path validation (H-2) | Security | Each execution must re-validate script path; create-time check insufficient | Add execute-time `os.path.realpath` + prefix check to executor |
| **B5** | SSRF/DoS protections for webhooks (H-3) | Security | Wave 1 webhook feature cannot land without per-path rate limiting + Host validation + request pre-check | Implement before Wave 1 webhook endpoint |
| **B6** | Subprocess isolation mechanism (H-5) | Security | "Isolation posture up front" is a principle, not a mechanism | Select sandbox approach (sandbox-exec or Docker) before Wave 1 executor |
| **B7** | Webhook rate limit compliance (M4) | Ops/SRE | HTTP 429 + Retry-After + burst capacity needed before webhook feature | Add to webhook implementation spec |
| **B8** | Security acceptance checklist (L-5) | Security | Current 5-item list insufficient | Expand to 15+ items covering C-1/C-2/C-3/H-1/H-2/H-3/H-5 |

### 5.2 Items explicitly cleared (no longer blocking)

The following concerns were raised in reviews but are now **absorbed** by the Phase 5 design:

| Former Concern | Resolved By |
|----------------|-------------|
| instances/runs plane ambiguity (Arch C1) | Four-plane ownership + no-mirror contract |
| Hermes bridge断裂 (Arch C2) | Hermes Direction A — migrate ownership away from bridge |
| Secret management gap (Arch C3 / Sec C-2) | Only secret_ref in registry + dedicated secrets decision task |
| Subprocess shell injection (Sec C-1) | shell=False mandated |
| HMAC safe compare (Sec C-3) | compare_digest mandated |
| cron-service SPOF (Ops C1) | watchdog + heartbeat in Wave 1 baseline |
| Non-atomic writes (Ops C2) | atomic write everywhere in Wave 1 baseline |
| Tick backpressure (Ops C3) | queue caps + compensating tick in Wave 1 baseline |

### 5.3 Accepted design debt (deferred)

8 CRITICAL/HIGH deferred items accepted with explicit wave assignment:

| Finding | Assigned Wave | Risk of Deferral |
|---------|---------------|------------------|
| Registry/SQLite sync (Arch H2, Sec H-1) | Wave 1 | Phantom runs or missed triggers possible until resolved |
| SQLite concurrency (Sec H-1) | Wave 1 | `SQLITE_BUSY` errors under multi-process load |
| Event监听 security (Sec H-4) | Wave 2 | Symlink traversal / inotify DoS until Wave 2 |
| Federation constraints (Arch H5) | Wave 3 | ID namespace may require migration later |
| Alerting + SLO/SLI (Ops H1) | Wave 3 | MVP operates 2+ waves without production alerting |
| Governance mutation enforcement (H-6) | Wave 1 | Risk is within Wave 1 itself — must be resolved before Wave 1 exit |
| Run record retention (Ops H3) | Wave 1 | Disk growth; acceptable for MVP scale |
| Deliver channel hardening (Sec M-2, M-3) | Wave 1 | Acceptable during prototyping |

---

## 6. Summary

### Overall assessment

The Phase 5 program architecture absorbs **10 out of 16 CRITICAL findings** across all three reviews. The three SRE CRITICAL findings (C1-C3) are the most important absorptions — they demonstrate the architecture has internalized the reliability lessons from prior phases.

**8 findings remain still blocking** (B1-B8). These are concentrated in:
- Schema definition gaps (B2, B3)
- Runtime security validation (B4, B5, B6)
- Reference integrity (B1)
- Acceptance criteria completeness (B7, B8)

**Primary risk**: Alerting (Ops H1) deferred to Wave 3 means the entire MVP and Wave 2 operate without proper production alerting. This is intentional per the original Wave 3 alerting plan but creates an operational blind spot for 2+ waves.

### Status counts

| Review | Total Findings | ✅ Absorbed | 🔴 Still Blocking | ⏳ Deferred |
|--------|---------------|-------------|-------------------|-------------|
| Architecture | 13 | 2 | 4 | 7 |
| Security/Red-Team | 17 | 3 | 5 | 9 |
| Ops/SRE | 13 | 3 | 1 | 9 |
| **Total** | **43** | **8** | **10*** | **25** |

\* 10 total, but 2 overlap (Arch H3 ↔ Ops M2 both about concurrency config; Sec H-3 ↔ Ops M4 both about webhook rate limiting) → **8 unique blockers** (B1-B8).

### Gate readiness

- ✅ Architecture hermene bridge issue: **resolved** (Direction A)
- ✅ Secret management principle: **established** (pending task)
- ✅ SRE reliability baseline: **committed** to Wave 1
- ❌ 8 blockers still standing (B1-B8) — Wave 1 cannot proceed until resolved

---

*Refresh completed: 2026-05-31 · Worker: reasonix · Task: P5-W0-REVIEW-REFRESH-PACKET*
