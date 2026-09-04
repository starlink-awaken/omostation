---
lifecycle: stable
owner: governance-team
last_updated: 2026-08-24
title: 场景卡激活剧本 v1 — 主人侧操作手册
type: doc
---

# 场景卡激活剧本 v1 — 主人侧操作手册

> **定位**: 项目战略 v1 §1 / §6 的落地操作手册 — 让主人 5 分钟走完一次场景卡 mini-trial
> **回答的问题**: "我应该怎么用场景卡? 升级门是什么? 我手勾 useful 之后会发生什么?"
> **关联**: docs/architecture/project-strategy-v1.md §1, §3, §6

---

## 0. 一句话总结

场景卡是 **"主人 + 自治 agent 协同做一件具体事"** 的契约. 当前 9 张卡全部停在 `shadow` 阶段 (0 samples). 本文给出 **mini-shadow 模式**: 主人手勾 3 次"有用"即可升级到 `assisted`, 替代原 30-sample 校准门.

---

## 1. 5 分钟走完一次

```
1. 收到场景卡触发 (signal_router / 决策收件箱)
   ↓
2. agent 跑一遍 (3-10 分钟, 主人不必等)
   ↓
3. 主人看输出结果, 一句话勾选:
   python3 bin/gac/scene-card-mini-shadow.py --record <scene_id> --outcome useful
                                                   └─ 或 --outcome not_useful
   ↓
4. 当某张卡的 useful 累计 ≥ 3, 工具会自动产出:
   "promotion_recommendation: mini-shadow 模式: ... 建议升级到 assisted."
   ↓
5. 主人人工 review 输出, 决定是否正式激活
```

**单次操作耗时**: 10-30 秒 (与跑批时间无关)

---

## 2. 升级门 (Gates) 详解

### 2.1 mini-shadow 模式 (本剧本默认)

| 字段 | 值 |
|------|-----|
| 触发门 | useful_count ≥ 3 |
| 反向门 | not_useful_count > useful_count (auto-revert) |
| 校准要求 | **无** (替代原 30-sample 校准) |
| 适用范围 | 当前所有 9 张 shadow 场景卡 |

### 2.2 标准模式 (兼容性保留)

| 字段 | 值 |
|------|-----|
| 触发门 | min_samples: 30 + min_calibration: 0.6 + rollback_evidence: required |
| 适用条件 | 升级到 `assisted` 之后, 需向 `supervised` 跃迁时 |

### 2.3 跃迁矩阵

```
shadow ──(mini-trial 3 useful)──→ assisted ──(30 samples + 0.6 cal)──→ supervised
   ↑                                  ↓                                    ↓
   └──── (rollback if not_useful > useful) ────────────────────  routine (autonomous)
```

---

## 3. 主人 30 秒操作清单

```bash
# 1. 查看所有 shadow 卡的 mini-trial 状态
python3 bin/gac/scene-card-mini-shadow.py --list

# 2. 列出已达成升级门槛的卡
python3 bin/gac/scene-card-mini-shadow.py --eligible

# 3. 勾选某次跑批的输出
python3 bin/gac/scene-card-mini-shadow.py --record <scene_id> --outcome useful
# 或:
python3 bin/gac/scene-card-mini-shadow.py --record <scene_id> --outcome not_useful

# 4. 退出
# (工具自动判定: 3 useful → 输出 promotion_recommendation)
```

---

## 4. 9 张场景卡当前状态 (2026-08-24)

| scene_id | 当前 samples | mini-trial useful | 距升级 |
|----------|---------------|-------------------|--------|
| document-review | 0 | 0/3 | 3 |
| engineering-delivery-dogfood | 0 | 0/3 | 3 |
| knowledge-curation | 0 | 0/3 | 3 |
| meeting-supervision | 0 | 0/3 | 3 |
| periodic-reporting | 0 | 0/3 | 3 |
| project-supervision | 0 | 0/3 | 3 |
| research-pipeline | 0 | 0/3 | 3 |
| unified-inbox | 0 | 0/3 | 3 |
| agora-bos-gateway | 0 | 0/3 | 3 |

**总目标**: 12 个月内全部 9 张达 `assisted`, 3 张达 `autonomous` (即 routine).

---

## 5. 反模式 (识别即停)

- **S1 仪式疲劳**: 一周做 30-sample 校准, 主人放弃
  - **应对**: mini-shadow 3-sample 即可
- **S2 草率勾选 useful**: 主人不认真看, 走形式
  - **应对**: 工具记录 timestamp + 来源 (未来加 signal_router 追溯)
- **S3 单一场景卡独占**: 主人 80% 时间在 unified-inbox, 其他卡饿死
  - **应对**: weekly-review 卡片轮询所有 9 张

---

## 6. 与 weekly-review 的集成 (未来)

周一 weekly-review 卡片默认包含:

```
=== 场景卡 mini-trial 摘要 (2026-W34) ===
[document-review] 1/3 useful  (上次: 2026-08-21)
[unified-inbox]   0/3 useful
...

⚠ 距升级最近的 3 张:
  - document-review (1/3)
  - unified-inbox (0/3, 但 owner-attest 已 5 次)
  ...
```

---

## 7. 关联工具与文档

| 工具 / 文档 | 用途 |
|-------------|------|
| `bin/gac/scene-card-mini-shadow.py` | 主工具 (本剧本配套) |
| `bin/ssot/scene-card-lifecycle.py` | lifecycle 状态机 (assisted/routine 等) |
| `bin/ssot/scene-outcome-recorder.py` | outcome 记录 (与本文工具互补) |
| `bin/ssot/internal-scene-preflight.py` | 升级前的 preflight 校验 |
| `bin/ssot/scene-card-review.py` | 校准 / 30-sample 路径 (标准模式) |
| `bin/ssot/scene-feedback-collector.py` | 主人反馈的自动采集 (未来) |
| `bin/ssot/weekly-review.py` | 周仪式投递 |
| `bin/gac/strategy-check.py` | 9 维战略矩阵 (场景卡维度 = 维度 1) |

---

## 8. 30 天验证路径

| 周次 | 行动 | 验证 |
|------|------|------|
| W+1 | 主人手勾 1 张卡 1 次 useful | 工具日志记录 |
| W+2 | 累计 2 张卡, 3-5 次 useful | --list 看到 useful_count > 0 |
| W+3 | 至少 1 张卡触发 promotion_recommendation | --eligible 非空 |
| W+4 | 主人人工 review 该卡, 决定升级 | lifecycle 字段改 assisted |

---

## 9. 失败模式与回退

| 失败 | 触发 | 应对 |
|------|------|------|
| not_useful 累积 | not_useful_count > useful_count | 自动回退 (工具判断 + 主人确认) |
| 卡 30 天无样本 | shadow_age_days > 30 | weekly-review 红色提示 |
| 升级后失败 | assisted 30 天内 0 跑批 | 降级 shadow |
