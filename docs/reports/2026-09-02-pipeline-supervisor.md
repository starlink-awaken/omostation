---
schema_version: report/v1
lifecycle: history
type: delivery-report
owner: governance-team
created: 2026-09-02
last_updated: 2026-09-02
bet: BET-Y1Q4-T2-05
---

# 数字大脑管线 supervisor 常驻化（交付报告）

## 交付概览

| 项 | 结果 |
|----|------|
| supervisor 本体 | `pipeline_supervisor.py` — 纯编排层，单站 subprocess + 降级续跑 |
| 定时通道 | `--tick-morning` 四站全链（launchd 07:30）：radar 12s→bus→embed→render |
| 文件监听 | `--watch` ~/Inbox/ocr-inbound/ + `--process-file` 手动 |
| 嵌入站 | **Mac mini 远程节点优先**（T3-02 P3 首战实战），本地 omlxc 降级链 |
| resident 注册 | routes PipelineTick/PipelineInbound（execute 角色）|
| 告警闭环 | convergence-pulse 第四源 pipeline_supervisor |
| verify | `make resident-status` → **exit 0, health: recovered** ✅ |

## 首跑实测（2026-09-02）

**定时通道**（四站全绿零降级，25.3s）：
```
radar:  ok 11954ms (真实网络采集+打标)
bus:    ok 1ms     (15 items → 事件流 ledger)
embed:  ok 5819ms  (backend=mac-mini-node ← 远程节点实战)
render: ok 7473ms  (brief md → GB/T DOCX)
```

**入站通道**（真实扫描件 redheader-seal.png）：OCR 4.0s → 嵌入 4.0s →
卡片落盘 → `cockpit im-triage` 面板可视（"ocr-inbound/扫描件" 高优卡片）。

**降级语义**（坏文件注入）：degraded=[embed, card] 续跑不崩 + state alerts 记录
→ pulse health 当场捕获（"管线 supervisor 降级: inbound_degraded"）。

## 守护化部署（三 launchd）

| Label | 作用 |
|-------|------|
| com.omostation.pipeline-morning | 日历 07:30 定时全链 |
| com.omostation.embed-node (Mac mini) | KeepAlive 嵌入服务自愈 |
| com.omostation.resident-daemon | KeepAlive resident 常驻 |
| com.omostation.tailscale-heartbeat | 600s 心跳（阶段 0）|

## 关键工程决策

1. **embed 远程优先本地兜底**：Mac mini 节点（维度 512）为默认后端，中继抖动
   （5s timeout）时降级本地 omlxc——可用性优先，来源标注进向量记录。
2. **_run 输出契约**：uv 包装 CLI 的 stdout 可能混 build 日志或被截断——
   JSON 场景全量捕获 + `find("{")` 前导剥离（首跑实测教训）。
3. **状态滚动窗口**：morning_runs[-30] / alerts[-50]——state 文件不膨胀。

## 真实闸门（done_when 长期项）

- 连续 3 天自动晨报：morning_runs 逐日记录（launchd 已挂，观察期开始）
- 真实扫描件全链 ✅（本报告首跑已验）
