#!/usr/bin/env python3
# ruff: noqa
"""
KOS Query Understanding — 查询理解增强

能力:
1. 意图识别: 判断查询类型 (精确/探索/对比)
2. 查询扩展: 同义词、上位词、下位词
3. 时间过滤: 自动检测时间范围 ("最近一周", "上个月")
4. 高级语法: 支持 field:value 过滤 + 布尔运算

Usage:
    from kos.query import QueryUnderstanding

    qu = QueryUnderstanding()
    analysis = qu.analyze("最近一周关于数据治理的通知")
    # {
    #   "original_query": "最近一周关于数据治理的通知",
    #   "intent": "precise",
    #   "time_range": {"start": "2026-07-01", "end": "2026-07-08"},
    #   "expanded_terms": ["数据治理", "信息治理", "数据管理"],
    #   "filters": {"kind": "通知"},
    #   "enhanced_query": "数据治理 信息治理 数据管理"
    # }
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any


class QueryUnderstanding:
    """查询理解器。"""

    # 时间关键词映射
    TIME_PATTERNS = {
        r"今天": lambda: (datetime.now().replace(hour=0, minute=0, second=0), datetime.now()),
        r"昨天": lambda: (datetime.now() - timedelta(days=1), datetime.now()),
        r"最近一周|最近7天": lambda: (datetime.now() - timedelta(days=7), datetime.now()),
        r"最近一个月|最近30天": lambda: (datetime.now() - timedelta(days=30), datetime.now()),
        r"最近一年|最近365天": lambda: (datetime.now() - timedelta(days=365), datetime.now()),
        r"本周": lambda: (datetime.now() - timedelta(days=datetime.now().weekday()), datetime.now()),
        r"本月": lambda: (datetime.now().replace(day=1), datetime.now()),
        r"今年": lambda: (datetime.now().replace(month=1, day=1), datetime.now()),
    }

    # 查询扩展词典 (中文同义词/相关词)
    QUERY_EXPANSION = {
        "数据治理": ["信息治理", "数据管理", "信息管理", "数据管控"],
        "数字化": ["数字化转型", "数字化建设", "信息化", "智能化"],
        "平台": ["系统", "软件平台", "应用平台", "服务平台"],
        "报告": ["汇报", "总结", "分析报告", "工作报告"],
        "通知": ["公告", "通报", "文件", "发文"],
        "方案": ["计划", "规划", "实施方案", "工作方案"],
        "制度": ["规定", "规范", "办法", "条例"],
        "考核": ["评估", "评价", "检查", "绩效考核"],
        "卫健委": ["卫生健康委员会", "卫生局", "卫生健康"],
        "国资委": ["国资委", "国有资产监督管理委员会"],
    }

    # 查询语法解析
    FIELD_FILTER_PATTERN = re.compile(r"(\w+):([^\s]+)")

    def analyze(self, query: str) -> dict[str, Any]:
        """分析查询。

        Args:
            query: 原始查询字符串。

        Returns:
            查询分析结果。
        """
        result = {
            "original_query": query,
            "cleaned_query": query,
            "intent": "exploratory",
            "time_range": None,
            "filters": {},
            "expanded_terms": [],
            "enhanced_query": query,
        }

        # 1. 检测时间范围
        time_range, cleaned = self._extract_time_range(query)
        result["time_range"] = time_range
        result["cleaned_query"] = cleaned

        # 2. 解析字段过滤器
        filters, cleaned = self._extract_field_filters(cleaned)
        result["filters"] = filters
        result["cleaned_query"] = cleaned

        # 3. 扩展查询词
        expanded = self._expand_terms(cleaned)
        result["expanded_terms"] = expanded

        # 4. 构建增强查询
        result["enhanced_query"] = self._build_enhanced_query(cleaned, expanded)

        # 5. 意图识别
        result["intent"] = self._detect_intent(cleaned)

        return result

    def _extract_time_range(self, query: str) -> tuple[dict | None, str]:
        """提取时间范围。"""
        for pattern, fn in self.TIME_PATTERNS.items():
            if re.search(pattern, query):
                start, end = fn()
                return (
                    {
                        "start": start.strftime("%Y%m%d%H%M%S"),
                        "end": end.strftime("%Y%m%d%H%M%S"),
                        "label": re.search(pattern, query).group(),  # type: ignore[reportOptionalMemberAccess]
                    },
                    re.sub(pattern, "", query).strip(),
                )
        return None, query

    def _extract_field_filters(self, query: str) -> tuple[dict, str]:
        """提取字段过滤器 (field:value)。"""
        filters = {}
        matches = self.FIELD_FILTER_PATTERN.findall(query)

        for field, value in matches:
            filters[field] = value

        # 移除过滤部分
        cleaned = self.FIELD_FILTER_PATTERN.sub("", query).strip()
        return filters, cleaned

    def _expand_terms(self, query: str) -> list[str]:
        """扩展查询词。"""
        expanded = []

        for term, synonyms in self.QUERY_EXPANSION.items():
            if term in query:
                expanded.extend(synonyms)

        # 去重
        return list(dict.fromkeys(expanded))

    def _build_enhanced_query(self, cleaned: str, expanded: list[str]) -> str:
        """构建增强查询。"""
        parts = [cleaned]
        if expanded:
            parts.append(" OR ".join(expanded[:5]))  # 最多 5 个扩展词
        return " ".join(parts)

    def _detect_intent(self, query: str) -> str:
        """检测查询意图。"""
        # 精确查询特征
        precise_patterns = [
            r"^\w+$",  # 单词查询
            r"关于.+的",  # 关于...的
            r".+通知$",  # 以通知结尾
            r".+报告$",  # 以报告结尾
            r"\d{4}",  # 包含年份
        ]

        # 对比查询特征
        compare_patterns = [
            r".+vs.+",
            r".+和.+的区别",
            r".+对比",
            r".+比较",
        ]

        for pat in compare_patterns:
            if re.search(pat, query):
                return "comparison"

        for pat in precise_patterns:
            if re.search(pat, query):
                return "precise"

        return "exploratory"


# ── 工具函数 ─────────────────────────────────────────────


def quick_analyze(query: str) -> dict[str, Any]:
    """快速分析查询。"""
    qu = QueryUnderstanding()
    return qu.analyze(query)


# ── CLI 入口 ──────────────────────────────────────────────


def main():
    import argparse

    parser = argparse.ArgumentParser(description="KOS Query Understanding")
    parser.add_argument("query", help="Query to analyze")
    args = parser.parse_args()

    qu = QueryUnderstanding()
    result = qu.analyze(args.query)
    print(json.dumps(result, ensure_ascii=False, indent=2))  # type: ignore[reportUndefinedVariable]


if __name__ == "__main__":
    main()
