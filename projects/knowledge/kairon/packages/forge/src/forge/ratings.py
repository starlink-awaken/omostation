"""ratings — 插件质量/安全评分引擎。

提取自 D_Extension org/plugin_rating_engine.py。
评分维度：代码结构、文档、测试覆盖、BOS-URI 合规、安全检测。
"""

from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

# ============================================================================
# 数据模型
# ============================================================================


@dataclass
class QualityScore:
    """质量评分组件分解。"""

    code_structure: float = 0.0  # 0-100, __init__/lifecycle 方法
    documentation: float = 0.0  # 0-100, docstring/README
    test_coverage: float = 0.0  # 0-100, tests 目录
    bos_uri_compliance: float = 0.0  # 0-100, BOS-URI 合规
    total: float = 0.0  # 0-100, 加权总分


@dataclass
class SecurityScore:
    """安全评分组件分解。"""

    dangerous_calls: float = 0.0  # 0-100, 越低违规越多
    filesystem_access: float = 0.0  # 0-100, 无路径遍历
    network_access: float = 0.0  # 0-100, 无硬编码 secret
    secret_exposure: float = 0.0  # 0-100, 无硬编码凭据
    total: float = 0.0  # 0-100, 加权总分


@dataclass
class PluginRating:
    """插件完整评分结果。"""

    extension_id: str
    quality: QualityScore
    security: SecurityScore
    composite_score: float = 0.0  # 0-100

    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        # composite = 0.4 * quality + 0.6 * security
        self.composite_score = round(0.4 * self.quality.total + 0.6 * self.security.total, 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "extension_id": self.extension_id,
            "composite_score": self.composite_score,
            "quality_total": self.quality.total,
            "security_total": self.security.total,
            "quality_breakdown": {
                "code_structure": self.quality.code_structure,
                "documentation": self.quality.documentation,
                "test_coverage": self.quality.test_coverage,
                "bos_uri_compliance": self.quality.bos_uri_compliance,
            },
            "security_breakdown": {
                "dangerous_calls": self.security.dangerous_calls,
                "filesystem_access": self.security.filesystem_access,
                "network_access": self.security.network_access,
                "secret_exposure": self.security.secret_exposure,
            },
            "violations": self.violations,
            "warnings": self.warnings,
        }


# ============================================================================
# 危险模式检测器
# ============================================================================

_DANGEROUS_CALL_PATTERNS: list[tuple[str, str, re.RegexFlag]] = [
    (r"\beval\s*\(", "eval() call", re.MULTILINE),
    (r"\bexec\s*\(", "exec() call", re.MULTILINE),
    (r"subprocess\.call\s*\(\s*shell\s*=\s*True", "subprocess.call with shell=True", re.MULTILINE),
    (r"subprocess\.run\s*\(\s*shell\s*=\s*True", "subprocess.run with shell=True", re.MULTILINE),
    (r"subprocess\.Popen\s*\(\s*shell\s*=\s*True", "subprocess.Popen with shell=True", re.MULTILINE),
    (r"os\.system\s*\(", "os.system() call", re.MULTILINE),
    (r"os\.popen\s*\(", "os.popen() call", re.MULTILINE),
]

_SECRET_PATTERNS: list[tuple[str, str, re.RegexFlag]] = [
    (r"\.\./", "path traversal attempt (..)", re.MULTILINE),
    (r"\bopen\s*\([^)]*\+\s*request\.", "dynamic file open with user input", re.MULTILINE),
    (r'password\s*=\s*["\'][^"\']{3,}["\']', "hardcoded password", re.IGNORECASE | re.MULTILINE),
    (r'api[_-]?key\s*=\s*["\'][^"\']{8,}["\']', "hardcoded API key", re.IGNORECASE | re.MULTILINE),
    (r'secret\s*=\s*["\'][^"\']{8,}["\']', "hardcoded secret", re.IGNORECASE | re.MULTILINE),
    (r'token\s*=\s*["\'][A-Za-z0-9_\-]{20,}["\']', "hardcoded token", re.IGNORECASE | re.MULTILINE),
]


# ============================================================================
# 插件评分引擎
# ============================================================================


