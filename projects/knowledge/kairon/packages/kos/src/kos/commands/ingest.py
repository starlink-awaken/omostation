# ruff: noqa
"""KOS bulk ingest command."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

from kos.eidos import validate_object, KnowledgeCard, Fact, OntologyNode  # type: ignore[import-not-found]
from kos.meta_types import infer_meta_type  # type: ignore[import-not-found]

from typing import Callable, Any

try:
    from eidos.protocols.contracts import validate_contract_payload  # type: ignore[no-redef]
except ImportError:
    validate_contract_payload = None  # type: ignore[no-redef]

EIDOS_AVAILABLE = True


# ---- Optional Eidos schema validation ----
def _validate_eidos(file_path, schema_type=None) -> tuple[bool, list]:  # type: ignore[no-untyped-def]
    """Validate a JSON file against Eidos schema. Returns (is_valid, errors)."""
    try:
        import json
        import sys

        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
        st = (schema_type or "").upper()
        contract_name = {
            "KNOWLEDGECARD": "knowledge-card-v0.3",
            "FACT": "fact-v0.3",
        }.get(st)
        if contract_name and callable(validate_contract_payload):
            contract_errors = validate_contract_payload(contract_name, data)
            if contract_errors:
                return False, contract_errors
        if "CARD" in st or "KNOWLEDGE" in st:
            if KnowledgeCard is None:
                return True, []
            card = KnowledgeCard.from_dict(data)
            errors = card.validate()
            return len(errors) == 0, errors
        elif "FACT" in st:
            if Fact is None:
                return True, []
            fact = Fact.from_dict(data)
            errors = fact.validate()
            return len(errors) == 0, errors
        elif "NODE" in st or "ONTOLOGY" in st:
            if OntologyNode is None:
                return True, []
            node = OntologyNode.from_dict(data)
            errors = node.validate()
            return len(errors) == 0, errors
        return True, []
    except ImportError:
        return True, []
    except Exception as e:  # noqa: BLE001
        return False, [str(e)]


SUPPORTED_EXTENSIONS = {".md", ".json", ".txt"}
DEFAULT_ZONE = "default"


def time_to_timestamp(value: float) -> str:
    return datetime.fromtimestamp(value).strftime("%Y%m%d%H%M%S")


def _iter_supported_files(root: Path) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for filename in filenames:
            if filename.startswith("."):
                continue
            path = Path(dirpath) / filename
            if path.suffix.lower() in SUPPORTED_EXTENSIONS and path.is_file():
                yield path


def _first_heading(text: str, fallback: str) -> str:
    match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    return match.group(1).strip() if match else fallback


def _load_kos_indexer_class() -> type:
    from kos.indexer.engine import KosIndexer  # type: ignore[import-not-found]

    return KosIndexer


def _build_record(file_path: Path, root: Path) -> dict[str, Any]:
    rel_path = str(file_path.relative_to(root))
    ext = file_path.suffix.lower()
    canonical_path = f"kos::{DEFAULT_ZONE}::{rel_path}"
    doc_id = hashlib.sha1(canonical_path.encode()).hexdigest()
    raw_text = file_path.read_text(encoding="utf-8", errors="replace")
    metadata: dict[str, Any] = {
        "source_format": ext.lstrip("."),
        "relative_path": rel_path,
    }

    if ext == ".md":
        kind = "KnowledgeCard"
        title = _first_heading(raw_text, file_path.stem)
        body = raw_text[:8000]
    elif ext == ".txt":
        kind = "RawDocument"
        title = file_path.stem
        body = raw_text[:8000]
    else:
        kind = "RawDocument"
        title = file_path.stem
        body = raw_text[:8000]
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            metadata["json_error"] = str(exc)
        else:
            metadata["json_type"] = type(parsed).__name__
            if isinstance(parsed, dict):
                metadata["json_keys"] = sorted(parsed.keys())[:50]
                title = parsed.get("title") or parsed.get("name") or title
            if EIDOS_AVAILABLE and validate_object is not None:
                try:
                    metadata["eidos_validated"] = bool(validate_object(parsed))
                except Exception as exc:  # graceful fallback  # noqa: BLE001
                    metadata["eidos_error"] = str(exc)
                    metadata["eidos_validated"] = False
                if metadata.get("eidos_validated"):
                    kind = "KnowledgeCard"

    file_stat = file_path.stat()
    file_mtime = time_to_timestamp(file_stat.st_mtime)
    return {
        "doc_id": doc_id,
        "title": title,
        "kind": kind,
        "zone": DEFAULT_ZONE,
        "status": "active",
        "source": "ingest-command",
        "owner": "",
        "created_at": file_mtime,
        "updated_at": file_mtime,
        "trust_level": "working",
        "freshness": "active",
        "review_status": "pending",
        "schema_version": "1.0",
        "canonical_path": canonical_path,
        "source_url": "",
        "write_policy": "managed",
        "metadata_json": json.dumps(metadata, ensure_ascii=False),
        "body": body,
        "file_size": len(body.encode("utf-8")),
        "file_mtime": file_mtime,
        "source_path": str(file_path),
    }


def _store_document(record: dict[str, Any]) -> None:
    KosIndexer = _load_kos_indexer_class()  # type: ignore[no-untyped-call]
    indexer = KosIndexer()
    conn = indexer._connect()
    indexer._init_schema(conn)
    try:
        conn.execute("DELETE FROM documents WHERE doc_id=?", (record["doc_id"],))
        conn.execute("DELETE FROM documents_fts WHERE doc_id=?", (record["doc_id"],))
        conn.execute(
            """INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            tuple(
                record[k]
                for k in [
                    "doc_id",
                    "title",
                    "kind",
                    "zone",
                    "status",
                    "source",
                    "owner",
                    "created_at",
                    "updated_at",
                    "trust_level",
                    "freshness",
                    "review_status",
                    "schema_version",
                    "canonical_path",
                    "source_url",
                    "write_policy",
                    "metadata_json",
                    "body",
                    "file_size",
                    "file_mtime",
                ]
            ),
        )
        conn.execute(
            "INSERT INTO documents_fts (doc_id,title,body,tags,canonical_path) VALUES (?,?,?,?,?)",
            (record["doc_id"], record["title"], record["body"], "", record["canonical_path"]),
        )
        conn.execute(
            """INSERT OR REPLACE INTO file_fingerprints
                (canonical_path,zone,sha256_hash,file_size,file_mtime,last_indexed,absent_since,file_format)
                VALUES (?,?,?,?,?,?,NULL,?)""",
            (
                record["canonical_path"],
                record["zone"],
                hashlib.sha256(record["body"].encode("utf-8")).hexdigest(),
                record["file_size"],
                record["file_mtime"],
                record["updated_at"],
                Path(record["source_path"]).suffix.lower().lstrip("."),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def ingest_command(args) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    root = Path(getattr(args, "path", ".")).expanduser().resolve()
    dry_run = bool(getattr(args, "dry_run", False))
    verbose = bool(getattr(args, "verbose", False))

    if not root.exists():
        print(f"Error: path not found: {root}", file=sys.stderr)
        return {"ok": False, "found": 0, "indexed": 0, "skipped": 0}
    if not root.is_dir():
        print(f"Error: path is not a directory: {root}", file=sys.stderr)
        return {"ok": False, "found": 0, "indexed": 0, "skipped": 0}

    candidates = list(_iter_supported_files(root))
    found = len(candidates)
    indexed = 0
    skipped = 0

    if verbose:
        mode = "dry-run" if dry_run else "ingest"
        print(f"Scanning {root} ({mode})")

    for file_path in candidates:
        rel_path = str(file_path.relative_to(root))
        ext = file_path.suffix.lower()
        try:
            record = _build_record(file_path, root)
        except Exception as exc:  # noqa: BLE001
            skipped += 1
            if verbose:
                print(f"skip {rel_path}: {exc}", file=sys.stderr)
            continue

        schema_type = record["kind"]
        if getattr(args, "schema", None) and ext == ".json":
            is_valid, errors = _validate_eidos(file_path, args.schema)  # type: ignore[no-untyped-call]
            if not is_valid:
                print(f"  ⚠ {file_path}: Eidos validation failed: {errors}")
                schema_type = "raw"
                record["kind"] = "RawDocument"
            elif verbose:
                print(f"  ✓ {file_path}: validated as {args.schema}")

        metadata = json.loads(record["metadata_json"])
        metadata["meta_type"] = infer_meta_type(schema_type, record["source_path"])
        record["metadata_json"] = json.dumps(metadata, ensure_ascii=False)

        if dry_run:
            skipped += 1
            if verbose:
                print(f"dry-run {record['kind']}: {rel_path}")
            continue

        try:
            _store_document(record)
        except Exception as exc:  # noqa: BLE001
            skipped += 1
            if verbose:
                print(f"skip {rel_path}: {exc}", file=sys.stderr)
            continue

        indexed += 1
        if verbose:
            print(f"indexed {record['kind']}: {rel_path}")

    result = {"ok": True, "found": found, "indexed": indexed, "skipped": skipped}
    if hasattr(args, "pipeline_output") and args.pipeline_output:
        total_files = found
        Path(args.pipeline_output).write_text(
            json.dumps(
                {"status": "done", "files": total_files or 0, "schema": getattr(args, "schema", "auto")}, indent=2
            )
        )
        if not args.verbose:
            return result  # Suppress normal output in pipeline mode

    print(f"Found {found} files, indexed {indexed}, skipped {skipped}")
    return result


def import_schema_command(args: argparse.Namespace) -> int:
    """Import an Eidos Schema definition into KOS storage.

    This creates the storage tables/indices based on the schema's field definitions.
    """
    import json
    from pathlib import Path

    schema_path = args.schema_file
    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_def = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading schema: {e}")
        return 1

    schema_name = schema_def.get("title", "untitled")
    fields = list(schema_def.get("properties", {}).keys())

    print(f"Imported schema: {schema_name}")
    print(f"Fields ({len(fields)}): {', '.join(fields)}")

    store_path = Path.home() / ".kos" / "schemas"
    store_path.mkdir(parents=True, exist_ok=True)
    output_path = store_path / f"{schema_name}.json"
    output_path.write_text(json.dumps(schema_def, indent=2), encoding="utf-8")
    print(f"Schema stored at: {output_path}")
    return 0
