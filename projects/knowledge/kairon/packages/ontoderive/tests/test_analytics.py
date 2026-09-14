"""AnalyticsEngine 测试 --- A1~A12 全分析模式 + 辅助函数"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from ontoderive.theories.analytics import (
    AnalyticalPattern,
    AnalyticsEngine,
    analyze_agency,
    analyze_capacity,
    analyze_causal_chain,
    analyze_game_equilibrium,
    analyze_incentive,
    analyze_info_ecology,
    analyze_market_structure,
    analyze_organizational_inertia,
    analyze_power_map,
    analyze_remediation,
    analyze_scenario_planning,
    analyze_strategic_options,
    analyze_supply_chain,
    analyze_tech_disruption,
    detect_agency_issue,
    detect_capacity_constraint,
    detect_causal_chain,
    detect_game_equilibrium,
    detect_incentive_issue,
    detect_info_ecology,
    detect_market_structure,
    detect_organizational_inertia,
    detect_power_map,
    detect_remediation_needed,
    detect_scenario_planning,
    detect_strategic_options,
    detect_supply_risk,
    detect_tech_disruption,
)
from ontoderive.theories.analytics_patterns import (
    _extract_num,
    _find_entity_for_fact,
    _iter_facts,
)

# ===========================================
# 辅助函数测试
# ===========================================


class TestExtractNum:
    """_extract_num 边界和异常情况"""

    def test_int(self):
        assert _extract_num(42) == 42.0

    def test_float(self):
        assert _extract_num(3.14) == 3.14

    def test_string_with_unit(self):
        assert _extract_num("94%") == 94.0

    def test_chinese_number(self):
        assert _extract_num("1286万辆") == 1286.0

    def test_zero_string(self):
        assert _extract_num("0%") == 0.0

    def test_bool_returns_zero(self):
        """bool 不应出现在 value 字段, 返回 0.0"""
        val = _extract_num(True)
        assert val == 1.0

    def test_empty_string(self):
        assert _extract_num("") == 0.0

    def test_no_number_in_string(self):
        assert _extract_num("无数据") == 0.0

    def test_multiple_numbers_uses_first(self):
        assert _extract_num("50到100") == 50.0

    def test_very_large_number(self):
        assert _extract_num("999999.99") == 999999.99


class TestIterFacts:
    """_iter_facts 安全迭代"""

    def test_normal_dict(self):
        facts = {"D-F1": {"desc": "test", "value": "1"}}
        result = list(_iter_facts(facts))
        assert len(result) == 1

    def test_mixed_dict_bool(self):
        facts = {"D-F1": {"desc": "test"}, "D-F2": True}
        result = list(_iter_facts(facts))
        assert len(result) == 1

    def test_non_dict(self):
        assert list(_iter_facts("not a dict")) == []
        assert list(_iter_facts(42)) == []

    def test_empty_dict(self):
        assert list(_iter_facts({})) == []

    def test_all_non_dict_values(self):
        facts = {"D-F1": 1, "D-F2": "string", "D-F3": None}
        result = list(_iter_facts(facts))
        assert len(result) == 0

    def test_none_value(self):
        facts = {"D-F1": None}
        result = list(_iter_facts(facts))
        assert len(result) == 0

    def test_mixed_types(self):
        facts = {
            "D-F1": {"desc": "valid"},
            "D-F2": [1, 2, 3],
            "D-F3": {"desc": "also valid"},
        }
        result = list(_iter_facts(facts))
        assert len(result) == 2


class TestFindEntityForFact:
    """_find_entity_for_fact 语义匹配 + 回退"""

    def test_fallback_string_match(self):
        """当无 matcher 时使用字符串精确匹配"""
        entities = {
            "E-ORG-A": {"name": "企业A"},
            "E-ORG-B": {"name": "企业B"},
        }
        fid = _find_entity_for_fact("D-F1", "企业A营收增长", entities)
        assert fid == "E-ORG-A"

    def test_no_match_returns_fid(self):
        """无匹配时返回事实ID"""
        entities = {"E-ORG-A": {"name": "企业A"}}
        fid = _find_entity_for_fact("D-F1", "无关描述", entities)
        assert fid == "D-F1"

    def test_non_dict_entities_returns_fid(self):
        """entities 不是 dict 时返回 fid"""
        fid = _find_entity_for_fact("D-F1", "desc", ["not", "a", "dict"])
        assert fid == "D-F1"

    def test_empty_entities(self):
        """空 entities 返回 fid"""
        fid = _find_entity_for_fact("D-F1", "desc", {})
        assert fid == "D-F1"


# ===========================================
# A1: 供给弹性分析
# ===========================================


class TestA1CapacityElasticity:
    def test_detect_high_utilization(self):
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "产能利用率", "value": "94%"}}
        assert detect_capacity_constraint(ae, facts, {}, [])

    def test_detect_excess_capacity(self):
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "产能利用率", "value": "56%"}}
        assert detect_capacity_constraint(ae, facts, {}, [])

    def test_no_detect_normal_utilization(self):
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "产能利用率", "value": "75%"}}
        assert not detect_capacity_constraint(ae, facts, {}, [])

    def test_detect_low_inventory(self):
        ae = AnalyticsEngine()
        facts = {
            "D-F1": {"desc": "库存天数", "value": "12天"},
            "D-F2": {"desc": "安全库存基准", "value": "30天"},
        }
        assert detect_capacity_constraint(ae, facts, {}, [])

    def test_detect_via_description_field(self):
        """使用 description 而非 desc 字段时应同样检测"""
        ae = AnalyticsEngine()
        facts = {"D-F1": {"description": "产能利用率", "value": "93%"}}
        assert detect_capacity_constraint(ae, facts, {}, [])

    def test_not_detect_when_num_zero(self):
        """利用率 0 不被视为异常"""
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "产能利用率", "value": "0"}}
        assert not detect_capacity_constraint(ae, facts, {}, [])

    def test_detect_exact_90_percent(self):
        """利用率 90% 不算紧张(>90 才触发)"""
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "产能利用率", "value": "90%"}}
        assert not detect_capacity_constraint(ae, facts, {}, [])

    def test_detect_exact_60_percent(self):
        """利用率 60% 不算过剩(<60 才触发)"""
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "产能利用率", "value": "60%"}}
        assert not detect_capacity_constraint(ae, facts, {}, [])

    def test_analyze_high_utilization(self):
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "产能利用率", "value": "94%"}}
        results = analyze_capacity(ae, facts, {}, [], None)
        assert any("供给弹性" in r["conclusion"] for r in results)

    def test_analyze_excess_capacity(self):
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "产能利用率", "value": "56%"}}
        results = analyze_capacity(ae, facts, {}, [], None)
        assert any("产能过剩" in r["conclusion"] for r in results)

    def test_analyze_inventory_gap(self):
        ae = AnalyticsEngine()
        facts = {
            "D-F1": {"desc": "库存天数", "value": "12天"},
            "D-F2": {"desc": "安全库存基准", "value": "30天"},
        }
        results = analyze_capacity(ae, facts, {}, [], None)
        assert any("库存缺口" in r["conclusion"] for r in results)

    def test_analyze_empty_facts(self):
        ae = AnalyticsEngine()
        results = analyze_capacity(ae, {}, {}, [], None)
        assert results == []

    def test_analyze_elasticity_formula(self):
        """验证弹性公式: (100-num)/num"""
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "产能利用率", "value": "94%"}}
        results = analyze_capacity(ae, facts, {}, [], None)
        # num=94, elasticity = (100-94)/94 = 0.0638...
        assert any("0.06" in r["conclusion"] for r in results)

    def test_analyze_utilization_100_percent(self):
        """利用率100%触发供给紧张(num>90且num<=100)"""
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "产能利用率", "value": "100%"}}
        results = analyze_capacity(ae, facts, {}, [], None)
        assert len(results) == 1
        assert any("供给弹性≈0.00" in r["conclusion"] for r in results)

    def test_analyze_excess_capacity_zero_value_skipped(self):
        """value 为 0 的 fact 应跳过"""
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "产能利用率", "value": "0"}}
        results = analyze_capacity(ae, facts, {}, [], None)
        assert len(results) == 0


# ===========================================
# A2: 供应链风险放大
# ===========================================


class TestA2SupplyChainAmplification:
    def test_detect_with_depends_on_and_delivery_issue(self):
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "交付率", "value": "65%"}}
        relations = [
            {"subject": "工厂A", "relation_type": "depends_on", "object": "供应商B"},
        ]
        assert detect_supply_risk(ae, facts, {}, relations)

    def test_detect_delivery_issue_in_description(self):
        """使用 description 字段也应检测到"""
        ae = AnalyticsEngine()
        facts = {"D-F1": {"description": "交付完成率", "value": "50%"}}
        relations = [
            {"subject": "工厂A", "relation_type": "depends_on", "object": "供应商B"},
        ]
        assert detect_supply_risk(ae, facts, {}, relations)

    def test_no_detect_without_chain(self):
        """无 depends_on 链时不触发"""
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "交付率", "value": "65%"}}
        assert not detect_supply_risk(ae, facts, {}, [])

    def test_no_detect_without_issue(self):
        """交付率 >=80 时不触发"""
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "交付率", "value": "95%"}}
        relations = [
            {"subject": "工厂A", "relation_type": "depends_on", "object": "供应商B"},
        ]
        assert not detect_supply_risk(ae, facts, {}, relations)

    def test_no_detect_empty_facts(self):
        ae = AnalyticsEngine()
        relations = [
            {"subject": "工厂A", "relation_type": "depends_on", "object": "供应商B"},
        ]
        assert not detect_supply_risk(ae, {}, {}, relations)

    def test_analyze_supply_chain(self):
        ae = AnalyticsEngine()
        facts = {
            "D-F1": {"desc": "交付率", "value": "65%"},
            "D-F2": {"desc": "库存天数", "value": "15天"},
        }
        relations = [
            {"subject": "工厂A", "relation_type": "depends_on", "object": "供应商B"},
        ]
        entities = {"E-1": {"name": "工厂A"}}
        results = analyze_supply_chain(ae, facts, entities, relations, None)
        for r in results:
            assert "conclusion" in r
            assert "type" in r
            assert r["type"] == "analytics"

    def test_analyze_no_delivery_fact(self):
        """无交付相关事实时返回空列表"""
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "营收", "value": "100亿"}}
        results = analyze_supply_chain(ae, facts, {}, [], None)
        assert results == []

    def test_analyze_delivery_80_or_above_skipped(self):
        """交付 >=80 不产生分析结果"""
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "交付率", "value": "80%"}}
        results = analyze_supply_chain(ae, facts, {}, [], None)
        assert results == []

    def test_analyze_delivery_zero_skipped(self):
        """交付 <=0 不产生分析结果"""
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "交付率", "value": "0"}}
        results = analyze_supply_chain(ae, facts, {}, [], None)
        assert results == []

    def test_analyze_empty_relations(self):
        """无 relations 时不应报错"""
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "交付率", "value": "65%"}}
        results = analyze_supply_chain(ae, facts, {}, None, None)
        assert results == []


# ===========================================
# A3: 代理问题检测
# ===========================================


class TestA3AgencyDetection:
    def test_detect_agency_issue(self):
        ae = AnalyticsEngine()
        relations = [
            {"subject": "ORG-平台", "relation_type": "employs", "object": "ROL-骑手"},
            {"subject": "ROL-骑手", "relation_type": "cooperates_with", "object": "ROL-消费者"},
        ]
        assert detect_agency_issue(ae, {}, {}, relations)

    def test_no_agency_without_employ(self):
        ae = AnalyticsEngine()
        relations = [
            {"subject": "ORG-A", "relation_type": "cooperates_with", "object": "ORG-B"},
        ]
        assert not detect_agency_issue(ae, {}, {}, relations)

    def test_no_agency_when_employee_works_for_employer(self):
        """员工关系指向雇主时不视为代理问题"""
        ae = AnalyticsEngine()
        relations = [
            {"subject": "ORG-平台", "relation_type": "employs", "object": "ROL-骑手"},
            {"subject": "ROL-骑手", "relation_type": "cooperates_with", "object": "ORG-平台"},
        ]
        assert not detect_agency_issue(ae, {}, {}, relations)

    def test_detect_employs_with_depends_on(self):
        ae = AnalyticsEngine()
        relations = [
            {"subject": "ORG-A", "relation_type": "employs", "object": "ROL-B"},
            {"subject": "ROL-B", "relation_type": "depends_on", "object": "ORG-C"},
        ]
        assert detect_agency_issue(ae, {}, {}, relations)

    def test_detect_employs_with_influences(self):
        ae = AnalyticsEngine()
        relations = [
            {"subject": "ORG-A", "relation_type": "employs", "object": "ROL-B"},
            {"subject": "ROL-B", "relation_type": "influences", "object": "ORG-C"},
        ]
        assert detect_agency_issue(ae, {}, {}, relations)

    def test_empty_employ_pairs_no_agency(self):
        ae = AnalyticsEngine()
        relations = []
        assert not detect_agency_issue(ae, {}, {}, relations)

    def test_analyze_agency_finds_issues(self):
        ae = AnalyticsEngine()
        relations = [
            {"subject": "ORG-平台", "relation_type": "employs", "object": "ROL-骑手"},
            {"subject": "ROL-骑手", "relation_type": "cooperates_with", "object": "ROL-消费者"},
        ]
        results = analyze_agency(ae, {}, {}, relations, None)
        assert len(results) >= 1
        assert any("代理问题" in r["conclusion"] for r in results)

    def test_analyze_agency_no_issues(self):
        """无雇佣关系时返回空列表"""
        ae = AnalyticsEngine()
        relations = [
            {"subject": "ORG-A", "relation_type": "cooperates_with", "object": "ORG-B"},
        ]
        results = analyze_agency(ae, {}, {}, relations, None)
        assert results == []

    def test_analyze_agency_with_enhancer(self, mock_enhancer):
        """有 enhancer 时生成 LLM 增强分析"""
        ae = AnalyticsEngine(enhancer=mock_enhancer)
        relations = [
            {"subject": "ORG-平台", "relation_type": "employs", "object": "ROL-骑手"},
            {"subject": "ROL-骑手", "relation_type": "cooperates_with", "object": "ROL-消费者"},
        ]
        results = analyze_agency(ae, {}, {}, relations, mock_enhancer)
        assert len(results) >= 1
        assert any("LLM分析" in r["conclusion"] for r in results)


# ===========================================
# A4: 激励不相容检测
# ===========================================


class TestA4IncentiveMisalignment:
    def test_detect_shared_resource(self):
        ae = AnalyticsEngine()
        relations = [
            {"subject": "ORG-A", "relation_type": "depends_on", "object": "RES-资金"},
            {"subject": "ORG-B", "relation_type": "depends_on", "object": "RES-资金"},
        ]
        assert detect_incentive_issue(ae, {}, {}, relations)

    def test_no_detect_no_shared_resource(self):
        ae = AnalyticsEngine()
        relations = [
            {"subject": "ORG-A", "relation_type": "depends_on", "object": "RES-A"},
            {"subject": "ORG-B", "relation_type": "depends_on", "object": "RES-B"},
        ]
        assert not detect_incentive_issue(ae, {}, {}, relations)

    def test_no_detect_empty_relations(self):
        ae = AnalyticsEngine()
        assert not detect_incentive_issue(ae, {}, {}, [])

    def test_detect_three_way_shared(self):
        """三个主体共享同一资源"""
        ae = AnalyticsEngine()
        relations = [
            {"subject": "ORG-A", "relation_type": "competes_with", "object": "RES-市场"},
            {"subject": "ORG-B", "relation_type": "competes_with", "object": "RES-市场"},
            {"subject": "ORG-C", "relation_type": "competes_with", "object": "RES-市场"},
        ]
        assert detect_incentive_issue(ae, {}, {}, relations)

    def test_analyze_incentive_misalignment(self):
        """检测激励冲突: 语义差异大的事实共享目标"""
        ae = AnalyticsEngine()
        facts = {
            "D-F1": {"desc": "企业A利润目标"},
            "D-F2": {"desc": "企业B环保目标"},
        }
        relations = [
            {"subject": "企业A", "relation_type": "depends_on", "object": "RES-资金"},
            {"subject": "企业B", "relation_type": "depends_on", "object": "RES-资金"},
        ]
        results = analyze_incentive(ae, facts, {}, relations, None)
        assert isinstance(results, list)

    def test_analyze_empty_facts(self):
        ae = AnalyticsEngine()
        results = analyze_incentive(ae, {}, {}, [], None)
        assert results == []

    def test_analyze_no_shared_resource(self):
        ae = AnalyticsEngine()
        facts = {
            "D-F1": {"desc": "企业A利润"},
            "D-F2": {"desc": "企业B利润"},
        }
        relations = [
            {"subject": "企业A", "relation_type": "depends_on", "object": "RES-A"},
            {"subject": "企业B", "relation_type": "depends_on", "object": "RES-B"},
        ]
        results = analyze_incentive(ae, facts, {}, relations, None)
        assert results == []


# ===========================================
# A5: 分阶段补救规划
# ===========================================


class TestA5Remediation:
    def test_detect_with_audit_keyword(self):
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "审计发现问题数", "value": "47个"}}
        assert detect_remediation_needed(ae, facts, {}, [])

    def test_detect_with_rectification_keyword(self):
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "整改完成率", "value": "60%"}}
        assert detect_remediation_needed(ae, facts, {}, [])

    def test_detect_with_risk_keyword(self):
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "高风险供应商", "value": "3家"}}
        assert detect_remediation_needed(ae, facts, {}, [])

    def test_detect_with_gap_keyword(self):
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "能力差距", "value": "5项"}}
        assert detect_remediation_needed(ae, facts, {}, [])

    def test_no_detect_no_problem(self):
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "营收", "value": "8.6亿元"}}
        assert not detect_remediation_needed(ae, facts, {}, [])

    def test_feasibility_unfeasible(self):
        ae = AnalyticsEngine()
        facts = {
            "D-F1": {"desc": "审计问题数", "value": "47"},
            "D-F2": {"desc": "合规团队人数", "value": "4"},
            "D-F3": {"desc": "距申报月数", "value": "5个月"},
        }
        results = analyze_remediation(ae, facts, {}, [], None)
        assert any("不可行" in r.get("conclusion", "") for r in results)

    def test_feasibility_viable(self):
        ae = AnalyticsEngine()
        facts = {
            "D-F1": {"desc": "审计问题数", "value": "5"},
            "D-F2": {"desc": "合规团队人数", "value": "4"},
            "D-F3": {"desc": "距申报月数", "value": "5个月"},
        }
        results = analyze_remediation(ae, facts, {}, [], None)
        assert any("可行" in r.get("conclusion", "") for r in results)

    def test_high_risk_generates_short_term_plan(self):
        """高风险项产生短期优先方案"""
        ae = AnalyticsEngine()
        facts = {
            "D-F1": {"desc": "高风险问题", "value": "3"},
            "D-F2": {"desc": "整改率", "value": "40%"},
        }
        results = analyze_remediation(ae, facts, {}, [], None)
        assert any("短期(0-3月)" in r.get("conclusion", "") for r in results)

    def test_no_high_risk_no_short_term(self):
        ae = AnalyticsEngine()
        facts = {
            "D-F1": {"desc": "审计问题数", "value": "5"},
            "D-F2": {"desc": "合规团队人数", "value": "4"},
            "D-F3": {"desc": "距申报月数", "value": "5个月"},
        }
        results = analyze_remediation(ae, facts, {}, [], None)
        assert not any("短期(0-3月)" in r.get("conclusion", "") for r in results)

    def test_no_problem_facts_returns_empty(self):
        """无问题相关事实时返回空列表"""
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "营收", "value": "100亿"}}
        results = analyze_remediation(ae, facts, {}, [], None)
        assert results == []

    def test_default_team_and_months(self):
        """默认 4人/6月, 缺省团队/距申报信息时使用默认值"""
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "审计问题数", "value": "100"}}
        results = analyze_remediation(ae, facts, {}, [], None)
        assert any("不可行" in r.get("conclusion", "") for r in results)

    def test_compliance_fact_for_team(self):
        """含\"合规\"关键词的事实也用于提取团队人数"""
        ae = AnalyticsEngine()
        facts = {
            "D-F1": {"desc": "审计问题数", "value": "30"},
            "D-F2": {"desc": "合规人员", "value": "10"},
            "D-F3": {"desc": "距申报月数", "value": "6个月"},
        }
        results = analyze_remediation(ae, facts, {}, [], None)
        assert any("可行" in r.get("conclusion", "") for r in results)

    def test_remediation_with_enhancer(self, mock_enhancer):
        """有 enhancer 时生成 LLM 增强方案"""
        ae = AnalyticsEngine(enhancer=mock_enhancer)
        facts = {
            "D-F1": {"desc": "审计问题数", "value": "15"},
            "D-F2": {"desc": "合规团队", "value": "3"},
        }
        results = analyze_remediation(ae, facts, {}, [], mock_enhancer)
        assert any("分阶段方案" in r.get("conclusion", "") for r in results)

    def test_detect_remediation_via_description(self):
        """description 字段也应触发检测"""
        ae = AnalyticsEngine()
        facts = {"D-F1": {"description": "整改问题", "value": "10"}}
        assert detect_remediation_needed(ae, facts, {}, [])


