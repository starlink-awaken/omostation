import argparse
import hashlib
import re
from pathlib import Path

from .omo_ingress import create_planned_task
from .omo_paths import find_omo_dir


def get_omo_dir(base_dir: Path) -> Path:
    return find_omo_dir(base_dir)


def _generate_task_id(title: str) -> str:
    hash_slug = hashlib.md5(title.encode()).hexdigest()[:6]
    return f"IMPORTED-{hash_slug}"


def _resolve_depends_on(
    depends_on: list[str], title_to_imported: dict[str, str]
) -> list[str]:
    resolved: list[str] = []
    for ref in depends_on:
        ref = ref.strip()
        if not ref:
            continue
        matched = None
        for title, imported_id in title_to_imported.items():
            if (
                title == ref or title.startswith((ref + ":", ref + " "))
            ):
                matched = imported_id
                break
        resolved.append(matched if matched else ref)
    return resolved


def _infer_phase_wave(task_id_or_title: str) -> tuple[int | None, str | None]:
    match = re.search(r"P(\d+)-W(\d+)", task_id_or_title)
    if not match:
        return (None, None)
    return (int(match.group(1)), f"W{match.group(2)}")


def _validate_planned_task(task_data: dict) -> bool:
    from omo.omo_task_schema import validate_task_data

    validation_errors = validate_task_data(task_data, group="planned")
    if validation_errors:
        print("  ❌ M2 防腐层拦截 (Schema Validation Failed)")
        for err in validation_errors:
            print(f"     - {err}")
        return False
    return True


def _import_bmad(file_path: Path, omo_dir: Path, sequential: bool = False):
    print(f"🌉 正在将 BMAD / OpenSpec 规范转换为 OMO Planned Tasks: {file_path}")
    content = file_path.read_text(encoding="utf-8")
    tasks_created = 0

    test_plan_parsed: list[str] = []
    evidence_parsed: list[str] = []
    in_test, in_evid = False, False
    for line in content.split("\n"):
        if line.startswith("### 7.1"):
            in_test, in_evid = True, False
            continue
        if line.startswith("### 7.2"):
            in_test, in_evid = False, True
            continue
        if line.startswith("#"):
            in_test, in_evid = False, False
            continue
        if in_test and line.strip().startswith("- "):
            test_plan_parsed.append(line.split("- ", 1)[1].strip())
        elif in_evid and line.strip().startswith("- "):
            evidence_parsed.append(line.split("- ", 1)[1].strip())

    if not test_plan_parsed:
        test_plan_parsed = ["[Fallback] Default test plan"]
    if not evidence_parsed:
        evidence_parsed = ["[Fallback] Default evidence"]

    title_to_imported: dict[str, str] = {}
    parsed_tasks: list[tuple[str, list[str]]] = []
    for line in content.split("\n"):
        if "- [ ]" not in line:
            continue
        raw_title = line.split("- [ ]", 1)[1].strip()
        depends_on_raw: list[str] = []
        if "(depends_on:" in raw_title:
            parts = raw_title.split("(depends_on:", 1)
            task_title = parts[0].strip()
            deps_str = parts[1].split(")", 1)[0].strip()
            depends_on_raw = [d.strip() for d in deps_str.split(",") if d.strip()]
        else:
            task_title = raw_title
        title_to_imported[task_title] = _generate_task_id(task_title)
        parsed_tasks.append((task_title, depends_on_raw))

    last_task_id: str | None = None
    for task_title, depends_on_raw in parsed_tasks:
        task_id = title_to_imported[task_title]
        if depends_on_raw:
            depends_on = _resolve_depends_on(depends_on_raw, title_to_imported)
        elif sequential and last_task_id:
            depends_on = [last_task_id]
        else:
            depends_on = []

        phase, wave = _infer_phase_wave(task_title)
        task_data: dict = {
            "id": task_id,
            "title": task_title,
            "status": "candidate",
            "task_type": "feature",
            "risk_level": "L0",
            "depends_on": depends_on,
            "source_docs": [str(file_path.absolute())],
            "deliverables": ["执行记录与源码修改"],
            "imported_via": "omo_bridge",
            "context_uri": f"bos://memory/openspecs/{file_path.name}#{task_id}",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "governance_refs": [
                ".omo/standards/omo-governance-surfaces.md",
                ".omo/_truth/registry/omo-governance-surfaces.yaml",
            ],
            "entry_gate": [],
            "evidence_required": evidence_parsed,
            "test_plan": test_plan_parsed,
            "allowed_operation_level": "L0",
            "human_approval_required": False,
        }
        if phase is not None:
            task_data["phase"] = phase
        if wave is not None:
            task_data["wave"] = wave

        if "TODO" in task_title or "TBD" in task_title:
            print(
                f"  ❌ 预检拦截 (Pre-check Failed): 任务 {task_id} 含有未决议项 ({task_title})，拒绝流入 OMO 稳态区。"
            )
            continue

        if not _validate_planned_task(task_data):
            continue

        create_planned_task(
            omo_dir,
            task_data=task_data,
            ingress_plane="projects/omo",
            source_ref=f"omo:bridge:bmad:{file_path.name}:{task_id}",
        )
        print(f"  -> 创建了任务: {task_id} (依赖: {depends_on}) [M2 Validated]")
        tasks_created += 1
        last_task_id = task_id

    print(f"✅ 完成转换，共生成且经过 M2 强校验了 {tasks_created} 个任务。")


