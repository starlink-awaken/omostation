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
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

MAX_SOURCE_BYTES = 4 * 1024 * 1024
SAFE_SOURCE_PART = re.compile(r"^[^/\\\x00]+$")
SAFE_TOOL_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,256}$")
AGORA_COMPOSITE_SOURCE_REF = "projects/agora/src/agora/server/mcp.py"
AGORA_COMPOSITE_MODULE = "agora.server.mcp"
AGORA_COMPOSITE_NATIVE_NAME = "Agora — Service Convergence Hub"
AGORA_SOURCE_PREFIX = "projects/agora/src/"


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


def _parse_python_module(content: bytes, source_ref: str) -> ast.Module:
    try:
        tree = ast.parse(content.decode("utf-8"), filename=source_ref, feature_version=(3, 9))
    except (SyntaxError, UnicodeDecodeError):
        _fail("source_schema_unsupported")
    if not isinstance(tree, ast.Module):
        _fail("source_schema_unsupported")
    return tree


def _top_level_fastmcp_binding(tree: ast.Module) -> tuple[str, ast.Call]:
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
    return authorities[0]


def _tool_factory_name(
    call: ast.Call, binding: str, default: str
) -> Optional[str]:  # noqa: UP045 -- Python 3.9 contract
    function = call.func
    if not (
        isinstance(function, ast.Attribute)
        and function.attr == "tool"
        and isinstance(function.value, ast.Name)
        and function.value.id == binding
    ):
        return None
    if call.args:
        _fail("source_unprovable")
    if not call.keywords:
        name = default
    elif (
        len(call.keywords) == 1
        and call.keywords[0].arg == "name"
        and isinstance(call.keywords[0].value, ast.Constant)
        and isinstance(call.keywords[0].value.value, str)
    ):
        name = call.keywords[0].value.value
    else:
        _fail("source_unprovable")
    if not SAFE_TOOL_NAME.fullmatch(name):
        _fail("source_unprovable")
    return name


def _decorated_tool_names(function: ast.AST, binding: str) -> tuple[list[str], set[int]]:
    if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return [], set()
    tools: list[str] = []
    recognized_calls: set[int] = set()
    for decorator in function.decorator_list:
        if isinstance(decorator, ast.Call):
            name = _tool_factory_name(decorator, binding, function.name)
            if name is not None:
                tools.append(name)
                recognized_calls.add(id(decorator))
        elif (
            isinstance(decorator, ast.Attribute)
            and decorator.attr == "tool"
            and isinstance(decorator.value, ast.Name)
            and decorator.value.id == binding
        ):
            _fail("source_unprovable")
    return tools, recognized_calls


def _registration_tool_names(function: ast.AST, binding_parameter: str) -> list[str]:
    if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
        _fail("source_unprovable")
    tools: list[str] = []
    recognized_calls: set[int] = set()
    for statement in function.body:
        declared, decorator_calls = _decorated_tool_names(statement, binding_parameter)
        tools.extend(declared)
        recognized_calls.update(decorator_calls)
        if not isinstance(statement, ast.Expr) or not isinstance(statement.value, ast.Call):
            continue
        outer = statement.value
        if not isinstance(outer.func, ast.Call):
            continue
        inner = outer.func
        if not (
            len(outer.args) == 1
            and isinstance(outer.args[0], ast.Name)
            and not outer.keywords
        ):
            if _tool_factory_name(inner, binding_parameter, "invalid") is not None:
                _fail("source_unprovable")
            continue
        name = _tool_factory_name(inner, binding_parameter, outer.args[0].id)
        if name is not None:
            tools.append(name)
            recognized_calls.update({id(inner), id(outer)})

    parent: dict[int, ast.AST] = {}
    for node in ast.walk(function):
        for child in ast.iter_child_nodes(node):
            parent[id(child)] = node
        if isinstance(node, ast.Name) and node.id == binding_parameter and isinstance(node.ctx, (ast.Store, ast.Del)):
            _fail("source_unprovable")
    for node in ast.walk(function):
        if not isinstance(node, ast.Name) or node.id != binding_parameter or not isinstance(node.ctx, ast.Load):
            continue
        current: Optional[ast.AST] = parent.get(id(node))  # noqa: UP045 -- Python 3.9 contract
        proved = False
        while current is not None and current is not function:
            if isinstance(current, ast.Call) and id(current) in recognized_calls:
                proved = True
                break
            current = parent.get(id(current))
        if not proved:
            _fail("source_unprovable")
    return tools


def _module_imports(tree: ast.Module, module: str, source_ref: str) -> dict[str, tuple[str, str]]:
    imports: dict[str, tuple[str, str]] = {}
    is_package = source_ref.endswith("/__init__.py")
    for statement in _module_guard_statements(tree.body):
        if not isinstance(statement, ast.ImportFrom):
            continue
        if any(alias.name == "*" for alias in statement.names):
            _fail("source_unprovable")
        if statement.level:
            base = module.split(".") if is_package else module.split(".")[:-1]
            remove = statement.level - 1
            if remove > len(base):
                _fail("source_unprovable")
            base = base[: len(base) - remove] if remove else base
            target_module = ".".join([*base, *(statement.module or "").split(".")]).rstrip(".")
        else:
            target_module = statement.module or ""
        if not target_module:
            _fail("source_unprovable")
        for alias in statement.names:
            local_name = alias.asname or alias.name
            target = (target_module, alias.name)
            if local_name in imports and imports[local_name] != target:
                _fail("duplicate_authority_claim")
            imports[local_name] = target
    return imports


