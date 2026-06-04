import argparse
from pathlib import Path
import yaml
import json
import hashlib

def get_omo_dir(base_dir: Path) -> Path:
    current = base_dir.resolve()
    while current != current.parent:
        if (current / ".omo").is_dir():
            return current / ".omo"
        current = current.parent
    return base_dir / ".omo"

def _generate_task_id(title: str) -> str:
    hash_slug = hashlib.md5(title.encode()).hexdigest()[:6]
    return f"IMPORTED-{hash_slug}"

def _import_bmad(file_path: Path, omo_dir: Path, sequential: bool = False):
    print(f"🌉 正在将 BMAD / OpenSpec 规范转换为 OMO Planned Tasks: {file_path}")
    content = file_path.read_text(encoding="utf-8")
    tasks_created = 0
    
    planned_dir = omo_dir / "tasks" / "planned"
    planned_dir.mkdir(parents=True, exist_ok=True)
    
    last_task_id = None

    for line in content.split("\n"):
        if "- [ ]" in line:
            raw_title = line.split("- [ ]")[1].strip()
            
            # Parse explicit depends_on, e.g., "Task title (depends_on: ID123)"
            depends_on = []
            if "(depends_on:" in raw_title:
                parts = raw_title.split("(depends_on:")
                task_title = parts[0].strip()
                deps_str = parts[1].split(")")[0].strip()
                depends_on = [d.strip() for d in deps_str.split(",")]
            else:
                task_title = raw_title
                if sequential and last_task_id:
                    depends_on.append(last_task_id)

            task_id = _generate_task_id(task_title)
            task_file = planned_dir / f"{task_id}.yaml"
            task_data = {
                "id": task_id,
                "title": task_title,
                "status": "planned",
                "task_type": "feature",
                "depends_on": depends_on,
                "source_docs": [str(file_path.absolute())],
                "deliverables": [],
                "imported_via": "omo_bridge"
            }
            task_file.write_text(yaml.dump(task_data, allow_unicode=True, sort_keys=False))
            print(f"  -> 创建了任务: {task_id} (依赖: {depends_on})")
            tasks_created += 1
            last_task_id = task_id
            
    print(f"✅ 完成转换，共生成了 {tasks_created} 个任务。")

def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="OMO Bridge (Connect external tools like BMAD, OpenSpec)")
    parser.add_argument("source_file", type=str, help="The file to import from")
    parser.add_argument("--format", type=str, choices=["bmad", "openspec"], default="bmad", help="Format of the source file")
    parser.add_argument("--sequential", action="store_true", help="Automatically make each task depend on the previous one")
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
