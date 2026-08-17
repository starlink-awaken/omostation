"""
Formalizer — 符号化引擎 (Phase 1+2)
=====================================
LLM从自然语言提取结构化知识 → 本体对齐 → OntoLang符号化
"""

import json
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SymbolicFact:
    id: str
    description: str
    value: str
    source: str = ""
    confidence: float = 0.90
    category: str = "data"  # data | policy
    meta_type: str = "FACT"


@dataclass
class SymbolicEntity:
    id: str
    name: str
    entity_type: str  # ORG | ROL | PRJ
    role: str = ""
    meta_type: str = "DOMAIN"


@dataclass
class SymbolicInference:
    id: str
    title: str
    derives_from: list[str] = field(default_factory=list)
    conclusion: str = ""
    confidence: str = "inference"
    meta_type: str = "INFERENCE"


@dataclass
class FormalKnowledge:
    facts: list[SymbolicFact] = field(default_factory=list)
    entities: list[SymbolicEntity] = field(default_factory=list)
    inferences: list[SymbolicInference] = field(default_factory=list)
    abox: dict = field(default_factory=dict)  # 断言箱: 具体实例
    tbox: dict = field(default_factory=dict)  # 术语箱: 类型层级


class Formalizer:
    """LLM提取 + 规则降级 + 符号化"""

    _CONNECTOR_PREFIX = re.compile(r"^[与和及的]+")

    def _rule_extract(self, text: str) -> FormalKnowledge:
        """规则引擎降级提取 — 零LLM, 正则匹配数值和实体"""
        knowledge = FormalKnowledge()
        fid_counter = 1
        # 提取数值事实 — 精确模式, 避免垃圾匹配
        patterns = [
            (r"(\d+)\s*家\s*(入驻)?企[业商]", "入驻企业数", "家"),
            (r"(\d+)\s*次.*?(对接|交易|调用)", "对接量", "次"),
            (r"(\d+\.?\d*)\s*%\s*(转化|成功|覆盖|增长|满意)", "比率", "%"),
            (r"与\s*(\d+)\s*所\s*(高校|大学|机构)", "合作高校", "所"),
            (r"(\d+)\s*[人名位个].*?(经理|专家|博士|导师)", "人员数", "人"),
            (r"NPS.*?(\d+)", "NPS得分", "分"),
            (r"(\d+\.?\d*)\s*[万亿千百]\s*(元|美元|营收|收入|预算|成本)", "金额", ""),
            (r"(\d+)\s*[台次个].*?(服务器|设备|机器)", "设备数", "台"),
            # 新增模式 — 覆盖更多常见文档事实
            (r"(\d+)\s*[件项个].*?(专利|发明|软著|著作权)", "知识产权数", "件"),
            (r"成立于\s*(\d{4})\s*年", "成立年份", "年"),
            (r"(\d+\.?\d*)\s*[万亿千百]?(平方米|亩|公顷|平方公里)", "占地面积", ""),
            (r"(?:投资|融资|投入)\s*(\d+\.?\d*)\s*[万亿千百]?(元|美元|万元)", "投资金额", ""),
            (r"(\d+\.?\d*)\s*%\s*(?:同比)?增[长速]", "增长率", "%"),
            (r"(?:排名|位居).*?[第前]?\s*(\d+)\s*[名位]", "排名", "名"),
            (r"(?:用户|会员|注册|访问).*?(\d+\.?\d*)\s*[万亿千百]?(人|个|次)", "用户量", ""),
            (r"(?:历时|周期|耗时).*?(\d+\.?\d*)\s*(天|月|年|小时)", "耗时", ""),
            # v3.6: 政府公文+财报+专利+政策
            (r"(?:批准|批复)日期\s*[：:]?\s*(\d{4}[年/-]\d{1,2}[月/-]\d{1,2})", "批准日期", ""),
            (r"(\d+\.?\d*)\s*[万亿千百]?(?:营收|收入)", "营收额", ""),
            (r"(?:净利润|利润).*?(\d+\.?\d*)\s*[万亿千百]?(?:元|美元)", "净利润", ""),
            (r"ROE\s*[：:＝=]?\s*(\d+\.?\d*)\s*%?", "ROE", "%"),
            (r"(?:资产负债率|负债率)\s*[：:＝=]?\s*(\d+\.?\d*)\s*%?", "资产负债率", "%"),
            (r"专利号\s*[：:＝=]?\s*([A-Z]{2}\d+[A-Z]?\d*)", "专利号", ""),
            (r"IPC分类\s*[：:＝=]?\s*([A-H]\d{2}[A-Z]/\d+)", "IPC分类", ""),
            (r"(?:补贴|资助).*?(\d+\.?\d*)\s*[万亿千百]?(?:元|万元)", "补贴金额", ""),
            (r"(?:补贴|资助)比例\s*[：:＝=]?\s*(\d+\.?\d*)\s*%", "补贴比例", "%"),
            (r"(?:覆盖|涉及).*?(\d+\.?\d*)\s*[万亿千百]?(人|家|个|项)", "覆盖范围", ""),
        ]
        for pattern, desc, unit in patterns:
            for m in re.finditer(pattern, text):
                val = f"{m.group(1)}{unit}"
                knowledge.facts.append(
                    SymbolicFact(
                        id=f"D-F{fid_counter}",
                        description=desc,
                        value=val,
                        source="规则提取",
                        confidence=0.85,
                    )
                )
                fid_counter += 1

        # 提取实体 — 精确模式, 去重, 避免垃圾匹配
        seen_names = set()
        entity_patterns = [
            # 机构/组织
            (r"(国家.{2,6}(?:中心|平台|基地|实验室))", "ORG", "运营主体"),
            (r"((?:中关村|北京|上海|深圳|广东|浙江|江苏).{2,4}(?:园区|新区|开发区|高新区))", "ORG", "区域"),
            (r"([一-鿿]{2,6}(?:大学|学院|研究院|研究所))", "ORG", "合作方"),
            (r"([一-鿿]{2,8}(?:公司|集团|有限公司|股份有限公司))", "ORG", "企业"),
            # 项目/平台
            (r"((?:技术|成果|创新|产业|数字).{2,6}(?:平台|系统|体系|工程))", "PRJ", "核心项目"),
            # 政策/文件
            (r"([一-鿿]{2,6}[发|办|字|函]\s*[\[［]\s*\d{4}\s*[\]］]\s*\d+\s*号)", "DOC", "政策文件"),
            # 标准/认证
            (r"(ISO\s*\d+|GB/T\s*\d+|国家标准.{2,6}|行业标准.{2,6})", "STD", "标准规范"),
        ]
        for pattern, etype, role in entity_patterns:
            for m in re.finditer(pattern, text):
                name = m.group(1)
                name = self._CONNECTOR_PREFIX.sub("", name)
                if name not in seen_names and len(name) >= 3:
                    seen_names.add(name)
                    knowledge.entities.append(
                        SymbolicEntity(
                            id=f"{etype}-{name[:10]}",
                            name=name,
                            entity_type=etype,
                            role=role,
                        )
                    )

        # L1 NER: 命名实体识别增强 — 补正则到LLM之间的能力断层
        try:
            from ontoderive.intelligence.ner import extract_entities

            for name, etype in extract_entities(text, use_jieba=True):
                if name not in seen_names and len(name) >= 3:
                    seen_names.add(name)
                    knowledge.entities.append(
                        SymbolicEntity(
                            id=f"{etype}-{name[:10]}",
                            name=name,
                            entity_type=etype,
                            role="NER识别" if etype == "ORG" else "人员",
                        )
                    )
        except ImportError:
            pass

        return knowledge

    EXTRACT_PROMPT = """从文本提取结构化JSON。只输出JSON，不要解释。

文本: {text}

输出格式 (严格JSON):
{{"facts":[{{"id":"D-F1","desc":"入驻企业数","val":"240家"}}],"entities":[{{"id":"ORG-A","name":"国家中心","type":"ORG","role":"运营"}}],"inferences":[{{"id":"INF-1","title":"推论标题","from":["D-F1"],"conc":"结论"}}]}}

规则:
- facts: 数字+单位 (id= D-F1..D-Fn, desc≤15字, val含单位)
- entities: 组织/角色/项目 (id= ORG-/ROL-/PRJ-, type=组织|角色|项目)
- inferences: 结论/判断 (id= INF-1.., from=引用的事实id列表, conc≤80字)"""

    def __init__(self, enhancer: Any = None) -> None:
        self.enhancer = enhancer

    def _smart_chunk(self, text: str, max_chars: Any = 3000, max_total: Any = 12000) -> Any:
        """智能分块: 按段落边界切割, 避免截断句子"""
        text = text[:max_total]
        if len(text) <= max_chars:
            return [text]
        chunks = []
        pos = 0
        while pos < len(text):
            end = min(pos + max_chars, len(text))
            if end < len(text):
                # 回退到最近的段落边界
                boundary = max(text.rfind("\n\n", pos, end), text.rfind("\n", pos, end))
                if boundary > pos + max_chars // 2:
                    end = boundary + 1
            chunks.append(text[pos:end])
            pos = end
        return chunks

    def _parse_llm_fact(self, f: dict, idx: int) -> SymbolicFact:
        """解析LLM提取的事实 — 兼容新旧Prompt格式"""
        return SymbolicFact(
            id=f.get("id", f"D-F{idx}"),
            description=f.get("desc", f.get("description", ""))[:20],
            value=str(f.get("val", f.get("value", ""))),
            source=f.get("source", "LLM提取"),
            confidence=0.90,
        )

    def _parse_llm_entity(self, e: dict, idx: int) -> SymbolicEntity:
        """解析LLM提取的实体"""
        etype = e.get("type", "组织")
        if etype in ("组织", "ORG"):
            etype = "ORG"
        elif etype in ("角色", "ROL"):
            etype = "ROL"
        elif etype in ("项目", "PRJ"):
            etype = "PRJ"
        return SymbolicEntity(
            id=e.get("id", f"{etype}-{e.get('name', '未知')[:10]}"),
            name=e.get("name", ""),
            entity_type=etype,
            role=e.get("role", ""),
        )

    def _parse_llm_inference(self, inf: dict, idx: int) -> SymbolicInference:
        """解析LLM提取的推论"""
        return SymbolicInference(
            id=inf.get("id", f"INF-L{idx}"),
            title=inf.get("title", ""),
            derives_from=inf.get("from", inf.get("derives_from", [])),
            conclusion=inf.get("conc", inf.get("conclusion", "")),
        )

    def extract_from_text(self, text: str, mode: Any = "llm_first") -> FormalKnowledge:
        """Phase 1: LLM主提取 → 降级规则引擎

        mode: llm_first (默认, LLM优先+规则降级)
              llm_only (仅LLM)
              rule_only (仅规则)
        """
        knowledge = FormalKnowledge()

        # LLM主提取
        if mode != "rule_only" and self.enhancer and self.enhancer.available:
            print(f"[formalize] 🤖 LLM提取中 ({self.enhancer.model})...")
            # 智能分块: 按段落边界切割, 最大3000字/块
            chunks = self._smart_chunk(text, max_chars=3000, max_total=12000)
            for chunk in chunks:
                data = {}
                result = self.enhancer._call(
                    self.EXTRACT_PROMPT.format(text=chunk),
                    "只输出JSON。",
                    0.1,  # 低temperature适合结构化提取
                )
                if result:
                    try:
                        data = json.loads(result)
                    except json.JSONDecodeError:
                        m = re.search(r"\{[\s\S]*\}", result)
                        data = json.loads(m.group()) if m else {}

                for f in data.get("facts", []):
                    knowledge.facts.append(self._parse_llm_fact(f, len(knowledge.facts) + 1))
                for e in data.get("entities", []):
                    knowledge.entities.append(self._parse_llm_entity(e, len(knowledge.entities) + 1))
                for inf in data.get("inferences", []):
                    knowledge.inferences.append(self._parse_llm_inference(inf, len(knowledge.inferences) + 1))

        # LLM失败/超时 → 规则引擎降级 (仅llm_first模式)
        if not knowledge.facts:
            if mode == "llm_only":
                print("[formalize] ⚠️ LLM提取为空, llm_only模式不降级, 返回空结果")
            else:
                print("[formalize] ⚠️ LLM提取为空/超时, 已降级为规则引擎 (覆盖约15-20%)")
                knowledge = self._rule_extract(text)

        self._validate(knowledge)
        # 构建ABox/TBox
        self._build_abox_tbox(knowledge)
        return knowledge

    def _validate(self, knowledge: FormalKnowledge) -> None:
        """规则校验: TypeValidator检查ID格式 + 属性约束校验"""
        try:
            from ontoderive.foundation.typesystem import TypeValidator
        except ImportError:
            from ontoderive.foundation.typesystem import TypeValidator
        tv = TypeValidator()
        for f in knowledge.facts:
            if not tv.check_id(f.id).is_valid:
                f.id = f"D-F{hash(f.description) % 10000}"  # 自动修复
        for e in knowledge.entities:
            if not tv.check_id(e.id).is_valid:
                e.id = f"ORG-{e.name[:10]}"
        self._validate_properties(knowledge)

    def _validate_properties(self, knowledge: FormalKnowledge) -> None:
        """属性约束校验: 基于TBox PROPERTY/META_TYPES检查字段完整性和类型"""
        issues = []
        # 事实属性校验
        for f in knowledge.facts:
            if not f.value or f.value.strip() in ("", "-", "—"):
                issues.append(f"事实 {f.id}: value字段为空")
            elif not any(c.isdigit() for c in str(f.value)):
                # 非纯数值型事实(如政策引用), 跳过
                pass
            if not f.source or f.source.strip() in ("", "-"):
                issues.append(f"事实 {f.id}: source字段为空, 可追溯性受影响")

        # 实体属性校验
        for e in knowledge.entities:
            if not e.name or len(e.name.strip()) < 2:
                issues.append(f"实体 {e.id}: name字段过短或为空 ('{e.name}')")
            if not e.entity_type or e.entity_type.strip() == "":
                issues.append(f"实体 {e.id}: entity_type字段为空")
            # 检查entity_type是否在TBox已知类型中
            known_types = {"ORG", "ROL", "PRJ", "RES", "DOC", "STD", "POL", "DAT"}
            if e.entity_type and e.entity_type not in known_types:
                issues.append(f"实体 {e.id}: entity_type='{e.entity_type}'不在已知类型{known_types}中")

        # 推论属性校验
        for inf in knowledge.inferences:
            if not inf.derives_from:
                issues.append(f"推论 {inf.id}: derives_from为空, 推论不可追溯")
            if not inf.conclusion or len(inf.conclusion.strip()) < 5:
                issues.append(f"推论 {inf.id}: conclusion为空或过短")

        if issues:
            knowledge.abox["_validation_issues"] = issues

    def _build_abox_tbox(self, knowledge: FormalKnowledge) -> None:
        """Phase 2: 构建ABox(断言)和TBox(术语)"""
        knowledge.abox = {
            "facts": {f.id: {"description": f.description, "value": f.value} for f in knowledge.facts},
            "entities": {e.id: {"name": e.name, "type": e.entity_type} for e in knowledge.entities},
        }
        knowledge.tbox = {
            "DOMAIN": {"subtypes": ["ORG", "ROL", "PRJ", "RES"]},
            "DOCUMENT": {"subtypes": ["COL", "DOC", "CH", "SEC", "STD"]},
            "FACT": {"subtypes": ["DAT", "POL"]},
            "INFERENCE": {"subtypes": ["CLAIM", "STRATEGY", "DIAGNOSIS"]},
            "PROPERTY": {"numeric": ["value", "count", "rate"], "textual": ["description", "source"]},
        }

    def to_markdown(self, knowledge: FormalKnowledge) -> str:
        """符号化知识→Markdown (供现有derive/check消费)"""
        lines = ["# 形式化知识库\n"]
        if knowledge.facts:
            lines.append("## 事实\n")
            lines.append("| 编号 | 数据 | 数值 | 来源 |")
            lines.append("|------|------|------|------|")
            for f in knowledge.facts:
                lines.append(f"| {f.id} | {f.description} | {f.value} | {f.source} |")
            lines.append("")
        if knowledge.entities:
            lines.append("## 实体\n")
            lines.append("| 实体 | 类型 | 角色 |")
            lines.append("|------|------|------|")
            for e in knowledge.entities:
                lines.append(f"| **{e.id}** | {e.entity_type} | {e.role} |")
            lines.append("")
        if knowledge.inferences:
            lines.append("## 推论\n")
            for inf in knowledge.inferences:
                lines.append(f"### {inf.id}：{inf.title}")
                lines.append(f"- derives_from: {inf.derives_from}")
                if inf.conclusion:
                    lines.append(f"- 结论: {inf.conclusion}")
                lines.append(f"confidence: {inf.confidence}")
                lines.append("")
        return "\n".join(lines)
