---
schema: md/v1
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-25
type: ssot
last_updated: 2026-09-17
---

# Superpowers Spec Registry

本目录存放 `eCOS` 超能力项目的规格说明书（specs），用于约束高风险 bet 的设计和验收。

## Spec 生命周期

每个 spec 经历以下状态流转：

```
draft → accepted → superseded
```

- **draft**：草稿状态，正在讨论和完善
- **accepted**：已通过 grill-me 收束，成为约束性规格
- **superseded**：已被新 spec 替代，保留历史记录

## Spec 模板

新建 spec 时，请复制 `_TEMPLATE.md` 并填写各章节。必含章节：

- **背景与问题**：基于事实的问题描述
- **验收标准**：每条可被命令验证（assertion + evidence_type）
- **反指标**：明确不作为成功度量的指标（对齐蓝图 §20）
- **Decision Log**：grill-me 拷问裁定表（|#|分叉|裁定|理由）

## Grill-me 收束约定

所有 L2/L3 高风险 bet 必须经过 grill-me 收束：

1. 在 spec 中通过 **Decision Log** 章节记录关键分叉的裁定
2. 每条裁定包含明确的理由（基于事实或约束）
3. 避免模糊表述，确保裁定可追溯

## Digest 绑定机制

L2/L3 bet 必须绑定 accepted spec：

1. 在 bet 的 `accepted_specifications` 字段中声明
2. 每条绑定包含：
   - `spec_ref`：spec 文件路径（相对本目录）
   - `content_digest`：spec 文件的 SHA256 哈希
3. `bet-ledger.py lint` 会自动验证文件存在性和 digest 匹配

向后兼容窗口：2026-09-01 起强制。

## 现有 Specs

| 文件 | 状态 | BET | 最后审查 |
|------|------|-----|----------|
| `_TEMPLATE.md` | draft | — | — |
| `2026-08-12-documents-owner-job-design.md` | active | — | 2026-08-13 |
| `2026-08-13-codex-exec-worker-design.md` | active | — | 2026-08-13 |
| `2026-08-13-orchestration-contract-mvp-design.md` | active | — | 2026-08-13 |
| `2026-08-13-personal-capability-mainline-restore.md` | active | — | 2026-08-13 |
| `2026-08-14-codex-acp-stdio-cutover-design.md` | active | — | 2026-08-14 |
| `2026-08-14-supervised-blueprint-control-loop-design.md` | active | BET-Y1Q2-T1-18 | 2026-08-14 |
| `2026-08-14-weijian-sanyi-status-consistency-design.md` | active | — | 2026-08-14 |

### 2026-09-10—09-11 opening wave (T10-145 ~ T10-153, T16, T5-03 等)

| 文件 | 状态 | BET | 最后审查 |
|------|------|-----|----------|
| `2026-09-10-claims-authority-bridge-wp1-shadow-design.md` | accepted | BET-Y1Q4-T10-145 | 2026-09-11 |
| `2026-09-11-a5-aetherforge-gateway-restore-fix.md` | accepted | BET-Y1Q4-T10-153 | 2026-09-11 |
| `2026-09-11-a5-launchd-ws-t1069-fix.md` | accepted | BET-Y1Q4-T10-152 | 2026-09-11 |
| `2026-09-11-cockpit-nextgen-architecture-and-six-planes-spec.md` | accepted | BET-Y1Q4-T8-24 | 2026-09-11 |
| `2026-09-11-ops-drift-guard-design.md` | accepted | BET-Y1Q4-T16 | 2026-09-11 |
| `2026-09-11-orca-r0-verify-design.md` | accepted | BET-Y1Q4-T10-149 | 2026-09-11 |
| `2026-09-11-persistent-queue-design.md` | accepted | BET-Y1Q4-T10-147 | 2026-09-11 |
| `2026-09-11-t10-05-offline-sandbox-vault-spec.md` | accepted | BET-Y1Q4-T10-05 | 2026-09-11 |
| `2026-09-11-t10-125-bos-gateway-spec.md` | accepted | BET-Y1Q4-T10-125 | 2026-09-11 |
| `2026-09-11-t5-03-resident-a2a-delegation-spec.md` | accepted | BET-Y1Q4-T5-03 | 2026-09-11 |
| `2026-09-11-t8-24a-observatory-convergence-spec.md` | accepted | BET-Y1Q4-T8-24A | 2026-09-11 |
| `2026-09-11-zhixing-dashboard-full-causal-mesh-spec.md` | accepted | BET-Y1Q4-T8-25 | 2026-09-11 |

### 2026-09-12—09-17 delivery wave

