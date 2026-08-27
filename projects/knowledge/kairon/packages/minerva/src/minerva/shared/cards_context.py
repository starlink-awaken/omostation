import logging
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


def get_cards_context() -> str:
    """Reads L4 CARDS active goals/context to inject into agent prompts."""
    cards_dir = Path.home() / "Documents" / "驾驶舱" / "CARDS"
    if not cards_dir.exists():
        return ""

    active_p0 = []
    try:
        for f in cards_dir.glob("*.md"):
            try:
                content = f.read_text(encoding="utf-8")
                if content.startswith("---"):
                    fm_text = content.split("---")[1]
                    fm = yaml.safe_load(fm_text)
                    if isinstance(fm, dict):
                        if fm.get("status") not in ("closed", "done") and fm.get("priority") == "P0":
                            active_p0.append(f"{fm.get('title', f.stem)} (Status: {fm.get('status', 'open')})")
            except Exception as e:
                logger.debug(f"Skipping malformed CARDS file {f.name}: {e}")
                continue
    except Exception as e:
        logger.warning(f"Failed to read CARDS: {e}")
        return ""

    if not active_p0:
        return ""

    context = "\n\n### L4 User Context (Active P0 CARDS)\n"
    context += "Please align your research/planning with the user's current high-priority goals:\n"
    for card in active_p0[:10]:
        context += f"- {card}\n"
    return context