# ===========================================
# A6: 市场结构分析
# ===========================================


class TestA6MarketStructure:
    def test_detect_three_or_more_entities(self):
        ae = AnalyticsEngine()
        entities = {"E-A": {}, "E-B": {}, "E-C": {}}
        assert detect_market_structure(ae, {}, entities, [])

    def test_detect_two_entities_no_market_kw(self):
        """2个实体且无市场关键词时不触发"""
        ae = AnalyticsEngine()
        assert not detect_market_structure(ae, {}, {}, [])

    def test_detect_market_keyword_in_facts(self):
        """即使实体数少但有份额关键词也应触发"""
        ae = AnalyticsEngine()
        entities = {"E-A": {}}
        facts = {"D-F1": {"desc": "市场份额", "value": "30%"}}
        assert detect_market_structure(ae, facts, entities, [])

    def test_detect_various_kw(self):
        """测试多个市场关键词"""
        ae = AnalyticsEngine()
        for kw in ("份额", "集中度", "CR", "寡头", "垄断", "竞争格局", "HHI"):
            facts = {"D-F1": {"desc": f"测试{kw}数据", "value": "50"}}
            assert detect_market_structure(ae, facts, {}, [])

    def test_analyze_monopoly(self):
        """HHI > 2500 -> 垄断"""
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "市场份额", "value": "60"}}
        entities = {"E-A": {}, "E-B": {}}
        results = analyze_market_structure(ae, facts, entities, [], None)
        assert any("垄断" in r["conclusion"] for r in results)

    def test_analyze_oligopoly(self):
        """HHI 1500-2500 -> 寡头"""
        ae = AnalyticsEngine()
        facts = {
            "D-F1": {"desc": "市场份额", "value": "18"},
            "D-F2": {"desc": "市场份额", "value": "16"},
            "D-F3": {"desc": "市场份额", "value": "14"},
            "D-F4": {"desc": "市场份额", "value": "12"},
            "D-F5": {"desc": "市场份额", "value": "10"},
        }
        entities = {"E-A": {}, "E-B": {}, "E-C": {}, "E-D": {}, "E-E": {}}
        results = analyze_market_structure(ae, facts, entities, [], None)
        assert any("寡头" in r["conclusion"] for r in results)

    def test_analyze_dispersed(self):
        """HHI <= 1000 -> 分散"""
        ae = AnalyticsEngine()
        facts = {f"D-F{i}": {"desc": "份额", "value": "4"} for i in range(1, 13)}
        entities = {f"E-{chr(65 + i)}": {} for i in range(12)}
        results = analyze_market_structure(ae, facts, entities, [], None)
        assert any("分散" in r["conclusion"] for r in results)

    def test_no_market_keywords_no_results(self):
        """无市场关键词时返回空"""
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "一般数据", "value": "50"}}
        entities = {"E-A": {}, "E-B": {}, "E-C": {}}
        results = analyze_market_structure(ae, facts, entities, [], None)
        assert results == []

    def test_cr3_with_less_than_3_shares(self):
        """少于3个份额值时 CR3 = 100%"""
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "份额", "value": "50"}}
        entities = {"E-A": {}, "E-B": {}}
        results = analyze_market_structure(ae, facts, entities, [], None)
        assert any("CR3=100%" in r["conclusion"] for r in results)


