# 治本方案 — 治理状态平面写协议

> 2026-07-16
> 根因: .omo/ 有 4+ 个独立写入方, 无写权限分层, 无合并协议

---

## 一、根因诊断

```
所有问题的共同源头:

.omo/ 是 git 跟踪的目录 → 多个进程直接读写文件
  ├─ cron 健康扫描   → 写 system.yaml / system_health.yaml
  ├─ c2g.strategy sync → 写 system.yaml / health.yaml / BRIEF.md
  ├─ agent patch     → 写 system.yaml / health.yaml / 任意文件
  └─ cockpit sync    → 写 submodule 指针 + product 文件

没有 "谁可以写什么" 的协议
没有 "冲突了怎么办" 的规则
没有 "写错了能回滚" 的保障
```

### 症状 vs 根因

| 症状 | 表象 | 根因 |
|:-----|:-----|:-----|
| Debt 目录被删 | 外部 sync `rsync --delete` | 无目录写保护 |
| 4 个 health_score | 各写各的 | 无 SSOT 字段归属定义 |
| GaC 永不绿 | governance-semantic WARN 阻断 | 门禁无 HARD/SOFT 分级 |
| BRIEF.md 被覆盖 | generate-brief.py 直接覆盖 | 无写前 diff 保护 |
| Gateway 无 /health | 从未实现 | 技术债, 非治理问题 |

---

## 二、治本方案: 写协议

### 2.1 字段 SSOT 定义

在 `.omo/_truth/registry/write-owners.yaml` 中定义每个字段的唯一写入方：

```yaml
# 每个字段的 SSOT 写入方
fields:
  system.yaml:
    health_score:          # OWNER: c2g.strategy (顶部复合值)
    runtime_health_summary: # OWNER: cron 健康扫描
      health_score:         # 运行时在线率 (3/4 or 4/4)
    debt_adjusted_*:        # OWNER: omo debt system
    current_phase:          # OWNER: agent workflow
    phase4*_status:         # OWNER: agent workflow
    next_milestone:         # OWNER: strategy sync / agent

  health.yaml:
    health_score:           # OWNER: c2g.strategy (复合分 SSOT)
    immutable: true         # MARKER: 不允许外部覆盖

  .omo/debt/:
    items/*.yaml:           # OWNER: omo debt system
    禁止非 broker 写入      # RULE: pre-commit guard
```

**GaC #38 扩展**: 不仅仅是检测重复 key, 而是检测"非 OWNER 写入"。

### 2.2 门禁分级 (HARD / SOFT)

```yaml
gate_severity:
  hard: ["bos-tracking", "debt-integrity", "ssot-guardian"]  # 必过
  soft: ["governance-semantic", "state-freshness"]           # 提醒不阻断
```

- `hard` 失败 → GaC 门禁 FAIL (当前行为)
- `soft` 失败 → GaC 门禁 WARN (新行为, 不翻转 gate)

**当前**: governance-semantic WARN 导致门禁 FAIL → 人学会忽略门禁
**治本**: soft WARN 不翻转 gate, 只有 hard FAIL 才翻转

### 2.3 目录写保护: `.omo/debt/` pre-commit hook

```bash
# pre-commit 检查: 禁止删除 .omo/debt/items/
if git diff --cached --name-only | grep -q "^\.omo/debt/items/"; then
  echo "❌ 禁止直接操作 .omo/debt/items/ — 请使用 omo debt CLI"
  exit 1
fi
```

### 2.4 sync 进程改为走 OMO broker

当前:
```
c2g.strategy → write_file health.yaml    ← 直接写
c2g.strategy → write_file system.yaml    ← 直接写
```

治本:
```
c2g.strategy → omo state set health_score 100   ← 走 OMO CLI
c2g.strategy → omo state set phase next          ← 走 OMO CLI
```

OMO CLI 内部校验 write-owner, 并更新 GaC #38 检测的修改轨迹。

---

## 三、实施路径 (3 波)

### 第一波: 立规矩 (今天可做)

| # | 行动 | 文件 |
|:-:|:-----|:-----|
| 1 | 创建 `write-owners.yaml` | `.omo/_truth/registry/write-owners.yaml` |
| 2 | GaC #38 扩展: 按 write-owners 检测未授权写入 | `bin/gac/omo-state-write-guard.py` |
| 3 | `.omo/debt/` pre-commit 保护 | `.githooks/pre-commit` |
| 4 | 删除 system.yaml 多余的 health_score | `.omo/state/system.yaml` |
| 5 | BRIEF.md 写保护: generate-brief.py 加 `--protect` 模式 | `bin/mof/generate-brief.py` |

### 第二波: 修门禁 (本周)

| # | 行动 | 文件 |
|:-:|:-----|:-----|
| 6 | GaC gate_severity HARD/SOFT 分级 | `bin/gac/gac-local-gate.py` |
| 7 | governance-semantic 降级为 SOFT | `bin/gac/gac-local-gate.py` |
| 8 | .omo/state 统一写入接口 (OMO CLI) | `projects/omo/src/omo/cli.py` |

### 第三波: 补架构 (本月)

| # | 行动 | 价值 |
|:-:|:-----|:------|
| 9 | agora-gateway HTTP /health 端点 | 消除架构盲区 |
| 10 | sync 进程改为走 OMO broker | 根治覆盖问题 |

---

## 四、预期效果

```
当前:  4 个写入方, 0 个规则, 每轮修完被覆盖
第一波: 有规则, 有检测, 有保护
第二波: 门禁真正可用 (GREEN 是 GREEN, WARN 是 WARN)
第三波: 架构上不存在覆盖路径
```

**关键指标**: GaC 门禁从永远 FAIL 变为 GREEN (hard 检查全部 PASS, soft WARN 不阻断)。

---

## 五、风险

| 风险 | 缓解 |
|:-----|:------|
| write-owners 定义本身不被遵守 | GaC #38 自动检测违规 |
| pre-commit hook 被跳过 | GaC #38 在 gate 层二次检测 |
| OMO broker 尚未完善 | 第一波用 GaC 检测兜底, 不依赖 broker |
| external sync 进程无法修改 | 先在接收端加保护 (防火墙思维, 非 sender 思维) |
