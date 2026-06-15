import hashlib
import re

def _generate_task_id(title: str) -> str:
    """从 task title 产生稳定的 IMPORTED-{hash6} ID."""
    hash_slug = hashlib.md5(title.encode()).hexdigest()[:6]
    return f"IMPORTED-{hash_slug}"

def _infer_phase_wave(task_id_or_title: str) -> tuple[int | None, str | None]:
    """从 `P42-W0-MERGE-STATE` 形式推断 (phase, wave)."""
    m = re.search(r"P(\d+)-W(\d+)", task_id_or_title)
    if not m:
        return (None, None)
    return (int(m.group(1)), f"W{m.group(2)}")