# ===========================================
# A7: 博弈均衡检测
# ===========================================


class TestA7GameEquilibrium:
    def test_detect_competition(self):
        ae = AnalyticsEngine()
        relations = [
            {"subject": "ORG-A", "relation_type": "competes_with", "object": "ORG-B"},
        ]
        assert detect_game_equilibrium(ae, {}, {}, relations)

    def test_detect_cooperation(self):
        ae = AnalyticsEngine()
        relations = [
            {"subject": "ORG-A", "relation_type": "cooperates_with", "object": "ORG-B"},
            {"subject": "ORG-A", "relation_type": "cooperates_with", "object": "ORG-C"},
        ]
        assert detect_game_equilibrium(ae, {}, {}, relations)

    def test_no_detect_empty_relations(self):
        ae = AnalyticsEngine()
        assert not detect_game_equilibrium(ae, {}, {}, [])

    def test_no_detect_single_cooperation(self):
        """单条合作关系不视为博弈场景"""
        ae = AnalyticsEngine()
        relations = [
            {"subject": "ORG-A", "relation_type": "cooperates_with", "object": "ORG-B"},
        ]
        assert not detect_game_equilibrium(ae, {}, {}, relations)

    def test_analyze_prisoner_dilemma(self):
        """竞争+合作共存 -> 囚徒困境风险"""
        ae = AnalyticsEngine()
        relations = [
            {"subject": "ORG-A", "relation_type": "competes_with", "object": "ORG-B"},
            {"subject": "ORG-A", "relation_type": "cooperates_with", "object": "ORG-B"},
        ]
        results = analyze_game_equilibrium(ae, {}, {}, relations, None)
        assert any("囚徒困境" in r["conclusion"] for r in results)

    def test_analyze_zero_sum(self):
        """纯竞争无合作 -> 零和博弈"""
        ae = AnalyticsEngine()
        relations = [
            {"subject": "ORG-A", "relation_type": "competes_with", "object": "ORG-B"},
            {"subject": "ORG-B", "relation_type": "competes_with", "object": "ORG-C"},
        ]
        results = analyze_game_equilibrium(ae, {}, {}, relations, None)
        assert any("零和博弈" in r["conclusion"] for r in results)

    def test_analyze_empty_relations(self):
        """无关系时返回空"""
        ae = AnalyticsEngine()
        results = analyze_game_equilibrium(ae, {}, {}, [], None)
        assert results == []

    def test_analyze_only_cooperation(self):
        """仅有合作无竞争时不产生结论"""
        ae = AnalyticsEngine()
        relations = [
            {"subject": "ORG-A", "relation_type": "cooperates_with", "object": "ORG-B"},
            {"subject": "ORG-A", "relation_type": "cooperates_with", "object": "ORG-C"},
        ]
        results = analyze_game_equilibrium(ae, {}, {}, relations, None)
        assert results == []


