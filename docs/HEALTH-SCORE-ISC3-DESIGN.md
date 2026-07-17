---
title: 收敛期 P1 · health_score ISC-3 重构设计
status: active
type: design-spec
owner: 夏明星
created: 2026-07-15
related:
  - .omo/_knowledge/decisions/0210-three-year-strategy-execution-convergence.md
  - .omo/state/health.yaml
  - docs/RUNTIME-DAEMON-REMEDIATION.md
  - docs/STRATEGY-M1-EVIDENCE.md
note: >
  health_score 口径重构设计。权威源 .omo/state/health.yaml（ISC-1 guarded，
  改动须走 OMO broker，不得直写 health_score）。本文是设计，非落地。
---

# 收敛期 P1 · health_score ISC-3 重构设计（2026-07-15）

> **核心判断**：P1「执行面权重↑」在 2026-07-14 的 ISC-2 里**权重已调对**，
> 但**喂进公式的分项仍被污染**——权重是对的，输入是脏的。ISC-3 的任务不是再动权重，
> 是**让三个分项各自诚实**。

## 一、现状：ISC-2 已调权重（好），但分项失真（问题）

| 分项 | 权重(ISC-2) | 当前值 | 贡献 | 诚实度 |
|------|-----------|--------|------|--------|
| governance | 0.3（ISC-1 的 0.5 已降）| 100 | 30.0 | ❌ 声明面：anomaly=0 → 100，对我实测的并发抢主仓/抢号**无感** |
| freshness | 0.2 | 80 | 16.0 | 🟡 尚可 |
| runtime | 0.5（ISC-1 的 0.3 已升）| 75 | 37.5 | ❌ 假红灯：0.75 来自 daemon 探测假阳性（见 RUNTIME-DAEMON-REMEDIATION）|
| **total** | | | **83** | |

**权重方向对了**（执行面 runtime 0.5 已是最大头），但：
- runtime 75 是**假红灯**——daemon 没死，探测误判 stdio 为故障。修 probe 后真值≈100。
- governance 100 是**声明面**——anomaly_count=0 就给满分，对本会话实测的并发冲突/ADR 抢号 0 惩罚。

> 讽刺：ISC-2 把 runtime 权重升到 0.5 想反映执行面，却因为 runtime 分项本身是假红灯，
> **放大了一个假信号**——把真实≈96 的系统压成 83。这正是"权重对、输入脏"的典型。

## 二、ISC-3 设计：保权重，清分项

### 原则：权重不动（ISC-2 的 0.3/0.2/0.5 保留），治三个输入

### 改 1 · runtime 分项去假阳性（依赖 P0 runtime 整改）
- runtime 子分改用**去假阳性后的** service_online_ratio（stdio 后端不计 dead、idle 计在线）。
- 预期：0.75(假) → ~1.0(真)，runtime 子分 75 → ~100，贡献 37.5 → ~50。
- **依赖**：`RUNTIME-DAEMON-REMEDIATION.md` 的 probe 修复先落地，否则 ISC-3 又放大假信号。

### 改 2 · governance 分项执行面化（本 P1 核心）
现状 governance=100 仅因 anomaly_count=0（GaC 规则过 = 声明面）。ISC-3 让它**掺入执行面实证**：

```
governance_isc3 = 100
  − 并发主仓冲突数 × Wc        # 来自 ADR-0218 证据 / worktree 抢占
  − ADR 抢号/重号事件数 × Wn   # 本会话 0214→0218 即 1 次
  − 孤儿 worktree 数 × Wo      # 卫生债
  （下限 0；GaC anomaly 仍保留为其中一维）
```

- 效果：governance 不再"anomaly=0 就满分"，会因真实并发事故**诚实下探**——
  本会话若计入（1 次抢号 + 若干孤儿），governance 会从 100 降到 ~85-90。

### 改 3 · service_online_ratio 单源（收口径分化）
- 现 system.yaml=0.6 vs health.yaml=0.75 分歧。ISC-3 定 health.yaml 为权威，
  system.yaml 改 AUTOGEN 回指（消除 SSOT drift）。

## 三、ISC-3 预期分数演变（诚实化的双向运动）

| 场景 | governance | freshness | runtime | total | 解读 |
|------|-----------|-----------|---------|-------|------|
| 现 ISC-2 | 30.0 | 16.0 | 37.5 | **83** | 假红(runtime)+假满(gov) 抵消，虚高又虚低 |
| ISC-3 仅修 runtime | 30.0 | 16.0 | ~50 | **~96** | runtime 去假阳性，真值浮现 |
| ISC-3 + gov 执行面化 | ~26 | 16.0 | ~50 | **~92** | gov 因并发事故诚实下探 |

> **关键**：ISC-3 后分数会**先升后微降**——升是 runtime 去假红灯（真的更健康），
> 微降是 governance 开始惩罚真实并发事故（诚实）。最终 ~92 是**可信的**，
> 因为它对执行面事故敏感，而 83 是两个假信号的巧合抵消。

## 四、落地步骤（授权 dev 环境，OMO broker，勿直写 health_score）

1. **先落 P0 runtime probe 修复**（前置），否则 ISC-3 放大假信号。
2. 改 governance 子分算法：接入并发冲突/抢号/孤儿三个执行面计数源。
3. service_online_ratio 单源化（health.yaml 权威 + system.yaml AUTOGEN 回指）。
4. 经 OMO broker 更新 health.yaml 公式注释（ISC-2 → ISC-3），保留 immutable guard。
5. 回归：`omo state sync` 重算，验证 total 与分项可追溯到执行面实证。

## 五、验收标准（P1 门禁，对齐 ADR-0210）

- health_score 三分项均可追溯到**执行面实测**（非 anomaly=0 / 假 ratio）。
- 制造一次真实并发冲突 → governance 子分**可下探**（证明对执行面敏感）。
- system.yaml 与 health.yaml 的 service_online_ratio 一致（口径单源）。

## 六、一句话

> P1 不是"再调权重"——ISC-2 已把 runtime 权重升到 0.5。真问题是**权重对、输入脏**：
> runtime 是假红灯、governance 是假满分，一升一降巧合抵成 83。ISC-3 让三分项各自诚实，
> 分数才第一次真正"反映实物"——先升到真值，再对并发事故敏感地波动。

---

*ISC-3 设计 · 2026-07-15 · 夏明星 · 权威源 .omo/state/health.yaml（勿直写 health_score）*
