import argparse
import re
from pathlib import Path
import yaml
import hashlib


def get_omo_dir(base_dir: Path) -> Path:
    current = base_dir.resolve()
    while current != current.parent:
        if (current / ".omo").is_dir():
            return current / ".omo"
        current = current.parent
    return base_dir / ".omo"


def _generate_task_id(title: str) -> str:
    """从 task title 产生稳定的 IMPORTED-{hash6} ID.

    Hash 稳定是依赖链解析的前提, 测试 test_generate_task_id_is_deterministic 守门.
    """
    hash_slug = hashlib.md5(title.encode()).hexdigest()[:6]
    return f"IMPORTED-{hash_slug}"


def _resolve_depends_on(
    depends_on: list[str],
    title_to_imported: dict[str, str],
) -> list[str]:
    """把 (depends_on: P42-W0-MERGE-STATE) 字面引用重 hash 成 IMPORTED-xxxxx.

    修 P42-W0 揭出的依赖断链 bug:
    - 输入 `["P42-W0-MERGE-STATE"]` 不会自动指向 `IMPORTED-a5a8ea`
    - 调用方需传入 `title_to_imported` 映射, 我们按字面找 title → 再用相同 hash
      函数算出 IMPORTED id

    解析不出的 ID 保留原值, 不抛异常 (向下兼容已有 P40 任务如 `P39-W2-W3-COMBO`).
    空字符串 / 纯空白丢弃, 不污染 yaml.
    """
    resolved: list[str] = []
    for ref in depends_on:
        ref = ref.strip()
        if not ref:
            continue
        # 反向查 title_to_imported: 哪些 IMPORTED 的 title 以 ref 开头?
        # 因为 spec 写法是 "P42-W0-MERGE-STATE: 描述", title 比 ref 长.
        matched = None
        for title, imported_id in title_to_imported.items():
            # ref 必须是 title 的前缀 (id 形式), 防止 P42 撞 P420
            if (
                title == ref
                or title.startswith(ref + ":")
                or title.startswith(ref + " ")
            ):
                matched = imported_id
                break
        resolved.append(matched if matched else ref)
    return resolved


def _infer_phase_wave(task_id_or_title: str) -> tuple[int | None, str | None]:
    """从 `P42-W0-MERGE-STATE` 形式推断 (phase, wave).

    多 W 形式 (P40-W2-W3) 取第一个.
    不匹配返回 (None, None), 调用方写 yaml 时跳过.
    """
    m = re.search(r"P(\d+)-W(\d+)", task_id_or_title)
    if not m:
        return (None, None)
    return (int(m.group(1)), f"W{m.group(2)}")


def _import_bmad(file_path: Path, omo_dir: Path, sequential: bool = False):
    print(f"🌉 正在将 BMAD / OpenSpec 规范转换为 OMO Planned Tasks: {file_path}")
    content = file_path.read_text(encoding="utf-8")
    tasks_created = 0

    planned_dir = omo_dir / "tasks" / "planned"
    planned_dir.mkdir(parents=True, exist_ok=True)

    # Pass 1: 解析 QA 质量保障模块 (Test Plan & Evidence Required)
    test_plan_parsed = []
    evidence_parsed = []
    in_test, in_evid = False, False
    for line in content.split("\n"):
        if line.startswith("### 7.1"):
            in_test, in_evid = True, False
            continue
        elif line.startswith("### 7.2"):
            in_test, in_evid = False, True
            continue
        elif line.startswith("#"):
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

    # Pass 2: 收集所有 - [ ] 行的 title, 算好 title → IMPORTED id 映射.
    # Pass 3: 写文件时 depends_on 用映射回查, 避免断链.
    title_to_imported: dict[str, str] = {}
    parsed_tasks: list[
        tuple[str, list[str]]
    ] = []  # [(task_title, depends_on_raw), ...]

    for line in content.split("\n"):
        if "- [ ]" not in line:
            continue
        raw_title = line.split("- [ ]")[1].strip()

        depends_on_raw: list[str] = []
        if "(depends_on:" in raw_title:
            parts = raw_title.split("(depends_on:")
            task_title = parts[0].strip()
            deps_str = parts[1].split(")")[0].strip()
            depends_on_raw = [d.strip() for d in deps_str.split(",") if d.strip()]
        else:
            task_title = raw_title

        # 解析 sequential 模式下的隐式依赖, 暂时用 task_title 占位
        title_to_imported[task_title] = _generate_task_id(task_title)
        parsed_tasks.append((task_title, depends_on_raw))

    # Pass 2: 写文件, depends_on 用 _resolve_depends_on 替换为真实 IMPORTED id.
    last_task_id: str | None = None
    for idx, (task_title, depends_on_raw) in enumerate(parsed_tasks):
        task_id = title_to_imported[task_title]

        # 显式依赖优先; 没有时, sequential 模式追加上一个 task 的 IMPORTED id
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
            # [M2 CONTRACT] 必须的空位字段
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
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

        # [DEVIL'S GATEKEEPER]: OMO Pre-Check Before Materialization
        if "TODO" in task_title or "TBD" in task_title:
            print(
                f"  ❌ 预检拦截 (Pre-check Failed): 任务 {task_id} 含有未决议项 ({task_title})，拒绝流入 OMO 稳态区。"
            )
            continue

        # [MODEL-DRIVEN M2 VALIDATION & X1-X4 Governance Checks]
        from .adapters import get_providers
    gov, store = get_providers(omo_dir)
    from .domain import TaskSchema
    t = TaskSchema(**task_data)
    if not gov.validate_task(t):
        validation_errors = ["M2 validation failed"]
    else:
        validation_errors = []
            if validation_errors:
                print(
                    f"  [Attempt {attempt}] ⚠️ 逆向推导引擎拦截幻觉 (Schema Validation Failed): 任务 {task_id}"
                )
                for err in validation_errors:
                    print(f"     - {err}")

                if attempt < max_retries:
                    print(
                        "  🔄 触发重试逻辑 (Retry Loop) - 要求大模型基于 schema 修正脏数据..."
                    )
                    # TODO: Inject real LLM Structured Output API call here
                    # task_data = llm_structured_output(prompt=f"Fix {validation_errors}", schema=OMO_TASK_SCHEMA)
                    break  # Break loop for now since LLM is mocked
                else:
                    print("  ❌ 达到最大重试次数，拒绝脏数据流入 OMO。")
                    break
            else:
                validation_passed = True

        if not validation_passed:
            continue

        task_file = planned_dir / f"{task_id}.yaml"
        task_file.write_text(yaml.dump(task_data, allow_unicode=True, sort_keys=False))
        print(f"  -> 创建了任务: {task_id} (依赖: {depends_on}) [M2 Validated]")
        tasks_created += 1
        last_task_id = task_id

    print(f"✅ 完成转换，共生成且经过 M2 强校验了 {tasks_created} 个任务。")


