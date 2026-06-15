from pathlib import Path

def get_omo_dir(base_dir: Path) -> Path:
    current = base_dir.resolve()
    while current != current.parent:
        if (current / ".omo").is_dir():
            return current / ".omo"
        current = current.parent
    return base_dir / ".omo"
