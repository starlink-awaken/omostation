"""Deterministic MOF Control Compiler — core API.

Reads the W1 core M2 YAML schemas (``src/ecos/ssot/mof/m2/*.yaml``) as the
single model truth and deterministically compiles them into a set of artifact
classes (JSON Schema, Pydantic, Zod, SQLite DDL).

Determinism contract
--------------------
Given the same set of M2 input files, repeated compilation MUST produce
byte-identical artifacts:

- schemas are processed in sorted-by-filename order;
- properties keep their YAML declaration order (the M2 files are the truth);
- emitted JSON is key-sorted and never embeds timestamps, absolute paths or
  process-dependent state;
- every artifact carries a header that references the model-truth files and
  the compiler version, but no generation time.

The :class:`MofCompiler` exposes three entry points:

- :meth:`MofCompiler.compile` — in-memory artifact generation (the reusable
  Python API);
- :meth:`MofCompiler.write` — persist artifacts plus a SHA-256 manifest;
- :meth:`MofCompiler.check` — verify existing output matches a fresh
  compilation (tamper detection).

The thin CLI wrapper lives in ``ecos.ssot.tools.mof_compile``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ecos.ssot.mof.compiler.emitters import (
    ARTIFACT_CLASSES,
    emit_json_schema,
    emit_pydantic,
    emit_sqlite,
    emit_zod,
)

__all__ = [
    "ARTIFACT_CLASSES",
    "M2Property",
    "M2Schema",
    "MofCompiler",
    "CompilerError",
]

M2_DIR_DEFAULT = Path(__file__).resolve().parents[1] / "m2"

# Canonical M2 types used by the IR/emitters.
CANONICAL_TYPES = {
    "string",
    "int",
    "number",
    "bool",
    "enum",
    "list",
    "map",
    "ref",
    "date",
    "datetime",
}

# Type aliases found in the W1 M2 truth, normalized at parse time.
TYPE_ALIASES = {
    "integer": "int",
    "float": "number",
    "boolean": "bool",
    "array": "list",
    "object": "map",
    "dict": "map",
    "path": "string",
    "semver": "string",
}

SUPPORTED_TYPES = CANONICAL_TYPES | set(TYPE_ALIASES)

_REF_TARGET_RE = "→([A-Za-z][A-Za-z0-9_]*)"


class CompilerError(RuntimeError):
    """Raised when the M2 input cannot be compiled."""


@dataclass(frozen=True)
class M2Property:
    """A single property of an M2 schema (required or optional)."""

    name: str
    type: str
    description: str
    pattern: str | None = None
    format: str | None = None
    items_type: str | None = None
    ref_target: str | None = None
    enum_values: tuple[str, ...] | None = None
    required: bool = False


@dataclass(frozen=True)
class M2Schema:
    """Parsed M2 contract — the intermediate representation of one type."""

    name: str
    version: str
    m3_parent: str
    description: str
    properties: tuple[M2Property, ...] = field(default_factory=tuple)
    state_machine: tuple[tuple[str, tuple[str, ...]], ...] = field(
        default_factory=tuple
    )
    validation_rules: tuple[dict, ...] = field(default_factory=tuple)

    @property
    def required_names(self) -> tuple[str, ...]:
        return tuple(p.name for p in self.properties if p.required)

    @property
    def referenced(self) -> tuple[str, ...]:
        """Explicit reference targets used by this schema (deduplicated, order-preserving)."""
        seen: list[str] = []
        for p in self.properties:
            if p.ref_target and p.ref_target not in seen:
                seen.append(p.ref_target)
        return tuple(seen)


def _parse_ref_target(description: str | None) -> str | None:
    if not description:
        return None
    import re

    m = re.search(_REF_TARGET_RE, description)
    return m.group(1) if m else None


def _normalize_type(ptype: str, name: str, path: Path) -> str:
    if ptype not in SUPPORTED_TYPES:
        raise CompilerError(
            f"{path.name}: property '{name}': unsupported type '{ptype}'"
        )
    return TYPE_ALIASES.get(ptype, ptype)


def _snake_case(name: str) -> str:
    import re as _re

    return _re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _resolve_body(raw: dict, m2_type: str, path: Path) -> dict:
    """Fail-closed generic body resolution.

    Rules (WP-W1-02-008):
    1. Exact ``raw[m2_type]`` always wins.
    2. The **only** allowed compatibility key is ``_snake_case(m2_type)``.
       Any other marker-bearing top-level dict is ignored — a ``wrong_body``
       key never becomes a false compatibility body.
    3. If exact body exists and the canonical compatibility key differs and
       is present, the two must be equal or the file raises
       :class:`CompilerError`.
    4. Without an exact body, only ``raw[compat_key]`` (when it is a dict)
       is accepted; anything else raises ``no resolvable body``.
    """
    exact = raw.get(m2_type)
    if isinstance(exact, dict):
        compat_key = _snake_case(m2_type)
        if compat_key != m2_type:
            compat = raw.get(compat_key)
            if isinstance(compat, dict) and compat != exact:
                raise CompilerError(
                    f"{path.name}: schema '{m2_type}' has divergent exact and"
                    f" compatible ('{compat_key}') bodies"
                )
        return exact
    compat_key = _snake_case(m2_type)
    if compat_key != m2_type:
        body = raw.get(compat_key)
        if isinstance(body, dict):
            return body
    raise CompilerError(f"{path.name}: schema '{m2_type}' has no resolvable body")


def _parse_property(
    name: str, spec: dict, required: bool, model_names: set[str], path: Path
) -> M2Property:
    raw_type = str(spec.get("type", "string"))
    description = str(spec.get("description", "")).strip()
    if raw_type in model_names:
        ptype = "ref"
        ref_target = raw_type
        items_type = None
    else:
        ptype = _normalize_type(raw_type, name, path)
        ref_target = (
            _parse_ref_target(description) if ptype in ("ref", "list") else None
        )
        items_type = None
    if ptype == "list":
        items = spec.get("items") or {}
        items_raw = str(items.get("type", "string"))
        if items_raw in model_names:
            items_type = "ref"
            ref_target = items_raw
        else:
            items_type = _normalize_type(items_raw, f"{name}.items", path)
            if ref_target is None and items_type in ("ref", "list"):
                ref_target = _parse_ref_target(str(items.get("description", "")))
    enum_values = None
    if ptype == "enum":
        values = spec.get("enum") or spec.get("values")
        if not values:
            raise CompilerError(
                f"{path.name}: property '{name}': enum type requires explicit values"
            )
        enum_values = tuple(str(v) for v in values)
    return M2Property(
        name=name,
        type=ptype,
        description=description,
        pattern=spec.get("pattern"),
        format=spec.get("format"),
        items_type=items_type,
        ref_target=ref_target,
        enum_values=enum_values,
        required=required,
    )


def _parse_properties(
    body: dict, model_names: set[str], path: Path
) -> tuple[M2Property, ...]:
    props: list[M2Property] = []
    seen: dict[str, bool] = {}
    canonical = (("requiredProperties", True), ("optionalProperties", False))
    for section, default_required in canonical:
        specs = body.get(section)
        if specs is None:
            continue
        if not isinstance(specs, dict):
            raise CompilerError(f"{path.name}: '{section}' must be a mapping")
        for name, spec in specs.items():
            name = str(name)
            if name in seen:
                raise CompilerError(
                    f"{path.name}: conflicting duplicate property '{name}'"
                )
            seen[name] = default_required
            props.append(
                _parse_property(name, spec, default_required, model_names, path)
            )
    legacy = body.get("properties")
    if legacy is not None:
        if not isinstance(legacy, dict):
            raise CompilerError(f"{path.name}: 'properties' must be a mapping")
        for name, spec in legacy.items():
            name = str(name)
            if name in seen:
                raise CompilerError(
                    f"{path.name}: conflicting duplicate property '{name}'"
                )
            seen[name] = True
            required = bool(spec.get("required", False))
            props.append(_parse_property(name, spec, required, model_names, path))
    return tuple(props)


def _parse_state_machine(sm_raw: dict) -> tuple[tuple[str, tuple[str, ...]], ...]:
    if isinstance(sm_raw.get("states"), list):
        transitions_by_from: dict[str, list[str]] = {}
        for t in sm_raw.get("transitions") or []:
            if isinstance(t, dict):
                transitions_by_from.setdefault(str(t.get("from", "")), []).append(
                    str(t.get("to", ""))
                )
        return tuple(
            (str(state), tuple(transitions_by_from.get(str(state), ())))
            for state in sm_raw["states"]
        )
    state_machine: list[tuple[str, tuple[str, ...]]] = []
    for state, meta in sm_raw.items():
        if isinstance(meta, dict):
            transitions = tuple(str(t) for t in (meta.get("transitions") or []))
        else:
            transitions = tuple()
        state_machine.append((str(state), transitions))
    return tuple(state_machine)


def load_m2_dir(m2_dir: Path) -> list[M2Schema]:
    """Load every M2 YAML file in ``m2_dir`` via a deterministic two-pass load.

    Pass 1 collects the full set of model names so a property whose type names
    a known M2 model (e.g. ``GovernanceEvent.result: GovernanceCheck``) becomes
    an explicit reference. Pass 2 resolves each file's body (exact key first,
    then P1-S0 snake_case compatibility), normalizes canonical and legacy
    property sections, and parses properties.

    Files are processed in sorted-by-filename order so the returned list is
    deterministic. Files that do not carry a top-level ``m2_type``/``version``
    envelope are skipped (e.g. READMEs or notes); files that do carry one but
    cannot resolve an unambiguous body raise :class:`CompilerError`.
    """
    raw_files: list[tuple[Path, dict, str, str]] = []
    model_names: set[str] = set()
    for path in sorted(m2_dir.glob("*.yaml")):
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise CompilerError(f"{path.name}: invalid YAML: {exc}") from exc
        if not isinstance(raw, dict):
            continue
        m2_type = raw.get("m2_type")
        version = raw.get("version")
        if not m2_type or not version:
            continue
        m2_type, version = str(m2_type), str(version)
        model_names.add(m2_type)
        raw_files.append((path, raw, m2_type, version))

    schemas: list[M2Schema] = []
    for path, raw, m2_type, version in raw_files:
        body = _resolve_body(raw, m2_type, path)
        schemas.append(
            M2Schema(
                name=m2_type,
                version=version,
                m3_parent=str(body.get("m3_parent", "")),
                description=str(body.get("description", "")).strip(),
                properties=_parse_properties(body, model_names, path),
                state_machine=_parse_state_machine(body.get("stateMachine") or {}),
                validation_rules=tuple(body.get("validationRules") or []),
            )
        )
    return schemas


class MofCompiler:
    """Deterministic MOF Control Compiler.

    ``m2_dir`` defaults to the checked-in W1 M2 truth
    (``src/ecos/ssot/mof/m2``). Set ``out_dir`` per instance for convenience,
    or pass it explicitly to :meth:`write` / :meth:`check`.
    """

    def __init__(
        self, m2_dir: Path | str | None = None, out_dir: Path | str | None = None
    ) -> None:
        self.m2_dir = Path(m2_dir) if m2_dir else M2_DIR_DEFAULT
        self.out_dir = Path(out_dir) if out_dir else None

    # ── model truth ────────────────────────────────────────────────

    def load(self) -> list[M2Schema]:
        return load_m2_dir(self.m2_dir)

    # ── compilation ────────────────────────────────────────────────

    def compile(self, artifact_classes: list[str] | None = None) -> dict[str, str]:
        """Compile all M2 schemas into the requested artifact classes.

        Returns ``{artifact_class: content}``. When ``artifact_classes`` is
        ``None`` every registered class is emitted.
        """
        schemas = self.load()
        if not schemas:
            raise CompilerError(f"no M2 schemas found in {self.m2_dir}")
        classes = artifact_classes or list(ARTIFACT_CLASSES)
        unknown = set(classes) - set(ARTIFACT_CLASSES)
        if unknown:
            raise CompilerError(f"unknown artifact class(es): {sorted(unknown)}")
        emit = {
            "json-schema": emit_json_schema,
            "pydantic": emit_pydantic,
            "zod": emit_zod,
            "sqlite": emit_sqlite,
        }
        return {cls: emit[cls](schemas, self.m2_dir) for cls in classes}

    # ── persistence + tamper detection ─────────────────────────────

    def artifact_path(self, out_dir: Path | None = None) -> dict[str, Path]:
        base = Path(out_dir) if out_dir else (self.out_dir or Path.cwd())
        return {
            "json-schema": base / "mof-control.schema.json",
            "pydantic": base / "mof_control_models.py",
            "zod": base / "mof-control-schemas.ts",
            "sqlite": base / "mof-control.sql",
        }

    def manifest_path(self, out_dir: Path | None = None) -> Path:
        base = Path(out_dir) if out_dir else (self.out_dir or Path.cwd())
        return base / "mof-control.manifest.json"

    def write(self, out_dir: Path | None = None) -> dict[str, Path]:
        """Compile and persist every artifact plus a SHA-256 manifest.

        The manifest records the canonical artifact hash so :meth:`check`
        can detect tampering without re-arguing about content.
        """
        base = Path(out_dir) if out_dir else (self.out_dir or Path.cwd())
        base.mkdir(parents=True, exist_ok=True)
        artifacts = self.compile()
        written: dict[str, Path] = {}
        manifest: dict[str, str] = {}
        for cls, content in artifacts.items():
            path = self.artifact_path(base)[cls]
            path.write_text(content, encoding="utf-8")
            written[cls] = path
            manifest[cls] = hashlib.sha256(content.encode("utf-8")).hexdigest()
        manifest_path = self.manifest_path(base)
        manifest_path.write_text(
            json.dumps(
                {"artifacts": manifest, "source_dir": self.m2_dir.name},
                sort_keys=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        written["manifest"] = manifest_path
        return written

    def check(self, out_dir: Path | None = None) -> list[str]:
        """Verify on-disk artifacts match a fresh compilation.

        Returns a list of mismatch descriptions; an empty list means the
        output is untampered. Detected: missing or unreadable manifest,
        manifest hash differing from the fresh compile, on-disk artifact
        content differing from a fresh compile, and artifact bytes whose
        hash disagrees with the manifest record. Callers should treat a
        non-empty result as a hard failure (nonzero exit).
        """
        base = Path(out_dir) if out_dir else (self.out_dir or Path.cwd())
        problems: list[str] = []
        artifacts = self.compile()
        fresh_hashes = {
            cls: hashlib.sha256(content.encode("utf-8")).hexdigest()
            for cls, content in artifacts.items()
        }
        manifest_path = self.manifest_path(base)
        recorded: dict[str, str] = {}
        if not manifest_path.exists():
            problems.append(f"missing manifest: {manifest_path}")
        else:
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                recorded = manifest.get("artifacts", {})
            except (json.JSONDecodeError, OSError) as exc:
                problems.append(
                    f"tampered manifest: {manifest_path} (unreadable: {exc})"
                )
            else:
                for cls in artifacts:
                    if recorded.get(cls) != fresh_hashes[cls]:
                        problems.append(
                            f"tampered manifest: {manifest_path} (hash mismatch for {cls})"
                        )
        for cls, content in artifacts.items():
            path = self.artifact_path(base)[cls]
            if not path.exists():
                problems.append(f"missing artifact: {path}")
                continue
            actual = path.read_text(encoding="utf-8")
            if actual != content:
                problems.append(
                    f"tampered artifact: {path} (content differs from fresh compile)"
                )
            elif recorded.get(cls) and hashlib.sha256(
                actual.encode("utf-8")
            ).hexdigest() != recorded.get(cls):
                problems.append(
                    f"tampered artifact: {path} (hash differs from manifest record)"
                )
        return problems
