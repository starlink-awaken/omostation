"""
SSOT Kernel — Test Data Generators
====================================
测试数据生成器模块

功能：
1. 生成大规模测试数据（实体、事实、规则、关系）
2. 生成特定场景的测试数据（矛盾检测、复杂依赖等）
3. 确保生成的数据有效且可验证
"""

import random
from datetime import datetime, timedelta

from ..meta_model import (
    Confidence,
    DomainConfig,
    Entity,
    Fact,
    Inference,
    MetaType,
    Relation,
    Rule,
)


class TestDataGenerator:
    """
    测试数据生成器

    功能：
    1. 生成随机但有效的领域数据
    2. 生成特定场景的测试数据
    3. 确保数据的一致性和完整性
    """

    def __init__(self):
        # 实体类型和属性模板
        self.entity_templates = {
            "ORG": {
                "prefix": "ORG",
                "types": ["Organization", "Institution", "Center"],
                "attributes": ["mechanism", "status", "funding", "scale", "location"],
            },
            "ROL": {
                "prefix": "ROL",
                "types": ["Role", "Position", "Function"],
                "attributes": ["responsibility", "authority", "department", "level"],
            },
            "PRJ": {
                "prefix": "PRJ",
                "types": ["Project", "Initiative", "Program"],
                "attributes": ["status", "phase", "budget", "timeline", "owner"],
            },
            "RES": {
                "prefix": "RES",
                "types": ["Resource", "Asset", "Equipment"],
                "attributes": ["type", "availability", "location", "capacity"],
            },
        }

        # 事实数据模板
        self.fact_templates = {
            "DAT": {
                "prefix": "DAT",
                "types": ["quantity", "percentage", "count", "metric"],
                "units": ["项", "个", "人", "万元", "%", "MB", "GB"],
            }
        }

        # 规则模式模板
        self.rule_patterns = [
            {
                "pattern": "contradiction",
                "condition_template": 'entity_attr("{entity_id}", "{attr}") == "{value}"',
                "logic_template": "检测到{entity_id}的{attr}为{value}，需要相应解决方案",
            },
            {
                "pattern": "consistency",
                "condition_template": 'entity_exists("{prefix}", "{keyword}")',
                "logic_template": "检查{prefix}类型实体中是否存在{keyword}",
            },
            {
                "pattern": "theory_match",
                "condition_template": 'fact_ratio("{fact_a}", "{fact_b}") > {threshold}',
                "logic_template": "{fact_a}与{fact_b}的比例超过{threshold}，匹配相关理论",
            },
            {
                "pattern": "capability_gap",
                "condition_template": 'entity_attr("{entity_id}", "{attr}") in "{expected}"',
                "logic_template": "{entity_id}缺少{attr}能力，需要进行补充",
            },
        ]

        # 常用词汇
        self.vocabulary = {
            "mechanism": ["双轨", "单轨", "并行", "串行"],
            "status": ["active", "pending", "completed", "failed"],
            "funding": ["自筹", "拨款", "混合"],
            "scale": ["大型", "中型", "小型"],
            "location": ["北京", "上海", "广州", "深圳"],
            "responsibility": ["全面负责", "部分负责", "协助", "监督"],
            "department": ["技术部", "市场部", "运营部", "财务部"],
            "level": ["高级", "中级", "初级"],
            "phase": ["规划", "设计", "开发", "测试", "部署"],
            "type": ["硬件", "软件", "服务", "数据"],
        }

    def generate_test_domain(
        self,
        entity_count: int = 100,
        fact_count: int = 200,
        rule_count: int = 500,
        inference_count: int = 50,
        relation_count: int = 20,
    ) -> DomainConfig:
        """生成标准测试领域数据"""

        domain = DomainConfig()
        domain.domain = {
            "name": "performance_test_domain",
            "version": "1.0",
            "description": "自动生成的性能测试领域数据",
            "created": datetime.now().isoformat(),
        }

        # 生成实体
        domain.entities = self._generate_entities(entity_count)

        # 生成事实
        domain.facts = self._generate_facts(fact_count)

        # 生成推论
        domain.inferences = self._generate_inferences(
            inference_count, domain.entities, domain.facts
        )

        # 生成规则
        domain.rules = self._generate_rules(rule_count, domain.entities, domain.facts)

        # 生成关系
        domain.relations = self._generate_relations(relation_count, domain.entities)

        return domain

    def _generate_entities(self, count: int) -> list[Entity]:
        """生成实体列表"""
        entities = []

        # 按比例分配不同类型的实体
        type_distribution = {
            "ORG": 0.3,  # 30% 组织
            "ROL": 0.25,  # 25% 角色
            "PRJ": 0.25,  # 25% 项目
            "RES": 0.2,  # 20% 资源
        }

        for prefix, ratio in type_distribution.items():
            count_for_type = max(1, int(count * ratio))
            template = self.entity_templates[prefix]

            for i in range(count_for_type):
                entity_type = random.choice(template["types"])  # noqa: S311
                entity_id = f"{template['prefix']}-{random.randint(1, 10000):04d}"  # noqa: S311

                # 生成属性
                attributes = {}
                for attr_name in template["attributes"]:
                    if attr_name in self.vocabulary:
                        attributes[attr_name] = random.choice(
                            self.vocabulary[attr_name]
                        )  # noqa: S311
                    else:
                        attributes[attr_name] = self._generate_random_value(attr_name)

                entity = Entity(
                    id=entity_id,
                    name=f"测试{prefix}_{i + 1}",
                    meta_type=MetaType.DOMAIN,
                    entity_type=entity_type,
                    status=random.choice(self.vocabulary["status"]),  # noqa: S311
                    attributes=attributes,
                    confidence=Confidence.FACT,
                    source="performance_test_generator",
                )

                entities.append(entity)

        return entities

    def _generate_facts(self, count: int) -> list[Fact]:
        """生成事实列表"""
        facts = []

        # 生成政策事实（10%）
        policy_count = max(1, int(count * 0.1))
        for i in range(policy_count):
            fact = Fact(
                id=f"POL-P-{i + 1:03d}",
                title=f"政策{i + 1}",
                value=random.choice(["批准", "通过", "发布", "修订"]),  # noqa: S311
                source="performance_test_generator",
                date=(
                    datetime.now() - timedelta(days=random.randint(0, 365))
                ).isoformat(),  # noqa: S311
                tags=["policy"],
            )
            facts.append(fact)

        # 生成数据事实（90%）
        data_count = count - policy_count
        template = self.fact_templates["DAT"]

        for i in range(data_count):
            fact = Fact(
                id=f"DAT-D-{i + 1:03d}",
                title=f"数据{i + 1}",
                value=random.randint(1, 1000),  # noqa: S311
                unit=random.choice(template["units"]),  # noqa: S311
                source="performance_test_generator",
                date=(
                    datetime.now() - timedelta(days=random.randint(0, 365))
                ).isoformat(),  # noqa: S311
                tags=["data"],
            )
            facts.append(fact)

        return facts

    def _generate_inferences(
        self, count: int, entities: list[Entity], facts: list[Fact]
    ) -> list[Inference]:
        """生成推论列表"""
        inferences: list[Inference] = []

        if not entities and not facts:
            return inferences

        for i in range(count):
            # 随机选择依赖的实体和事实
            derives_from = []

            if entities and random.random() > 0.3:  # noqa: S311
                entity_refs = random.sample(entities, min(3, len(entities)))
                derives_from.extend([e.id for e in entity_refs])

            if facts and random.random() > 0.3:  # noqa: S311
                fact_refs = random.sample(facts, min(3, len(facts)))
                derives_from.extend([f.id for f in fact_refs])

            inference = Inference(
                id=f"INF-{i + 1:03d}",
                title=f"推论{i + 1}",
                derives_from=derives_from,
                logic=f"基于{len(derives_from)}个前提的推论",
                conclusion=f"推论结论{i + 1}",
                theory=random.choice(["组织理论", "系统理论", "管理理论", "网络理论"]),  # noqa: S311
                confidence=random.choice([Confidence.INFERENCE, Confidence.HYPOTHESIS]),  # noqa: S311
                status=random.choice(["active", "needs_review", "deprecated"]),  # noqa: S311
            )

            inferences.append(inference)

        return inferences

    def _generate_rules(
        self, count: int, entities: list[Entity], facts: list[Fact]
    ) -> list[Rule]:
        """生成规则列表"""
        rules = []

        for i in range(count):
            # 选择规则模式
            pattern_info = random.choice(self.rule_patterns)  # noqa: S311
            pattern = pattern_info["pattern"]

            # 生成前提条件
            premises = []
            premise_count = random.randint(1, 3)  # noqa: S311

            for j in range(premise_count):
                # 替换模板中的占位符
                if entities:
                    entity_id = random.choice(entities).id  # noqa: S311
                else:
                    entity_id = "ORG-0001"

                attr = random.choice(self.vocabulary["mechanism"])  # noqa: S311
                value = random.choice(self.vocabulary["mechanism"])  # noqa: S311

                condition = pattern_info["condition_template"].format(
                    entity_id=entity_id,
                    attr=attr,
                    value=value,
                    prefix="ORG",
                    keyword=random.choice(self.vocabulary["mechanism"]),  # noqa: S311
                    fact_a=f"DAT-D-{random.randint(1, 99):03d}",  # noqa: S311
                    fact_b=f"DAT-D-{random.randint(1, 99):03d}",  # noqa: S311
                    threshold=str(random.random() * 0.5),  # noqa: S311
                    expected="双轨",
                )

                premises.append({"condition": condition})

            # 生成规则
            rule = Rule(
                id=f"R-{pattern.upper()}-{i + 1:03d}",
                pattern=pattern,
                name=f"测试规则{i + 1}",
                premises=premises,
                logic=self._generate_rule_logic(pattern_info, entity_id, attr, value),
                params={
                    "template": "通用模板",
                    "severity": random.choice(["BLOCKER", "ERROR", "WARN"]),
                },  # noqa: S311
            )

            rules.append(rule)

        return rules

    def _generate_relations(self, count: int, entities: list[Entity]) -> list[Relation]:
        """生成关系列表"""
        relations: list[Relation] = []

        if len(entities) < 2:
            return relations

        relation_types = [
            "part_of",
            "depends_on",
            "participates_in",
            "cites",
            "interlocks_with",
        ]

        for i in range(count):
            source = random.choice(entities)  # noqa: S311
            target = random.choice(entities)  # noqa: S311

            # 确保不是自己引用自己
            while target.id == source.id:
                target = random.choice(entities)  # noqa: S311

            relation = Relation(
                source_id=source.id,
                target_id=target.id,
                relation_type=random.choice(relation_types),  # noqa: S311
                confidence=Confidence.FACT,
            )

            relations.append(relation)

        return relations

    def _generate_rule_logic(
        self, pattern_info: dict, entity_id: str, attr: str, value: str
    ) -> str:
        """生成规则逻辑，处理不同的模板格式"""
        template = pattern_info["logic_template"]

        # 检查模板需要的占位符
        placeholders = []
        for key in ["entity_id", "attr", "value", "prefix", "keyword"]:
            if "{" + key + "}" in template:
                placeholders.append(key)

        # 生成参数值
        params = {}
        if "entity_id" in placeholders:
            params["entity_id"] = entity_id
        if "attr" in placeholders:
            params["attr"] = attr
        if "value" in placeholders:
            params["value"] = value
        if "prefix" in placeholders:
            params["prefix"] = "ORG"
        if "keyword" in placeholders:
            params["keyword"] = random.choice(self.vocabulary["mechanism"])  # noqa: S311

        # 安全格式化
        try:
            return template.format(**params)
        except KeyError as e:
            # 如果有缺少的占位符，返回通用逻辑
            return f"检测到相关条件，需要相应解决方案 (规则模板: {e})"

    def _generate_random_value(self, field_name: str) -> str:
        """生成随机值"""
        if "count" in field_name.lower() or "number" in field_name.lower():
            return str(random.randint(1, 1000))  # noqa: S311
        elif "amount" in field_name.lower() or "budget" in field_name.lower():
            return str(random.randint(100, 1000000))  # noqa: S311
        elif "date" in field_name.lower():
            return (
                datetime.now() + timedelta(days=random.randint(-365, 365))
            ).isoformat()  # noqa: S311
        else:
            return f"random_value_{random.randint(1, 1000)}"  # noqa: S311

    def generate_contradiction_test_domain(self, rule_count: int) -> DomainConfig:
        """生成矛盾检测专用测试数据"""
        domain = DomainConfig()
        domain.domain = {
            "name": "contradiction_test_domain",
            "version": "1.0",
            "description": "矛盾检测性能测试专用数据",
        }

        # 生成特定实体（用于矛盾检测）
        entity_count = min(100, rule_count // 5)
        domain.entities = self._generate_contradiction_entities(entity_count)

        # 生成特定事实
        fact_count = min(200, rule_count // 2)
        domain.facts = self._generate_contradiction_facts(fact_count)

        # 生成矛盾检测规则
        domain.rules = self._generate_contradiction_rules(
            rule_count, domain.entities, domain.facts
        )

        return domain

    def _generate_contradiction_entities(self, count: int) -> list[Entity]:
        """生成矛盾检测专用实体"""
        entities = []

        # 生成双轨和单轨两种类型的组织
        for i in range(count):
            mechanism = "双轨" if i % 2 == 0 else "单轨"

            entity = Entity(
                id=f"ORG-TEST-{i + 1:03d}",
                name=f"测试组织{i + 1}",
                meta_type=MetaType.DOMAIN,
                entity_type="Organization",
                status="active",
                attributes={
                    "mechanism": mechanism,
                    "status": "running",
                    "scale": random.choice(["大型", "中型", "小型"]),  # noqa: S311
                },
                confidence=Confidence.FACT,
                source="contradiction_test_generator",
            )

            entities.append(entity)

        return entities

    def _generate_contradiction_facts(self, count: int) -> list[Fact]:
        """生成矛盾检测专用事实"""
        facts = []

        # 生成用于比例计算的事实
        for i in range(count):
            value_a = random.randint(10, 1000)  # noqa: S311
            value_b = random.randint(10, 1000)  # noqa: S311

            fact = Fact(
                id=f"DAT-CONT-{i + 1:03d}",
                title=f"矛盾检测数据{i + 1}",
                value=value_a,
                unit="项",
                source="contradiction_test_generator",
                date=datetime.now().isoformat(),
                tags=["contradiction_test"],
                metadata={"related_fact_b": f"DAT-CONT-{i + 1:03d}-B"},
            )

            # 配对的B事实
            fact_b = Fact(
                id=f"DAT-CONT-{i + 1:03d}-B",
                title=f"矛盾检测数据{i + 1}-B",
                value=value_b,
                unit="项",
                source="contradiction_test_generator",
                date=datetime.now().isoformat(),
                tags=["contradiction_test"],
            )

            facts.extend([fact, fact_b])

        return facts

    def _generate_contradiction_rules(
        self, count: int, entities: list[Entity], facts: list[Fact]
    ) -> list[Rule]:
        """生成矛盾检测规则"""
        rules = []

        for i in range(count):
            # 生成不同类型的矛盾检测条件
            condition_type = random.choice(
                ["mechanism_check", "ratio_check", "existence_check"]
            )  # noqa: S311

            if condition_type == "mechanism_check" and entities:
                entity = random.choice(entities)  # noqa: S311
                condition = f'entity_attr("{entity.id}", "mechanism") == "双轨"'
                logic = f"检测到{entity.name}采用双轨机制，可能导致资源冲突"

            elif condition_type == "ratio_check" and len(facts) >= 2:
                fact_a = random.choice(facts)  # noqa: S311
                fact_b = random.choice(facts)  # noqa: S311
                condition = f'fact_ratio("{fact_a.id}", "{fact_b.id}") < 0.1'
                logic = f"检测到{fact_a.title}与{fact_b.title}比例过低，可能存在问题"

            else:
                condition = 'entity_exists("ORG-", "双轨")'
                logic = "检测到双轨组织存在"

            rule = Rule(
                id=f"R-CONT-{i + 1:03d}",
                pattern="contradiction",
                name=f"矛盾检测规则{i + 1}",
                premises=[{"condition": condition}],
                logic=logic,
                params={
                    "template": "矛盾检测模板",
                    "solutions": ["资源整合", "流程优化", "机制分离"],
                    "severity": random.choice(["BLOCKER", "ERROR", "WARN"]),  # noqa: S311
                },
            )

            rules.append(rule)

        return rules

    def generate_complex_dependency_domain(
        self, entity_count: int = 100, fact_count: int = 200, dependency_depth: int = 5
    ) -> DomainConfig:
        """生成复杂依赖关系测试数据"""
        domain = DomainConfig()
        domain.domain = {
            "name": "complex_dependency_test_domain",
            "version": "1.0",
            "description": f"复杂依赖关系测试，深度{dependency_depth}",
        }

        # 生成实体链
        domain.entities = self._generate_entity_chain(entity_count, dependency_depth)

        # 生成事实链
        domain.facts = self._generate_fact_chain(fact_count, dependency_depth)

        # 生成复杂依赖规则
        domain.rules = self._generate_dependency_rules(
            entity_count, domain.entities, domain.facts, dependency_depth
        )

        return domain

    def _generate_entity_chain(self, count: int, depth: int) -> list[Entity]:
        """生成实体依赖链"""
        entities = []
        chain_length = count // depth

        for chain_id in range(depth):
            for i in range(chain_length):
                # 每个链有层次关系
                entity = Entity(
                    id=f"ORG-CHAIN-{chain_id + 1}-{i + 1:03d}",
                    name=f"依赖链{chain_id + 1}实体{i + 1}",
                    meta_type=MetaType.DOMAIN,
                    entity_type="Organization",
                    status="active",
                    attributes={
                        "chain_id": str(chain_id),
                        "chain_level": str(i),
                        "depends_on_chain": str(chain_id - 1)
                        if chain_id > 0
                        else "root",
                    },
                    confidence=Confidence.FACT,
                    source="dependency_test_generator",
                )

                entities.append(entity)

        return entities

    def _generate_fact_chain(self, count: int, depth: int) -> list[Fact]:
        """生成事实依赖链"""
        facts = []
        chain_length = count // depth

        for chain_id in range(depth):
            for i in range(chain_length):
                # 每个链有数值递增关系
                fact = Fact(
                    id=f"DAT-CHAIN-{chain_id + 1}-{i + 1:03d}",
                    title=f"依赖链{chain_id + 1}数据{i + 1}",
                    value=(chain_id * chain_length + i + 1) * 10,
                    unit="项",
                    source="dependency_test_generator",
                    date=datetime.now().isoformat(),
                    tags=["dependency_chain"],
                    metadata={"chain_id": str(chain_id), "chain_level": str(i)},
                )

                facts.append(fact)

        return facts

    def _generate_dependency_rules(
        self, count: int, entities: list[Entity], facts: list[Fact], depth: int
    ) -> list[Rule]:
        """生成依赖关系检测规则"""
        rules = []

        for i in range(count):
            # 生成跨链依赖检测规则
            chain_a = random.randint(1, depth)  # noqa: S311
            chain_b = random.randint(1, depth)  # noqa: S311

            if chain_a == chain_b:
                chain_b = (chain_a % depth) + 1

            condition = f'entity_attr("ORG-CHAIN-{chain_a}-*", "depends_on_chain") == "{chain_b - 1}"'
            logic = f"检测到链{chain_a}依赖链{chain_b}"

            rule = Rule(
                id=f"R-DEP-{i + 1:03d}",
                pattern="consistency",
                name=f"依赖检测规则{i + 1}",
                premises=[{"condition": condition}],
                logic=logic,
                params={
                    "dependency_depth": depth,
                    "chain_a": chain_a,
                    "chain_b": chain_b,
                },
            )

            rules.append(rule)

        return rules

    def _inject_custom_domain(self, result, domain: DomainConfig):
        """将自定义域数据注入到测试结果中"""
        if hasattr(result, "report") and result.report:
            # 如果需要，可以修改报告中的域数据
            pass


class DomainDataFactory:
    """领域数据工厂 - 专门用于创建特定模式的测试数据"""

    @staticmethod
    def create_standard_medium_dataset() -> DomainConfig:
        """创建标准中等规模数据集"""
        generator = TestDataGenerator()
        return generator.generate_test_domain(
            entity_count=100,
            fact_count=200,
            rule_count=500,
            inference_count=50,
            relation_count=20,
        )

    @staticmethod
    def create_large_dataset() -> DomainConfig:
        """创建大规模数据集"""
        generator = TestDataGenerator()
        return generator.generate_test_domain(
            entity_count=200,
            fact_count=400,
            rule_count=1000,
            inference_count=100,
            relation_count=40,
        )

    @staticmethod
    def create_high_dependency_dataset() -> DomainConfig:
        """创建高依赖关系数据集"""
        generator = TestDataGenerator()
        return generator.generate_complex_dependency_domain(
            entity_count=150, fact_count=300, dependency_depth=8
        )

    @staticmethod
    def create_contradiction_heavy_dataset() -> DomainConfig:
        """创建矛盾检测重型数据集"""
        generator = TestDataGenerator()
        return generator.generate_contradiction_test_domain(rule_count=800)
