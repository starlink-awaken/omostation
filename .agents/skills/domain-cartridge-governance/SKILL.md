---
type: ssot
name: domain-cartridge-governance
description: "Master governance and execution skill for domain-specific .cartridge capsules (ADR-0203). Guides packaging, cryptographic verification, intent extraction, and sandboxed policy-compliant execution for Sovereign Health and Family Hub workflows."

last-reviewed: 2026-08-26
owner: governance-team
---

# 👁️ 领域治理卡带胶囊化与沙箱运行时规范 (ADR-0203)

本规范定义了接入 `omostation` 的自主智能体 (Agents) 如何调用、打包和在沙箱中安全执行特定的长尾领域卡带 (`.cartridge`)。

---

## 1. 生产级领域卡带清单

| 卡带标识 | 卡带名称 | 目标域 (`domain`) | 核心能力与意图模式 | 核心政策红线 |
| :--- | :--- | :---: | :--- | :--- |
| **`cartridge-weijian-v1`** | 卫健委信息化与等保立项治理卡带 | `work-weijian` | • 等保三级测评<br/>• 互联互通成熟度测评<br/>• 智慧医院信息化立项 | • 医疗数据严禁未经脱敏出网<br/>• 预算超50万必须专家前置论证<br/>• 核心业务上线必须等保三级 |
| **`cartridge-family-hub-v1`** | 家庭主权数字枢纽与资产卡带 | `family-hub` | • 家庭月度财务对账<br/>• 主权私有云资产同步<br/>• 健康体检指标趋势分析 | • 财务隐私数据仅在本地 omlxc 离线处理<br/>• 核心数据多副本加密快照 |

---

## 2. CLI 操作与沙箱调用

### 2.1 检查卡带清单与元数据
```bash
cockpit cartridge inspect domains/cartridges/weijian-governance.cartridge
```

### 2.2 在隔离沙箱中执行领域意图
```bash
# 卫健委等保立项意图
cockpit cartridge run domains/cartridges/weijian-governance.cartridge --intent "良乡医院HIS升级项目等保三级测评立项申报"

# 家庭主权财务对账意图
cockpit cartridge run domains/cartridges/family-hub.cartridge --intent "汇总分析本月家庭财务对账明细"
```

### 2.3 领域源码目录打包为签名胶囊
```bash
cockpit cartridge pack domains/weijian-governance --output domains/cartridges/weijian-governance.cartridge
```

---

## 3. 安全与合规红线 (Policy-as-Code)

1. **零信任沙箱隔离**：卡带在 `tempfile.TemporaryDirectory` 的独立沙箱环境中解压并执行，严禁突破当前工作区访问外部未授权路径。
2. **密码学完整性**：每次加载前必须校验 `manifest.json` 包含的 SHA-256 签名，篡改即拒。
3. **审计凭证联动 (ADR-0201)**：所有卡带执行产生的决策结果必须生成 Merkle Inclusion Proof 登记入账。
