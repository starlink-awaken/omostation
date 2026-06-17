# X4 Standard: MutationProposal & HITL Lifecycle

> Status: ACTIVE | Applied: Phase 9
> Authority: Cockpit HITL Gate

## 1. 目标
防止自动进化逻辑对物理环境造成不可控的非预期破坏。

## 2. 提案封套 (MutationProposal)
- 所有自愈或代码优化建议必须包装为 `MutationProposal` YAML 对象。
- 存储路径：`.omo/state/proposals/`。
- 必填字段：`id`, `type`, `debt_id`, `suggestion`, `risk`。

## 3. 审批生命周期 (HITL)
- **Pending**: 存放在提案目录，显示在 Cockpit 队列。
- **Review**: 人类操作员通过 Cockpit UI 查看差异与建议。
- **Approve**: 触发 `_execute_mutation` 真实物理变更，随后删除提案并销毁关联债务。
- **Reject**: 直接删除提案文件。

## 4. 安全要求
- 审批 API 必须进行权限校验。
- 所有的物理变更必须产生审计日志。