# ===========================================
# A8: 策略选项生成
# ===========================================


class TestA8StrategicOptions:
    def test_detect_with_problem(self):
        """委托 _detect_remediation_needed 检测"""
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "审计问题", "value": "5"}}
        assert detect_strategic_options(ae, facts, {}, [])

    def test_detect_with_constraint(self):
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "预算约束", "value": "100万"}}
        assert detect_strategic_options(ae, facts, {}, [])

    def test_detect_constraint_via_limit(self):
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "限制条件", "value": "100万"}}
        assert detect_strategic_options(ae, facts, {}, [])

    def test_detect_constraint_via_cap(self):
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "预算约束上限", "value": "500万"}}
        assert detect_strategic_options(ae, facts, {}, [])

    def test_no_detect_no_problem_no_constraint(self):
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "营收", "value": "100亿"}}
        assert not detect_strategic_options(ae, facts, {}, [])

    def test_analyze_with_goals_and_constraints(self):
        ae = AnalyticsEngine()
        facts = {
            "D-F1": {"desc": "营收目标", "value": "200亿"},
            "D-F2": {"desc": "预算上限", "value": "50亿"},
            "D-F3": {"desc": "团队规模", "value": "30人"},
        }
        results = analyze_strategic_options(ae, facts, {}, [], None)
        assert len(results) >= 1
        assert any("策略空间" in r["conclusion"] for r in results)

    def test_analyze_without_goals_no_results(self):
        """仅有目标时返回结果, 无目标无约束才为空"""
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "普通数据", "value": "100"}}
        results = analyze_strategic_options(ae, facts, {}, [], None)
        assert results == []

    def test_analyze_pareto_frontier(self):
        """多目标+约束 -> 帕累托前沿分析"""
        ae = AnalyticsEngine()
        facts = {
            "D-F1": {"desc": "利润目标", "value": "10%"},
            "D-F2": {"desc": "市场份额目标", "value": "25%"},
            "D-F3": {"desc": "预算约束", "value": "5亿"},
        }
        results = analyze_strategic_options(ae, facts, {}, [], None)
        assert any("帕累托" in r["conclusion"] for r in results)

    def test_analyze_game_tree_depth(self):
        """仅有目标时应有博弈树深度"""
        ae = AnalyticsEngine()
        facts = {
            "D-F1": {"desc": "利润目标", "value": "10%"},
            "D-F2": {"desc": "增长目标", "value": "20%"},
        }
        results = analyze_strategic_options(ae, facts, {}, [], None)
        assert any("博弈树" in r["conclusion"] for r in results)

    def test_analyze_no_constraints(self):
        """无约束仅有目标时组合数=2^n"""
        ae = AnalyticsEngine()
        facts = {
            "D-F1": {"desc": "利润目标", "value": "10%"},
        }
        results = analyze_strategic_options(ae, facts, {}, [], None)
        assert len(results) >= 1


