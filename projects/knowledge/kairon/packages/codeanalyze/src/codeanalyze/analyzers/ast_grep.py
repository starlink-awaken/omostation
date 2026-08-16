"""ast-grep 分析器 — AST 结构化模式搜索

ast-grep (sg) 使用 AST 而非纯文本进行代码搜索，能精确匹配语法结构。
比 ripgrep 更精准：可找"所有没有 try/except 的 async def"等结构模式。

支持语言: Python, JavaScript, TypeScript, Rust, Go, Java, C, C++...
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SgMatch:
    """单个 ast-grep 匹配结果"""

    path: str
    line_start: int
    line_end: int
    col_start: int
    col_end: int
    text: str
    rule_id: str = ""


@dataclass
class SgResult:
    """AST 搜索结果集"""

    pattern: str
    path: str
    language: str
    matches: list[SgMatch] = field(default_factory=list)
    total: int = 0
    error: str | None = None


def is_available() -> bool:
    """检查 ast-grep (sg) 是否已安装。"""
    return shutil.which("sg") is not None or shutil.which("ast-grep") is not None


def _sg_cmd() -> str:
    """返回可用的 ast-grep 命令名。"""
    return "sg" if shutil.which("sg") else "ast-grep"


def get_version() -> str | None:
    """获取 ast-grep 版本。"""
    if not is_available():
        return None
    try:
        r = subprocess.run(
            [_sg_cmd(), "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        first_line = (r.stdout or r.stderr).strip().split("\n")[0]
        return first_line or None
    except Exception:
        return None


def search(
    pattern: str,
    path: str = ".",
    language: str | None = None,
    strict: bool = False,
    max_count: int = 100,
) -> SgResult:
    """使用 ast-grep 进行 AST 结构化搜索。

    Args:
        pattern: AST 模式（如 `$FUNC($___)` 匹配所有函数调用）
        path: 搜索路径（文件或目录）
        language: 指定语言（py/js/ts/rs/go/java/c/cpp 等）
        strict: 严格模式（不允许元变量省略）
        max_count: 最大匹配数
    """
    root = Path(path).resolve()
    result = SgResult(pattern=pattern, path=str(root), language=language or "auto")

    if not is_available():
        result.error = "ast-grep 未安装. 安装: brew install ast-grep"
        return result

    cmd = [_sg_cmd(), "run", "--pattern", pattern, "--json"]

    if language:
        cmd.extend(["--lang", language])
    if strict:
        cmd.append("--strict")

    cmd.append(str(root))

    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if r.returncode not in (0, 1):
            result.error = (r.stderr or "").strip()[:500] or f"exit code {r.returncode}"
            return result

        stdout = r.stdout.strip()
        if not stdout:
            return result

        _parse_json_output(result, stdout, max_count)

    except subprocess.TimeoutExpired:
        result.error = "搜索超时（60s）"
    except FileNotFoundError:
        result.error = "ast-grep 未安装"

    return result


def search_rule(
    rule_yaml: str,
    path: str = ".",
    max_count: int = 100,
) -> SgResult:
    """使用 YAML 规则文件进行复杂 AST 搜索。

    Args:
        rule_yaml: YAML 规则内容（支持 pattern/kind/any/all/not 组合）
        path: 搜索路径
        max_count: 最大匹配数
    """
    import tempfile

    root = Path(path).resolve()
    result = SgResult(pattern="[rule]", path=str(root), language="multi")

    if not is_available():
        result.error = "ast-grep 未安装. 安装: brew install ast-grep"
        return result

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(rule_yaml)
        rule_path = f.name

    try:
        cmd = [_sg_cmd(), "scan", "--rule", rule_path, "--json", str(root)]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if r.returncode not in (0, 1):
            result.error = (r.stderr or "").strip()[:500]
            return result

        if r.stdout.strip():
            _parse_json_output(result, r.stdout.strip(), max_count)

    except subprocess.TimeoutExpired:
        result.error = "规则搜索超时（60s）"
    except FileNotFoundError:
        result.error = "ast-grep 未安装"
    finally:
        Path(rule_path).unlink(missing_ok=True)

    return result


def dump_ast(
    code: str,
    language: str,
) -> dict:
    """展示代码片段的 AST 结构（辅助调试 pattern）。

    Args:
        code: 代码字符串
        language: 语言（py/js/ts 等）
    """
    if not is_available():
        return {"error": "ast-grep 未安装"}

    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=_lang_ext(language), delete=False) as f:
        f.write(code)
        tmp = f.name

    try:
        cmd = [_sg_cmd(), "run", "--pattern", "$_", "--lang", language, "--json", tmp]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        matches = []
        if r.stdout.strip():
            for line in r.stdout.strip().split("\n"):
                try:
                    matches.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return {"language": language, "nodes": matches[:20]}
    except Exception as e:
        return {"error": str(e)}
    finally:
        Path(tmp).unlink(missing_ok=True)


def _parse_json_output(result: SgResult, stdout: str, max_count: int) -> None:
    """解析 ast-grep JSON 输出（每行一个 JSON 对象或 JSON 数组）。"""
    # ast-grep --json 可能输出 JSON 数组或 NDJSON
    stdout = stdout.strip()
    objs: list[dict] = []

    if stdout.startswith("["):
        try:
            objs = json.loads(stdout)
        except json.JSONDecodeError:
            pass
    else:
        for line in stdout.split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                objs.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    for obj in objs[:max_count]:
        rng = obj.get("range", {})
        start = rng.get("start", {})
        end = rng.get("end", {})
        match = SgMatch(
            path=obj.get("file", ""),
            line_start=start.get("line", 0) + 1,  # 0-indexed → 1-indexed
            line_end=end.get("line", 0) + 1,
            col_start=start.get("column", 0),
            col_end=end.get("column", 0),
            text=obj.get("text", ""),
            rule_id=obj.get("ruleId", ""),
        )
        result.matches.append(match)
        result.total += 1


def _lang_ext(language: str) -> str:
    """语言 → 文件扩展名。"""
    mapping = {
        "py": ".py",
        "python": ".py",
        "js": ".js",
        "javascript": ".js",
        "ts": ".ts",
        "typescript": ".ts",
        "rs": ".rs",
        "rust": ".rs",
        "go": ".go",
        "java": ".java",
        "c": ".c",
        "cpp": ".cpp",
    }
    return mapping.get(language.lower(), f".{language}")


def search_to_entities(
    pattern: str,
    path: str = ".",
    language: str | None = None,
) -> list[dict]:
    """搜索并返回实体格式结果（兼容 codeanalyze 统一格式）。"""
    result = search(pattern, path, language)
    if result.error:
        return [{"error": result.error}]

    entities = []
    for m in result.matches:
        entities.append(
            {
                "id": f"sg-{hash(m.path + str(m.line_start)) % 1000000:06d}",
                "name": m.text.strip()[:80],
                "type": "AstMatch",
                "source": "ast-grep",
                "source_path": m.path,
                "source_line": m.line_start,
                "confidence": 1.0,
                "properties": {
                    "pattern": pattern,
                    "language": language or "auto",
                    "line_end": m.line_end,
                    "col_start": m.col_start,
                    "rule_id": m.rule_id,
                },
            }
        )
    return entities
