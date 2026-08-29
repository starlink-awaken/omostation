#!/usr/bin/env python3
"""BOS runtime shim for the committed ReachBridge KEMS adapter.

The transport contract lives in ``projects/runtime``. This file only builds
the redacted manifest from the local inbox and delegates dispatch, so the
external runtime directory cannot grow a second implementation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

SOURCE_PATTERNS = (
    "*-auto-seeyon-oa-pending.md",
    "*-auto-netease-mailmaster.md",
    "*-auto-apple-mail.md",
    "*-auto-iphone-sms.md",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Submit a redacted BOS mesh manifest to ReachBridge")
    parser.add_argument("--docs-root", type=Path, default=Path(os.environ.get("BOS_DOCS_ROOT", "/Users/xiamingxing/Documents")))
    parser.add_argument("--run-id", default=os.environ.get("BOS_MESH_RUN_ID", ""))
    parser.add_argument("--timeout", type=int, default=int(os.environ.get("BOS_REACHBRIDGE_TIMEOUT", "15")))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--production", action="store_true", help="require enterprise HTTP and record a receipt")
    parser.add_argument("--receipt-output", type=Path, help="path for the redacted dispatch receipt")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(docs_root: Path, run_id: str) -> dict[str, object]:
    inbox = docs_root / "_inbox"
    documents = []
    for pattern in SOURCE_PATTERNS:
        for path in sorted(inbox.glob(pattern)):
            if path.is_file():
                documents.append(
                    {
                        "source_ref": f"vault://redacted/{path.name}",
                        "filename": path.name,
                        "sha256": sha256(path),
                        "bytes": path.stat().st_size,
                    }
                )
    return {
        "schema": "bos.reachbridge.manifest.v1",
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dispatch_mode": "review_only",
        "documents": documents,
    }


def _runtime_root() -> Path:
    configured_root = Path(os.environ.get("BOS_RUNTIME_ROOT", "")).expanduser()
    workspace_root = Path(os.environ.get("BOS_WORKSPACE_ROOT", "/Users/xiamingxing/Workspace"))
    candidates = [
        configured_root,
        workspace_root / "projects" / "runtime",
        Path("/Users/xiamingxing/ws-runtime-kems-m6-20260731"),
    ]
    resolved = next(
        (candidate for candidate in candidates if candidate and (candidate / "scripts" / "reachbridge-kems-gateway.py").is_file()),
        None,
    )
    if resolved is None:
        raise RuntimeError("committed runtime ReachBridge adapter is unavailable")
    return resolved


def delegate(manifest: dict[str, object], timeout: int) -> tuple[dict[str, object], Path]:
    resolved_root = _runtime_root()
    cli = resolved_root / "scripts" / "reachbridge-kems-gateway.py"
    package_src = resolved_root / "packages" / "reach" / "src"
    with tempfile.NamedTemporaryFile(prefix="bos-reachbridge-", suffix=".json", delete=False) as handle:
        payload_path = Path(handle.name)
        handle.write(json.dumps(manifest, ensure_ascii=False).encode("utf-8"))
    payload_path.chmod(0o600)
    try:
        env = {**os.environ, "PYTHONPATH": str(package_src)}
        result = subprocess.run(
            [sys.executable, str(cli), str(payload_path), "--timeout", str(timeout)],
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout + 5,
            check=False,
        )
        raw_output = result.stdout.strip() or result.stderr.strip()
        try:
            output = json.loads(raw_output) if raw_output else {}
        except json.JSONDecodeError as exc:
            raise RuntimeError("ReachBridge adapter returned invalid JSON") from exc
        if result.returncode or output.get("status") == "failed":
            raise RuntimeError(str(output.get("error", "ReachBridge adapter failed")))
        return output, resolved_root
    finally:
        payload_path.unlink(missing_ok=True)


def run_production_preflight(
    docs_root: Path, runtime_root: Path, run_id: str, timeout: int
) -> Path:
    """Fail closed before direct production use of this wrapper."""
    script = runtime_root / "scripts" / "kems_production_preflight.py"
    if not script.is_file():
        raise RuntimeError("committed KEMS production preflight is unavailable")
    workspace_root = Path(
        os.environ.get("BOS_WORKSPACE_ROOT", "/Users/xiamingxing/Workspace")
    ).expanduser()
    evidence_output = (
        docs_root
        / "@公共"
        / "_runtime"
        / "evidence"
        / f"production-preflight-{run_id}.json"
    )
    command = [
        sys.executable,
        str(script),
        "--docs-root",
        str(docs_root),
        "--omo-root",
        str(workspace_root / ".omo"),
        "--evidence-output",
        str(evidence_output),
        "--production",
    ]
    try:
        result = subprocess.run(
            command,
            cwd=runtime_root,
            env={**os.environ, "BOS_DOCS_ROOT": str(docs_root)},
            capture_output=True,
            text=True,
            timeout=min(timeout, 60),
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("KEMS production preflight failed to execute") from exc
    if result.returncode:
        raise RuntimeError("KEMS production preflight blocked production dispatch")
    return evidence_output


def record_receipt(
    manifest: dict[str, object],
    response: dict[str, object],
    runtime_root: Path,
    output_path: Path,
    timeout: int,
    production: bool,
) -> None:
    cli = runtime_root / "scripts" / "kems_dispatch_receipt.py"
    if not cli.is_file():
        raise RuntimeError("committed KEMS receipt recorder is unavailable")
    with (
        tempfile.NamedTemporaryFile(prefix="bos-receipt-manifest-", suffix=".json", delete=False) as manifest_handle,
        tempfile.NamedTemporaryFile(prefix="bos-receipt-response-", suffix=".json", delete=False) as response_handle,
    ):
        manifest_path = Path(manifest_handle.name)
        response_path = Path(response_handle.name)
        manifest_handle.write(json.dumps(manifest, ensure_ascii=False).encode("utf-8"))
        response_handle.write(json.dumps(response, ensure_ascii=False).encode("utf-8"))
    manifest_path.chmod(0o600)
    response_path.chmod(0o600)
    try:
        command = [
            sys.executable,
            str(cli),
            "--manifest",
            str(manifest_path),
            "--response",
            str(response_path),
            "--output",
            str(output_path.expanduser().resolve()),
        ]
        if production:
            command.append("--production")
        result = subprocess.run(
            command,
            cwd=runtime_root,
            capture_output=True,
            text=True,
            timeout=timeout + 5,
            check=False,
        )
        if result.returncode:
            raise RuntimeError("KEMS dispatch receipt was not accepted")
    finally:
        manifest_path.unlink(missing_ok=True)
        response_path.unlink(missing_ok=True)


def main() -> int:
    args = parse_args()
    if not args.run_id:
        print(json.dumps({"status": "failed", "error": "missing_run_id"}), file=sys.stderr)
        return 2
    docs_root = args.docs_root.expanduser().resolve()
    try:
        runtime_root = _runtime_root()
    except RuntimeError as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    if args.production:
        try:
            run_production_preflight(docs_root, runtime_root, args.run_id, args.timeout)
        except RuntimeError as exc:
            print(json.dumps({"status": "blocked", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
            return 1
    manifest = build_manifest(docs_root, args.run_id)
    if not manifest["documents"]:
        print(json.dumps({"status": "failed", "error": "no_source_documents"}, ensure_ascii=False), file=sys.stderr)
        return 1
    if args.dry_run:
        print(json.dumps({"status": "planned", "manifest": manifest}, ensure_ascii=False))
        return 0
    try:
        output, runtime_root = delegate(manifest, args.timeout)
        receipt_output = args.receipt_output
        if args.production and receipt_output is None:
            dispatch_id = str(output.get("dispatch_id", args.run_id))
            receipt_output = args.docs_root / "@公共" / "_runtime" / "receipts" / f"{dispatch_id}.json"
        if receipt_output is not None:
            record_receipt(manifest, output, runtime_root, receipt_output, args.timeout, args.production)
            output["receipt_path"] = str(receipt_output.expanduser().resolve())
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