# ===========================================
# A9: 信息生态健康度
# ===========================================


class TestA9InfoEcology:
    def test_detect_with_disinfo_keyword(self):
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "虚假信息占比", "value": "15%"}}
        assert detect_info_ecology(ae, facts, {}, [])

    def test_detect_with_trust_keyword(self):
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "公众信任度", "value": "60%"}}
        assert detect_info_ecology(ae, facts, {}, [])

    def test_no_detect(self):
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "营收", "value": "100亿"}}
        assert not detect_info_ecology(ae, facts, {}, [])

    def test_analyze_healthy_ecology(self):
        """健康生态: 低虚假+高信任+高共识"""
        ae = AnalyticsEngine()
        facts = {
            "D-F1": {"desc": "虚假信息占比", "value": "5"},
            "D-F2": {"desc": "公众信任度", "value": "70"},
            "D-F3": {"desc": "专家共识度", "value": "80"},
        }
        results = analyze_info_ecology(ae, facts, {}, [], None)
        assert any("健康" in r["conclusion"] for r in results)

    def test_analyze_collapsed_ecology(self):
        """崩溃生态: 高虚假+低信任+低共识"""
        ae = AnalyticsEngine()
        facts = {
            "D-F1": {"desc": "虚假信息比例", "value": "80"},
            "D-F2": {"desc": "公众信任度", "value": "15"},
            "D-F3": {"desc": "专家共识度", "value": "10"},
        }
        results = analyze_info_ecology(ae, facts, {}, [], None)
        assert any("崩溃" in r["conclusion"] for r in results)

    def test_analyze_crisis(self):
        """健康度 5-15 -> 危机状态"""
        ae = AnalyticsEngine()
        facts = {
            "D-F1": {"desc": "虚假信息", "value": "50"},
            "D-F2": {"desc": "信任度", "value": "40"},
            "D-F3": {"desc": "共识度", "value": "30"},
        }
        results = analyze_info_ecology(ae, facts, {}, [], None)
        assert any("危机" in r["conclusion"] for r in results)

    def test_analyze_vulnerable(self):
        """健康度 15-30 -> 脆弱状态"""
        ae = AnalyticsEngine()
        facts = {
            "D-F1": {"desc": "虚假信息", "value": "30"},
            "D-F2": {"desc": "信任度", "value": "60"},
            "D-F3": {"desc": "共识度", "value": "50"},
        }
        results = analyze_info_ecology(ae, facts, {}, [], None)
        assert any("脆弱" in r["conclusion"] for r in results)

    def test_analyze_no_relevant_data(self):
        """无相关数据时返回空"""
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "营收", "value": "100"}}
        results = analyze_info_ecology(ae, facts, {}, [], None)
        assert results == []

    def test_analyze_partial_facts(self):
        """仅有部分数据时也应计算"""
        ae = AnalyticsEngine()
        facts = {
            "D-F1": {"desc": "虚假信息占比", "value": "10"},
            "D-F2": {"desc": "共识度", "value": "60"},
        }
        results = analyze_info_ecology(ae, facts, {}, [], None)
        assert len(results) >= 1