def _load_agora_module(
    root: Path,
    module: str,
    cache: dict[str, tuple[str, bytes, ast.Module]],
    sources: dict[str, bytes],
) -> tuple[str, bytes, ast.Module]:
    if module in cache:
        return cache[module]
    if not module.startswith("agora.") or not all(SAFE_SOURCE_PART.fullmatch(part) for part in module.split(".")):
        _fail("source_unprovable")
    relative = module.replace(".", "/")
    candidates = (
        f"{AGORA_SOURCE_PREFIX}{relative}/__init__.py",
        f"{AGORA_SOURCE_PREFIX}{relative}.py",
    )
    for candidate in candidates:
        try:
            content = read_stable_source(root, candidate)
        except NativeInspectionError as exc:
            if str(exc) != "source_unprovable":
                raise
            continue
        loaded = (candidate, content, _parse_python_module(content, candidate))
        cache[module] = loaded
        sources[candidate] = content
        return loaded
    _fail("source_unprovable")


def _resolve_registration_function(
    root: Path,
    module: str,
    symbol: str,
    cache: dict[str, tuple[str, bytes, ast.Module]],
    sources: dict[str, bytes],
    seen: set[tuple[str, str]],
) -> tuple[str, ast.AST]:
    key = (module, symbol)
    if key in seen:
        _fail("source_unprovable")
    seen.add(key)
    source_ref, _content, tree = _load_agora_module(root, module, cache, sources)
    matches = [
        statement
        for statement in tree.body
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)) and statement.name == symbol
    ]
    if len(matches) > 1:
        _fail("duplicate_authority_claim")
    if matches:
        return source_ref, matches[0]
    imported = _module_imports(tree, module, source_ref).get(symbol)
    if imported is None:
        _fail("source_unprovable")
    return _resolve_registration_function(root, imported[0], imported[1], cache, sources, seen)


def _composite_proof_content(sources: Mapping[str, bytes]) -> bytes:
    payload = bytearray(b"python-ast-fastmcp-composite/v1\x00")
    for source_ref in sorted(sources):
        encoded_ref = source_ref.encode("utf-8")
        content = sources[source_ref]
        payload.extend(len(encoded_ref).to_bytes(8, "big"))
        payload.extend(encoded_ref)
        payload.extend(len(content).to_bytes(8, "big"))
        payload.extend(content)
    return bytes(payload)


def parse_fastmcp_composite_authority(root: Path, source_ref: str, server_id: str) -> dict[str, Any]:
    """Prove Agora's exact static FastMCP registration graph without importing it."""
    if source_ref != AGORA_COMPOSITE_SOURCE_REF or server_id != "agora":
        _fail("source_unprovable")
    entry_content = read_stable_source(root, source_ref)
    tree = _parse_python_module(entry_content, source_ref)
    binding, call = _top_level_fastmcp_binding(tree)
    native_name = _literal_native_name(call)
    if native_name != AGORA_COMPOSITE_NATIVE_NAME:
        _fail("source_unprovable")

    sources = {source_ref: entry_content}
    module_cache: dict[str, tuple[str, bytes, ast.Module]] = {}
    imported_symbols = _module_imports(tree, AGORA_COMPOSITE_MODULE, source_ref)
    tools: list[str] = []
    for statement in tree.body:
        declared, _recognized = _decorated_tool_names(statement, binding)
        tools.extend(declared)

    registrations: set[tuple[str, str]] = set()
    for statement in _module_guard_statements(tree.body):
        if not isinstance(statement, ast.Expr) or not isinstance(statement.value, ast.Call):
            continue
        registration = statement.value
        if (
            not registration.args
            or not isinstance(registration.args[0], ast.Name)
            or registration.args[0].id != binding
        ):
            continue
        if not isinstance(registration.func, ast.Name):
            _fail("source_unprovable")
        if registration.keywords or any(isinstance(argument, ast.Starred) for argument in registration.args):
            _fail("source_unprovable")
        target = imported_symbols.get(registration.func.id)
        if target is None:
            _fail("source_unprovable")
        if target in registrations:
            _fail("duplicate_authority_claim")
        registrations.add(target)
        _registration_ref, function = _resolve_registration_function(
            root, target[0], target[1], module_cache, sources, set()
        )
        parameters = (
            [*function.args.posonlyargs, *function.args.args]
            if isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef))
            else []
        )
        if not parameters:
            _fail("source_unprovable")
        required_parameters = len(parameters) - len(function.args.defaults)
        if (
            function.args.vararg is not None
            or function.args.kwarg is not None
            or any(default is None for default in function.args.kw_defaults)
            or not required_parameters <= len(registration.args) <= len(parameters)
        ):
            _fail("source_unprovable")
        tools.extend(_registration_tool_names(function, parameters[0].arg))

    if not registrations:
        _fail("source_unprovable")
    if len(tools) != len(set(tools)):
        _fail("duplicate_authority_claim")

    version_value = _literal_keyword_value(call, "version")
    version: Optional[str] = None  # noqa: UP045 -- Python 3.9 contract
    version_status = "unprovable"
    if isinstance(version_value, str) and version_value.strip() == version_value and 0 < len(version_value) <= 64:
        if not any(ord(character) < 32 for character in version_value):
            version = version_value
            version_status = "proved"
    return {
        "binding": binding,
        "native_name": native_name,
        "tools": sorted(tools),
        "source_refs": sorted(sources),
        "content": _composite_proof_content(sources),
        "native_version": version,
        "native_version_status": version_status,
    }


def parse_fastmcp_authority(content: bytes, source_ref: str, server_id: str) -> dict[str, Any]:
    """Prove one exact top-level FastMCP binding and its static tool set."""
    tree = _parse_python_module(content, source_ref)
    binding, call = _top_level_fastmcp_binding(tree)
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
