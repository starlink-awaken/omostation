"""推理规则函数"""

from typing import Any

# =============================================
# 模块级常量
# =============================================

UNIT_GROUPS = {
    "人数": ["人", "团队", "员工", "用户", "工程师", "博士", "经理", "专家", "导师", "工人"],
    "金额": ["万", "亿", "元", "预算", "营收", "收入", "成本", "金额", "投资", "赔偿", "市值"],
    "百分比": ["%", "率", "覆盖", "转化", "NPS", "满意度", "渗透", "份额", "占比", "集中度", "卸载率", "流失率"],
    "数量": ["次", "项", "个", "所", "家", "篇", "起", "件", "台", "单", "辆"],
    "时间": ["年份", "历时", "周期", "耗时", "成立于"],
    "面积": ["平方米", "亩", "公顷", "平方公里", "面积"],
}


VALUE_UNIT_MAP = {
    "%": "百分比",
    "万元": "金额",
    "亿元": "金额",
    "美元": "金额",
    "人": "人数",
    "家": "数量",
    "次": "数量",
    "件": "数量",
    "台": "数量",
    "月": "时间",
    "天": "时间",
    "小时": "时间",
    "平方米": "面积",
    "亩": "面积",
    "公顷": "面积",
    "万辆": "数量",
    "万单": "数量",
    "万台": "数量",
}


_STOP_CHARS = set("的是在与和及第年月个日一二三四五六七八九十前后")

_INVERSE_RELATIONS = {
    "employs": "employed_by",
    "part_of": "contains",
    "contains": "part_of",
    "cooperates_with": "cooperates_with",
    "competes_with": "competes_with",
    "depends_on": "depended_on_by",
    "authored_by": "authors",
    "precedes": "follows",
    "belongs_to": "contains",
    "influences": "influenced_by",
}

ONTOLOGY_HIERARCHY = {
    "DOMAIN": ["ORG", "ROL", "PRJ", "RES"],
    "FACT": ["DAT", "POL"],
    "INFERENCE": ["CONTRADICTION", "BUSINESS", "ARCHITECTURE"],
    "STATE": ["T", "F", "H"],
    "DOCUMENT": ["COL", "DOC", "CH", "SEC", "STD"],
}

_ID_PREFIX_MAP = {
    "ORG-": "DOMAIN",
    "ROL-": "DOMAIN",
    "PRJ-": "DOMAIN",
    "RES-": "DOMAIN",
    "D-F": "FACT",
    "P-F": "FACT",
    "INF-": "INFERENCE",
    "INF-V2-": "INFERENCE",
    "DOC-": "DOCUMENT",
    "CH-": "DOCUMENT",
    "SEC-": "DOCUMENT",
    "DCH-": "DOCUMENT",
    "STD-": "DOCUMENT",
    "CON-": "CONSTRAINT",
    "IP": "CONSTRAINT",
    "T": "STATE",
    "F": "STATE",
    "H": "STATE",
}


_PREFIX_TO_PARENT = {}
for _parent, _subs in ONTOLOGY_HIERARCHY.items():
    for _sub in _subs:
        _PREFIX_TO_PARENT[_sub] = _parent


# =============================================
# 模块级函数
# =============================================


def detect_domain(engine: Any, value: Any, label: Any) -> Any:
    """从值和标签中检测语义域, 优先用值的显式单位"""
    vs = str(value)
    for suffix, domain in VALUE_UNIT_MAP.items():
        if suffix in vs:
            return domain
    for domain, keywords in UNIT_GROUPS.items():
        if any(kw in label for kw in keywords):
            return domain
    return None


def char_overlap(engine: Any, label_a: Any, label_b: Any) -> Any:
    """检测两个标签的共同CJK字符数 ≥ 阈值"""
    chars_a = {c for c in label_a if "一" <= c <= "鿿" and c not in _STOP_CHARS}
    chars_b = {c for c in label_b if "一" <= c <= "鿿" and c not in _STOP_CHARS}
    return len(chars_a & chars_b) >= 2


def comparable(engine: Any, label_a: Any, label_b: Any, val_a: Any = None, val_b: Any = None) -> Any:
    """判断两个事实是否可比较 — 域匹配+字符重叠"""
    if val_a is not None and val_b is not None:
        dom_a = detect_domain(engine, val_a, label_a)
        dom_b = detect_domain(engine, val_b, label_b)
        if dom_a and dom_b:
            if dom_a != dom_b:
                return False
            return char_overlap(engine, label_a, label_b)
        if dom_a or dom_b:
            return False
    for group, keywords in UNIT_GROUPS.items():
        a_in = any(kw in label_a for kw in keywords)
        b_in = any(kw in label_b for kw in keywords)
        if a_in and b_in:
            return char_overlap(engine, label_a, label_b)
    return False


