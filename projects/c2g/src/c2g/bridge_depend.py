def _resolve_depends_on(
    depends_on: list[str],
    title_to_imported: dict[str, str],
) -> list[str]:
    """把 (depends_on: P42-W0-MERGE-STATE) 字面引用重 hash 成 IMPORTED-xxxxx."""
    resolved: list[str] = []
    for ref in depends_on:
        ref = ref.strip()
        if not ref:
            continue
        matched = None
        for title, imported_id in title_to_imported.items():
            if (
                title == ref
                or title.startswith(ref + ":")
                or title.startswith(ref + " ")
            ):
                matched = imported_id
                break
        resolved.append(matched if matched else ref)
    return resolved
