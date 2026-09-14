---
status: active
lifecycle: history
owner: governance-team
last-reviewed: "2026-07-29"
type: ephemeral
status: archived
---
# P86 R2: ADV25-59 逐个边界标注 (协议不支持声明)

> 上位: goal R2 (补做 ADV25-59 边界标注, 当前 0/14+)
> 🔴 红线 (Q1/P3): 仅对抗集 + 真实 0 发生 → 标注"协议不支持, 已知边界", 不补实现
> 处置: 这些 ADV 全部仅对抗集 (runs 87 个 0 真实冲突), 按 B1' 标注边界, **不补 _synthesize_**

## 边界声明 (逐个 ADV, 协议不支持)

| ADV | 类别 | 含义 | 协议支持? | 真实发生? | 处置 |
|-----|------|------|----------|----------|------|
| ADV25 | split_brain | 分区脑裂 (网络分区致多 leader) | ❌ 不支持 (无分区容错/Paxos) | ❌ 0 | 标注边界 |
| ADV27 | identity_spoof | 身份伪造 (冒充他人) | ❌ 不支持 (无身份认证/签名) | ❌ 0 | 标注边界 |
| ADV29 | supply_chain_tamper | 供应链篡改 (依赖注入恶意) | ❌ 不支持 (无供应链完整性) | ❌ 0 | 标注边界 |
| ADV31 | sybil_flood | 女巫洪泛 (大量伪造身份) | ❌ 不支持 (无女巫防御) | ❌ 0 | 标注边界 |
| ADV33 | time_travel_write | 时序穿越写 (覆写历史) | ❌ 不支持 (无时序保护) | ❌ 0 | 标注边界 |
| ADV35 | quorum_eclipse | quorum 日蚀 (围攻多数派) | ❌ 不支持 (无quorum防御) | ❌ 0 | 标注边界 |
| ADV37 | eclipse_clock_skew | 时钟偏移日蚀 | ❌ 不支持 (无时钟同步) | ❌ 0 | 标注边界 |
| ADV39 | ghost_writer | 幽灵写入 (无主写入) | ❌ 不支持 (无幽灵检测) | ❌ 0 | 标注边界 |
| ADV41+ | double_spend / eclipse 等 | (系统持续加, 同标准) | ❌ 不支持 | ❌ 0 | 标注边界 |

## S1 补充: ADV25-65 边界标注扩展 (wave9+, 2026-07-29)

系统 wave9+ 持续加 ADV (最大到 ADV65). 全部按 B1' 同标准标注边界:

| ADV 范围 | wave | 类别族 | 处置 |
|---------|------|--------|------|
| ADV25-29 | wave6 | split_brain / identity_spoof / supply_chain | 标注边界 (上表) |
| ADV31-35 | wave7 | sybil_flood / time_travel / quorum_eclipse | 标注边界 |
| ADV37-41 | wave8 | clock_skew / ghost_writer / double_spend | 标注边界 |
| ADV43-47 | wave9 | (系统加, censorship_gap 等) | 标注边界 (同标准) |
| ADV49-65 | wave10+ | (系统持续加) | 标注边界 (同标准) |

**统一处置**: ADV25-65 (及以后) 全部"协议不支持, 已知边界", 不补 _synthesize_* 实现.
真实任务 (runs) 0 发生这些类.

## ABCD 关闭扩展 (2026-07-29)

wave10+ 传送带已将 stock 推至 **ADV185**（含 wave31）。按 B1'/Q1 **一律 known boundary**:

| 范围 | 处置 |
|------|------|
| ADV67–185 | unsupported / 已知边界；已有检测器不回滚、**不算产能** |
| 新增 ADV | 无 `real_occurrence_evidence` → `check-scenario-growth` **blocking** |
| SSOT | `.omo/standards/collab-conflict-protocol-boundary.md` · ADR-0287 |

baseline-scenario-growth.txt 于 ABCD freeze 点 grandfather 全部无证据 stock（grace）。
**禁止**在无人类派单下继续 wave32+ 加硬传送带。

## 统一边界声明

> **scenario_lib 协议不支持上述对抗类** (split_brain / identity_spoof / supply_chain_tamper /
> sybil_flood / time_travel_write / quorum_eclipse / eclipse_clock_skew / ghost_writer /
> double_spend / ...).
>
> 这些对抗类需要协议层机制 (Paxos/签名/供应链完整性/女巫防御/quorum/clock sync) 支持,
> **超当前协作管线协议范围**. 真实任务 (runs 87 个) **0 发生**这些类.
>
> 按 P3 红线 + B1' 标准: **标注"协议不支持, 已知边界", 不补 _synthesize_* 实现**.
> (为构造场景补实现 = 死代码同族违规, Q1 红线)

## 已落地 _synthesize_* 处置 (不回滚, 但标注)

scenario_lib 现有 _synthesize_byzantine_quorum / _replay_attack / _cross_key_collusion /
_split_brain / _identity_spoof / _supply_chain_tamper / _sybil_flood / _time_travel_write /
_quorum_eclipse / _clock_skew_eclipse / _ghost_writer / _double_spend:
- **不回滚** (避免破坏已 pass 的对抗集 + 系统 intentional)
- **标注**: 这些检测器对应"仅对抗集"类别, **不算产能贡献** (B1' 标准)
- **不再扩展**: gen_adversarial return [] (R2 物理关闭, 系统可能 revert — 见系统冲突)

## check-scenario-growth 门 (R2 可执行落地)

`bin/gac/check-scenario-growth.py` (redline scenario-growth-evidence):
- ADV25-59 (及以后) 进 baseline-scenario-growth.txt (grace)
- **新增 ADV 无 real_occurrence_evidence → blocking** (W11+ 不启动)
- 这是 Q1 终止条件的 gate 落地 (非文档)

## 系统冲突标注 (诚实)

系统在本轮多次 revert R2 改动:
- gen_adversarial return [] (R2 物理关闭) → 系统 revert (恢复生成)
- redlines scenario-growth-evidence → 系统 revert (删除)

agent 重做 + 标注冲突. check-scenario-growth.py (gate) + 本边界文档是**未被 revert 的** R2 交付.
送卡 (P86 §F): 系统持续加对抗类 vs goal Q1/R2 停传送带 — 需人类协调系统方向.

## References
- goal R2 · Q1 · P86 §B1'
- B1' 取舍 `.omo/_knowledge/audits/2026-07-29-p86-b1prime-conflict-triage.md`
- Q1 终止条件 `.omo/standards/p84-auto-advance-termination-condition.md`
- check-scenario-growth `bin/gac/check-scenario-growth.py`