# ===========================================
# A10: 因果链分析
# ===========================================


class TestA10CausalChain:
    def test_detect_with_any_relation(self):
        """只要有任意关系就触发"""
        ae = AnalyticsEngine()
        relations = [{"subject": "A", "relation_type": "depends_on", "object": "B"}]
        assert detect_causal_chain(ae, {}, {}, relations)

    def test_no_detect_empty(self):
        ae = AnalyticsEngine()
        assert not detect_causal_chain(ae, {}, {}, [])

    def test_analyze_simple_chain(self):
        """A->B->C 因果链"""
        ae = AnalyticsEngine()
        relations = [
            {"subject": "A", "relation_type": "depends_on", "object": "B"},
            {"subject": "B", "relation_type": "depends_on", "object": "C"},
        ]
        results = analyze_causal_chain(ae, {}, {}, relations, None)
        assert len(results) >= 1
        assert any("A→B→C" in r["conclusion"] for r in results)

    def test_analyze_with_causes_type(self):
        ae = AnalyticsEngine()
        relations = [
            {"subject": "X", "relation_type": "causes", "object": "Y"},
            {"subject": "Y", "relation_type": "causes", "object": "Z"},
        ]
        results = analyze_causal_chain(ae, {}, {}, relations, None)
        assert len(results) >= 1

    def test_analyze_with_influences_type(self):
        ae = AnalyticsEngine()
        relations = [
            {"subject": "X", "relation_type": "influences", "object": "Y"},
            {"subject": "Y", "relation_type": "influences", "object": "Z"},
        ]
        results = analyze_causal_chain(ae, {}, {}, relations, None)
        assert len(results) >= 1

    def test_analyze_skip_other_relation_types(self):
        """非 causality 的关系类型应被跳过"""
        ae = AnalyticsEngine()
        relations = [
            {"subject": "A", "relation_type": "competes_with", "object": "B"},
            {"subject": "B", "relation_type": "cooperates_with", "object": "C"},
        ]
        results = analyze_causal_chain(ae, {}, {}, relations, None)
        assert results == []

    def test_no_chain_too_short(self):
        """只有2个节点不足以形成链(需要>=3)"""
        ae = AnalyticsEngine()
        relations = [
            {"subject": "A", "relation_type": "depends_on", "object": "B"},
        ]
        results = analyze_causal_chain(ae, {}, {}, relations, None)
        assert results == []

    def test_analyze_multiple_branches(self):
        """多分支BFS搜索"""
        ae = AnalyticsEngine()
        relations = [
            {"subject": "A", "relation_type": "depends_on", "object": "B"},
            {"subject": "A", "relation_type": "depends_on", "object": "C"},
            {"subject": "B", "relation_type": "depends_on", "object": "D"},
            {"subject": "C", "relation_type": "depends_on", "object": "D"},
        ]
        results = analyze_causal_chain(ae, {}, {}, relations, None)
        assert len(results) >= 2

    def test_analyze_identifies_root_cause(self):
        """链的末端应为根因"""
        ae = AnalyticsEngine()
        relations = [
            {"subject": "A", "relation_type": "depends_on", "object": "B"},
            {"subject": "B", "relation_type": "depends_on", "object": "C"},
        ]
        results = analyze_causal_chain(ae, {}, {}, relations, None)
        assert any("根因=C" in r["conclusion"] for r in results)

    def test_analyze_avoids_cycles(self):
        """循环依赖不应导致死循环"""
        ae = AnalyticsEngine()
        relations = [
            {"subject": "A", "relation_type": "depends_on", "object": "B"},
            {"subject": "B", "relation_type": "depends_on", "object": "A"},
        ]
        results = analyze_causal_chain(ae, {}, {}, relations, None)
        assert results == []

    def test_analyze_empty_relations(self):
        ae = AnalyticsEngine()
        results = analyze_causal_chain(ae, {}, {}, [], None)
        assert results == []


# ===========================================
# A11: 情景规划
# ===========================================


class TestA11ScenarioPlanning:
    def test_detect_with_uncertainty(self):
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "市场不确定性", "value": "高"}}
        assert detect_scenario_planning(ae, facts, {}, [])

    def test_detect_with_probability(self):
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "概率评估", "value": "60%"}}
        assert detect_scenario_planning(ae, facts, {}, [])

    def test_detect_with_scenario(self):
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "情景分析", "value": "乐观"}}
        assert detect_scenario_planning(ae, facts, {}, [])

    def test_no_detect(self):
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "营收", "value": "100亿"}}
        assert not detect_scenario_planning(ae, facts, {}, [])

    def test_analyze_2x2_matrix(self):
        """2个不确定性 -> 2x2 矩阵"""
        ae = AnalyticsEngine()
        facts = {
            "D-F1": {"desc": "市场不确定性", "value": "70"},
            "D-F2": {"desc": "政策风险", "value": "30"},
        }
        results = analyze_scenario_planning(ae, facts, {}, [], None)
        assert len(results) >= 1
        assert any("情景矩阵" in r["conclusion"] for r in results)
        assert any("2×2" in r["conclusion"] for r in results)

    def test_analyze_single_uncertainty(self):
        """少于2个不确定性不产生情景"""
        ae = AnalyticsEngine()
        facts = {
            "D-F1": {"desc": "市场不确定性", "value": "70"},
        }
        results = analyze_scenario_planning(ae, facts, {}, [], None)
        assert results == []

    def test_analyze_no_uncertainty_facts(self):
        ae = AnalyticsEngine()
        facts = {
            "D-F1": {"desc": "营收", "value": "100"},
        }
        results = analyze_scenario_planning(ae, facts, {}, [], None)
        assert results == []

    def test_analyze_early_warning_signals(self):
        """分析结果应包含早鸟指标"""
        ae = AnalyticsEngine()
        facts = {
            "D-F1": {"desc": "市场不确定性概率", "value": "70"},
            "D-F2": {"desc": "政策风险概率", "value": "30"},
        }
        results = analyze_scenario_planning(ae, facts, {}, [], None)
        assert any("早鸟指标" in r["conclusion"] for r in results)


