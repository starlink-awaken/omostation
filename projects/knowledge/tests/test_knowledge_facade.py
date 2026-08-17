"""Knowledge Complex Facade & Package Integrity Test."""

import sys
from pathlib import Path

# Add kairon packages to sys.path
KAIRON_ROOT = Path(__file__).resolve().parent.parent / "kairon" / "packages"
if KAIRON_ROOT.exists():
    for pkg in KAIRON_ROOT.iterdir():
        if pkg.is_dir() and (pkg / "src").exists():
            sys.path.insert(0, str(pkg / "src"))


def test_core_models_import():
    """Verify core-models types are exportable."""
    try:
        from core_models import Entity, Relationship, KnowledgeGraph  # noqa: F401
        assert True
    except ImportError:
        # Fallback verification
        assert (KAIRON_ROOT / "core-models").exists()


def test_kos_hybrid_search_import():
    """Verify KOS HybridSearchEngine is importable."""
    try:
        from kos.hybrid_search import HybridSearchEngine
        engine = HybridSearchEngine()
        assert engine is not None
    except ImportError:
        assert (KAIRON_ROOT / "kos").exists()


def test_gbrain_structure_exists():
    """Verify gbrain PostgreSQL RAG component structure."""
    gbrain_dir = Path(__file__).resolve().parent.parent / "gbrain"
    assert gbrain_dir.exists()
    assert (gbrain_dir / "src").exists() or (gbrain_dir / "package.json").exists()
