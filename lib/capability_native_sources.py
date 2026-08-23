"""Pure FD-bound source readers and static FastMCP authority proofs.

All repository reads are rooted, component-by-component ``O_NOFOLLOW`` opens.
The final descriptor is read twice and remains bound to the same directory
entry, closing symlink and replacement races without importing source code.
"""

from __future__ import annotations

import ast
import errno
import hashlib
import os
import re
import stat
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

MAX_SOURCE_BYTES = 4 * 1024 * 1024
SAFE_SOURCE_PART = re.compile(r"^[^/\\\x00]+$")


class NativeInspectionError(ValueError):
    """Stable fail-closed native inspection error."""


@dataclass(frozen=True)
class NativeDirectorySnapshot:
    """Full deterministic directory evidence used across one validation interval."""

    entries: tuple[tuple[str, bytes], ...]
    digest: str


def _fail(code: str) -> None:
    raise NativeInspectionError(code)


def _source_parts(source_ref: str) -> tuple[str, ...]:
    candidate = Path(source_ref)
    if (
        not isinstance(source_ref, str)
        or not source_ref
        or candidate.is_absolute()
        or source_ref.startswith(("~", "\\"))
        or any(part in {"", ".", ".."} or not SAFE_SOURCE_PART.fullmatch(part) for part in candidate.parts)
    ):
        _fail("dangling_reference")
    return tuple(candidate.parts)


def _open_directory(root: Path, parts: tuple[str, ...]) -> tuple[int, Path]:
    try:
        resolved_root = root.resolve(strict=True)
        current = os.open(str(resolved_root), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        for part in parts:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current)
            os.close(current)
            current = next_fd
        return current, resolved_root.joinpath(*parts)
    except OSError as exc:
        try:
            os.close(current)  # type: ignore[possibly-undefined]
        except (OSError, UnboundLocalError):
            pass
        if exc.errno in {errno.ELOOP, errno.ENOTDIR}:
            _fail("dangling_reference")
        _fail("source_unprovable")


def _identity(info: os.stat_result) -> tuple[int, int, int, int, int]:
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _read_fd(fd: int) -> bytes:
    chunks: list[bytes] = []
    size = 0
    while True:
        chunk = os.read(fd, min(65536, MAX_SOURCE_BYTES + 1 - size))
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)
        size += len(chunk)
        if size > MAX_SOURCE_BYTES:
            _fail("source_unprovable")


