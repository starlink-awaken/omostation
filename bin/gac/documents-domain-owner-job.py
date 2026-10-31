"""Run one Workspace-bound Documents owner job through Runtime isolation."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
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
    # ⚠⚠⚥ §5.165：**把 binding 一起带出来** —— ⚠ 域归属 ＋ 声明写入面都在它里面
    #   ⇒ ⇒ ⚠ 留痕要记的正是这两样（⚠ 而 `spec.writes` 是运行时的空元组）
    return jobs, spec, binding


def _resolve_ledger_path():
    """⚠ **账本落点**（⚠ §5.165 的自踩修法）。

    ⚠⚠⚥ **解析不出来 ⇒ ⇒ 返回 `None`** ⇒ ⇒ **一条都不写**
    ⇒ ⇒ ⚠ **宁可缺账 ⇒ ⇒ 也不许往猜的路径写**（⚠ 猜错就是污染真账本
    ⇒ ⇒ ⚠ 而真账本是 append-only ⇒ ⇒ 错的那条**删不掉**）

    ⚠⚠⚥ **落点由【环境】点名**（⚠ `OMO_EVENT_LEDGER_DB` 优先 ⇒ ⇒ 那是仓内
    声明过的**测试隔离面**）⇒ ⇒ ⚠ 既有测试以子进程调本作业 ⇒ ⇒
    ⚠ **它必须显式点一个临时账本** ⇒ ⇒ 否则测试会把测试事件写进真账本
    ⇒ ⇒ ⚠ **实测踩过：跑一次测试 ⇒ ⇒ 真账本多 5 条**（⚠ 编造的事实）
    """
    try:
        from lib.documents_change_ledger import resolve_ledger_path

        return resolve_ledger_path()
    except Exception:  # noqa: BLE001 —— ⚠ 解析不出来 ⇒ ⇒ 不留痕（⚠ 不许猜落点）
        return None


def _record_change(
    *,
    job_id: str,
    domain_id: object,
    writes: object,
    status: str,
    exit_code: int | None,
    started_at: str | None,
    ledger_path: object = None,
) -> None:
    """⚠ **把这次作业写进事件账本**（⚠ §5.165 · USER-ACTIONS #117）。

    ⚠⚠⚥ **失败不许挡住作业**（⚠ 留痕是旁路）⇒ ⇒ ⚠ 这里连异常都不往外抛。
    ⚠⚠⚥ **域归属拿不到 ⇒ ⇒ 也要写**（⚠ 用 ``unknown-domain`` 标出来）⇒ ⇒
    ⚠ **不许因为「不知道是哪个域」就整条丢掉**（⚠ 那正是【不可判】⇒ ⇒ 不许折成「没有账」）。
    ⚠⚠⚥ **账本落点拿不到 ⇒ ⇒ 不写**（⚠ 猜落点＝污染真账本 ⇒ ⇒ 那是编造事实）。
    """
    if ledger_path is None:
        return
    try:
        from lib.documents_change_ledger import record_domain_change

        record_domain_change(
            job_id=str(job_id),
            domain_id=str(domain_id) if domain_id else "unknown-domain",
            writes=list(writes) if isinstance(writes, (list, tuple)) else None,
            status=str(status),
            exit_code=exit_code,
            started_at=started_at,
            db_path=ledger_path,
        )
    except Exception:  # noqa: BLE001 —— ⚠ 留痕是旁路 ⇒ ⇒ 写不进去也不许挡住作业
        return


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    started_at = datetime.now(timezone.utc).isoformat()
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

    # ⚠⚠⚥ §5.165：**binding 先置空** —— ⚠ `_build_job` 自己抛异常时
    #   ⇒ ⇒ except 分支里它还没被绑定 ⇒ ⇒ 不许 NameError
    binding = None
    # ⚠⚠⚥ §5.165：**账本落点先解析出来** —— ⚠ 成功与失败两条路径共用同一个落点
    #   ⇒ ⇒ ⚠ **不许成功路径写一处、失败路径写另一处**（⚠ 那会分成两本账）
    ledger_path = _resolve_ledger_path()
    try:
        jobs, spec, binding = _build_job(
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
        # ⚠⚠⚥ §5.165：**失败也要留痕** —— ⚠ 「跑砸了」本身也是一次可追查的事件
        _record_change(
            job_id=args.job_id,
            domain_id=(binding.get("domain_id") if isinstance(binding, dict) else None),
            writes=(binding.get("writes") if isinstance(binding, dict) else None),
            status="failed",
            exit_code=2,
            started_at=started_at,
            ledger_path=ledger_path,
        )
        if args.json_output:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(f"documents owner job: {exc}", file=sys.stderr)
        return 2

    # ⚠⚠⚥ §5.165：**作业跑完 ⇒ ⇒ 往事件账本写一条**（⚠ USER-ACTIONS #117）
    #   ⇒ ⇒ ⚠ 知识域的存量变动**从此有账** ⇒ ⇒ ⚠ 下一次变动**可追查**
    _record_change(
        job_id=result.job_id,
        domain_id=binding.get("domain_id"),
        writes=binding.get("writes"),
        status=result.status,
        exit_code=result.exit_code,
        started_at=started_at,
        ledger_path=ledger_path,
    )
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
