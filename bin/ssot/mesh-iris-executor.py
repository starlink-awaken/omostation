#!/usr/bin/env python3
"""mesh-iris-executor.py — mesh worker 执行 iris connector (N1+N9 P0).

固化 P0 第一块验证的 mesh 状态机要求 + iris connector sync 自动化.
流程: seed workflow run 链 → iris connector list_items (跨项目) → WorkflowSucceeded → EvidenceRecorded.

mesh 状态机要求 (fabric 红线, 深挖发现):
  1. admission grant 完整 schema (10 字段) + proof = SHA-256(canonical(admission 减 proof))
  2. StepDispatched payload 含 admission_id (跟 admission 匹配)
  3. EvidenceRecorded 只在 succeeded 状态 (要先 WorkflowSucceeded)
  4. transition: planned→admitted→dispatched→running→succeeded

用法:
  python3 bin/ssot/mesh-iris-executor.py --connector apple_mail --omo-dir .omo
  python3 bin/ssot/mesh-iris-executor.py --connector apple_mail --dry-run  # 测试 omo_dir
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
OMO_SRC = WORKSPACE / "projects/omo/src"
KAIRON = WORKSPACE / "projects/kairon"


def _load_mesh():
    """加载 omo mesh 模块 (sys.path 注入)."""
    if str(OMO_SRC) not in sys.path:
        sys.path.insert(0, str(OMO_SRC))
    from omo.omo_external_receipt import record_external_receipt
    from omo.workflow_mesh import (
        WorkflowMeshStore,
        _canonical_admission,
        new_workflow_event,
    )

    return (
        WorkflowMeshStore,
        new_workflow_event,
        _canonical_admission,
        record_external_receipt,
    )


def seed_workflow_run(store, new_event, canonical, run_id, capability):
    """seed mesh 状态机链: Requested→Admitted→Dispatched→Started (running 状态)."""
    step_run_id = f"{run_id}:execute"
    admission_id = f"{run_id}:admission"
    now = datetime.now(timezone.utc)
    store.append(
        new_event(
            "WorkflowRequested",
            run_id,
            producer="mesh-iris-executor",
            payload={"capability_refs": [capability], "scene_id": "document-review"},
        )
    )
    admission = {
        "admission_id": admission_id,
        "workflow_run_id": run_id,
        "trace_id": run_id,
        "status": "admitted",
        "capabilities": [capability],
        "step_run_ids": [step_run_id],
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=1)).isoformat(),
        "policy_digest": "external-connection-fabric/v1",
    }
    admission["proof"] = hashlib.sha256(canonical(admission)).hexdigest()
    store.append(
        new_event(
            "WorkflowAdmitted",
            run_id,
            producer="mesh-iris-executor",
            payload={"admission": admission},
        )
    )
    store.append(
        new_event(
            "StepDispatched",
            run_id,
            producer="mesh-iris-executor",
            payload={
                "step_run_id": step_run_id,
                "capability": capability,
                "admission_id": admission_id,
            },
        )
    )
    store.append(
        new_event(
            "StepStarted",
            run_id,
            producer="mesh-iris-executor",
            payload={"step_run_id": step_run_id, "admission_id": admission_id},
        )
    )
    return step_run_id, admission_id


def execute_iris_connector(connector: str, limit: int = 5) -> list[dict]:
    """跨项目执行 iris connector list_items (subprocess cd kairon + uv run)."""
    code = (
        "import importlib.metadata as m, json\n"
        f"target = '{connector}'\n"
        "for ep in m.entry_points(group='external.resources'):\n"
        "    if ep.name != target:\n"
        "        continue\n"
        "    inst = ep.load()()\n"
        "    items = inst.list_items(limit=" + str(limit) + ")\n"
        "    print(json.dumps([{'id': i.id, 'title': i.title[:60]} for i in items]))\n"
        "    break\n"
    )
    result = subprocess.run(
        ["uv", "run", "--package", "iris", "python", "-c", code],
        cwd=KAIRON,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError(f"iris {connector} 执行失败: {result.stderr[:200]}")
    return json.loads(result.stdout.strip().splitlines()[-1])


def record_iris_evidence(
    store,
    new_event,
    record_receipt,
    omo_dir,
    run_id,
    step_run_id,
    admission_id,
    connector,
    items,
):
    """WorkflowSucceeded + EvidenceRecorded (iris receipt)."""
    now = datetime.now(timezone.utc)
    store.append(
        new_event(
            "WorkflowSucceeded",
            run_id,
            producer="mesh-iris-executor",
            payload={"step_run_id": step_run_id, "admission_id": admission_id},
        )
    )
    output_digest = hashlib.sha256(
        json.dumps([i["id"] for i in items]).encode()
    ).hexdigest()
    receipt = {
        "resource_id": f"iris:{connector}",
        "receipt_id": f"{run_id}:exec",
        "operation": "list_items",
        "status": "succeeded",
        "output_digest": output_digest,
        "trace_id": run_id,
        "observed_at": now.isoformat(),
        "policy_digest": "external-connection-fabric/v1",
        "provenance_ref": f"iris:{connector}:list_items",
        "result_state": "succeeded",
    }
    return record_receipt(
        omo_dir,
        receipt,
        workflow_run_id=run_id,
        step_run_id=step_run_id,
        producer="mesh-iris-executor",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="mesh worker 执行 iris connector (N1+N9 P0)"
    )
    parser.add_argument(
        "--connector",
        required=True,
        help="iris 连接器名 (apple_mail/netease_mailmaster/...)",
    )
    parser.add_argument("--omo-dir", default=".omo", help="omo 目录 (默认 .omo)")
    parser.add_argument("--limit", type=int, default=5, help="list_items limit")
    parser.add_argument(
        "--dry-run", action="store_true", help="用临时 omo_dir, 不污染生产"
    )
    args = parser.parse_args()

    WorkflowMeshStore, new_event, canonical, record_receipt = _load_mesh()

    if args.dry_run:
        omo_dir = Path(tempfile.mkdtemp())
        (omo_dir / "_knowledge" / "workflow-mesh").mkdir(parents=True)
    else:
        omo_dir = Path(args.omo_dir).resolve()

    store = WorkflowMeshStore(omo_dir)
    run_id = (
        f"iris-{args.connector}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    )

    print(f"🚀 mesh-iris-executor: connector={args.connector} run_id={run_id}")
    step_run_id, admission_id = seed_workflow_run(
        store, new_event, canonical, run_id, f"iris:{args.connector}"
    )
    print("✅ seed 链 (Requested→Admitted→Dispatched→Started)")

    items = execute_iris_connector(args.connector, args.limit)
    print(f"✅ iris {args.connector} 执行: {len(items)} items")

    result = record_iris_evidence(
        store,
        new_event,
        record_receipt,
        omo_dir,
        run_id,
        step_run_id,
        admission_id,
        args.connector,
        items,
    )
    events_f = omo_dir / "_knowledge" / "workflow-mesh" / "events.jsonl"
    print("✅ WorkflowSucceeded + EvidenceRecorded")
    print(f"   evidence_id: {result.get('evidence_id')}")
    print(f"   events.jsonl: {len(events_f.read_text().splitlines())} 事件")
    print(
        f"   output_digest: {hashlib.sha256(json.dumps([i['id'] for i in items]).encode()).hexdigest()[:16]}..."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