| 文件 | 状态 | BET | 最后审查 |
|------|------|-----|----------|
| `2026-09-12-multica-as0-verify-design.md` | accepted | BET-Y1Q4-T10-150 | 2026-09-11 |
| `2026-09-12-studio-view-deep-delivery-spec.md` | accepted | BET-Y1Q4-T8-24C | 2026-09-12 |
| `2026-09-12-t10-157-aetherforge-responses-pointer-close.md` | accepted | BET-Y1Q4-T10-157 | 2026-09-12 |
| `2026-09-12-t10-158-omlxc-probe-candidates-pointer-close.md` | accepted | BET-Y1Q4-T10-158 | 2026-09-12 |
| `2026-09-12-t10-159-aetherforge-anthropic-messages-pointer-close.md` | accepted | BET-Y1Q4-T10-159 | 2026-09-12 |
| `2026-09-12-t10-161-gitlink-freshness-remote-integrity-guard.md` | accepted | BET-Y1Q4-T10-161 | 2026-09-12 |
| `2026-09-12-t10-162-omlxc-inventory-baseline-reset-pointer-close.md` | accepted | BET-Y1Q4-T10-162 | 2026-09-12 |
| `2026-09-12-t10-165-omo-persistent-semantics-design.md` | accepted | BET-Y1Q4-T10-165 | 2026-09-12 |
| `2026-09-12-t2-06-mail-calendar-ingress-design.md` | accepted | BET-Y1Q4-T2-06 | 2026-09-12 |
| `2026-09-12-t3-01-persona-radar-engine-design.md` | accepted | BET-Y2Q2-T3-01 | 2026-09-12 |
| `2026-09-12-t5-04-sovereign-connector-fabric-design.md` | accepted | BET-Y1Q4-T5-04 | 2026-09-12 |
| `2026-09-12-t5-05-resident-causal-decision-design.md` | accepted | BET-Y1Q4-T5-05 | 2026-09-12 |
| `2026-09-12-t6-25-openhuman-bridge-biometric-normalizer-design.md` | accepted | BET-Y1Q4-T6-25 | 2026-09-12 |
| `2026-09-12-t6-26-semantica-graph-kernel-design.md` | accepted | BET-Y1Q4-T6-26 | 2026-09-12 |
| `2026-09-12-t7-04-scene-navigation-guardrails-design.md` | accepted | BET-Y1Q4-T7-04 | 2026-09-12 |
| `2026-09-12-t7-05-scene-lifecycle-cruiser-design.md` | accepted | BET-Y1Q4-T7-05 | 2026-09-12 |
| `2026-09-12-t7-06-contract-net-taskforce-design.md` | accepted | BET-Y1Q4-T7-06 | 2026-09-12 |
| `2026-09-12-t8-21-decision-proposals-closeout-spec.md` | accepted | BET-Y1Q4-T8-21 | 2026-09-12 |
| `2026-09-12-t8-24d-operations-mission-design.md` | accepted | BET-Y1Q4-T8-24D | 2026-09-12 |
| `2026-09-12-t8-24e-a9-observatory-closeout-design.md` | accepted | BET-Y1Q4-T8-24E | 2026-09-12 |
| `2026-09-12-y2q2-t7-03-health-monitor-design.md` | accepted | BET-Y2Q2-T7-03 | 2026-09-12 |
| `2026-09-12-y2q3-t7-01-family-asset-governance-spec.md` | accepted | BET-Y2Q3-T7-01 | 2026-09-12 |
| `2026-09-13-t6-28-cognitive-hierarchy-radix-kv-design.md` | accepted | BET-Y1Q4-T6-28 | 2026-09-13 |
| `2026-09-13-t8-23-resident-flight-deck-design.md` | accepted | BET-Y1Q4-T8-23 | 2026-09-13 |
| `2026-09-14-a4-remote-hygiene-cron-registry-parity-design.md` | accepted | BET-Y1Q4-T16-02 | 2026-09-14 |
| `2026-09-14-t3-05-mindmodel-four-pieces-spec.md` | accepted | BET-Y2Q1-T3-05 | 2026-09-14 |
| `2026-09-14-t5-01-strategy-sandbox-design.md` | accepted | BET-Y2Q1-T5-01 | 2026-09-14 |
| `2026-09-14-t8-22-tinybos-mesh-spec.md` | accepted | BET-Y1Q4-T8-22 | 2026-09-15 |
| `2026-09-15-a8-omo-external-transaction-lifecycle-design.md` | accepted | BET-Y1Q4-T10-151 | 2026-09-15 |
| `2026-09-15-t10-167-ledger-schema-hardening.md` | accepted | BET-Y1Q4-T10-167 | 2026-09-15 |
| `2026-09-15-t3-02-lora-matrix-spec.md` | accepted | BET-Y2Q2-T3-02 | 2026-09-15 |
| `2026-09-15-t7-07-review-remediation-design.md` | accepted | BET-Y2Q1-T7-07 | 2026-09-15 |
| `2026-09-15-y2q1-t7-06-health-gov-doc-cycle-design.md` | accepted | BET-Y2Q1-T7-06 | 2026-09-15 |
| `2026-09-16-t10-146-maturity-rollup-tracking.md` | accepted | BET-Y1Q4-T10-146 | 2026-09-16 |
| `2026-09-16-t6-30-persona-mirror-spec.md` | accepted | BET-Y1Q4-T6-30 | 2026-09-16 |
| `2026-09-16-t7-01-org-network-graph-spec.md` | accepted | BET-Y2Q1-T7-01 | 2026-09-16 |
| `2026-09-16-y3h1-t5-02-routine-hosting-spec.md` | accepted | BET-Y3H1-T5-02 | 2026-09-16 |
| `2026-09-17-siri-40-documentation-convergence-design.md` | accepted | BET-Y1Q4-T10-168 | 2026-09-17 |
| `2026-09-17-t7-02-assisted-escalation-design.md` | accepted | BET-Y3H1-T7-02 | 2026-09-17 |
| `2026-09-17-t7-08-scene-journey-admission-convergence-design.md` | accepted | BET-Y1Q4-T7-08 | 2026-09-17 |
| `2026-09-19-t10-169-dependabot-root-scope-design.md` | accepted | BET-Y1Q4-T10-169 | 2026-09-19 |
| `2026-09-20-t4-01-value-ingress-and-signal-loop-design.md` | accepted | BET-Y2Q1-T4-01 | 2026-09-20 |
| `2026-09-21-t4-02-signal-daemon-and-resident-loop-design.md` | accepted | BET-Y2Q1-T4-02 | 2026-09-21 |
| `2026-09-21-t4-03-spine-diff-adaptation-design.md` | accepted | BET-Y2Q1-T4-03 | 2026-09-21 |

> 旧版条目保留为历史手工登记；后续应将本表迁移为生成型索引，避免新的 accepted spec 再次脱离导航。