class PluginRatingEngine:
    """插件评分引擎 —— 质量和安全维度评分。

    评分公式:
        composite = 0.4 * quality_total + 0.6 * security_total

    质量权重:
        code_structure: 30%, documentation: 25%, test_coverage: 25%, bos_uri_compliance: 20%

    安全权重:
        dangerous_calls: 35%, filesystem_access: 20%, network_access: 20%, secret_exposure: 25%
    """

    def __init__(self) -> None:
        self._cache: dict[str, PluginRating] = {}

    # ── 公共 API ──

    def rate(
        self,
        extension_id: str,
        extension_path: Path | str,
        use_cache: bool = True,
    ) -> PluginRating:
        """按扩展 ID 和路径评分。

        Args:
            extension_id: 扩展唯一标识
            extension_path: 扩展目录路径
            use_cache: 是否使用缓存结果

        Returns:
            包含质量、安全、综合评分的 PluginRating。
        """
        if use_cache and extension_id in self._cache:
            _log.debug("返回缓存评分: %s", extension_id)
            return self._cache[extension_id]

        path = Path(extension_path)
        if not path.exists():
            _log.warning("扩展路径不存在: %s", path)
            return self._empty_rating(extension_id)

        py_files = list(path.rglob("*.py"))

        quality = self._rate_quality(path, py_files)
        security, violations, warnings = self._rate_security(path, py_files)

        rating = PluginRating(
            extension_id=extension_id,
            quality=quality,
            security=security,
            violations=violations,
            warnings=warnings,
        )

        self._cache[extension_id] = rating
        _log.info(
            "已评分扩展 %s: composite=%.1f (Q=%.1f, S=%.1f)",
            extension_id,
            rating.composite_score,
            quality.total,
            security.total,
        )

        return rating

    # ── 质量评分 ──

    def _rate_quality(self, path: Path, py_files: list[Path]) -> QualityScore:
        code_structure = self._score_code_structure(path, py_files)
        documentation = self._score_documentation(path)
        test_coverage = self._score_test_coverage(path)
        bos_uri_compliance = self._score_bos_uri_compliance(py_files)

        total = 0.30 * code_structure + 0.25 * documentation + 0.25 * test_coverage + 0.20 * bos_uri_compliance

        return QualityScore(
            code_structure=code_structure,
            documentation=documentation,
            test_coverage=test_coverage,
            bos_uri_compliance=bos_uri_compliance,
            total=round(total, 2),
        )

    def _score_code_structure(self, path: Path, py_files: list[Path]) -> float:
        if not py_files:
            return 0.0

        score = 50.0  # base
        if (path / "__init__.py").exists():
            score += 15.0

        has_lifecycle = False
        for py_file in py_files:
            try:
                content = py_file.read_text()
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        if node.name in ("on_birth", "on_death", "activate", "deactivate", "handle_task"):
                            has_lifecycle = True
                            break
            except (SyntaxError, OSError):
                pass
        if has_lifecycle:
            score += 20.0

        for py_file in py_files:
            try:
                content = py_file.read_text()
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ExceptHandler) and node.type is None:
                        score -= 10.0
                        break
            except (SyntaxError, OSError):
                pass

        return max(0.0, min(100.0, score))

    def _score_documentation(self, path: Path) -> float:
        score = 0.0
        for name in ("README.md", "README.txt", "README"):
            if (path / name).exists():
                score += 30.0
                break

        py_files = list(path.rglob("*.py"))
        if py_files:
            documented = 0
            total = 0
            for py_file in py_files:
                try:
                    content = py_file.read_text()
                    tree = ast.parse(content)
                    for node in ast.walk(tree):
                        if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                            if ast.get_docstring(node):
                                documented += 1
                            total += 1
                except (SyntaxError, OSError):
                    pass
            if total > 0:
                score += 40.0 * (documented / total)

        typed_funcs = 0
        total_funcs = 0
        for py_file in py_files:
            try:
                content = py_file.read_text()
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        if node.returns or any(arg.annotation for arg in node.args.args):
                            typed_funcs += 1
                        total_funcs += 1
            except (SyntaxError, OSError):
                pass
        if total_funcs > 0:
            score += 30.0 * (typed_funcs / total_funcs)

        return max(0.0, min(100.0, score))

    def _score_test_coverage(self, path: Path) -> float:
        test_paths = [path / "tests", path / "test", path / "__tests__"]
        for tp in test_paths:
            if tp.exists() and tp.is_dir():
                test_files = list(tp.rglob("test_*.py")) + list(tp.rglob("*_test.py"))
                return min(100.0, 40.0 + 20.0 * len(test_files))
        return 0.0

    def _score_bos_uri_compliance(self, py_files: list[Path]) -> float:
        if not py_files:
            return 0.0

        compliant_files = 0
        total = len(py_files)

        for py_file in py_files:
            try:
                content = py_file.read_text()
                direct_import_pattern = re.compile(
                    r"^from\s+organs\.D_[A-Z]|^import\s+organs\.D_[A-Z]",
                    re.MULTILINE,
                )
                if not direct_import_pattern.search(content):
                    compliant_files += 1
            except OSError:
                pass

        return 100.0 * (compliant_files / total) if total > 0 else 0.0

    # ── 安全评分 ──

    def _rate_security(self, path: Path, py_files: list[Path]) -> tuple[SecurityScore, list[str], list[str]]:
        violations: list[str] = []
        warnings: list[str] = []

        dangerous_calls = self._check_dangerous_calls(py_files, violations, warnings)
        filesystem_score = self._check_filesystem_access(py_files, violations, warnings)
        network_score = self._check_network_access(py_files, violations, warnings)
        secret_score = self._check_secret_exposure(py_files, violations, warnings)

        total = 0.35 * dangerous_calls + 0.20 * filesystem_score + 0.20 * network_score + 0.25 * secret_score

        return (
            SecurityScore(
                dangerous_calls=dangerous_calls,
                filesystem_access=filesystem_score,
                network_access=network_score,
                secret_exposure=secret_score,
                total=round(total, 2),
            ),
            violations,
            warnings,
        )

    def _check_dangerous_calls(self, py_files: list[Path], violations: list[str], _warnings: list[str]) -> float:
        base_score = 100.0
        for pattern, description, flags in _DANGEROUS_CALL_PATTERNS:
            for py_file in py_files:
                try:
                    content = py_file.read_text()
                    matches = re.findall(pattern, content, flags)
                    if matches:
                        violations.append(f"{py_file.name}: {description}")
                        base_score -= 15.0
                except OSError:
                    pass
        return max(0.0, base_score)

    def _check_filesystem_access(self, py_files: list[Path], violations: list[str], _: list[str]) -> float:
        score = 100.0
        for py_file in py_files:
            try:
                content = py_file.read_text()
                if re.search(r"\.\./", content):
                    violations.append(f"{py_file.name}: path traversal pattern (..) detected")
                    score -= 20.0
            except OSError:
                pass
        return max(0.0, score)

    def _check_network_access(self, py_files: list[Path], _violations: list[str], warnings: list[str]) -> float:
        del _violations
        score = 100.0
        network_patterns = [
            (r"urllib\.request", "urllib.request usage"),
            (r"requests\.", "requests library usage"),
            (r"http\.client", "http.client usage"),
            (r"socket\.socket", "socket creation"),
        ]
        for py_file in py_files:
            try:
                content = py_file.read_text()
                for pattern, desc in network_patterns:
                    if re.search(pattern, content):
                        warnings.append(f"{py_file.name}: {desc} (allowed but logged)")
            except OSError:
                pass
        return max(0.0, score)

    def _check_secret_exposure(self, py_files: list[Path], violations: list[str], _: list[str]) -> float:
        score = 100.0
        for pattern, description, flags in _SECRET_PATTERNS:
            for py_file in py_files:
                try:
                    content = py_file.read_text()
                    matches = re.findall(pattern, content, flags)
                    if matches:
                        violations.append(f"{py_file.name}: {description}")
                        score -= 20.0
                except OSError:
                    pass
        return max(0.0, score)

    # ── 辅助方法 ──

    def _empty_rating(self, extension_id: str) -> PluginRating:
        return PluginRating(
            extension_id=extension_id,
            quality=QualityScore(),
            security=SecurityScore(),
        )

    def clear_cache(self) -> None:
        self._cache.clear()


# 单例
_rating_engine: PluginRatingEngine | None = None


def get_rating_engine() -> PluginRatingEngine:
    """获取评分引擎单例。"""
    global _rating_engine
    if _rating_engine is None:
        _rating_engine = PluginRatingEngine()
    return _rating_engine
