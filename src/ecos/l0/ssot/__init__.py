"""
SSOT Kernel — 单一事实源知识工程通用引擎
=========================================

基于 8 元类型 / 4 元关系元模型的知识工程引擎，通过确定性规则驱动。

核心能力:
    - 元模型管理: 8 类 MET-Type 正交验证
    - 规则引擎: 5+1 内置模式（矛盾/理论匹配/链联动/一致性/能力缺失/版本校验）
    - YAML 配置: 领域知识以 YAML 格式定义，加载时 Schema 校验
    - 知识提取: 模板 + LLM 双路提取流水线，自动降级
    - 自进化: checkpoint + 规则挖掘闭环

子命令 (CLI):
    ssot-kernel init      初始化新领域
    ssot-kernel compile   编译 YAML → JSON
    ssot-kernel derive    执行规则引擎推导
    ssot-kernel check     快速检查
    ssot-kernel graph     可视化（实体图/状态机）
    ssot-kernel report    生成报告
    ssot-kernel verify    验证元模型正交性
    ssot-kernel evolve    进化分析/规则挖掘
    ssot-kernel extract   文本 → YAML 提取

一键导入:
    from .config_loader import load_domain
    from .engine import RuleEngine
    from .meta_model import DomainConfig, Entity, Fact, Rule
"""

__version__ = "1.0.0"
__all__ = (
    "__version__",
)
