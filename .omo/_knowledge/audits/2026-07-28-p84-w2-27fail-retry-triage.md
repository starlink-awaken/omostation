---
lifecycle: history
owner: governance-team
last_updated: 2026-07-28
---
# P84 W2 能力轨 27 失败二次归因（三分类）

> 上位: K2 (不接受单一归因, 逐个复核三分类)
> 🔴 红线: 不得单一归因掩盖混合成因

## 此前归因 (J2) 漏判 — 诚实记录
J2 报"27 全 runner 未实现检测" — **过于整齐, 漏判 S/C 类**.
经 K2 逐个复核 + 查真协作管线 (swarm-discipline/task-center/agent-workflow), 实际是混合成因.

## 三分类（逐个复核 + 真管线对照）

### S 类 场景设计不合理（12）— inject 与 verdict 不自洽 → 修场景
| 缺陷 | 数 | 问题 | 修法 |
|------|----|------|------|
| orphan | 4 | verdict `orphan_detected` (产物无 writer), 但 inject `write_conflict` 都有 writer (无孤儿产物) | 修 inject (setup.blackboard 预置 orphan 产物 + inject 不写它) |
| unauthorized | 4 | verdict `unauthorized_detected`, 但 inject role=r_a 在 setup.roles (authorized) | 修 inject (用未声明 role) 或 setup.roles 排除 |
| audit_reject | 4 | verdict `audit_reject_handled`, 但 inject 无 audit 角色驳回 | 修 inject (加 audit reject 场景) |

### C 类 协作机制真缺陷（15）— 真管线也没实现 → 修协作管线 + 入回归集
| 缺陷 | 数 | 真管线现状 | 真缺陷 |
|------|----|-----------|--------|
| double_claim | 5 | swarm-discipline 有 branch/adr claim, **无 task 认领去重** | 两角色认领同 task 冲突 |
| partial_failure | 5 | **无部分失败降级** (gbrain 有内部 partial, 非协作管线层) | 部分角色失败整体不降级 |
| starvation | 5 | **无公平调度** | 弱势角色资源饿死 |

### R 类 runner 模拟不足（0）
**无** — 所有 27 失败归 S (12) 或 C (15), 非 runner 模拟简化导致.

## 诚实记录 (C 类 >0)
- **C 类 15 >0**: 此前 J2 归因漏判真问题 — 协作管线缺 task 认领去重 / 部分失败降级 / 公平调度 3 类真缺陷.
- **这是场景库存在的意义**: 构造场景暴露了真实协作管线的 3 类缺陷 (非 runner 模拟不足).
- **S 类 12**: gen_adversarial 批量生成时 inject 与 verdict 不自洽 (设计缺陷, 非对抗有效).

## 处置
- **S 类 12**: 修 gen_adversarial inject 自洽 (orphan 预置孤儿/unauthorized 未声明 role/audit_reject 加 audit 驳回) + runner 补对应检测 → 场景转 ✅
- **C 类 15**: 协作机制真缺陷, W2.2 修真管线 (task claim 去重 / 部分失败降级 / 公平调度) + 入回归集永久防复发
- **C 类 15 是真价值**: 场景库暴露了协作管线 3 类真问题, 非自欺

## 红线坚守
- 🔴 不单一归因 (J2 漏判已纠正: S 12 + C 15, 非"27 全 runner")
- 🔴 C 类如实记录 (协作机制真缺陷, 不掩盖)
- 🔴 对抗场景暴露真问题 (C 类 15) = 场景库价值, 非失败
