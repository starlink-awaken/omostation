---
type: ephemeral
created: 2026-09-03
---

# 运行时治理深度分析 — 为何时间一久就失控 & 自进化框架

> 2026-08-22 · 依据本日全量运行时盘点证据链（crontab 手术 / #1918 / #1922 / 服务重扫）

## 一、失控根因（五条，全部有当日实证）

| # | 根因 | 本会话实证 |
|---|------|-----------|
| 1 | **死引用无巡检**：配置中路径/模块引用随重构腐烂，失败静默 | crontab 8 条指向已删 scripts/；compass_radar 硬编码 projects/c2g/src 断链数月 |
| 2 | **监控者无人监控**：GaC 查代码合规，无人查检查器本身活性 | debt-dashboard 停更 25 天、system_health 停摆 3 天、health.yaml 陈旧 5 天——均无告警 |
| 3 | **度量不咬合行动**：指标长期 ❌ 却无强制响应 | debt-closed-per-feature 连续多次 BELOW threshold；health 45 挂 5 天 |
| 4 | **熵源 > 熵汇，无日落条款**：机制新增快于退役 | 完成期的 OPC P5/P6/P7 调度残留；33 CI workflows / 136 GaC 规则只增不减 |
| 5 | **并发会话无共享态势**：多 agent 各持局部真相 | 主检出在多分支间被来回切换；交接靠人脑 |

## 二、自进化框架（四机制）

### M1 心跳契约
一切定时机制（cron/launchd/CI schedule/daemon）必须发 freshness 心跳；单一 meta-doctor 每日巡检全部心跳，**沉默即告警**。现有资产：signal-poller + repo-health-daily 已具雏形，缺的是覆盖面（不含 crontab 有效性、dashboard 龄、radar 可导入性）。

### M2 引用活性校验
配置中每个路径/模块引用入图；周期 walk；断链**自动经 ingress broker 转成债务项**——让断链进债治体系而非烂掉。本会话 10+ 处死引用若在位可全部提前捕获。

### M3 三级自动处置
T0 自动修复（投影重生成/服务重启）→ T1 自动开债（broker）→ T2 通知人。模板：quota-monitor 的分级告警 + omo ingress-debt。

### M4 日落条款
规则/workflow/cron 全带 `last_verified_at`；N 天未验证自动进复审队列；**完成期任务的调度随期退役**（OPC 即例证）。governance-checks.yaml 已有 lifecycle 字段，补 review_by 强制执行即可。

## 三、落地路线（拼装现有资产，不造新轮子）

1. M1+M2 合成一个 `bin/gac/meta-doctor.py`：复用现有 check 脚本清单 + 引用扫描，挂 operating-rhythm 日更 + CI governance-check 每 6h
2. M3 复用 `omo governance ingress-debt` broker + quota-monitor osascript 通知模式
3. M4 在 governance-checks.yaml 规则上强制 `review_by` 过期即 warn

北极星转变：**从"治理代码"升级为"治理治理本身"——维护机制成为一等交付物。**

## 四、同日配套动作（证据）

- crontab 手术：移除 8 条死心跳（备份 runtime/logs/crontab-backup-20260822.txt）
- opc-closeout-crontab 登记退役 → _archived-20260822
- compass_radar vendored 路径修复 #1918
- rule-vitality retention #1922（36k→10k 行）+ 首次收敛 6.8→1.9MB
- system_health 重扫 8/8 healthy（ollama 假阴性修复）
- health SSOT 真实刷新：28 分含 67 任务真审计（非空壳）

---
> 架构决策详见 ADR-0424 (.omo/_knowledge/decisions/0424-anti-corruption-pipeline-and-value-pacemaker.md)