def find_chain(engine: Any, node: Any, inferences: Any, visited: Any) -> Any:
    if node in visited or node not in inferences:
        return [node]
    visited.add(node)
    longest = [node]
    for parent in inferences[node].get("derives_from", []):
        if parent.startswith("INF"):
            parent_chain = find_chain(engine, parent, inferences, visited.copy())
            if len(parent_chain) + 1 > len(longest):
                longest = [node] + parent_chain
    return longest


# ═══ R15: 变化检测 (Change Detection / 时态推理) ═══


def extract_prefix(engine: Any, id_str: Any) -> Any:
    """从ID中提取完整前缀模式 (如 D-F1→D-F, ORG-xxx→ORG-)"""
    # 按长度降序匹配, 优先匹配更长模式 (INF-V2- 优先于 INF-)
    for prefix in sorted(_ID_PREFIX_MAP.keys(), key=lambda x: -len(x)):
        if id_str.startswith(prefix):
            return prefix
    # 回退: 首个分隔符前的部分
    return id_str.split("-")[0] if "-" in id_str else id_str[:3]


def guess_parent(engine: Any, prefix: Any, type_map: Any) -> Any:
    """根据前缀模式猜测最可能的父类型 — 基于ID前缀→类型映射"""
    known = _ID_PREFIX_MAP
    # 直接匹配: 如果前缀以已知前缀开头, 返回对应类型
    for kp, parent in sorted(known.items(), key=lambda x: -len(x[0])):
        if prefix.startswith(kp) or kp.startswith(prefix):
            return parent
    # 单字母/短前缀: 基于字符重叠找最相似的已知前缀
    best, best_score = "DOMAIN", 0
    for kp in known:
        score = len(set(prefix) & set(kp))
        if score > best_score:
            best_score = score
            best = known[kp]
    return best


def closest_known(engine: Any, prefix: Any) -> Any:
    """找到最相似的已知ID前缀"""
    best, best_score = "ORG-", 0
    for kp in _ID_PREFIX_MAP:
        score = len(set(prefix) & set(kp))
        if score > best_score:
            best_score = score
            best = kp
    return best


# ═══ R10: 影响传播 (Influence Analysis) ═══


def calc_depth(engine: Any, node: Any, inferences: Any, depths: Any, visited: Any) -> Any:
    if node in visited or node not in inferences:
        depths[node] = 0
        return 0
    visited.add(node)
    max_parent = 0
    for parent in inferences[node].get("derives_from", []):
        if parent.startswith("INF"):
            max_parent = max(max_parent, calc_depth(engine, parent, inferences, depths, visited))
    depths[node] = max_parent + 1
    return depths[node]


# ═══ R19: 案例推理 CBR (Case-Based Reasoning) ═══


def disjunctive_syllogism(engine: Any, inferences: Any) -> Any:
    """A或B的推论结构: 如果两个推论引用相同事实但结论方向不同, 检测是否存在'排中'结构"""
    results = []
    inf_list = list(inferences.items())
    for i in range(len(inf_list)):
        for j in range(i + 1, len(inf_list)):
            a_id, a_info = inf_list[i]
            b_id, b_info = inf_list[j]
            shared = set(a_info.get("derives_from", [])) & set(b_info.get("derives_from", []))
            if len(shared) >= 2:
                a_text = a_info.get("text", "")
                b_text = b_info.get("text", "")
                # 检测排中结构: "应A" vs "应B" 且 A和B可能是互斥选项
                dichotomy_pairs = [
                    ("研发", "营销"),
                    ("增加", "控制"),
                    ("优先", "推迟"),
                    ("内部", "外部"),
                    ("自建", "采购"),
                ]
                for w1, w2 in dichotomy_pairs:
                    if (w1 in a_text and w2 in b_text) or (w2 in a_text and w1 in b_text):
                        results.append(
                            {
                                "type": "disjunctive_syllogism",
                                "conclusion": (f"'{a_id[:25]}'和'{b_id[:25]}'构成选言结构({w1} vs {w2}), 需明确优先级"),
                                "derived_from": list(shared),
                                "confidence": 0.70,
                                "method": "rule_engine",
                            }
                        )
                        break
    return results


# ═══ R14: 假言三段论 (Hypothetical Syllogism Chain) ═══


def hypothetical_syllogism(engine: Any, inferences: Any) -> Any:
    """IF A THEN B, IF B THEN C → IF A THEN C 检测跨层推导链并计算衰减系数"""
    results = []
    for title, info in inferences.items():
        chain = find_chain(engine, title, inferences, set())
        if len(chain) >= 3:
            decay = 0.9 ** (len(chain) - 1)
            results.append(
                {
                    "type": "hypothetical_syllogism",
                    "conclusion": f"推导链:{'→'.join(chain[:5])}, 衰减系数={decay:.2f}({len(chain)}层)",
                    "derived_from": chain,
                    "confidence": 0.80,
                    "method": "rule_engine",
                }
            )
    return results