def _import_fast_track(source_topic: Path, omo_dir: Path):
    import time

    print(f"🚀 正在触发 Fast-Track 免签降维: {source_topic.name}")
    task_id = f"FAST-{int(time.time())}"
    task_data = {
        "id": task_id,
        "title": str(source_topic.name),
        "status": "candidate",
        "task_type": "feature",
        "risk_level": "L0",
        "depends_on": [],
        "source_docs": ["bos://memory/fast-track/virtual-doc"],
        "deliverables": ["直接代码修改"],
        "imported_via": "fast_track_cli",
        "context_uri": f"bos://memory/fast-track/{task_id}",
        "evidence_required": ["代码修改自证"],
        "test_plan": ["冒烟测试"],
        "allowed_operation_level": "L0",
        "human_approval_required": False,
        "assigned_to": None,
        "dispatch_id": None,
        "run_ref": None,
        "approval_ref": None,
        "review_ref": None,
        "knowledge_refs": [],
        "handoff_refs": [],
        "governance_refs": [
            ".omo/standards/omo-governance-surfaces.md",
            ".omo/_truth/registry/omo-governance-surfaces.yaml",
        ],
        "entry_gate": ["FAST_TRACK_L0"],
    }

    if not _validate_planned_task(task_data):
        return

    create_planned_task(
        omo_dir,
        task_data=task_data,
        ingress_plane="projects/omo",
        source_ref=f"omo:bridge:fast-track:{source_topic.name}:{task_id}",
    )
    print(f"✅ Fast-Track 成功: 已落盘为 OMO CARDS ({task_id}.yaml)")


def _import_pitch(source_file: Path, omo_dir: Path):
    from omo.omo_goal import cmd_goal_create

    print(f"🌉 [C2G v4] 正在将 Pitch 转化为 OMO Bet: {source_file.name}")
    content = source_file.read_text(encoding="utf-8")

    upstream = None
    appetite = "Unknown"
    for line in content.split("\n"):
        if "> **Upstream**" in line:
            upstream = line.split(":", 1)[1].strip() if ":" in line else line.strip()
        if "**Appetite:**" in line:
            appetite = line.replace("**Appetite:**", "").strip()

    if not upstream:
        print(
            "  ❌ [CR-STRATEGY-01 孤儿拦截] Pitch 缺乏 Upstream 锚点，拒绝转化为 Bet。请在文档头部声明 `> **Upstream**: MS-XXX`。"
        )
        return

    bet_id = f"BET-{hashlib.md5(source_file.name.encode()).hexdigest()[:4]}"
    desc = f"Bet: {source_file.stem} (Appetite: {appetite})"
    cmd_goal_create(
        omo_dir,
        bet_id,
        desc,
        source_ref=f"omo:bridge:pitch-goal:{source_file.name}:{bet_id}",
    )

    task_id = f"IMPORTED-{hashlib.md5(bet_id.encode()).hexdigest()[:6]}"
    task_data = {
        "id": task_id,
        "title": f"执行 {bet_id}: {source_file.stem}",
        "status": "candidate",
        "task_type": "feature",
        "risk_level": "L0",
        "depends_on": [],
        "source_docs": [str(source_file.absolute())],
        "deliverables": [f"达成 {bet_id}"],
        "imported_via": "omo_bridge_pitch",
        "context_uri": f"bos://memory/sandbox/pitches/{source_file.name}",
        "evidence_required": ["回写 Pitch 并通过 Bet 验收"],
        "test_plan": ["依据 Pitch 验收"],
        "allowed_operation_level": "L0",
        "human_approval_required": False,
        "assigned_to": None,
        "dispatch_id": None,
        "run_ref": None,
        "approval_ref": None,
        "review_ref": None,
        "knowledge_refs": [],
        "handoff_refs": [],
        "governance_refs": [
            ".omo/standards/omo-governance-surfaces.md",
            ".omo/_truth/registry/omo-governance-surfaces.yaml",
        ],
        "entry_gate": ["BET_APPROVED"],
    }

    if not _validate_planned_task(task_data):
        return

    create_planned_task(
        omo_dir,
        task_data=task_data,
        ingress_plane="projects/omo",
        source_ref=f"omo:bridge:pitch-task:{source_file.name}:{task_id}",
    )
    print(f"✅ Bet 下注成功: 创建了执行计划 ({task_id}.yaml)")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="OMO Bridge (Connect external tools like BMAD, OpenSpec, Pitches)"
    )
    parser.add_argument("source_file", type=str, help="The file to import from")
    parser.add_argument(
        "--format",
        type=str,
        choices=["bmad", "openspec", "fast_track", "pitch"],
        default="bmad",
        help="Format of the source file",
    )
    parser.add_argument(
        "--sequential",
        action="store_true",
        help="Automatically make each task depend on the previous one",
    )
    args = parser.parse_args(argv)

    source = Path(args.source_file)
    if not source.exists():
        print(f"Error: {source} not found.")
        return 1

    omo_dir = get_omo_dir(Path.cwd())
    if not omo_dir.exists():
        print(f"Error: {omo_dir} not found.")
        return 1

    if args.format in ["bmad", "openspec"]:
        _import_bmad(source, omo_dir, args.sequential)
    elif args.format == "fast_track":
        _import_fast_track(source, omo_dir)
    elif args.format == "pitch":
        _import_pitch(source, omo_dir)

    return 0
