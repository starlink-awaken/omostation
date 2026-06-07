"""
SSOT Kernel — config_loader.py
================================
领域配置加载器。将 YAML/Markdown 配置编译为 DomainConfig 数据对象。

支持三种输入模式：
1. YAML 领域目录（推荐）
2. 直接传入 Python dict（编程使用）
3. 兼容 Markdown 前端（从现有 SSOT 迁移）
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .meta_model import (
    Confidence,
    Constraint,
    DomainConfig,
    Entity,
    Fact,
    Inference,
    MetaType,
    Relation,
    Rule,
    StateMachine,
    StateNode,
    Transition,
)


class ConfigLoader:
    """领域配置加载器"""

    CACHE_FILE = ".ssot_cache.json"
    YAML_FILES = ["domain", "entities", "facts", "inferences", "rules", "relations", "machines", "constraints"]

    def __init__(self, domain_dir: str | Path, use_cache: bool = True):
        self.domain_dir = Path(domain_dir)
        self._cache: dict[str, Any] = {}
        self.use_cache = use_cache

    # ── 缓存管理 ──────────────────────────────────────

    @classmethod
    def cache_path(cls, domain_dir: Path) -> Path:
        return domain_dir / cls.CACHE_FILE

    def _cache_fresh(self) -> bool:
        """检查缓存是否仍有效（所有 YAML 文件的 mtime 与缓存一致）"""
        if not self.use_cache:
            return False
        if not self.domain_dir.exists():
            return False
        cp = self.cache_path(self.domain_dir)
        if not cp.exists():
            return False
        try:
            cached = json.loads(cp.read_text("utf-8"))
        except Exception:
            return False
        for name in self.YAML_FILES:
            for ext in [".yaml", ".yml", ".json"]:
                path = self.domain_dir / f"{name}{ext}"
                if path.exists():
                    cached_mtime = cached.get("files", {}).get(name)
                    actual = str(path.stat().st_mtime)
                    if cached_mtime != actual:
                        return False
                    break
        return True

    def _load_from_cache(self) -> DomainConfig | None:
        """从缓存恢复完整的 DomainConfig"""
        if not self.domain_dir.exists():
            return None
        cp = self.cache_path(self.domain_dir)
        if not cp.exists():
            return None
        try:
            cached = json.loads(cp.read_text("utf-8"))
            data = cached.get("data")
            if not data:
                return None

            # 从 JSON 恢复时需要转换字符串 → MetaType 枚举
            def _restore_meta_type(e: dict) -> Entity:
                mt_str = e.pop("meta_type", "MET-DOMAIN")
                try:
                    mt = MetaType.from_str(mt_str)
                except (KeyError, ValueError):
                    mt = MetaType.DOMAIN
                e["meta_type"] = mt
                return Entity(**e)

            def _restore_confidence(obj: dict, field: str) -> None:
                val = obj.get(field)
                if isinstance(val, str):
                    mapping = {
                        "fact": Confidence.FACT,
                        "inference": Confidence.INFERENCE,
                        "hypothesis": Confidence.HYPOTHESIS,
                        "estimated": Confidence.ESTIMATED,
                    }
                    obj[field] = mapping.get(val, Confidence.FACT)

            entities = []
            for e_data in data.get("entities", []):
                _restore_meta_type(e_data)
                _restore_confidence(e_data, "confidence")
                entities.append(Entity(**e_data))

            # StateMachine 的 states/transitions 是嵌套 dataclass，需要递归恢复
            state_machines = []
            for sm_data in data.get("state_machines", []):
                sm_states = [StateNode(**s) for s in sm_data.pop("states", [])]
                sm_transitions = [Transition(**t) for t in sm_data.pop("transitions", [])]
                sm_data["states"] = sm_states
                sm_data["transitions"] = sm_transitions
                state_machines.append(StateMachine(**sm_data))

            return DomainConfig(
                domain=data.get("domain", {}),
                entities=entities,
                facts=[Fact(**f) for f in data.get("facts", [])],
                inferences=[Inference(**i) for i in data.get("inferences", [])],
                rules=[Rule(**r) for r in data.get("rules", [])],
                relations=[Relation(**r) for r in data.get("relations", [])],
                state_machines=state_machines,
                constraints=[Constraint(**c) for c in data.get("constraints", [])],
            )
        except Exception as e:
            print(f"  ⚠️ 缓存恢复失败: {e}")
            return None

    def _save_cache(self, config: DomainConfig) -> None:
        """保存 YAML 文件 mtime + 编译后的 DomainConfig 数据"""
        if not self.domain_dir.exists():
            return
        manifest: dict = {"files": {}, "data": self._config_to_dict(config)}
        for name in self.YAML_FILES:
            for ext in [".yaml", ".yml", ".json"]:
                path = self.domain_dir / f"{name}{ext}"
                if path.exists():
                    manifest["files"][name] = str(path.stat().st_mtime)
                    break
        cp = self.cache_path(self.domain_dir)
        cp.write_text(json.dumps(manifest, indent=2, default=str), "utf-8")

    @staticmethod
    def _config_to_dict(config: DomainConfig) -> dict:
        """将 DomainConfig 序列化为可 JSON 序列化的字典"""
        from dataclasses import asdict

        return {
            "domain": config.domain,
            "entities": [asdict(e) for e in config.entities],
            "facts": [asdict(f) for f in config.facts],
            "inferences": [asdict(i) for i in config.inferences],
            "rules": [asdict(r) for r in config.rules],
            "relations": [asdict(r) for r in config.relations],
            "state_machines": [asdict(sm) for sm in config.state_machines],
            "constraints": [asdict(c) for c in config.constraints],
        }

    def load(self) -> DomainConfig:
        """从领域目录加载完整配置（支持缓存）"""
        if not self.domain_dir.exists():
            raise FileNotFoundError(f"领域目录不存在: {self.domain_dir}")

        if self._cache_fresh():
            cached = self._load_from_cache()
            if cached:
                print("  ⚡ 缓存命中，从缓存恢复")
                return cached

        config = DomainConfig()
        errors: list[str] = []

        config.domain = self._load_yaml("domain") or {}
        domain_meta = config.domain.get("domain", config.domain)
        config.domain = domain_meta if isinstance(domain_meta, dict) else {"name": str(domain_meta)}

        entities_raw = self._load_yaml("entities") or {"entities": []}
        config.entities = [self._parse_entity(e) for e in entities_raw.get("entities", [])]
        self._deduplicate(config.entities, "实体")

        facts_raw = self._load_yaml("facts") or {}
        config.facts = [self._parse_fact(f, "policy") for f in facts_raw.get("policy", [])]
        config.facts += [self._parse_fact(f, "data") for f in facts_raw.get("data", [])]
        self._deduplicate(config.facts, "事实")

        config.inferences = [
            self._parse_inference(i) for i in (self._load_yaml("inferences") or {}).get("inferences", [])
        ]
        self._deduplicate(config.inferences, "推论")

        rules_raw = self._load_yaml("rules") or {"rules": []}
        config.rules = [self._parse_rule(r) for r in rules_raw.get("rules", [])]

        rels_raw = self._load_yaml("relations") or {"relations": []}
        config.relations = [self._parse_relation(r) for r in rels_raw.get("relations", [])]

        machines_raw = self._load_yaml("machines") or {"machines": []}
        config.state_machines = [self._parse_machine(m) for m in machines_raw.get("machines", [])]

        constraints_raw = self._load_yaml("constraints") or {"constraints": []}
        config.constraints = [self._parse_constraint(c) for c in constraints_raw.get("constraints", [])]

        # Schema 校验
        from .meta_model import validate_yaml_schema

        for yaml_name in ["domain", "entities", "facts", "inferences", "rules", "relations", "machines", "constraints"]:
            raw = self._cache.get(yaml_name)
            if raw is None:
                continue
            schema_errors = validate_yaml_schema(yaml_name, raw)
            for err in schema_errors:
                print(f"  ⚠️ [Schema] {yaml_name}.yaml: {err}")
                errors.append(f"{yaml_name}.yaml: {err}")
        if errors:
            print(f"  📋 共 {len(errors)} 条 Schema 校验提示")

        # 跨文件引用校验
        from .meta_model import validate_cross_references

        ref_errors = validate_cross_references(config)
        for err in ref_errors:
            print(f"  ❌ [引用] {err}")
        if ref_errors:
            errors.extend(ref_errors)
            print(f"  📋 共 {len(ref_errors)} 条引用断裂（请修复后重试）")

        # 保存缓存（含完整编译数据）
        self._save_cache(config)

        return config

    def _load_yaml(self, name: str) -> dict | None:
        """加载 YAML 文件（支持 YAML 和 JSON 格式）"""
        if name in self._cache:
            return self._cache[name]

        for ext in [".yaml", ".yml", ".json"]:
            path = self.domain_dir / f"{name}{ext}"
            if path.exists():
                content = path.read_text("utf-8")
                try:
                    if ext == ".json":
                        data = json.loads(content)
                    else:
                        import yaml

                        data = yaml.safe_load(content)
                    self._cache[name] = data
                    return data
                except Exception:
                    return None
        return None

    def _parse_entity(self, data: dict) -> Entity:
        meta_type_str = data.get("meta_type", "MET-DOMAIN")
        try:
            meta_type = MetaType.from_str(meta_type_str)
        except (KeyError, ValueError):
            meta_type = MetaType.DOMAIN

        return Entity(
            id=data.get("id", ""),
            name=data.get("name", data.get("id", "")),
            meta_type=meta_type,
            entity_type=data.get("type", "unknown"),
            status=data.get("status", "active"),
            attributes=data.get("attributes", {}),
            confidence=self._parse_confidence(data.get("confidence", "fact")),
            source=data.get("source", ""),
            metadata=data.get("metadata", {}),
        )

    def _parse_fact(self, data: dict, fact_type: str) -> Fact:
        return Fact(
            id=data.get("id", ""),
            title=data.get("title", data.get("name", "")),
            value=data.get("value"),
            unit=data.get("unit", ""),
            source=data.get("source", ""),
            date=data.get("date", ""),
            tags=[fact_type] + data.get("tags", []),
            warnings=data.get("warnings", data.get("⚠", [])),
        )

    def _parse_inference(self, data: dict) -> Inference:
        return Inference(
            id=data.get("id", ""),
            title=data.get("title", data.get("name", "")),
            derives_from=data.get("derives_from", []),
            logic=data.get("logic", ""),
            conclusion=data.get("conclusion", ""),
            theory=data.get("theory", ""),
            status=data.get("status", "active"),
            confidence=self._parse_confidence(data.get("confidence", "inference")),
            attributes=data.get("attributes", {}),
        )

    def _parse_rule(self, data: dict) -> Rule:
        return Rule(
            id=data.get("id", ""),
            pattern=data.get("pattern", "contradiction"),
            name=data.get("name", ""),
            premises=data.get("premises", []),
            logic=data.get("logic", ""),
            params=data.get("params", {}),
            output=data.get("output", {}),
        )

    def _parse_relation(self, data: dict) -> Relation:
        return Relation(
            source_id=data.get("source_id", data.get("from", "")),
            target_id=data.get("target_id", data.get("to", "")),
            relation_type=data.get("relation_type", data.get("type", "")),
            attributes=data.get("attributes", {}),
        )

    def _parse_machine(self, data: dict) -> StateMachine:
        states = [StateNode(**s) for s in data.get("states", [])]
        transitions = [Transition(**t) for t in data.get("transitions", [])]
        return StateMachine(
            id=data.get("id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            states=states,
            transitions=transitions,
        )

    def _parse_constraint(self, data: dict) -> Constraint:
        return Constraint(
            id=data.get("id", ""),
            name=data.get("name", ""),
            severity=data.get("severity", "WARN"),
            category=data.get("category", ""),
            check_type=data.get("check_type", ""),
            expectation=data.get("expectation", ""),
            target_paths=data.get("target_paths", []),
        )

    def _parse_confidence(self, val: str) -> Confidence:
        mapping = {
            "fact": Confidence.FACT,
            "inference": Confidence.INFERENCE,
            "hypothesis": Confidence.HYPOTHESIS,
            "estimated": Confidence.ESTIMATED,
        }
        return mapping.get(val.lower(), Confidence.FACT)

    def _deduplicate(self, items: list, label: str):
        """P1 fix: 检测并拒绝重复 ID。重复项会被移除并打印警告。"""
        seen: dict[str, int] = {}
        to_remove = []
        for i, item in enumerate(items):
            item_id = getattr(item, "id", "") or str(item)
            if not item_id:
                continue
            if item_id in seen:
                print(f"  ⚠️ [P1] 重复{label} ID: '{item_id}' (第{i + 1}项覆盖第{seen[item_id] + 1}项)")
                to_remove.append(seen[item_id])
            seen[item_id] = i
        if to_remove:
            for idx in sorted(to_remove, reverse=True):
                items.pop(idx)


def load_domain(domain_dir: str | Path, use_cache: bool = True) -> DomainConfig:
    """便捷函数：一行代码加载领域配置

    Args:
        domain_dir: 领域目录路径
        use_cache: 是否使用缓存（文件 mtime 不变时跳过加载）
    """
    loader = ConfigLoader(domain_dir, use_cache=use_cache)
    return loader.load()