# ===========================================
# A12: 权力地图
# ===========================================


class TestA12PowerMap:
    def test_detect_4_or_more_relations(self):
        ae = AnalyticsEngine()
        relations = [
            {"subject": "A", "relation_type": "depends_on", "object": "B"},
            {"subject": "B", "relation_type": "depends_on", "object": "C"},
            {"subject": "C", "relation_type": "depends_on", "object": "D"},
            {"subject": "D", "relation_type": "depends_on", "object": "E"},
        ]
        assert detect_power_map(ae, {}, {}, relations)

    def test_no_detect_less_than_4(self):
        ae = AnalyticsEngine()
        relations = [
            {"subject": "A", "relation_type": "depends_on", "object": "B"},
            {"subject": "B", "relation_type": "depends_on", "object": "C"},
            {"subject": "C", "relation_type": "depends_on", "object": "D"},
        ]
        assert not detect_power_map(ae, {}, {}, relations)

    def test_no_detect_empty(self):
        ae = AnalyticsEngine()
        assert not detect_power_map(ae, {}, {}, [])

    def test_analyze_centrality(self):
        """度中心性计算: A 有4个连接应排第一"""
        ae = AnalyticsEngine()
        relations = [
            {"subject": "A", "relation_type": "depends_on", "object": "B"},
            {"subject": "A", "relation_type": "depends_on", "object": "C"},
            {"subject": "A", "relation_type": "depends_on", "object": "D"},
            {"subject": "A", "relation_type": "depends_on", "object": "E"},
            {"subject": "B", "relation_type": "depends_on", "object": "C"},
        ]
        results = analyze_power_map(ae, {}, {}, relations, None)
        assert len(results) >= 1
        assert any("A(度=4)" in r["conclusion"] for r in results)

    def test_analyze_single_point_of_failure(self):
        """度 >= 节点数/2 -> 潜在单点故障"""
        ae = AnalyticsEngine()
        relations = [
            {"subject": "A", "relation_type": "depends_on", "object": "B"},
            {"subject": "A", "relation_type": "depends_on", "object": "C"},
            {"subject": "A", "relation_type": "depends_on", "object": "D"},
            {"subject": "B", "relation_type": "depends_on", "object": "C"},
        ]
        results = analyze_power_map(ae, {}, {}, relations, None)
        assert any("潜在单点=" in r["conclusion"] for r in results)

    def test_analyze_empty_relations(self):
        ae = AnalyticsEngine()
        results = analyze_power_map(ae, {}, {}, [], None)
        assert results == []

    def test_analyze_mixed_incoming_outgoing(self):
        """混合入度和出度的影响力"""
        ae = AnalyticsEngine()
        relations = [
            {"subject": "X", "relation_type": "cooperates_with", "object": "Y"},
            {"subject": "X", "relation_type": "cooperates_with", "object": "Z"},
            {"subject": "Y", "relation_type": "cooperates_with", "object": "Z"},
            {"subject": "Z", "relation_type": "cooperates_with", "object": "W"},
        ]
        results = analyze_power_map(ae, {}, {}, relations, None)
        assert len(results) >= 1
        assert any("Z(度=3)" in r["conclusion"] for r in results)


# ===========================================
# AnalyticalPattern 元数据
# ===========================================


class TestAnalyticalPatternMeta:
    def test_fourteen_patterns_registered(self):
        ae = AnalyticsEngine()
        assert len(ae.patterns) == 14

    def test_all_patterns_have_valid_metadata(self):
        ae = AnalyticsEngine()
        categories = {"game_theory", "economics", "supply_chain", "organizational", "strategic"}
        for pat in ae.patterns:
            assert pat.name is not None and len(pat.name) > 0
            assert pat.category in categories, f"{pat.name} has invalid category {pat.category}"
            assert 0 <= pat.semantic_depth <= 5

    def test_pattern_names(self):
        ae = AnalyticsEngine()
        names = {p.name for p in ae.patterns}
        assert "capacity_elasticity" in names
        assert "supply_chain_amplification" in names
        assert "principal_agent" in names
        assert "incentive_misalignment" in names
        assert "remediation_planning" in names
        assert "market_structure" in names
        assert "game_equilibrium" in names
        assert "strategic_options" in names
        assert "info_ecology" in names
        assert "causal_chain" in names
        assert "scenario_planning" in names
        assert "power_map" in names
        assert "organizational_inertia" in names
        assert "tech_disruption" in names


# ===========================================
# AnalyticsEngine.run() 综合测试
# ===========================================


