# LifeOS 用户运营手册

> 每天 5 分钟, 掌握系统全局.

---

## 一、日常操作 (每天)

### 1. 查看系统状态 (30 秒)

```bash
python3 bin/gac/lifeos-status.py
```

输出示例:
```
==================================================
  LifeOS 系统状态
==================================================
  时间: 2026-08-24 15:30

  UHS 健康度: 96.0/100 (Grade: A)
    tools       : ███████████████████░ 90.5%
    governance  : ████████████████████ 97.8%
    scenes      : ████████████████████ 90.0%
    docs        : ████████████████████ 98.0%
    value       : ████████████████████ 100.0%
    runtime     : ████████████████████ 100.0%

  活跃场景: 10/10
    ✓ agora-bos-gateway
    ✓ document-review
    ✓ engineering-delivery
    ✓ knowledge-ingest
    ✓ meeting-supervision
    ✓ periodic-reporting
    ✓ project-supervision
    ✓ research-pipeline
    ✓ unified-inbox

  价值度量: 3/12 qualifying episodes

  告警: 无 ✓

  最近事件:
    → WorkflowClosed: completed
    → StepFailed: failed
```

### 2. 持续监控模式

```bash
python3 bin/gac/lifeos-status.py --watch
```

每 30 秒自动刷新, 类似 `top` 命令.

### 3. JSON 输出 (供脚本消费)

```bash
python3 bin/gac/lifeos-status.py --json
```

---

## 二、场景操作

### 查看所有场景状态

```bash
python3 bin/ssot/scene-activation-sweeper.py
```

### 手动激活场景

编辑 `docs/scene-cards/<scene>.yaml`:
```yaml
lifecycle: assisted  # shadow → assisted
approval_state: confirmed  # pending → confirmed
```

### 场景观察报告

```bash
python3 bin/ssot/shadow-reporter.py --all
```

---

## 三、价值度量 (4 周达标路径)

### 记录时间节省 (每次 workflow 后)

```bash
python3 bin/ssot/value-recorder.py --review 120 --saved 300 --verdict accept
```

参数:
- `--review`: 你审核输出花了多少秒
- `--saved`: 系统帮你节省了多少秒
- `--verdict`: accept / edit / reject

### 查看进度

```bash
python3 bin/ssot/value-recorder.py --status
```

### 目标

- **12 个 qualifying episodes** = value 维度达标
- 每周 3 个 × 4 周 = 12 个
- 条件: 节省时间 > 审核时间 且 verdict = accept/edit

---

## 四、治理操作

### 检查系统健康

```bash
make gac-local-gate
```

### 查看 UHS 趋势

```bash
python3 bin/gac/unified-health-score.py
python3 bin/gac/unified-health-score.py --trend  # 30 天趋势
```

### 运行自修复

```bash
python3 bin/gac/remediation-engine.py --execute  # 自动修复
python3 bin/bin/gac/remediation-engine.py --dry-run  # 预览
```

---

## 五、运维自动化 (已配置 cron)

| 任务 | 频率 | 命令 |
|------|------|------|
| 信号轮询 | 每 2 分钟 | signal-poller.py --once |
| 文档保鲜 | 每 30 分钟 | remediation-engine.py --execute |
| 防腐检查 | 每小时 | anti-corrosion-check.py |
| UHS 评分 | 每天 | unified-health-score.py |
| North Star 周报 | 每周一 | north-star-weekly.py |

查看所有 cron:
```bash
bash bin/ssot/install-maturity-cron.sh --status
```

---

## 六、告警响应

### 告警类型

| 级别 | 含义 | 行动 |
|------|------|------|
| P0 | 约束/M1 违反 | 立即修复 |
| P1 | 推理引擎异常/覆盖率下降 | 当天处理 |
| P2 | 场景激活率/文档过期 | 计划处理 |

### 排查流程

1. `python3 bin/gac/lifeos-status.py` — 看全局
2. `python3 bin/gac/alert-check.py` — 看具体告警
3. 运行对应 runbook — 修复问题

---

## 七、快速命令参考

| 场景 | 命令 |
|------|------|
| 看全局状态 | `python3 bin/gac/lifeos-status.py` |
| 看 UHS | `python3 bin/gac/unified-health-score.py` |
| 看场景 | `python3 bin/ssot/scene-activation-sweeper.py` |
| 看价值进度 | `python3 bin/ssot/value-recorder.py --status` |
| 看告警 | `python3 bin/gac/alert-check.py` |
| 修复问题 | `python3 bin/gac/remediation-engine.py --execute` |
| 运行测试 | `cd projects/omo && python3 tests/test_age_v2.py` |
| 查看 CI | `gh pr checks <PR_NUMBER>` |

---

## 八、常见问题

**Q: UHS 分数下降了怎么办?**
A: 运行 `python3 bin/gac/unified-health-score.py --trend` 看趋势, 定位哪个维度下降, 然后针对性修复.

**Q: 价值度量不达标怎么办?**
A: 每次 Agent Workflow 结束后, 花 5 秒运行 `value-recorder.py` 记录时间节省. 4 周后自然达标.

**Q: 场景卡在 shadow 怎么办?**
A: 运行 `shadow-reporter.py --all` 查看原因, 通常是缺少 approval 或样本数据.

**Q: 如何停止所有自动化?**
A: `bash bin/ssot/install-maturity-cron.sh --remove`
