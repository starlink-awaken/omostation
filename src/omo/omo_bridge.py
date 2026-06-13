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
            if title == ref or title.startswith(ref + ":") or title.startswith(ref + " "):
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

    # Pass 1: 收集所有 - [ ] 行的 title, 算好 title → IMPORTED id 映射.
    # Pass 2: 写文件时 depends_on 用映射回查, 避免断链.
    title_to_imported: dict[str, str] = {}
    parsed_tasks: list[tuple[str, list[str]]] = []  # [(task_title, depends_on_raw), ...]

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
            "status": "planned",
            "task_type": "feature",
            "risk_level": "L0",
            "depends_on": depends_on,
            "source_docs": [str(file_path.absolute())],
            "deliverables": [],
            "imported_via": "omo_bridge",
        }
        if phase is not None:
            task_data["phase"] = phase
        if wave is not None:
            task_data["wave"] = wave

        task_file = planned_dir / f"{task_id}.yaml"
        task_file.write_text(
            yaml.dump(task_data, allow_unicode=True, sort_keys=False)
        )
        print(f"  -> 创建了任务: {task_id} (依赖: {depends_on})")
        tasks_created += 1
        last_task_id = task_id

    print(f"✅ 完成转换，共生成了 {tasks_created} 个任务。")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="OMO Bridge (Connect external tools like BMAD, OpenSpec)"
    )
    parser.add_argument("source_file", type=str, help="The file to import from")
    parser.add_argument(
        "--format",
        type=str,
        choices=["bmad", "openspec"],
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

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main(sys.argv[1:]))