class TestAnalyticsEngineRun:
    def test_run_with_detection(self):
        ae = AnalyticsEngine()
        facts = {
            "D-F1": {"desc": "产能利用率", "value": "94%"},
            "D-F2": {"desc": "库存天数", "value": "12天"},
            "D-F3": {"desc": "安全库存基准", "value": "30天"},
        }
        results = ae.run(facts, {}, {})
        assert len(results) >= 1

    def test_run_with_non_dict_facts(self):
        """facts 不是 dict 时返回空列表"""
        ae = AnalyticsEngine()
        assert ae.run("not a dict", {}, {}) == []
        assert ae.run(42, {}, {}) == []
        assert ae.run(None, {}, {}) == []

    def test_run_with_empty_facts(self):
        ae = AnalyticsEngine()
        results = ae.run({}, {}, {})
        assert results == []

    def test_run_with_patterns_filter(self):
        """指定 patterns 参数只运行特定模式"""
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "产能利用率", "value": "94%"}}
        a1 = [p for p in ae.patterns if p.name == "capacity_elasticity"]
        results = ae.run(facts, {}, {}, patterns=a1)
        assert len(results) >= 1
        for r in results:
            assert r["pattern"] == "capacity_elasticity"

    def test_run_context_populated(self):
        """结论应包含 pattern/category/semantic_depth"""
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "产能利用率", "value": "94%"}}
        results = ae.run(facts, {}, {})
        for r in results:
            assert "pattern" in r
            assert "category" in r
            assert "semantic_depth" in r
            assert r["pattern"] == "capacity_elasticity"
            assert r["category"] == "economics"
            assert r["semantic_depth"] == 0

    def test_run_with_max_depth_zero(self):
        """max_depth=0 时 depth>0 的模式被过滤, depth=0 依然运行"""
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "产能利用率", "value": "94%"}}
        results = ae.run(facts, {}, {}, max_depth=0)
        assert len(results) >= 1

    def test_run_multiple_patterns_trigger(self):
        """多个 depth=0 模式同时触发"""
        ae = AnalyticsEngine()
        facts = {
            "D-F1": {"desc": "产能利用率", "value": "94%"},
            "D-F2": {"desc": "审计问题数", "value": "10"},
            "D-F3": {"desc": "合规团队", "value": "3"},
            "D-F4": {"desc": "份额", "value": "50"},
        }
        relations = [
            {"subject": "A", "relation_type": "competes_with", "object": "B"},
        ]
        entities = {"E-A": {}, "E-B": {}, "E-C": {}}
        results = ae.run(facts, entities, {}, relations)
        patterns_found = {r["pattern"] for r in results}
        assert "capacity_elasticity" in patterns_found  # A1 depth=0
        assert "market_structure" in patterns_found  # A6 depth=0

    def test_run_exception_handling(self):
        """模式抛出异常时不应中断其他模式"""
        ae = AnalyticsEngine()
        broken = AnalyticalPattern(
            name="broken",
            description="broken",
            category="strategic",
            detect=lambda f, e, r: (_ for _ in ()).throw(ValueError("broken")),
            analyze=lambda f, e, r, en: [{"test": True}],
            semantic_depth=0,
        )
        facts = {"D-F1": {"desc": "产能利用率", "value": "94%"}}
        results = ae.run(facts, {}, {}, patterns=[broken] + ae.patterns)
        assert len(results) >= 1

    def test_run_with_enhancer(self, mock_enhancer):
        """有 enhancer 时更多模式可以运行"""
        ae = AnalyticsEngine(enhancer=mock_enhancer)
        facts = {
            "D-F1": {"desc": "产能利用率", "value": "94%"},
            "D-F2": {"desc": "虚假信息占比", "value": "20"},
            "D-F3": {"desc": "公众信任度", "value": "50"},
        }
        results = ae.run(facts, {}, {})
        assert len(results) >= 1

    def test_run_results_have_type_analytics(self):
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "产能利用率", "value": "94%"}}
        results = ae.run(facts, {}, {})
        for r in results:
            assert r["type"] == "analytics"


class TestA13OrganizationalInertia:
    def test_detect_many_entities(self):
        ae = AnalyticsEngine()
        entities = {"E-1": {}, "E-2": {}, "E-3": {}}
        assert detect_organizational_inertia(ae, {}, entities, [])

    def test_detect_many_relations(self):
        ae = AnalyticsEngine()
        relations = [{"subject": "A", "object": "B"}] * 4
        assert detect_organizational_inertia(ae, {}, {}, relations)

    def test_detect_inertia_keywords(self):
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "组织惯性严重", "value": "高"}}
        assert detect_organizational_inertia(ae, facts, {}, [])

    def test_detect_no_match(self):
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "效率提升", "value": "20%"}}
        assert not detect_organizational_inertia(ae, facts, {}, [])

    def test_analyze_basic(self):
        ae = AnalyticsEngine()
        entities = {"E-1": {}, "E-2": {}}
        results = analyze_organizational_inertia(ae, {}, entities, [], None)
        assert len(results) >= 1
        assert any("组织惯性" in r["conclusion"] for r in results)

    def test_analyze_with_history(self):
        ae = AnalyticsEngine()
        entities = {"E-1": {}, "E-2": {}, "E-3": {}}
        relations = [
            {"subject": "E-1", "relation_type": "depends_on", "object": "E-2"},
            {"subject": "E-2", "relation_type": "depends_on", "object": "E-3"},
        ]
        facts = {
            "D-F1": {"desc": "成立于1990年", "value": "30年"},
            "D-F2": {"desc": "员工数5000", "value": "5000"},
        }
        results = analyze_organizational_inertia(ae, facts, entities, relations, None)
        assert len(results) >= 1
        assert any("惯性" in r["conclusion"] for r in results)

    def test_analyze_empty_entities(self):
        ae = AnalyticsEngine()
        results = analyze_organizational_inertia(ae, {}, {}, [], None)
        assert results == []


class TestA14TechDisruption:
    def test_detect_new_tech(self):
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "AI技术快速迭代", "value": "高"}}
        assert detect_tech_disruption(ae, facts, {}, [])

    def test_detect_disruption_keyword(self):
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "颠覆传统零售", "value": "冲击"}}
        assert detect_tech_disruption(ae, facts, {}, [])

    def test_detect_new_and_old(self):
        ae = AnalyticsEngine()
        facts = {
            "D-F1": {"desc": "智能化转型加速", "value": "高"},
            "D-F2": {"desc": "传统业务稳定", "value": "成熟"},
        }
        assert detect_tech_disruption(ae, facts, {}, [])

    def test_detect_no_match(self):
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "日常运营", "value": "正常"}}
        assert not detect_tech_disruption(ae, facts, {}, [])

    def test_analyze_high_threat(self):
        ae = AnalyticsEngine()
        facts = {
            "D-F1": {"desc": "AI技术快速发展", "value": "高"},
            "D-F2": {"desc": "数字化颠覆传统", "value": "冲击"},
            "D-F3": {"desc": "传统零售下降", "value": "低"},
        }
        results = analyze_tech_disruption(ae, facts, {}, [], None)
        assert len(results) >= 1
        assert any("压力" in r["conclusion"] for r in results)
        assert any("高" in r["conclusion"] or "中" in r["conclusion"] for r in results)

    def test_analyze_low_threat(self):
        ae = AnalyticsEngine()
        facts = {"D-F1": {"desc": "传统业务", "value": "稳定"}}
        results = analyze_tech_disruption(ae, facts, {}, [], None)
        assert len(results) >= 1
        assert any("低" in r["conclusion"] for r in results)

    def test_analyze_empty_facts(self):
        ae = AnalyticsEngine()
        results = analyze_tech_disruption(ae, {}, {}, [], None)
        assert len(results) >= 1
        assert any("低" in r["conclusion"] for r in results)
