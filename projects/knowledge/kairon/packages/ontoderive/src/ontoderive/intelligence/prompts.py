"""
OntoDerive 提示词系统 v1 — 一等公民的提示词工程
==================================================
设计原则:
1. 每个提示词有明确的目的、输入变量、输出格式、温度
2. 支持领域预设（学术、商业、政策、技术）
3. 支持多轮推理链（Chain-of-Thought）
4. 版本化，可A/B测试
5. 所有提示词可导出为JSON，供外部工具消费

长远看: 提示词是OntoDerive的"推理引擎"。优质提示词 > 优质模型。
"""

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PromptTemplate:
    """一等公民的提示词模板"""

    name: str  # 唯一标识
    version: str  # 语义版本
    purpose: str  # 这个提示词解决什么问题
    domain: str  # academic | business | policy | tech | general
    system_prompt: str  # 系统提示
    user_prompt_template: str  # 用户提示模板（{var}占位）
    variables: list[str]  # 需要的输入变量
    output_format: str  # json | markdown | text | list
    temperature: float  # 0.0(确定性) ~ 1.0(创造性)
    max_tokens: int  # 输出上限
    chain_of_thought: bool  # 是否要求推理链
    fallback: str  # LLM不可用时的回退策略
    examples: list[dict] = field(default_factory=list)  # few-shot示例

    def render(self, **kwargs: Any) -> str:
        """填充模板变量"""
        prompt = self.user_prompt_template
        for var in self.variables:
            prompt = prompt.replace(f"{{{var}}}", str(kwargs.get(var, "")))
        return prompt


# ═══════════════════════════════════════════
# 核心提示词库 — 六大推导场景
# ═══════════════════════════════════════════

DERIVE_INSIGHTS = PromptTemplate(
    name="derive_insights",
    version="1.0.0",
    purpose="基于事实和现有推论，发现人可能忽略的新洞察",
    domain="general",
    system_prompt="""你是严谨的知识工程分析专家。你的所有结论必须:
1. 引用具体的编号（D-F1, INF-L2）
2. 区分"确定性发现"（基于事实）和"推测性洞察"（基于模式）
3. 如果证据不足，明确说"需要更多数据"
4. 不编造不在输入中的事实""",
    user_prompt_template="""分析以下知识库，找出人可能忽略的洞察。

## 事实基座
{facts_summary}

## 现有推论
{inferences_summary}

## 指令
1. 找出2-3条非显而易见的洞察
2. 每条必须引用具体的编号
3. 标注置信度（high/medium/low）

## 输出格式（JSON）
{{"insights":[
  {{"type":"derivation","content":"...","cites":["D-F1"],"confidence":"high","reasoning":"..."}}
]}}""",
    variables=["facts_summary", "inferences_summary"],
    output_format="json",
    temperature=0.3,
    max_tokens=800,
    chain_of_thought=True,
    fallback="规则引擎: 仅做格式检查，不生成新洞察。提示用户接入LLM以获得推导能力。",
)

JUDGE_QUALITY = PromptTemplate(
    name="judge_quality",
    version="1.0.0",
    purpose="综合评估知识工程质量，给出1-10评分和改善建议",
    domain="general",
    system_prompt="""你是知识工程质量评审专家。评审标准:
1. 逻辑连贯性: 结论是否从前提合理推出
2. 证据充分性: 引用的事实是否足够支撑结论
3. 可证伪性: 是否存在可以推翻推论的条件
4. 完整性: 是否覆盖了关键维度
评分不是越多越好，你需要严格打分。
5分以下=有严重缺陷。7分=合格。9分以上=优秀。""",
    user_prompt_template="""评估以下知识库的质量。

## 项目概况
{context}

## 事实基座（部分）
{facts_sample}

## 推论体系（部分）
{inferences_sample}

## 指令
1. 给出整体评分(1-10)
2. 列出2-3个优势
3. 列出2-3个缺陷
4. 给出3条改善建议（按优先级排序）

## 输出格式（JSON）
{{"score":5,"strengths":["..."],"weaknesses":["..."],"recommendations":["..."],"verdict":"..."}}""",
    variables=["context", "facts_sample", "inferences_sample"],
    output_format="json",
    temperature=0.2,
    max_tokens=600,
    chain_of_thought=True,
    fallback="规则引擎: 输出PASS/WARN/ERROR计数。明确标注'此为格式检查得分，非质量评分'。",
)

CHECK_CONTRADICTION = PromptTemplate(
    name="check_contradiction",
    version="1.0.0",
    purpose="语义级别判断两个推论是否存在实质性矛盾",
    domain="general",
    system_prompt=(
        "你是逻辑分析专家。判断两个命题是否存在实质性矛盾。注意区分: "
        "真矛盾(无法同时为真)、伪矛盾(表面冲突但可调和)、互补(不同角度)。"
    ),
    user_prompt_template="""判断以下两个推论是否存在实质性矛盾。

## 推论A: {inf_a_title}
{inf_a_text}

## 推论B: {inf_b_title}
{inf_b_text}

## 共享的事实引用: {shared_facts}

## 指令
1. 是否存在实质性矛盾？
2. 如果是表面冲突，说明为什么可以调和
3. 如果证据不足无法判断，说明需要什么额外信息

## 输出格式（JSON）
{{"is_contradiction":true/false,"reason":"...","missing_evidence":"..."}}""",
    variables=["inf_a_title", "inf_a_text", "inf_b_title", "inf_b_text", "shared_facts"],
    output_format="json",
    temperature=0.1,
    max_tokens=300,
    chain_of_thought=True,
    fallback="词法引擎: 30对关键词匹配。标注覆盖率(~6%中文对立空间)。明确提示'此处为词法检测，非语义判断'。",
)

