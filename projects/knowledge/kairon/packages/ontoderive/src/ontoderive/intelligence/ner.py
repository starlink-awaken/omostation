"""
L1 中文命名实体识别 — NER (零外部API, jieba可选)
====================================================
填补 正则匹配(L0) 到 LLM(L4) 之间的能力断层。
默认使用规则回退(jieba不可用时), 泛化能力显著高于硬编码正则。

规则回退策略:
- 组织名: 以常见后缀结尾的连续名词 (公司/集团/中心/大学/医院/园区/平台/实验室/...)
- 角色名: 以职业头衔结尾的词 (经理/专家/博士/工程师/主任/CEO/...)
- 地名: 以省/市/区/县/新区/开发区结尾的词
"""

import re
from typing import Any

# 组织名后缀 — 匹配以这些词结尾的名词短语
_ORG_SUFFIXES = (
    "公司",
    "集团",
    "中心",
    "大学",
    "学院",
    "医院",
    "园区",
    "平台",
    "实验室",
    "研究所",
    "研究院",
    "委员会",
    "协会",
    "基金会",
    "交易所",
    "银行",
    "证券",
    "保险",
    "基金",
    "信托",
    "事务所",
    "工作室",
    "政府",
    "部",
    "委",
    "局",
    "处",
    "署",
    "办公室",
    "领导小组",
    "工厂",
    "基地",
    "联盟",
    "网络",
    "系统",
    "体系",
    "工程",
)

_ROLE_SUFFIXES = (
    "经理",
    "专家",
    "博士",
    "工程师",
    "主任",
    "总监",
    "总裁",
    "CEO",
    "CTO",
    "CFO",
    "教授",
    "研究员",
    "顾问",
    "分析师",
    "设计师",
    "技术经理人",
    "经纪人",
    "代理人",
    "负责人",
    "主管",
    "专员",
)

_LOC_SUFFIXES = (
    "省",
    "市",
    "区",
    "县",
    "镇",
    "新区",
    "开发区",
    "高新区",
    "自贸区",
    "保税区",
    "试验区",
    "示范区",
    "先行区",
)


def _extract_entities_by_suffix(text: str, suffixes: tuple, prefix: Any = "ORG") -> Any:
    """通用后缀匹配: 提取以指定后缀结尾的2-8字名词短语"""
    entities = []
    for suffix in suffixes:
        # 匹配: 前面2-8个中文字符 + 后缀
        pattern = re.compile(r"([一-鿿　-〿A-Za-z]{2,8}" + re.escape(suffix) + r")")
        for m in pattern.finditer(text):
            name = m.group(1)
            if len(name) >= 3:
                entities.append((name, prefix))
    return entities


def extract_entities(text: str, use_jieba: Any = True) -> list:
    """提取文本中的命名实体, 返回 [(entity_name, entity_type), ...]"""
    entities = []

    # 优先: jieba词性标注 (如果可用)
    if use_jieba:
        try:
            import jieba.posseg as pseg

            words = pseg.cut(text)
            buf = ""
            for word, flag in words:
                if flag in ("nr", "ns", "nt", "nz"):  # 人名/地名/机构名/其他专名
                    buf += word
                else:
                    if len(buf) >= 3:
                        etype = "ORG" if flag in ("nt", "nz") else ("ROL" if flag == "nr" else "ORG")
                        entities.append((buf, etype))
                    buf = ""
                    # 单字实体也保留
                    if len(word) >= 2 and flag in ("nr", "ns", "nt", "nz"):
                        etype = "ORG" if flag in ("nt", "nz") else ("ROL" if flag == "nr" else "ORG")
                        entities.append((word, etype))
            if len(buf) >= 3:
                entities.append((buf, "ORG"))
        except ImportError:
            pass  # 回退规则

    # 回退: 后缀规则 (始终运行, 与jieba互补)
    if not entities:
        entities.extend(_extract_entities_by_suffix(text, _ORG_SUFFIXES, "ORG"))
        entities.extend(_extract_entities_by_suffix(text, _ROLE_SUFFIXES, "ROL"))
        entities.extend(_extract_entities_by_suffix(text, _LOC_SUFFIXES, "ORG"))

    # 去重
    seen = set()
    unique = []
    for name, etype in entities:
        if name not in seen:
            seen.add(name)
            unique.append((name, etype))
    return unique
