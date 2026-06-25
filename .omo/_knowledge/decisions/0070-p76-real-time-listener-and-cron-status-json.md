---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-23
---

# ADR-0070: P76 P0 listener 实时 API + governance-agent cron 完整安装

- **Status**: ACCEPTED
- **Date**: 2026-06-23
- **Authors**: omostation P76
- **Extends**: ADR-0069 (P75 management + alert-history 12 维 + graphify)
- **Superseded by**: (无)

## Context and Problem Statement

P75 收口后, P76 调研 4 项候选, 实施 2 项:

1. **P0 listener 实时 API** (替代 P74 轮询模式, --watch tail -f)
2. **governance-agent cron 完整安装** (--status-json 供 dashboard 消费)

跳过 2 项:
- management 物理迁移 (P76+ 留 P77+)
- 跨子仓联动 (P77+ 评估)

## Decision

### D1: p0-event-listener --watch 实时模式 (P76 R1)

**修改**: `bin/p0-event-listener.py` 加 `--watch` 选项

**实现**:
```python
# 类似 tail -f: 监控 omo-events.jsonl 文件 position + inode
last_pos = events_log.stat().st_size
last_inode = events_log.stat().st_ino
while True:
    cur_inode = events_log.stat().st_ino
    cur_pos = events_log.stat().st_size
    if cur_inode != last_inode:  # 文件被轮转
        last_inode = cur_inode
        last_pos = 0
    if cur_pos > last_pos:  # 新内容
        # 读新行, 处理 P0 事件
    time.sleep(0.5)
```

**vs P74 轮询**:
- P74: 60s 轮询 → 最坏 60s 延迟
- P76 --watch: 0.5s 检查 → 最坏 0.5s 延迟
- **优势**: 真实时, 文件轮转处理 (inode 检测)

**优势**:
- 实时 P0 检测 (亚秒级)
- 单文件 5 行代码, 轻量
- 不依赖 inotify (跨平台)

### D2: governance-agent cron --status-json (P76 R2)

**修改**: `scripts/omo/install-governance-agent-cron.sh` 加 `--status-json`

**输出** (JSON):
```json
{
    "installed": false,
    "cron_line": "",
    "wrapper": "/.../governance-agent.sh",
    "workspace_root": "/.../",
    "log_dir": "/.../.omo/_log",
    "run_count": 11,
    "command": "governance-agent.sh"
}
```

**实测**:
- installed=false (未安装 cron)
- run_count=11 (历史运行 11 次)

**vs 现有 --status**:
- --status: 人类可读 text
- --status-json: 机器可读 JSON, 供 dashboard/工具消费

## Consequences

### Positive

- **实时 P0 检测**: 0.5s 延迟, 文件轮转支持
- **结构化 cron 状态**: --status-json 供 dashboard 消费
- **轻量实现**: 单文件 5 行代码

### Negative

- **0.5s sleep 是 polling 退化**: 真正事件驱动需 inotify
- **--status-json 字段是简版**: run_count 是文件数, 不含时间戳

### Neutral

- **不增 linter 维度**: 沿用 P58 独立 bin 工具
- **不增 mof-drift 维度**: 8 维度持续

## Compliance

### 验证指标

| 指标 | P75 末 | **P76 末** | 变化 |
|------|-------:|-----------:|-----:|
| mof-version | v0.0.64 | **v0.0.65** | +1 |
| governance | 100 A+ | **100 A+** | 持平 |
| 独立 bin 治理工具 | 15 | **15** | 持平 |
| p0-event-listener 模式 | once / daemon | **+watch** | +1 |
| install-governance-agent-cron.sh 命令 | 4 | **5** (+--status-json) | +1 |
| ADR 数量 | 29 | **30** | +1 (0070) |

### 关联 ADR

- **ADR-0069**: P75 management + alert-history 12 维 (P76 直接扩展)
- **ADR-0068**: P74 事件驱动 (P76 --watch 强化)
- **ADR-0062**: P62 governance-agent cron (P76 完善)

### 关联 L0 规则

- `X2-FRESH-COMMIT-FATIGUE` — 实时 P0 检测避免告警风暴
- `CR-GOV-CLOSED-LOOP-01` — listener 写日志即 commit

## Notes

本 ADR 记录 P76 2 项候选实施:
- ✅ p0-event-listener --watch (实时 tail 模式)
- ✅ install-governance-agent-cron --status-json (JSON 输出)
- ⏸ management 物理迁移 (P77+)
- ⏸ 跨子仓联动 (P77+)

后续 P77+ 候选:
- management 物理迁移 (沿 P53 双指针)
- 跨子仓联动 (ecos/agora/cockpit)
- graphify 实际扫描 (需 OPENAI_API_KEY 配)
- dim-weight 真实数据调优 (需 30+ 快照)
- alert-history 自动洞察 (LSTM/ML)

---

*最后更新: 2026-06-23 · P76 · omostation 治理方法论持续深化*