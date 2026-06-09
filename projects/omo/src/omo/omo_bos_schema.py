"""Pydantic schema for BOS registry — W3 声明式注册核心.

P33 era: omo_bos.py 用 @dataclass, 灵活但缺运行时验证.
W3 升级: 引入 Pydantic BaseModel, 让:
  1. URI 格式在 schema 层强制 (与 validate_bos_uri 双校验)
  2. JSON 序列化/反序列化自带 (替 asdict 手动写)
  3. 字段约束 (endpoint 必须非空 for non-seed, protocol 必须白名单)
  4. registry 整体可作为一个 model (BosRegistryModel) 导入导出

保持 backward compat: 旧 @dataclass BosRegistration 仍可 import.
新代码推荐用 BosRegistrationModel.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# 复用 omo_bos 的白名单 (避免循环 import)
# 注: parse_bos_uri 在 field_validator 内部 lazy import, 这里不引 (避免 Pyright 误报)

Domain = Literal["memory", "governance", "analysis", "persona", "capability"]
Protocol = Literal["http", "stdio", "internal"]


class BosRegistrationModel(BaseModel):
    """BOS URI 注册记录 — Pydantic 声明式版本.

    W3 设计要点:
    - uri 字段强制 BOS_URI_PATTERN 匹配 (运行时验证)
    - protocol 仅 3 选项 (literal type)
    - endpoint 非空 (但允许占位符 placeholder://)
    - registered_at 默认 ISO8601 UTC
    """

    uri: str = Field(..., description="bos://<domain>/<package>/<action>")
    domain: Domain
    package: str = Field(..., min_length=1, max_length=64)
    action: str = Field(..., min_length=1, max_length=64)
    endpoint: str = Field(default="placeholder://", max_length=512)
    protocol: Protocol = "internal"
    description: str = Field(default="", max_length=512)
    registered_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    registered_by: str = Field(default="omo-bos-cli", max_length=64)

    @field_validator("uri")
    @classmethod
    def _validate_uri(cls, v: str) -> str:
        # 复用 omo_bos.parse_bos_uri (含 4-段 + 3-段 legacy 自动升级到 4-段),
        # 避免 URI 规则在 3 处 (BOS_URI_PATTERN / validate_bos_uri / schema) 漂移.
        from omo.omo_bos import parse_bos_uri
        try:
            parsed = parse_bos_uri(v)
        except ValueError as exc:
            raise ValueError(str(exc))
        # 重建规范 4-段形式 — 3-段 legacy 会被升级
        return f"bos://{parsed['domain']}/{parsed['package']}/{parsed['action']}"

    @field_validator("endpoint")
    @classmethod
    def _validate_endpoint(cls, v: str) -> str:
        # 占位符 (seed 但尚未实装) 允许
        if v.startswith("placeholder://") or v.startswith("http://") or v.startswith("https://"):
            return v
        # module:function 形式 — module 部分必须以字母开头
        if ":" in v:
            module = v.split(":", 1)[0].strip()
            if not re.match(r"^[a-zA-Z_][\w.]*$", module):
                raise ValueError(f"endpoint module part invalid: {module!r}")
            return v
        # 纯 module path
        if not re.match(r"^[a-zA-Z_][\w.]*$", v.strip()):
            raise ValueError(f"endpoint must be module:function, http(s)://, or placeholder://, got: {v!r}")
        return v

    @model_validator(mode="after")
    def _uri_matches_domain(self) -> "BosRegistrationModel":
        """强制 uri 内的 domain 与 domain 字段一致 (防止拼写漂移).

        复用 omo_bos.parse_bos_uri (不再独立跑 BOS_URI_PATTERN) — 避免 regex 3 次
        (BOS_URI_PATTERN / validate_bos_uri / 此处) 漂移风险.
        """
        from omo.omo_bos import parse_bos_uri
        try:
            parsed = parse_bos_uri(self.uri)
        except ValueError:
            return self  # _validate_uri 已拦截, 防御性兜底
        if parsed["domain"] != self.domain:
            raise ValueError(
                f"URI domain {parsed['domain']!r} != field domain {self.domain!r}"
            )
        return self

    def to_legacy_dict(self) -> dict[str, Any]:
        """兼容旧 dataclass-asdict 消费方."""
        return self.model_dump()


class BosRegistryModel(BaseModel):
    """整个 BOS registry 作为一个 model — 整文件验证."""

    version: Literal["1.0"] = "1.0"
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    registrations: list[BosRegistrationModel] = Field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.registrations)

    def by_domain(self, domain: Domain) -> list[BosRegistrationModel]:
        return [r for r in self.registrations if r.domain == domain]

    def by_package(self, package: str) -> list[BosRegistrationModel]:
        return [r for r in self.registrations if r.package == package]


__all__ = (
    "BosRegistrationModel",
    "BosRegistryModel",
    "Domain",
    "Protocol",
)


if __name__ == "__main__":
    # 快速自检
    sample = BosRegistrationModel(
        uri="bos://memory/kos/search",
        domain="memory",
        package="kos",
        action="search",
        endpoint="kairon.packages.kos.ontology.store:search_entities",
        description="KOS search",
    )
    print("[OK] sample model:", sample.model_dump_json(indent=2))

    # Case 2: 错 domain 应该抛 ValidationError
    try:
        BosRegistrationModel(
            uri="bos://bad/foo/bar",
            domain="memory",
            package="kos",
            action="search",
        )
    except Exception as e:
        print(f"[OK] bad domain caught: {type(e).__name__}")

    # Case 3: uri 内的 domain 与 field domain 不一致应该抛
    try:
        BosRegistrationModel(
            uri="bos://memory/kos/search",
            domain="governance",  # 故意不匹配
            package="kos",
            action="search",
        )
    except Exception as e:
        print(f"[OK] domain mismatch caught: {type(e).__name__}")

    # Case 4: legacy 3-段 URI 应该被自动升级
    legacy = BosRegistrationModel(
        uri="bos://omo/audit",  # 3-段, 通过 LEGACY_DOMAIN_MAP 升级为 governance
        domain="governance",
        package="omo",
        action="audit",
    )
    print(f"[OK] legacy auto-mapped: {legacy.uri}")