RECOMMEND_TOOLS = PromptTemplate(
    name="recommend_tools",
    version="1.0.0",
    purpose="根据分析目标和上下文，推荐最合适的思维工具",
    domain="general",
    system_prompt="你是方法论专家。你了解73种思维工具（波特五力、SWOT、PEST等），能根据分析目标推荐最合适的。",
    user_prompt_template="""为以下分析目标推荐3个最合适的思维工具。

## 分析目标: {goal}
## 上下文: {context}

## 可用工具（部分）
{tools_sample}

## 指令
1. 推荐3个最合适的工具ID
2. 简要说明为什么推荐

## 输出格式
M-001, S-003, T-001""",
    variables=["goal", "context", "tools_sample"],
    output_format="list",
    temperature=0.1,
    max_tokens=100,
    chain_of_thought=False,
    fallback="TF-IDF: 余弦相似度匹配。与LLM语义匹配相比准确率低~40%。",
)

# ═══════════════════════════════════════════
# 领域预设 — 不同场景优化不同的提示词
# ═══════════════════════════════════════════

DOMAIN_PRESETS = {
    "policy": {
        "description": "政策分析场景 — 政府、公共管理",
        "system_addon": "你熟悉中国的政策体系。关注利益相关者分析、政策窗口、渐进决策。",
        "keywords": ["政策", "政府", "公共", "法规", "合规", "治理"],
    },
    "business": {
        "description": "商业分析场景 — 市场、竞争、战略",
        "system_addon": "你熟悉商业策略。关注竞争优势、市场规模、ROI、增长曲线。",
        "keywords": ["市场", "竞争", "战略", "营收", "成本", "用户"],
    },
    "academic": {
        "description": "学术研究场景 — 论文、方法论、理论",
        "system_addon": "你熟悉学术研究规范。关注方法论严谨性、理论支撑、可复现性。",
        "keywords": ["理论", "方法", "研究", "论文", "实验", "数据"],
    },
    "tech": {
        "description": "技术分析场景 — 架构、系统、代码",
        "system_addon": "你熟悉软件架构和系统工程。关注技术债务、架构耦合、测试覆盖。",
        "keywords": ["架构", "系统", "代码", "测试", "性能", "安全"],
    },
}


def auto_detect_domain(facts_summary: Any, inferences_summary: Any) -> Any:
    """基于事实/推论内容自动检测领域"""
    text = f"{facts_summary} {inferences_summary}".lower()
    scores = {}
    for domain, info in DOMAIN_PRESETS.items():
        scores[domain] = sum(1 for kw in info["keywords"] if kw in text)
    if max(scores.values()) == 0:
        return "general"
    return max(scores, key=lambda k: scores[k])


def get_template(name: Any, domain: Any = "general") -> Any:
    """获取提示词模板，支持领域定制"""
    templates = {
        "derive_insights": DERIVE_INSIGHTS,
        "judge_quality": JUDGE_QUALITY,
        "check_contradiction": CHECK_CONTRADICTION,
        "recommend_tools": RECOMMEND_TOOLS,
    }
    tmpl = templates.get(name)
    if not tmpl:
        return None
    if domain != "general" and domain in DOMAIN_PRESETS:
        preset = DOMAIN_PRESETS[domain]
        tmpl.system_prompt = f"{tmpl.system_prompt}\n\n{preset['system_addon']}"
    return tmpl


def export_all_templates() -> Any:
    """导出所有提示词模板为JSON（供外部工具消费）"""
    templates = {
        "derive_insights": {
            "version": DERIVE_INSIGHTS.version,
            "purpose": DERIVE_INSIGHTS.purpose,
            "variables": DERIVE_INSIGHTS.variables,
            "temperature": DERIVE_INSIGHTS.temperature,
            "output_format": DERIVE_INSIGHTS.output_format,
        },
        "judge_quality": {
            "version": JUDGE_QUALITY.version,
            "purpose": JUDGE_QUALITY.purpose,
            "variables": JUDGE_QUALITY.variables,
            "temperature": JUDGE_QUALITY.temperature,
            "output_format": JUDGE_QUALITY.output_format,
        },
        "check_contradiction": {
            "version": CHECK_CONTRADICTION.version,
            "purpose": CHECK_CONTRADICTION.purpose,
            "variables": CHECK_CONTRADICTION.variables,
            "temperature": CHECK_CONTRADICTION.temperature,
            "output_format": CHECK_CONTRADICTION.output_format,
        },
        "recommend_tools": {
            "version": RECOMMEND_TOOLS.version,
            "purpose": RECOMMEND_TOOLS.purpose,
            "variables": RECOMMEND_TOOLS.variables,
            "temperature": RECOMMEND_TOOLS.temperature,
            "output_format": RECOMMEND_TOOLS.output_format,
        },
        "domain_presets": {k: v["description"] for k, v in DOMAIN_PRESETS.items()},
    }
    return json.dumps(templates, ensure_ascii=False, indent=2)
