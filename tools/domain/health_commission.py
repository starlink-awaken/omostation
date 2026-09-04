"""
卫健委领域插件
继承 BaseController/BaseExtractor/BasePredictor，复用通用能力
"""

from pathlib import Path

from tools.base import BaseController, BaseExtractor, BasePredictor


class HealthCommissionController(BaseController):
    """卫健委控制器"""

    def domain_specific_scan(self) -> dict:
        """卫健委特有的项目督导扫描"""
        return {
            "project_types": ["信息化", "三医联动", "绩效评价", "工作督导"],
            "scan_targets": ["项目进度", "资金使用", "验收情况"],
        }

    def domain_specific_eval(self) -> dict:
        """卫健委特有的绩效评价"""
        return {"eval_dimensions": ["项目完成率", "资金使用率", "验收通过率"], "metrics": {}}


class HealthCommissionExtractor(BaseExtractor):
    """卫健委知识提取器"""

    def get_domain_keywords(self) -> dict[str, list[str]]:
        return {
            "信息化建设": ["机房", "网络", "服务器", "数据库", "系统平台", "OA", "HIS", "LIS", "PACS"],
            "三医联动": ["医疗", "医保", "医药", "联动", "改革"],
            "绩效评价": ["绩效", "考核", "评价", "指标", "评分"],
            "网络安全": ["等保", "安全", "测评", "密评", "防火墙", "入侵检测"],
            "项目管理": ["招标", "投标", "监理", "验收", "变更", "决算"],
        }

    def extract_domain_specific(self, text: str) -> dict:
        """提取卫健委特有实体"""
        entities = {}
        # 项目编号
        proj_ids = re.findall(r"项目编号[：:]?\s*([A-Za-z0-9\-]+)", text)
        if proj_ids:
            entities["project_ids"] = proj_ids
        # 资金金额
        amounts = re.findall(r"(\d+[\.,，]*\d*\s*(万元|亿元))", text)
        if amounts:
            entities["amounts"] = [f"{a[0]}{a[1]}" for a in amounts]
        return entities


class HealthCommissionPredictor(BasePredictor):
    """卫健委预测器"""

    def predict_domain_trend(self) -> dict:
        """预测卫健委项目趋势"""
        return {"trend": "信息化项目持续增长", "predictions": ["电子票据", "紧密型医共体", "互联互通"]}

    def detect_domain_risks(self) -> dict:
        """检测卫健委特有风险"""
        return {"risk_areas": ["项目延期", "资金不到位", "验收不通过"], "alerts": []}


import re
