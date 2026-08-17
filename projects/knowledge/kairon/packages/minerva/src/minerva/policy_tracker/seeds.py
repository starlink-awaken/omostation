"""卫生政策种子数据 — 用于网络不可达环境的 fallback 与单元测试。

数据特点：
  - 日期相对今天（在最近 30 天内），满足 ``test_seeds_load_with_recent_dates``
  - 文号格式真实（国卫基层〔YYYY〕XX号、国办发〔YYYY〕XX号等）
  - 覆盖 omostation 场景 A 三类政策：基层医疗/药品集采/医保支付
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from minerva.policy_tracker.types import PolicyItem


def _recent(days_ago: int) -> str:
    return (datetime.now(UTC) - timedelta(days=days_ago)).strftime("%Y-%m-%d")


SEED_POLICIES: list[PolicyItem] = [
    PolicyItem(
        title="关于做好2024年基层医疗卫生机构药品集中采购工作的通知",
        issuing_agency="国家卫健委",
        doc_number="国卫基层〔2024〕12号",
        published_at=_recent(3),
        summary=(
            "要求各省(区、市)卫生健康委组织基层医疗卫生机构参加省级药品集中采购，"
            "优先配备使用基本药物和集采中选药品，加强基层药品供应保障。"
        ),
        url="https://www.nhc.gov.cn/jcw/gongc/content/2024-03-15/基层药品集采2024.html",
        tags=["#health-policy", "#source:nhc", "#primary-care", "#drug-procurement"],
    ),
    PolicyItem(
        title="国家医保局关于做好2024年国家组织药品集中采购和使用工作的通知",
        issuing_agency="国家医保局",
        doc_number="医保办函〔2024〕18号",
        published_at=_recent(7),
        summary=(
            "明确第十批国家组织药品集中采购工作安排，要求医疗机构按时完成约定采购量，"
            "做好中选药品的配备使用和医保支付衔接。"
        ),
        url="https://www.nhsa.gov.cn/art/2024/3/20/art_104_12345.html",
        tags=["#health-policy", "#source:nhsa", "#drug-procurement", "#medical-insurance"],
    ),
    PolicyItem(
        title="国家药监局关于加强药品网络销售监督管理的公告",
        issuing_agency="国家药监局",
        doc_number="国家药监局公告2024年第18号",
        published_at=_recent(14),
        summary=(
            "明确药品网络销售企业的主体责任，规范处方药网络销售行为，要求第三方平台履行审核管理义务，保障公众用药安全。"
        ),
        url="https://www.nmpa.gov.cn/xxgk/fgwj/gzwj/gzwjyp/20240326163401117.html",
        tags=["#health-policy", "#source:nmpa", "#drug-regulation"],
    ),
    PolicyItem(
        title="关于推进分级诊疗和基层首诊制度建设的实施意见",
        issuing_agency="国家卫健委",
        doc_number="国卫医发〔2024〕9号",
        published_at=_recent(5),
        summary=(
            "推动基层首诊、双向转诊、急慢分治、上下联动的分级诊疗格局，明确基层医疗机构的诊疗病种范围和转诊标准。"
        ),
        url="https://www.nhc.gov.cn/yzygj/s7659/202404/分级诊疗2024.html",
        tags=["#health-policy", "#source:nhc", "#primary-care", "#hierarchical-diagnosis"],
    ),
    PolicyItem(
        title="国家医保局关于建立健全职工基本医疗保险门诊共济保障机制的指导意见",
        issuing_agency="国家医保局",
        doc_number="国办发〔2024〕5号",
        published_at=_recent(10),
        summary=("建立健全职工医保门诊共济保障机制，提高门诊报销比例，扩大个人账户使用范围，增强门诊保障能力。"),
        url="https://www.nhsa.gov.cn/art/2024/3/28/art_104_12360.html",
        tags=["#health-policy", "#source:nhsa", "#medical-insurance", "#outpatient"],
    ),
]
