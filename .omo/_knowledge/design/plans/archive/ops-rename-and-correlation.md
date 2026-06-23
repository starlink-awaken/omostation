---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R1: Phase 1-13 历史执行计划归档, 当前阶段/状态以 .omo/state/system.yaml + .omo/goals/current.yaml 为准"
---
# OPS 解耦与关联推理引擎方案

> 两件事: 1) hermes-ops → ops 完全解耦  2) Correlation Engine 架构设计

---

## 一、解耦范围

### 当前状态（四处都有 hermes 痕迹）

```
~/Workspace/hermes-ops/           ← 项目目录
~/.hermes/ops/                    ← 旧数据路径 (部分已移走)
~/.hermes/scripts/ops-*           ← 6 个脚本
~/.hermes/secrets/                ← Secret 中 ops 的条目
AGENTS.md → "hermes-ops"
Forge → "forge:hermes-ops"
Agora → "hermes-ops"
docs/宪法 → "hermes-ops"
KOS → ops event 路径含 "hermes-ops"
server.py → FastMCP("hermes-ops")
```

### 解耦后

```
~/Workspace/ops/                  ← 新项目目录
~/Workspace/ops/scripts/          ← 脚本移入
~/Workspace/ops/data/             ← 数据 (已有)
AGENTS.md → "ops"
Forge → "forge:ops"
Agora → "ops"
server.py → FastMCP("ops")
```

### 不解的部分

```
~/.hermes/secrets/          ← 保留 (Secret 是共享的, ops 只是其中的条目)
~/.hermes/scripts/          ← 保留其余非 ops 脚本
```

### 重命名执行计划

| 步骤 | 操作 | 影响范围 |
|:----:|------|---------|
| 1 | 创建 `~/Workspace/ops/` 从 `hermes-ops/` 复制 | 1 目录 |
| 2 | 更新 server.py: FastMCP("hermes-ops") → FastMCP("ops") | 1 文件 |
| 3 | 更新 config.yaml: server.name: "ops" | 1 文件 |
| 4 | 更新 AGENTS.md: hermes-ops → ops | 1 文件 |
| 5 | 移入 6 个脚本: ~/.hermes/scripts/ops-* → ~/Workspace/ops/scripts/ | 6 文件 |
| 6 | 更新 crontab 中 ops 相关路径 | 4 条目 |
| 7 | 更新 KOS pattern_learner MCP 路径 | 2 文件 |
| 8 | 更新 Forge 注册表: ops | 1 文件 |
| 9 | 创建 `hermes-ops` symlink → `ops` (兼容过渡) | 1 symlink |
| 10 | 更新架构宪法: hermes-ops 引用 → ops | 3 文档 |

**总工作量**: ~1h（纯运维，无新功能）

---

## 二、Correlation Engine 架构设计

### 问题

```
当前: 日志存了 / 事件记了 / 告警触发了 / 指标收集了
      但它们之间没有关联分析
      
      看到: "disk_percent: 92%" + "BACKUP_FAIL" + "SERVICE_DOWN"
      当前: 三条独立记录 → 人去看 → 人判断
      期望: 自动关联 → 自动诊断 → 自动升级 → 自动通知
```

### 设计

在 `~/Workspace/ops/src/ops/correlation.py` 中：

```
┌─────────────────────────────────────────┐
│             Correlation Engine          │
│                                         │
│  输入: events (最近 5 分钟)             │
│        health (最近 3 次)               │
│        metrics (最近 10 个采样点)       │
│        logs (最近 50 条)                │
│                                         │
│  规则引擎: 匹配已知模式 → 输出决策      │
│                                         │
│  规则 1: DISK_FULL                      │
│    匹配: disk_percent > 85 + BACKUP_FAIL│
│    输出: escalate incident SEV1         │
│          触发 ops_retention 自动清理    │
│                                           │
│  规则 2: AGENT_DOWN                    │
│    匹配: health fail × 3 consecutive   │
│    输出: escalate incident SEV2        │
│          推送 ops_alert + 桌面通知     │
│                                           │
│  规则 3: PATTERN_DRIFT                 │
│    匹配: metrics 偏离历史基线 > 2σ     │
│    输出: ops_anomaly 告警 → Info      │
│                                           │
│  输出: list[Action]                     │
│    Action = {                          │
│      type: "escalate" / "auto_fix" /  │
│            "notify" / "ignore",        │
│      target: "incident" / "retention" /│
│              "alert" / "-",            │
│      severity: "SEV0-3",               │
│      summary: "..."                    │
│    }                                   │
└─────────────────────────────────────────┘
```

### MCP 工具

| 工具 | 功能 |
|:----|------|
| `ops_correlate()` | 执行一次关联分析 → 输出决策列表 |
| `ops_correlate_start(interval:60)` | 启动持续关联分析 (后台线程, 默认 60 秒一次) |
| `ops_correlate_stop()` | 停止持续关联分析 |
| `ops_correlate_rules()` | 列出当前关联规则 |

### 谁处理、谁验证

```
关联引擎检测到异常
  ↓
ops_correlate 匹配到已知规则
  ↓
创建/升级 ops_incident (SEV1-3)
  ↓
ops_alert 推送 (桌面/TTS)
  ↓
人工通过 ops_incident_resolve() 验证关闭
  ↓
如果 3 次相同 incident 重复出现 → 自动升级 SEV0
  → 要求人工 root cause
```

---

## 三、执行顺序

```
Step 1: 解耦重命名 (~1h)
  → Workspace/ops/  |  server.py → "ops"  |  脚本移入  |  引用更新

Step 2: Correlation Engine (~2h)
  → correlation.py  |  4 条规则  |  3 MCP tools  |  incident 关联

Step 3: 集成测试 + 文档更新 (~30min)
  → test-12-correlation  |  AGENTS.md ops 更新  |  架构图 ops
```

要开始执行 Step 1（解耦重命名）吗？
