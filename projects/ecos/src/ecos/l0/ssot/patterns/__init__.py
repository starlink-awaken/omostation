"""
SSOT Kernel — 规则模式（patterns）
====================================

确定性规则引擎的 5+1 内置模式。

内置模式:
    contradiction      矛盾检测 — 从事实条件出发检测结构性矛盾产出推论
    theory_match       理论匹配 — 为推论自动匹配理论支撑
    chain_trigger      链联动触发 — 状态机间 interlock 完整性检查
    consistency        一致性校验 — 推论依赖链连续性检查
    capability_gap     能力缺失检测 — 推论需求 → 实体覆盖检查
    version_consistency Schema 版本一致性校验（L1-1 契约）

所有模式继承自 patterns.base.BasePattern:
    class MyPattern(BasePattern):
        @property
        def pattern_name(self): return "my_pattern"
        def evaluate(self, rule, domain, context): ...

注册自定义模式:
    engine.registry.register("my_pattern", MyPattern())
"""
