# AAMF v4 迭代方案 — 治理体系补全

> **文档编号**: 32 | **前序**: #31 深度技术文档
> **定位**: 基于 v2 真实运行反馈的第三轮迭代
> **原则**: 补缺口不重建 · 低投入高产出 · 先修后优

---

## 一、现状 vs 目标

### v2 治理体系全景

```
宪法:    26 约束 (S1-S8, T1-T7, R1-R6, G1-G5)
节点:    27 注册 (含 bwg-vps)
脚本:    15 CLI
视图:    6 HTML 文件
架构熵:  0.0
运行:    ~2 天
```

### v3 缺口（来自 #31 分析）

| 缺口 | 严重度 | 说明 |
|------|--------|------|
| schema.py 不是权威源 | P1 | constraints.md 与 schema.py 双轨维护 |
| 无身份认证 | P2 | 单用户系统可接受，但起码记录操作者 |
| 跨机器拓扑缺位 | P0 | Mac mini 不感知 MBP 上的服务 |
| 状态机缺 ERROR 态 | P1 | 操作失败不可查 |
| 视图无联动 | P2 | 6 个 HTML 文件无导航 |
| 治理指标无校准 | P3 | 阈值为主观值 |
| SHA256 链截断 | P3 | 16 字符抗不住暴力碰 |

### 优先级

```
P0: 跨机器拓扑      ← 功能缺失，影响漂移检测覆盖
P1: schema 权威源    ← 架构债，长期不同步风险
P1: ERROR 状态       ← 运维盲区
P2: 视图联动         ← 体验优化
P2: 身份记录         ← 审计追溯
P3: SHA256 轮换      ← 安全加固
P3: 指标校准         ← 理论完善
```

---

## 二、方案设计

### I. 跨机器拓扑（X2 剩余 40%）

#### 设计

**不引入分布式系统。** 用 SSH + 本地探针的轻量方案。

```
Mac mini (服务器)
    │
    ├── local: drift-check / sniff-deps / watchdog
    │
    └── SSH → MBP M5 Max (开发机)
              ├── SSH: lsof -iTCP → 端口监听
              ├── SSH: health_check 端点探测
              └── SSH: 心跳检测
```

#### 实现

**新文件**: `~/.hermes/conf/hosts.json`

```json
{
  "hosts": [
    {
      "id": "mbp-m5",
      "name": "MBP M5 Max",
      "host": "192.168.x.x",
      "ssh_user": "xiamingxing",
      "ssh_port": 22,
      "ssh_key": "~/.ssh/id_rsa",
      "services": ["agent-runtime", "hermes-agent"]
    }
  ]
}
```

**扩展 `arcnode-drift-check`**: 新增 `--remote` 标志

```
arcnode-drift-check --remote
  ├── 对每个远程主机:
  │   ├── SSH: hostname + uptime (心跳)
  │   ├── SSH: lsof -iTCP -sTCP:LISTEN (端口)
  │   └── SSH: curl health_check (若可达)
  └── 输出:
      ├── 远程节点 drift 报告
      └── governance log observation (如有漂移)
```

**改动范围**: 1 个脚本 (~100 行追加) | 1 个 JSON 配置

#### 约束

| 约束 | 新规 | 校验 |
|------|------|------|
| R7 | 远程节点可被漂移检测 | drift-check --remote |
| R8 | SSH 连接失败时标记为 unknown，不阻塞 | drift-check --remote |

### II. schema.py 作为权威源（P1）

#### 设计

**当前**: constraints.md 手动编辑 → arcnode-sync-constitution 推 schema 变更到文档
**目标**: schema.py 是唯一权威源 → constraints.md 从代码生成

#### 实现

**改造 `arcnode-sync-constitution`**: 全面重写为生成器模式

```python
# 旧: 检测差异 → 追加缺失块
# 新: 读取 schema.py → 生成完整 constraints.md
```

生成逻辑：

```
schema.py
  ├── MetaType enum          → 第一章: 类型定义
  ├── TYPE_CONSTRAINTS        → 第二章: 类型约束 (T1-T7)
  ├── FORBIDDEN_RELATIONS     → 第三章: 禁止关系
  ├── detect_dep_cycle()      → 第四章: 运行时约束 (R2-R6)
  └── ...                     → 第五章: 治理约束 (G1-G5)
```

**Cron 变更**: `arcnode-sync-constitution` 从每日 6:20 改为随 evolve 运行

**改动范围**: 1 个脚本（重写 ~200 行）| 移除 constraints.md 手动编辑流程

### III. ERROR 状态（P1）

#### 设计

状态机增加 ERROR 态。操作失败不隐式回滚，而是记录 ERROR。

```
ACTIVE ──→ DRAINING ──→ STANDBY ──→ VERIFYING ──→ ACTIVE (new)
  │           │            │            │              │
  │           │            │            └──→ ERROR     │
  │           │            └──→ ERROR                  │
  │           └──→ ERROR                               │
  └──→ DECOMMISSIONED ←────────────────────────────────┘
                       ↑
                  ERROR ─┘

ERROR: 节点操作失败，当前状态未知
  → 治理日志记录 action=hotswap, status=error
  → arcnode report 可见 ERROR 节点
  → 人工确认后手动进入 ACTIVE 或 DECOMMISSIONED
```

#### 实现

**扩展 `agora-hotswap`**: 所有失败路径写 status=error 而非仅 log

```bash
agora hotswap agent-runtime --new-yaml v2
  ├── Step 3 drain 超时    → 回滚 + error
  ├── Step 4 bootstrap 失败 → error
  ├── Step 5 verify 失败    → error (已有)
  └── 成功                → decommissioned
```

