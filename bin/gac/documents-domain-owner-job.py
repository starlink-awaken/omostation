"""Run one Workspace-bound Documents owner job through Runtime isolation."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

ROOT = Path(__file__).resolve().parents[2]
RUNTIME_SRC = ROOT / "projects" / "runtime" / "src"
L4_SRC = ROOT / "projects" / "l4-kernel" / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
for source_root in (RUNTIME_SRC, L4_SRC):
    if str(source_root) not in sys.path:
        sys.path.insert(0, str(source_root))

if TYPE_CHECKING:
    from runtime.documents_plane.jobs import JobRegistry, JobSpec


def _relative_documents_path(path: Path, documents_root: Path, label: str) -> str:
    try:
        relative = path.resolve().relative_to(documents_root)
    except ValueError as exc:
        raise ValueError(f"{label} must be below Documents root") from exc
    if relative == Path("."):
        raise ValueError(f"{label} must name a file below Documents root")
    return str(relative)


def _project_registry(path: Path) -> dict[str, object]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ValueError(f"project registry invalid: {exc}") from exc
    if not isinstance(raw, dict):
        raise TypeError("project registry must be a mapping")
    return raw


def _build_job(
    *,
    job_id: str,
    documents_root: Path,
    domain_registry_path: Path,
    project_registry_path: Path,
    l4_executable: Path,
) -> tuple[JobRegistry, JobSpec]:
    from documents_domain_jobs import get_manifest_validation_job
    from l4_kernel.manifest_registry import ManifestRegistry
    from runtime.documents_plane.jobs import JobRegistry, JobSpec

    documents = documents_root.expanduser().resolve()
    domain_registry = domain_registry_path.expanduser().resolve()
    project = _project_registry(project_registry_path.expanduser().resolve())
    domain_binding = project.get("domain_registry")
    if not isinstance(domain_binding, dict):
        raise TypeError("domain_registry binding must be a mapping")
    registry_ref = domain_binding.get("documents_relative_ref")
    if not isinstance(registry_ref, str) or not registry_ref:
        raise ValueError("domain_registry.documents_relative_ref must be non-empty")
    relative_ref = Path(registry_ref)
    if relative_ref.is_absolute() or ".." in relative_ref.parts:
        raise ValueError("domain_registry.documents_relative_ref must be relative and non-traversing")
    if (documents / relative_ref).resolve() != domain_registry:
        raise ValueError("explicit domain registry does not match the Workspace binding")

    registry = ManifestRegistry.load(domain_registry)
    manifest_ids = [manifest.id for manifest in registry.list_all()]
    binding = get_manifest_validation_job(project.get("runtime_jobs"), job_id, manifest_ids)
    domain_id = str(binding["domain_id"])
    manifest = registry.get(domain_id)
    if manifest is None:  # pragma: no cover - shared binding validation owns this
        raise ValueError(f"runtime job references unknown domain: {domain_id}")

    executable = l4_executable.expanduser()
    if not executable.is_absolute():
        raise ValueError("--l4-executable must be an absolute path")
    executable = executable.resolve()
    spec = JobSpec(
        job_id=str(binding["id"]),
        reads=(
            _relative_documents_path(domain_registry, documents, "domain registry"),
            _relative_documents_path(manifest.root / "DOMAIN.yaml", documents, "domain manifest"),
        ),
        writes=(),
        owner=str(binding["owner"]),
        schedule=str(binding["schedule"]),
        timeout=float(binding["timeout_seconds"]),
        evidence_path=str(binding["evidence_path"]),
        fail_closed=True,
    )
    jobs = JobRegistry()
    jobs.register(
        spec,
        (
            str(executable),
            "domain",
            "validate-manifest",
            domain_id,
            "--registry",
            str(domain_registry),
            "--json",
        ),
    )
    return jobs, spec


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] == "learning-control":
        from lib.documents_learning_control import main as learning_control_main

        return learning_control_main(arguments[1:])
    if arguments and arguments[0] == "learning-control-plane":
        from lib.documents_learning_control_plane import main as learning_control_plane_main

        return learning_control_plane_main(arguments[1:])
    if arguments and arguments[0] == "client-recovery":
        from lib.documents_client_recovery_relocation import main as client_recovery_main

        return client_recovery_main(arguments[1:])
    from l4_kernel.contracts import ContractError
    from runtime.documents_plane.jobs import run_job

    if arguments and arguments[0] == "consumer-audit":
        from lib.documents_consumer_audit import main as consumer_audit_main

        return consumer_audit_main(arguments[1:])
    if arguments and arguments[0] == "freshness-audit":
        from lib.documents_freshness_owner import main as freshness_audit_main

        return freshness_audit_main(arguments[1:])
    if arguments and arguments[0] == "ocr-preflight":
        from lib.documents_ocr_preflight import main as ocr_preflight_main

        return ocr_preflight_main(arguments[1:])
    if arguments and arguments[0] == "bridge-preflight":
        from lib.documents_bridge_preflight import main as bridge_preflight_main

        return bridge_preflight_main(arguments[1:])
    if arguments and arguments[0] == "predictor-preflight":
        from lib.documents_predictor_preflight import main as predictor_preflight_main

        return predictor_preflight_main(arguments[1:])
    if arguments and arguments[0] == "controller-preflight":
        from lib.documents_controller_preflight import main as controller_preflight_main

        return controller_preflight_main(arguments[1:])
    if arguments and arguments[0] == "signals-preflight":
        from lib.documents_signals_preflight import main as signals_preflight_main

        return signals_preflight_main(arguments[1:])
    if arguments and arguments[0] == "convergence-preflight":
        from lib.documents_convergence_preflight import main as convergence_preflight_main

        return convergence_preflight_main(arguments[1:])
    if arguments and arguments[0] == "daily-health-preflight":
        from lib.documents_daily_health_preflight import main as daily_health_preflight_main

        return daily_health_preflight_main(arguments[1:])
    if arguments and arguments[0] == "kos-preflight":
        from lib.documents_kos_preflight import main as kos_preflight_main

        return kos_preflight_main(arguments[1:])
    if arguments and arguments[0] == "bos-neural-mesh-owner":
        from lib.bos_neural_mesh_owner import main as bos_neural_mesh_owner_main

        return bos_neural_mesh_owner_main(arguments[1:])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job_id")
    parser.add_argument("--documents-root", type=Path, required=True)
    parser.add_argument("--domain-registry", type=Path, required=True)
    parser.add_argument("--project-registry", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--l4-executable", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args(arguments)

    try:
        jobs, spec = _build_job(
            job_id=args.job_id,
            documents_root=args.documents_root,
            domain_registry_path=args.domain_registry,
            project_registry_path=args.project_registry,
            l4_executable=args.l4_executable,
        )
        if not args.dry_run and (not args.l4_executable.is_file() or not os.access(args.l4_executable, os.X_OK)):
            raise ValueError("--l4-executable must be an executable file")
        result = run_job(
            jobs,
            spec.job_id,
            dry_run=args.dry_run,
            documents_root=args.documents_root,
            state_root=args.state_root,
        )
    except (ContractError, OSError, UnicodeError, TypeError, ValueError) as exc:
        payload = {"status": "failed", "error": str(exc)}
        if args.json_output:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(f"documents owner job: {exc}", file=sys.stderr)
        return 2

    if args.json_output:
        print(json.dumps(result.as_dict(), ensure_ascii=False, sort_keys=True))
    else:
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        print(f"{result.job_id}: {result.status}")
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
