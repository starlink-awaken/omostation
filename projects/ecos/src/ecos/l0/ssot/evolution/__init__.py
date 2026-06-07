"""
SSOT Kernel — 自进化系统
==========================

从领域数据和引擎输出中自动挖掘新规则建议，驱动引擎迭代。

闭环流程:
    checkpoint → mine → suggest → apply → verify

核心组件:
    Evolver           进化引擎 — 串联闭环各步骤
    RuleMiner         规则挖掘机 — 6 种挖掘策略
    CheckpointManager 检查点管理器 — 修改前自动备份，支持回滚

6 种挖掘策略:
    UNPAIRED_FACTS     — 数值事实比例悬殊但无对应规则
    UNGUARDED_ENTITY   — 实体状态变更但无一致性规则覆盖
    CHAIN_GAP          — 状态机链间缺咬合
    THEORY_GAP         — 推论无理论支撑
    RECURRING_GAP      — 同一能力缺失反复出现
    NEW_CONTRADICTION  — 实体属性矛盾组合未被覆盖

使用:
    from .evolution.evolver import Evolver
    evolver = Evolver("domains/my-project")
    report = evolver.analyze()          # 挖规则
    evolver.apply_suggestion(suggestion)  # 应用规则
"""
