# OMO Playbook 38: 联邦Authority Re-Baseline、Ownership Recomposition与New Default Contract

> 状态: draft · 关联: Playbook 36 (永久降级/退出) · Playbook 37 (拆分/边界重置)
> 范围: 仅治理基线重置层。不覆盖 19 发布所有权、26 持续联邦权威协调。

---

## 一、触发门禁 (Activation Gate)

### 1.1 前置条件
- PB36 已完成（降级/退出最终化）或 PB37 已完成（拆分/边界重置生效）
- 联邦拓扑变更已广播至所有残留节点
- 旧默认合约已标记 `deprecated`

### 1.2 准入门禁清单
- [ ] 旧联邦退出节点已完全摘除（路由表无残留）
- [ ] 新子联邦边界已确认（无歧义归属节点）
- [ ] 共享资源清单已拉取（秘钥、路由表、数据面、合约）

### 1.3 不可跳过条件
- 旧 Primary Owner 仍在线但不属当前联邦 → 先隔离摘除，再进入本 PB
- 拆分后存在争议资源（两方均声称所有权）→ 升级至 PB26 协调，暂不执行本 PB

---

## 二、Authority Re-Baseline（权威重基线）

### 2.1 权威盘点
- 列出当前联邦所有节点的 authority claim
- 三种权威类型：
  - **Primary Authority** — 域内唯一决策权
  - **Delegated Authority** — 限定域内的委托决策权
  - **Observer Authority** — 只读+心跳

### 2.2 权威重分配三原则
1. 每个决策域有且仅有一个 Primary Authority
2. 拆分后子联邦自动获得其域内资源的 Primary Authority
3. 原共享资源归属判定：
   - 仅服务单一子联邦 → 归该子联邦
   - 多子联邦共享 → 归入 Shared Surface，各方持 Delegated Authority
   - 无法判定 → 暂挂 Neutral Zone，30 天内 PB26 协调

### 2.3 权威基线固化
- 生成 `authority-baseline.yaml`
- 所有节点数字签名确认
- 旧基线归档至 `_deprecated/`

### 2.4 冲突熔断
- 节点拒绝签署 → 进入 Quarantine（保留心跳、暂停 Delegated Authority）
- 7 天未解决 → 触发 PB36 退出流程

---

## 三、Ownership Recomposition（所有权重组）

### 3.1 所有权清单重建（按资源类型）
| 类型 | 内容 |
|------|------|
| 路由资源 | Route Table Entries, URI Prefixes |
| 秘钥资源 | Node Keys, Shared Secrets, API Tokens |
| 数据资源 | Shared DBs, Cache Partitions, Log Streams |
| 合约资源 | Default Contracts, SLA Definitions, Policy Rules |

### 3.2 所有权转移协议
- **协商转移**: 原 Owner 声明放弃 → 新 Owner 声明接掌 → 双签 → 广播事件
- **强制转移**（原 Owner 已退出/不可达）:
  - 新 Primary Owner 可单方声明所有权
  - 需附 PB36 Exit Finalization 证据
  - 72h 静默期，无异议即生效

### 3.3 孤儿资源处置
| 类别 | 处置方式 |
|------|---------|
| 秘钥类 | 立即轮换（安全基线） |
| 数据类 | 归档冷存储，保留 90 天 |
| 路由类 | 摘除，释放 URI 空间 |
| 合约类 | 随新 Default Contract 重建 |

### 3.4 所有权图谱
- 更新 `ownership-graph.yaml`
- 每个资源唯一 Owner；共享资源标注 Shared Surface + 所有 Delegated Owner

---

## 四、New Default Contract（新默认合约）

### 4.1 合约重建四项
1. **默认路由规则** — 未匹配显式路由的请求发往哪个节点
2. **默认鉴权策略** — 新节点加入的最低鉴权要求
3. **默认心跳参数** — 间隔、离线阈值、重连策略
4. **默认降级策略** — 节点故障时的自动降级路径

### 4.2 新 Primary Owner 确立
选择标准（优先级排序）：
1. 稳定性 — 最近 30 天在线率 ≥ 99.5%
2. 连通性 — 与 ≥ 80% 联邦节点直接可达
3. 容量 — 资源余量满足峰值负载 × 1.5
4. 确定性 fallback — 节点 ID 字典序（无明确优势时）

需同时指定 ≥ 1 个 Backup Primary。

### 4.3 新默认路由
```
default → new_primary_owner → backup_primary → broadcast(all_nodes)
```
路由表版本号递增，旧版本标记 `superseded`。

### 4.4 合约签署与生效
- 草案公示 → 24h 审阅窗口 → 节点签署（数字签名）
- Quorum ≥ 2/3 活跃节点 → 合约生效
- 未签署节点 → 7 天宽限期 → 仍未签署则触发 PB36 退出

---

## 五、验证闭环 (Verification & Closure)

### 5.1 功能验证
- 新 Primary Owner 可达性：所有节点心跳确认响应
- 默认路由验证：test probe → 确认正确到达新 Primary
- 所有权验证：抽查关键资源 owner 字段

### 5.2 一致性验证
- 所有节点 `authority-baseline.yaml` hash 一致
- 所有节点 `ownership-graph.yaml` hash 一致
- 所有节点 `default-contract.yaml` hash 一致

### 5.3 回滚条件
- 验证失败率 ≥ 20% 节点 → 自动回滚旧基线
- 回滚后进入诊断模式（PB26），暂不重试本 PB

### 5.4 闭环输出物
- `authority-baseline.yaml` — 新权威基线
- `ownership-graph.yaml` — 新所有权图谱
- `default-contract.yaml` — 新默认合约
- `reset-wave-38-evidence.json` — 执行证据链
- PB 状态 → `completed`，释放 Quarantine 节点

---

## 六、与其他 Playbook 的接口

| 接口 | 方向 | 说明 |
|------|------|------|
| PB36 → 38 | 输入 | 退出节点清单、Exit Finalization 证据 |
| PB37 → 38 | 输入 | 新子联邦边界定义、节点归属表 |
| 38 → PB26 | 升级 | 争议资源协调、验证失败诊断 |
| 38 → PB19 | 输出 | 新所有权图谱供发布流程引用（不覆盖 PB19 发布所有权判定逻辑） |