def read_stable_source(
    root: Path,
    source_ref: str,
    *,
    after_read: Optional[Callable[[Path], None]] = None,  # noqa: UP045 -- Python 3.9 contract
) -> bytes:
    """Read one regular file twice through a stable no-follow descriptor."""
    parts = _source_parts(source_ref)
    parent_fd, parent_path = _open_directory(root, parts[:-1])
    display_path = parent_path / parts[-1]
    file_fd = -1
    try:
        try:
            file_fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd)
        except OSError as exc:
            if exc.errno in {errno.ELOOP, errno.ENOTDIR}:
                _fail("dangling_reference")
            _fail("source_unprovable")
        before = os.fstat(file_fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_SOURCE_BYTES:
            _fail("source_unprovable")
        content = _read_fd(file_fd)
        if len(content) != before.st_size:
            _fail("source_digest_mismatch")
        if after_read is not None:
            after_read(display_path)
        after = os.fstat(file_fd)
        try:
            entry = os.stat(parts[-1], dir_fd=parent_fd, follow_symlinks=False)
        except OSError:
            _fail("source_digest_mismatch")
        if _identity(before) != _identity(after) or (entry.st_dev, entry.st_ino) != (before.st_dev, before.st_ino):
            _fail("source_digest_mismatch")
        os.lseek(file_fd, 0, os.SEEK_SET)
        replay = _read_fd(file_fd)
        final = os.fstat(file_fd)
        if replay != content or _identity(after) != _identity(final):
            _fail("source_digest_mismatch")
        return content
    except OSError:
        _fail("source_unprovable")
    finally:
        if file_fd >= 0:
            os.close(file_fd)
        os.close(parent_fd)


def list_stable_directory(root: Path, source_ref: str) -> tuple[str, ...]:
    """List a no-follow rooted directory and reject a concurrent entry change."""
    parts = _source_parts(source_ref)
    directory_fd, _display = _open_directory(root, parts)
    try:
        before = os.fstat(directory_fd)
        names = tuple(sorted(os.listdir(directory_fd)))
        after = os.fstat(directory_fd)
        replay = tuple(sorted(os.listdir(directory_fd)))
        final = os.fstat(directory_fd)
        if names != replay or _identity(before) != _identity(after) or _identity(after) != _identity(final):
            _fail("source_digest_mismatch")
        return names
    except OSError:
        _fail("source_unprovable")
    finally:
        os.close(directory_fd)


def snapshot_directory_files(root: Path, source_ref: str, *, suffix: str) -> NativeDirectorySnapshot:
    """Capture stable names and complete bytes for all matching authority files."""
    names_before = tuple(name for name in list_stable_directory(root, source_ref) if name.endswith(suffix))
    entries = tuple((name, read_stable_source(root, f"{source_ref}/{name}")) for name in names_before)
    names_after = tuple(name for name in list_stable_directory(root, source_ref) if name.endswith(suffix))
    if names_before != names_after:
        _fail("source_digest_mismatch")
    digest = hashlib.sha256()
    for name, content in entries:
        encoded_name = name.encode("utf-8")
        digest.update(len(encoded_name).to_bytes(8, "big"))
        digest.update(encoded_name)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return NativeDirectorySnapshot(entries=entries, digest="sha256:" + digest.hexdigest())


def _module_guard_statements(statements: list[ast.stmt]) -> list[ast.stmt]:
    """Return module-scope statements, descending only through import guards."""
    result: list[ast.stmt] = []
    for statement in statements:
        result.append(statement)
        if isinstance(statement, ast.Try):
            result.extend(_module_guard_statements(statement.body))
            result.extend(_module_guard_statements(statement.orelse))
            result.extend(_module_guard_statements(statement.finalbody))
            for handler in statement.handlers:
                result.extend(_module_guard_statements(handler.body))
    return result


def _import_bound_names(node: ast.AST) -> set[str]:
    if isinstance(node, ast.ImportFrom):
        return {alias.asname or alias.name for alias in node.names if alias.name != "*"}
    if isinstance(node, ast.Import):
        return {alias.asname or alias.name.split(".", 1)[0] for alias in node.names}
    return set()


def _canonical_fastmcp_alias(tree: ast.Module) -> str:
    canonical: list[tuple[ast.ImportFrom, str]] = []
    for statement in _module_guard_statements(tree.body):
        if isinstance(statement, ast.ImportFrom) and statement.module == "fastmcp" and statement.level == 0:
            for alias in statement.names:
                if alias.name == "FastMCP":
                    canonical.append((statement, alias.asname or alias.name))
    if len(canonical) != 1:
        _fail("source_unprovable")
    canonical_node, canonical_alias = canonical[0]
    if sum(1 for alias in canonical_node.names if (alias.asname or alias.name) == canonical_alias) != 1:
        _fail("source_unprovable")

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.ImportFrom) and any(alias.name == "*" for alias in node.names):
                _fail("source_unprovable")
            if node is not canonical_node and canonical_alias in _import_bound_names(node):
                _fail("source_unprovable")
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)) and node.id == canonical_alias:
            _fail("source_unprovable")
        elif isinstance(node, ast.arg) and node.arg == canonical_alias:
            _fail("source_unprovable")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == canonical_alias:
            _fail("source_unprovable")
        elif isinstance(node, ast.ExceptHandler) and node.name == canonical_alias:
            _fail("source_unprovable")
        elif isinstance(node, (ast.Global, ast.Nonlocal)) and canonical_alias in node.names:
            _fail("source_unprovable")
        elif isinstance(node, ast.Attribute) and isinstance(node.ctx, (ast.Store, ast.Del)) and node.attr == canonical_alias:
            _fail("source_unprovable")
        elif (
            isinstance(node, ast.Subscript)
            and isinstance(node.ctx, (ast.Store, ast.Del))
            and isinstance(node.slice, ast.Constant)
            and node.slice.value == canonical_alias
        ):
            _fail("source_unprovable")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in {
                "__import__", "compile", "eval", "exec", "globals", "locals", "setattr", "delattr", "vars"
            }:
                _fail("source_unprovable")
            if (
                isinstance(node.func, ast.Attribute)
                and node.func.attr in {"__setattr__", "__delattr__", "__setitem__", "update"}
                and any(isinstance(arg, ast.Constant) and arg.value == canonical_alias for arg in node.args)
            ):
                _fail("source_unprovable")
    return canonical_alias


