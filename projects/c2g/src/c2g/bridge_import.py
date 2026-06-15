import yaml
import hashlib
from pathlib import Path
from .bridge_id import _generate_task_id, _infer_phase_wave
from .bridge_depend import _resolve_depends_on

def _import_bmad(file_path: Path, omo_dir: Path, sequential: bool = False, adapter: str = "ecos"):
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
        gov, store = get_providers(base_dir, adapter)
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


def _import_fast_track(source_topic: Path, omo_dir: Path, adapter: str = "ecos"):
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
    gov, store = get_providers(base_dir, adapter)
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


def _import_pitch(source_file: Path, base_dir: Path, adapter: str = "ecos"):
    """[C2G v4] 将 Pitch (提案) 转换为 Bet 并在 OMO 中生成 Planned Task."""
    from .adapters import get_providers
    from .llm import extract_tasks_from_pitch
    gov, store = get_providers(base_dir, adapter)
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
    planned_dir = base_dir / "tasks" / "planned"
    planned_dir.mkdir(parents=True, exist_ok=True)

    print("  🧠 正在调用 LLM 结构化提取任务...")
    llm_tasks = extract_tasks_from_pitch(content)
    
    if not llm_tasks:
        # Fallback to single mock task if LLM fails or is absent
        llm_tasks = [{
            "title": f"执行 {bet_id}: {source_file.stem}",
            "description": f"从 Pitch转化而来的任务: {source_file.stem}",
            "task_type": "feature",
            "risk_level": "L0",
            "deliverables": [f"达成 {bet_id}"],
            "evidence_required": ["回写 Pitch 并通过 Bet 验收"],
            "test_plan": ["依据 Pitch 验收"]
        }]

    # Process and validate extracted tasks
    from .domain import TaskSchema
    tasks_created = 0
    for idx, extracted in enumerate(llm_tasks):
        task_id = f"IMPORTED-{hashlib.md5((bet_id + str(idx)).encode()).hexdigest()[:6]}"
        
        task_data = {
            "task_id": task_id,
            "title": extracted.get("title", f"Task {idx}"),
            "description": extracted.get("description", "No description"),
            "state": "planned",
            "task_type": extracted.get("task_type", "feature"),
            "risk_level": extracted.get("risk_level", "L0"),
            "depends_on": [],
            "source_docs": [str(source_file.absolute())],
            "deliverables": extracted.get("deliverables", []),
            "imported_via": "omo_bridge_pitch",
            "context_uri": f"bos://memory/sandbox/pitches/{source_file.name}",
            "evidence_required": extracted.get("evidence_required", []),
            "test_plan": extracted.get("test_plan", []),
            "allowed_operation_level": "L0",
            "human_approval_required": False,
            "assigned_to": None,
            "gate_status": "not_yet_passed",
            "wait_for_gate": ["BET_APPROVED"],
            "created_at": "2026-06-15T00:00:00Z",
            "updated_at": "2026-06-15T00:00:00Z"
        }

        # [MODEL-DRIVEN M2 VALIDATION]
        t = TaskSchema(**task_data)
        if not gov.validate_task(t):
            print(f"  ❌ M2 防腐层拦截 (Schema Validation Failed for task {task_id})")
            continue

        task_file = planned_dir / f"{task_id}.yaml"
        task_file.write_text(yaml.dump(task_data, allow_unicode=True, sort_keys=False))
        print(f"  ✅ 提取任务成功: {task_id} ({task_data['title']})")
        tasks_created += 1

    print(f"✅ Bet 下注成功: 共创建了 {tasks_created} 个执行计划。")

