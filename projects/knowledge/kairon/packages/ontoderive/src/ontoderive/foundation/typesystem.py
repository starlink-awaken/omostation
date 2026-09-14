"""
OntoDerive 类型系统 — MOF十元类型校验
======================================
实现10元类型的定义和校验：
- DOMAIN(ORG/ROL/PRJ/RES) · FACT(DAT/POL) · INFERENCE · STATE · DOCUMENT · CONSTRAINT · PROCESSOR
- 类型一致性检查：ID前缀与声明类型匹配
- 元关系域/值域约束
"""

from dataclasses import dataclass, field
from typing import Any

# ── 十元类型定义 ──
META_TYPES = {
    "DOMAIN": {
        "subtypes": {"ORG", "ROL", "PRJ", "RES"},
        "id_prefixes": ("ORG-", "ROL-", "PRJ-", "RES-"),
        "description": "领域实体 — 组织/角色/项目/资源",
        "required_fields": ["name"],
    },
    "FACT": {
        "subtypes": {"DAT", "POL"},
        "id_prefixes": ("D-F", "P-F"),
        "description": "事实 — 数据点(含数值)或政策条文",
        "required_fields": ["value", "source"],
    },
    "INFERENCE": {
        "subtypes": {"CONTRADICTION", "BUSINESS", "ARCHITECTURE", "POLICY", "ANALYSIS"},
        "id_prefixes": ("INF-", "INF-V2-"),
        "description": "推论 — 从事实推导的结论",
        "required_fields": ["derives_from"],
    },
    "STATE": {
        "subtypes": {"T", "F", "H"},
        "id_prefixes": ("T", "F", "H"),
        "description": "状态 — 推导阶段/事实/假设标记",
        "required_fields": [],
    },
    "DOCUMENT": {
        "subtypes": {"COL", "DOC", "CH", "SEC", "STD"},
        "id_prefixes": ("DOC-", "CH-", "SEC-", "DCH-", "STD-"),
        "description": "文档/标准 — 方案/章节/集合/标准规范",
        "required_fields": ["title"],
    },
    "CONSTRAINT": {
        "subtypes": {"CON"},
        "id_prefixes": ("CON-", "IP"),
        "description": "约束 — 规约/不变量",
        "required_fields": ["constraint"],
    },
    "PROCESSOR": {
        "subtypes": {"ENG"},
        "id_prefixes": ("ENG-",),
        "description": "处理器 — 引擎/推导器",
        "required_fields": [],
    },
}

# ID前缀→元类型映射
PREFIX_TO_META = {}
for meta_name, meta_info in META_TYPES.items():
    for prefix in meta_info["id_prefixes"]:
        PREFIX_TO_META[prefix] = meta_name


@dataclass
class TypeCheckResult:
    node_id: str
    declared_type: str = ""
    expected_type: str = ""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    file: str = ""
    line: int = 0

    @property
    def is_valid(self) -> Any:
        return len(self.errors) == 0


class TypeValidator:
    def __init__(self) -> None:
        self.results: list[TypeCheckResult] = []

    def check_id(self, node_id: str, declared_meta_type: str = "", file: str = "", line: int = 0) -> TypeCheckResult:
        """检查单个ID的类型一致性"""
        result = TypeCheckResult(node_id=node_id, declared_type=declared_meta_type, file=file, line=line)

        # 解析ID前缀
        inferred_type = self._infer_type(node_id)
        if inferred_type is None:
            result.errors.append(f"'{node_id}' 无法识别ID前缀，已知前缀: {sorted(PREFIX_TO_META.keys())}")
            result.expected_type = "UNKNOWN"
        else:
            result.expected_type = inferred_type

        # 检查声明类型与实际前缀是否一致
        if declared_meta_type and inferred_type and declared_meta_type != inferred_type:
            result.errors.append(f"'{node_id}': ID前缀推断为'{inferred_type}'但声明为'{declared_meta_type}'")

        # 检查子类型前缀是否匹配
        if inferred_type:
            self._check_subtype_prefix(node_id, inferred_type, result)

        self.results.append(result)
        return result

    def _infer_type(self, node_id: str) -> str | None:
        for prefix, meta_name in sorted(PREFIX_TO_META.items(), key=lambda x: -len(x[0])):
            if node_id.startswith(prefix):
                return meta_name
        return None

    def _check_subtype_prefix(self, node_id: str, meta_type: str, result: TypeCheckResult) -> None:
        meta = META_TYPES.get(meta_type, {})
        subtypes = meta.get("subtypes", set())
        if not subtypes:
            return

        main_prefix = node_id.split("-")[0] if "-" in node_id else node_id[:3]
        if main_prefix.startswith("INF"):
            main_prefix = "INF"
        if main_prefix in subtypes:
            return

        result.warnings.append(f"'{node_id}': 子类型前缀'{main_prefix}'不在 {meta_type}的已知子类型{subtypes}中")

    def check_batch(self, items: list[dict]) -> list[TypeCheckResult]:
        """批量检查"""
        results = []
        for item in items:
            r = self.check_id(
                item.get("id", ""),
                item.get("type", ""),
                item.get("file", ""),
                item.get("line", 0),
            )
            results.append(r)
        return results

    def has_errors(self) -> bool:
        return any(not r.is_valid for r in self.results)

    def error_count(self) -> int:
        return sum(1 for r in self.results if not r.is_valid)

    def summary(self) -> dict:
        return {
            "total": len(self.results),
            "valid": sum(1 for r in self.results if r.is_valid),
            "errors": self.error_count(),
            "by_type": {t: sum(1 for r in self.results if r.expected_type == t) for t in META_TYPES},
        }