**扩展 `arcnode-report`**: 新增 `--errors` 标志

```bash
arcnode report --errors
  → 近 7 天操作失败的节点列表
  → 含失败原因 + 时间戳
```

**改动范围**: 2 个脚本 (~50 行追加)

### IV. 视图联动（P2）

#### 设计

当前 6 个 HTML 文件无导航。联动后：
- dashboard.html → 节点可点击 → 跳转到 C4 Container 对应节点
- C4 Container → 每个节点链接到 C4 Component
- C4 Component → 每个节点链接到 C4 Code
- archimate.html → Application 层 CLI 链接到各自输出

#### 实现

**修改 `dashboard.html` (在 evolve 中)**: 节点名加 a 标签

```javascript
// 当前: y: nodeIds → 纯文本
// 新: y: nodeIds.map(id => `<a href="c4_container.html">${id}</a>`)
```

**修改 `gen_c4_container` (在 arcnode-graph 中)**: 每个节点名超链接

```python
nid -> f'<a href="c4_component.html" onclick="scrollTo(\'{nid}\')">{nid}</a>'
```

**改动范围**: 2 个生成函数 (~30 行追加)

### V. 身份记录（P2）

#### 设计

**不引入登录系统。** 使用 `$USER` 环境变量记录操作者。

```python
# log_governance 追加:
import os
entry["operator"] = os.environ.get("USER", "unknown")
```

当前 AAMF 的所有操作都由 Hermes（老王）执行。`$USER` = `xiamingxing`。如果未来有多用户场景（如 Agent Runtime 自动注册），operator 字段可以区分人和 Agent。

**改动范围**: 1 个函数 (~3 行) | schema.py 的 log_governance

### VI. SHA256 轮换（P3）

#### 设计

保持轻量，加一个季度签名脚本。

```bash
# 每季度执行
arcnode-sign-governance-log
  ├── 用 gpg 对 governance.jsonl 签名
  └── 输出 governance.jsonl.sig
```

不改现有 SHA256 链（完整保留），加一层外部签名。

**改动范围**: 1 个新脚本 (~30 行) | cron 每季度一次

### VII. 指标校准（P3）

#### 设计

基于实际运行数据校准阈值。运行 90 天后回顾：

- 实际 observation 平均多少天 resolve？
- 实际 drift rate 基线是多少？
- 实际约束违反率基线是多少？

**当前不行动**。留一个文档记录，等数据积累。

---

## 三、实施 Roadmap

### Phase 布局

```
Phase 8: 跨机器拓扑 + ERROR 态     [P0+P1, ~2h]
Phase 9: schema 权威源 + 身份记录   [P1+P2, ~1h]
Phase 10: 视图联动 + SHA256轮换    [P2+P3, ~1h]
Phase 11: 指标校准文档              [P3, ~0.5h]
```

### Phase 8 详细

| ID | 任务 | 工时 | 产出 |
|----|------|------|------|
| 8.1 | 创建 `hosts.json` 配置 | 10m | `~/.hermes/conf/hosts.json` |
| 8.2 | 扩展 drift-check (--remote) | 40m | SSH 远程节点探测 |
| 8.3 | 扩充 ARCH_NODE.yaml（远程节点） | 10m | MBP 上的服务注册 |
| 8.4 | 状态机 ERROR 态 | 20m | hotswap/report 改造 |
| 8.5 | R7-R8 追加 | 10m | constraints.md 同步 |

### Phase 9 详细

| ID | 任务 | 工时 | 产出 |
|----|------|------|------|
| 9.1 | 重写 sync-constitution 为生成器 | 30m | constraints.md 自动生成 |
| 9.2 | operator 字段注入 | 5m | 治理日志可追溯操作者 |

### Phase 10 详细

| ID | 任务 | 工时 | 产出 |
|----|------|------|------|
| 10.1 | dashboard ↔ C4 联动 | 20m | 节点可点击跳转 |
| 10.2 | SHA256 季度签名脚本 | 20m | `arcnode-sign-log` |

### Phase 11 详细

| ID | 任务 | 工时 | 产出 |
|----|------|------|------|
| 11.1 | 指标校准预留文档 | 30m | `33-治理指标校准.md`（90天后执行） |

---

## 四、验收标准

### Phase 8

```bash
# 跨机器探测
arcnode-drift-check --remote
→ MBPM5: online, 2 services, 0 drift
→ agent-runtime (remote): health_check ✅

# ERROR 态
arcnode report --errors
→ 0 ERROR nodes in last 7 days
```

### Phase 9

```bash
# schema 生成宪法
arcnode-sync-constitution --generate
→ constraints.md regenerated from schema.py (26 constraints)

# 身份追溯
cat governance.jsonl | grep operator
→ "operator": "xiamingxing" (每条记录都有)
```

### Phase 10

```bash
# 视图联动
open dashboard.html
→ 点击节点名 → 跳转到 C4 Container
→ 点击 C4 节点 → 跳转到 Component

# 签名
arcnode-sign-log
→ governance.jsonl.sig (GPG 签名)
```

---

## 五、不做的事

```
❌ 多人协作身份系统    — 单用户环境，过度设计
❌ 实时分布式拓扑      — SSH 探针足够
❌ 完整 GPG 密钥体系   — 季度签名够用
❌ 治理指标自动化校准  — 等 90 天数据
❌ 性能优化            — 当前 4,800 LOC 可控
```

---

> **文档位置**: `~/Documents/学习进化/基建架构/32-AAMF-v4-迭代方案.md`
> **前序**: #31 AAMF 深度技术文档
> **当前**: 方案待确认 → 确认后从 Phase 8 开始
