# 生态宪法 — 最小互通协议

> 制定: 2026-05-25 | 版本: v1 | 状态: 草案

## 一、参与节点类型

| 类型 | 说明 | 示例 |
|------|------|------|
| **Full Node** | 完整4+1+3架构实例 | starlink-core |
| **Light Node** | 仅有Agent能力，无OS基础设施 | 个人开发者单机 |
| **External Node** | 非Workspace体系的外部系统 | GitHub Actions |
| **Human Node** | 人类操作员 | 审核员 |

## 二、核心协议

1. **Identity Protocol** — 身份凭证签发与验证
2. **Capability Protocol** — 能力授权与审计
3. **Task Protocol** — 跨组织任务创建与认领
4. **Event Protocol** — 事件订阅与推送

## 三、发现机制

- 每个Agora实例公开AgentCard（A2A规范）
- 静态对等列表（配置驱动）
- 跨Agora事件同步状态

## 四、互通约束

- 最小共识：只需Identity+Task两协议即可互通
- 可选增强：Capability+Event是可选的
- 版本协商：调用时声明协议版本，回退到共同支持的版本

## 五、治理

- 变更流程：提出PR→公示期→评审→合并
- 分歧解决：组织级别X3 Consensus递归模型
