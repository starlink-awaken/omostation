"""M3MetaLoader — meta_model.py ↔ m3.yaml 桥接器 (M4 Phase 2.2, ADR-0132 P2-S2)

设计: 双轨桥接 (D3)
  - meta_model.py (Python) 作为 Single Source of Truth for runtime enum
  - m3.yaml + m3-meta.yaml (YAML) 作为 Single Source of Truth for schema
  - M3MetaLoader 把两者加载到内存,提供统一的 query API

API:
  - meta_type_to_m3(meta_type) -> m3 Element id
  - m3_to_meta_type(m3_id) -> MetaType enum
  - check_meta_relation_allowed(source, target, relation) -> bool
  - get_meta_relation_matrix() -> dict
  - get_layer_architecture() -> dict
  - compute_meta_confidence(entities) -> float

约束:
  - meta_model.py 不动 (read-only)
  - m3.yaml 不动
  - m3-meta.yaml 只读
  - 本文件 API 兼容: 当 meta_model.py 内部重构时, 这里用 m3_implements
    字段反向解析, 不依赖 import path
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


# 兼容 meta_model.py (lazy import 避免强依赖)
def _import_meta_model():
    try:
        # meta_model.py 在 src/ecos/l0/ssot/meta_model.py
        here = Path(__file__).resolve().parent
        if str(here) not in sys.path:
            sys.path.insert(0, str(here))
        import meta_model  # type: ignore[reportMissingImports]

        return {
            "MetaType": meta_model.MetaType,
            "MetaRelationType": meta_model.MetaRelationType,
            "MetaConstraint": meta_model.MetaConstraint,
            "Confidence": meta_model.Confidence,
            "LAYER_NAMES": meta_model.LAYER_NAMES,
            "_RELATION_MATRIX": meta_model._RELATION_MATRIX,
        }
    except Exception:
        return None


# Python 3.13: _import_meta_model 里 sys.path 必须在 import 前
import sys


@dataclass
class M3Element:
    """m3 Element 内存表示"""

    id: str
    name: str
    parent: str | None
    abstract: bool
    m3_implements: str | None  # 反向引用 meta_model enum 字串
    properties: dict[str, Any]


@dataclass
class MetaRelation:
    """元关系矩阵条目"""

    source: str
    target: str
    allowed: list[str]


class M3MetaLoader:
    """单例桥接器: 一次加载, 多次 query"""

    _instance: "M3MetaLoader | None" = None

    def __init__(
        self,
        m3_path: Path | str | None = None,
        m3_meta_path: Path | str | None = None,
        m2_dir: Path | str | None = None,
    ):
        # 默认路径 (基于 e2f8f4d7 实证)
        # mof_bridge.py: projects/ecos/src/ecos/l0/ssot/mof_bridge.py
        # m3.yaml:       projects/ecos/src/ecos/ssot/mof/m3.yaml
        # 跳 parents[2] = projects/ecos/src/ecos/, 然后 ssot/...
        here = Path(__file__).resolve()
        ssot_root = here.parents[2] / "ssot"
        if m3_path is None:
            m3_path = ssot_root / "mof" / "m3.yaml"
        if m3_meta_path is None:
            m3_meta_path = ssot_root / "mof" / "m3-meta.yaml"
        if m2_dir is None:
            m2_dir = ssot_root / "mof" / "m2"

        self.m3_path = Path(m3_path)
        self.m3_meta_path = Path(m3_meta_path)
        self.m2_dir = Path(m2_dir)

        # 加载 meta_model (Python)
        self._meta = _import_meta_model()
        if self._meta is None:
            # 不强制: 让调用方用 string-based fallback
            self._meta_types: dict[str, str] = {}
            self._meta_relations: dict[str, str] = {}
            self._meta_constraints: dict[str, str] = {}
            self._confidences: dict[str, str] = {}
            self._layer_names: dict[int, str] = {}
            self._relation_matrix: dict[str, list[str]] = {}
        else:
            self._meta_types = {m.name: m.value for m in self._meta["MetaType"]}
            self._meta_relations = {
                m.name: m.value for m in self._meta["MetaRelationType"]
            }
            self._meta_constraints = {
                m.name: m.value for m in self._meta["MetaConstraint"]
            }
            self._confidences = {m.name: m.value for m in self._meta["Confidence"]}
            self._layer_names = dict(self._meta["LAYER_NAMES"])
            self._relation_matrix = {}
            # _RELATION_MATRIX key is (MetaType.value string, MetaType.value string)
            for (s_key, t_key), rels in self._meta["_RELATION_MATRIX"].items():
                # 兼容 "MET-DOMAIN" 和 "DOMAIN" 两种命名空间
                s_norm = s_key.replace("MET-", "")
                t_norm = t_key.replace("MET-", "")
                key = f"{s_norm}_{t_norm}"
                self._relation_matrix[key] = [r.name for r in rels]
                self._relation_matrix[f"{s_key}_{t_key}"] = [r.name for r in rels]

        # 加载 m3 elements
        self._m3_elements: dict[str, M3Element] = {}
        self._m3_meta_elements: dict[str, M3Element] = {}
        self._m3_meta_relation_matrix: dict[str, list[str]] = {}
        self._layer_architecture: dict[int, str] = {}
        self._meta_to_m3_map_cache: dict[str, str] = {}

        self._load_m3()
        self._load_m3_meta()
        self._build_meta_to_m3_map()

    @classmethod
    def get_instance(cls) -> "M3MetaLoader":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    # ── loader (yaml) ──

    def _load_m3(self) -> None:
        """加载 m3.yaml Element"""
        try:
            import yaml
        except ImportError:
            return
        if not self.m3_path.exists():
            return
        data = yaml.safe_load(self.m3_path.read_text())
        elements = data.get("m3", {}).get("elements", {})
        for eid, edef in elements.items():
            self._m3_elements[eid] = M3Element(
                id=eid,
                name=edef.get("name", ""),
                parent=edef.get("parent"),
                abstract=bool(edef.get("abstract", False)),
                m3_implements=None,
                properties=edef.get("properties", {}),
            )

    def _load_m3_meta(self) -> None:
        """加载 m3-meta.yaml + 关系矩阵 + 8 层架构"""
        try:
            import yaml
        except ImportError:
            return
        if not self.m3_meta_path.exists():
            return
        data = yaml.safe_load(self.m3_meta_path.read_text())
        meta = data.get("m3_meta", {})
        for eid, edef in meta.items():
            if not isinstance(edef, dict):
                continue
            if "id" not in edef:
                continue  # 关系矩阵 / layer_architecture 等
            self._m3_meta_elements[eid] = M3Element(
                id=eid,
                name=edef.get("name", ""),
                parent=edef.get("parent"),
                abstract=bool(edef.get("abstract", False)),
                m3_implements=edef.get("m3_implements"),
                properties=edef.get("properties", {}),
            )
        # 关系矩阵
        matrix = meta.get("meta_relation_matrix", {}).get("entries", {})
        for k, v in matrix.items():
            self._m3_meta_relation_matrix[k] = v
        # 8 层架构
        layers = meta.get("layer_architecture", {}).get("entries", [])
        for idx, name in layers:
            self._layer_architecture[idx] = name

    # ── query API ──

    def meta_type_to_m3(self, meta_type: Enum | str) -> str | None:
        """MetaType enum / string → m3 Element id"""
        if isinstance(meta_type, Enum):
            key = meta_type.name
        else:
            key = str(meta_type)
        return self._meta_to_m3_map.get(key)

    def m3_to_meta_type(self, m3_id: str) -> str | None:
        """m3 Element id → MetaType enum string"""
        elem = self._m3_meta_elements.get(m3_id)
        if elem and elem.m3_implements:
            return elem.m3_implements
        return None

    def check_meta_relation_allowed(
        self,
        source: Enum | str,
        target: Enum | str,
        relation: Enum | str,
    ) -> bool:
        """检查 (source, target, relation) 是否在元关系矩阵允许列表内.

        两路 fallback:
          1. 优先用 meta_model._RELATION_MATRIX (Python, source of truth)
          2. 用 m3-meta.yaml meta_relation_matrix (派生)
        """
        s_name = source.name if isinstance(source, Enum) else str(source)
        t_name = target.name if isinstance(target, Enum) else str(target)
        r_name = relation.name if isinstance(relation, Enum) else str(relation)
        # 路径 1: python
        key = f"{s_name}_{t_name}"
        if self._relation_matrix:
            allowed = self._relation_matrix.get(key, [])
            return r_name in allowed
        # 路径 2: yaml
        if self._m3_meta_relation_matrix:
            allowed = self._m3_meta_relation_matrix.get(key, [])
            return r_name in allowed
        return False

    def get_meta_relation_matrix(self) -> dict[str, list[str]]:
        """返回元关系矩阵 (元 model python 优先, 否则 yaml 派生)"""
        if self._relation_matrix:
            return self._relation_matrix
        return self._m3_meta_relation_matrix

    def get_layer_architecture(self) -> dict[int, str]:
        """8 层架构 (Layer 0-7)"""
        if self._layer_names:
            return self._layer_names
        return self._layer_architecture

    def list_m3_meta_elements(self) -> list[M3Element]:
        return list(self._m3_meta_elements.values())

    def list_m3_elements(self) -> list[M3Element]:
        return list(self._m3_elements.values())

    @property
    def _meta_to_m3_map(self) -> dict[str, str]:
        """MetaType.name → m3 Element id 映射 (init 时构建)"""
        return self._meta_to_m3_map_cache

    def _build_meta_to_m3_map(self) -> None:
        """扫描 m3-meta elements 构建 MetaType.name → m3 Element id 映射

        优先选择 m3-implements 与 meta_model.MetaType.* 完全匹配的,
        因为 Confidence* 子类也用 Confidence.FACT 等做 m3_implements, 优先级低。

        ADR-0138 Round 2b: 现在 m3.yaml 主根已含 MetaEntity/MetaRelationType/
        MetaConstraintRule, 优先匹配这些 (m3.yaml 是 SSOT)。
        m3-meta.yaml 继续作为派生映射索引 / 关系矩阵 / 8 层架构源.
        """
        # 第一轮: 收集所有候选
        candidates: dict[str, list[str]] = {}
        # 优先看 m3.yaml (主根 SSOT)
        for eid, elem in self._m3_elements.items():
            # MetaEntity 等抽象类的子类型: 把 meta_type 属性值当锚
            if elem.parent == "MetaEntity":
                # 抽象类本身不直接当映射, 等子类
                continue
        # 第二轮: 同时扫 m3.yaml 和 m3-meta.yaml
        for elem in list(self._m3_elements.values()) + list(
            self._m3_meta_elements.values()
        ):
            if elem.m3_implements:
                last = elem.m3_implements.split(".")[-1]
                candidates.setdefault(last, []).append(elem.id)
        # 第三轮: 优先 m3.yaml (主根) 上的 Meta* 类
        priority_prefixes = (
            "MetaType",
            "MetaRelationType",
            "MetaConstraint",
            "Confidence",
        )
        # 也优先选 m3.yaml 主根 (ADR-0138)
        for name, ids in candidates.items():
            chosen = None
            # 先选 m3.yaml 主根匹配 Meta* 的子类
            for eid in ids:
                elem = self._get_element_anywhere(eid)
                if elem is None:
                    continue
                # ADR-0138: MetaEntity 子类 (MetaDomain/MetaFact/...) 来自 m3.yaml 主根
                # m3_implements 字段在 m3-meta.yaml
                if elem.parent in (
                    "MetaEntity",
                    "MetaRelationType",
                    "MetaConstraintRule",
                    "Confidence",
                    "MetaType",
                    "MetaRelation",
                    "MetaStruct",
                    "MetaDerive",
                    "MetaBehavior",
                    "MetaJustify",
                    "MetaConstraint",
                ):
                    chosen = eid
                    break
            if chosen is None:
                # fallback 到 m3-meta.yaml 派生
                for eid in ids:
                    elem = self._get_element_anywhere(eid)
                    if elem and elem.m3_implements:
                        middle = (
                            elem.m3_implements.split(".")[-2]
                            if "." in elem.m3_implements
                            else ""
                        )
                        if middle in priority_prefixes:
                            if middle == "MetaType" or (
                                middle == "Confidence" and chosen is None
                            ):
                                chosen = eid
            if chosen is None:
                chosen = ids[0]
            self._meta_to_m3_map_cache[name] = chosen

    def _get_element_anywhere(self, eid: str) -> "M3Element | None":
        """从 m3.yaml 或 m3-meta.yaml 找 Element"""
        elem = self._m3_elements.get(eid)
        if elem is not None:
            return elem
        return self._m3_meta_elements.get(eid)

    def compute_meta_confidence(self, confidences: list[Enum | str]) -> float:
        """聚合多个 MetaType.confidence.

        加权平均: fact=1.0, inference=0.7, hypothesis=0.4, estimated=0.5
        """
        weights = {"fact": 1.0, "inference": 0.7, "hypothesis": 0.4, "estimated": 0.5}
        if not confidences:
            return 0.0
        total = 0.0
        for c in confidences:
            name = c.name if isinstance(c, Enum) else str(c)
            total += weights.get(name.lower(), 0.5)
        return total / len(confidences)