def _import_fast_track(source_topic: Path, omo_dir: Path):
    """[C2G v2] 解法二: Fast-Track 免签降维."""
    import time

    print(f"🚀 正在触发 Fast-Track 免签降维: {source_topic.name}")
    planned_dir = omo_dir / "tasks" / "planned"
    planned_dir.mkdir(parents=True, exist_ok=True)

    # Generate task data directly without LLM
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
        "entry_gate": ["FAST_TRACK_L0"],
    }

    # [MODEL-DRIVEN M2 VALIDATION]
    from .adapters import get_providers
    gov, store = get_providers(omo_dir)
    from .domain import TaskSchema
    t = TaskSchema(**task_data)
    if not gov.validate_task(t):
        validation_errors = ["M2 validation failed"]
    else:
        validation_errors = []
    if validation_errors:
        print("  ❌ M2 防腐层拦截 (Schema Validation Failed)")
        for err in validation_errors:
            print(f"     - {err}")
        return

    task_file = planned_dir / f"{task_id}.yaml"
    task_file.write_text(yaml.dump(task_data, allow_unicode=True, sort_keys=False))
    print(f"✅ Fast-Track 成功: 已落盘为 OMO CARDS ({task_id}.yaml)")


def _import_pitch(source_file: Path, omo_dir: Path):
    """[C2G v4] 将 Pitch (提案) 转换为 Bet 并在 OMO 中生成 Planned Task."""
    from .adapters import get_providers
    gov, store = get_providers(omo_dir)
    print(f"🌉 [C2G v4] 正在将 Pitch 转化为 OMO Bet: {source_file.name}")
    content = source_file.read_text(encoding="utf-8")

    # [C2G v4] CR-STRATEGY-01 孤儿拦截约束
    upstream = None
    appetite = "Unknown"
    for line in content.split("\n"):
        if "> **Upstream**" in line:
            upstream = line.split(":", 1)[1].strip() if ":" in line else line.strip()
        if "**Appetite:**" in line:
            appetite = line.replace("**Appetite:**", "").strip()

    if not upstream:
        print("  ❌ [CR-STRATEGY-01 孤儿拦截] Pitch 缺乏 Upstream 锚点，拒绝转化为 Bet。请在文档头部声明 `> **Upstream**: MS-XXX`。")
        return

    # 创建 Bet (Goal)
    bet_id = f"BET-{hashlib.md5(source_file.name.encode()).hexdigest()[:4]}"
    desc = f"Bet: {source_file.stem} (Appetite: {appetite})"

    # 将 Bet 加入 current.yaml
    from .domain import BetSchema
    store.save_bet(BetSchema(goal_id=bet_id, title=source_file.stem, description=desc, appetite=appetite, created_at=""))

    # 派生 Planned Task
    planned_dir = omo_dir / "tasks" / "planned"
    planned_dir.mkdir(parents=True, exist_ok=True)

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
        "entry_gate": ["BET_APPROVED"],
    }

    # [MODEL-DRIVEN M2 VALIDATION]
    from .adapters import get_providers
    gov, store = get_providers(omo_dir)
    from .domain import TaskSchema
    t = TaskSchema(**task_data)
    if not gov.validate_task(t):
        validation_errors = ["M2 validation failed"]
    else:
        validation_errors = []
    if validation_errors:
        print("  ❌ M2 防腐层拦截 (Schema Validation Failed)")
        for err in validation_errors:
            print(f"     - {err}")
        return

    task_file = planned_dir / f"{task_id}.yaml"
    task_file.write_text(yaml.dump(task_data, allow_unicode=True, sort_keys=False))
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


if __name__ == "__main__":
    import sys

    sys.exit(main(sys.argv[1:]))