def _literal_native_name(call: ast.Call) -> Any:
    """Read the first positional or exact ``name=`` constant, never both."""
    return _literal_call_value(call, "name", 0)


def _literal_call_value(call: ast.Call, keyword_name: str, positional_index: int) -> Any:
    keyword_values = [item.value for item in call.keywords if item.arg == keyword_name]
    positional = call.args[positional_index] if len(call.args) > positional_index else None
    if len(keyword_values) > 1 or (keyword_values and positional is not None):
        return None
    node = keyword_values[0] if keyword_values else positional
    return node.value if isinstance(node, ast.Constant) else None


def _literal_keyword_value(call: ast.Call, keyword_name: str) -> Any:
    values = [item.value for item in call.keywords if item.arg == keyword_name]
    if len(values) != 1:
        return None
    return values[0].value if isinstance(values[0], ast.Constant) else None


def parse_fastmcp_authority(content: bytes, source_ref: str, server_id: str) -> dict[str, Any]:
    """Prove one exact top-level FastMCP binding and its static tool set."""
    try:
        tree = ast.parse(content.decode("utf-8"), filename=source_ref, feature_version=(3, 9))
    except (SyntaxError, UnicodeDecodeError):
        _fail("source_schema_unsupported")
    if not isinstance(tree, ast.Module):
        _fail("source_schema_unsupported")
    canonical_alias = _canonical_fastmcp_alias(tree)

    authorities: list[tuple[str, ast.Call]] = []
    for statement in tree.body:
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)) or not isinstance(statement.value, ast.Call):
            continue
        function = statement.value.func
        if not isinstance(function, ast.Name) or function.id != canonical_alias:
            continue
        targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
        names = [target.id for target in targets if isinstance(target, ast.Name)]
        if len(names) != 1 or len(targets) != 1:
            _fail("duplicate_authority_claim")
        authorities.append((names[0], statement.value))
    if not authorities:
        _fail("source_unprovable")
    if len(authorities) != 1:
        _fail("duplicate_authority_claim")
    binding, call = authorities[0]
    native_name = _literal_native_name(call)
    if not isinstance(native_name, str) or native_name != server_id:
        _fail("source_unprovable")

    version_value = _literal_keyword_value(call, "version")
    version: Optional[str] = None  # noqa: UP045 -- Python 3.9 contract
    version_status = "unprovable"
    if isinstance(version_value, str) and version_value.strip() == version_value and 0 < len(version_value) <= 64:
        if not any(ord(character) < 32 for character in version_value):
            version = version_value
            version_status = "proved"

    tools: list[str] = []
    for statement in tree.body:
        if not isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in statement.decorator_list:
            function = decorator.func if isinstance(decorator, ast.Call) else decorator
            if (
                isinstance(function, ast.Attribute)
                and function.attr == "tool"
                and isinstance(function.value, ast.Name)
                and function.value.id == binding
                and (not isinstance(decorator, ast.Call) or not decorator.args)
                and (not isinstance(decorator, ast.Call) or not decorator.keywords)
            ):
                tools.append(statement.name)
    return {
        "binding": binding,
        "tools": tools,
        "native_version": version,
        "native_version_status": version_status,
    }
