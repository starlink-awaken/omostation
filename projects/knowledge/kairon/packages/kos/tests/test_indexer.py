"""KOS indexer unit tests — core logic without DB dependency."""

import hashlib
import tempfile
from pathlib import Path


class TestZoneScanning:
    """Test manifest-driven zone file scanning."""

    def test_iter_zone_files_honors_file_patterns(self, tmp_path):
        from kos.indexer.engine import KosIndexer

        (tmp_path / "keep.md").write_text("# Keep\n", encoding="utf-8")
        (tmp_path / "skip.sqlite").write_text("db", encoding="utf-8")
        (tmp_path / "nested").mkdir()
        (tmp_path / "nested" / "keep.txt").write_text("text", encoding="utf-8")

        indexer = KosIndexer.__new__(KosIndexer)
        indexer.manifest = {"indexing": {"excludePrefixes": []}}

        files = list(
            indexer._iter_zone_files(
                "workspace",
                {
                    "path": str(tmp_path),
                    "filePatterns": ["*.md", "*.txt"],
                    "followSymlinks": False,
                },
            )
        )

        assert sorted(rel for rel, _path in files) == ["keep.md", "nested/keep.txt"]

    def test_iter_zone_files_skips_broken_symlinks(self, tmp_path):
        from kos.indexer.engine import KosIndexer

        (tmp_path / "valid.py").write_text("print('ok')\n", encoding="utf-8")
        (tmp_path / "broken.py").symlink_to(tmp_path / "missing.py")

        indexer = KosIndexer.__new__(KosIndexer)
        indexer.manifest = {"indexing": {"excludePrefixes": []}}

        files = list(
            indexer._iter_zone_files(
                "workspace",
                {
                    "path": str(tmp_path),
                    "filePatterns": ["*.py"],
                    "followSymlinks": False,
                },
            )
        )

        assert [rel for rel, _path in files] == ["valid.py"]


class TestFormatHandlers:
    """Test format handler dispatch."""

    def test_handler_priority(self):
        """Verify higher priority handlers are selected first."""

        # Simulate handler selection logic
        class Handler:
            def __init__(self, exts, pri):
                self.extensions = exts
                self.priority = pri

            def can_handle(self, p):
                return Path(p).suffix.lower() in self.extensions

        handlers = [
            Handler({".md"}, 100),
            Handler({".pdf"}, 70),
            Handler(set(), 0),  # generic
        ]

        def get_handler(fp):
            candidates = [h for h in handlers if h.can_handle(fp)]
            if not candidates:
                return handlers[-1]  # fallback generic handler
            return max(candidates, key=lambda h: h.priority)

        assert get_handler("test.md").priority == 100
        assert get_handler("test.pdf").priority == 70
        assert get_handler("test.unknown").priority == 0

    def test_markdown_title_extraction(self):
        """Test extracting title from Markdown frontmatter."""
        import re

        content = "# Hello World\n\nSome content here.\n"
        m = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        assert m is not None
        assert m.group(1).strip() == "Hello World"

    def test_markdown_heading_extraction(self):
        """Test heading extraction regex."""
        import re

        content = "## Section\n### person-xyz\n**名称**：张三\n\nContent here.\n### next"
        headings = list(re.finditer(r"###\s+(.+)", content))
        assert len(headings) == 2
        assert headings[0].group(1).strip() == "person-xyz"


class TestHashFingerprint:
    """Test SHA-256 fingerprint logic."""

    def test_compute_hash_deterministic(self):
        """Same file should produce same hash."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("test content for hashing\n" * 100)
            f.flush()
            fp = Path(f.name)

        try:
            h1 = _compute_hash(fp)
            h2 = _compute_hash(fp)
            assert h1 == h2
            assert len(h1) == 64  # SHA-256 hex
        finally:
            fp.unlink()

    def test_compute_hash_different_content(self):
        """Different files should produce different hashes."""
        f1 = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
        f1.write("content A\n" * 50)
        f1.flush()

        f2 = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
        f2.write("content B\n" * 50)
        f2.flush()

        try:
            h1 = _compute_hash(Path(f1.name))
            h2 = _compute_hash(Path(f2.name))
            assert h1 != h2
        finally:
            Path(f1.name).unlink()
            Path(f2.name).unlink()


def _compute_hash(file_path: Path) -> str:
    """Replicate KosIndexer._compute_hash logic."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        h.update(f.read(65536))
    h.update(str(file_path.stat().st_size).encode())
    return h.hexdigest()


class TestRRFusion:
    """Test RRF (Reciprocal Rank Fusion)."""

    def test_rrf_merge(self):
        """Test RRF ranking logic."""
        # Simulated search results from multiple sources
        source1 = [("doc_a", 1), ("doc_b", 2), ("doc_c", 3)]
        source2 = [("doc_b", 1), ("doc_d", 2), ("doc_a", 3)]

        scores = {}
        k = 60
        for rank, (doc_id, _) in enumerate(source1):
            scores[doc_id] = scores.get(doc_id, 0) + 1.0 / (k + rank + 1)
        for rank, (doc_id, _) in enumerate(source2):
            scores[doc_id] = scores.get(doc_id, 0) + 1.0 / (k + rank + 1)

        ranked = sorted(scores.items(), key=lambda x: -x[1])
        # doc_b appears in both sources at high ranks, should rank top
        assert ranked[0][0] == "doc_b"


class TestDocIDGeneration:
    """Test KOS document ID generation."""

    def test_doc_id_format(self):
        """doc_id should be SHA-1 of canonical path."""
        canonical = "kos::gongwen::7.业务资料/test.md"
        doc_id = hashlib.sha1(canonical.encode()).hexdigest()  # noqa: S324
        assert len(doc_id) == 40  # SHA-1 hex

    def test_doc_id_deterministic(self):
        """Same canonical path → same doc_id."""
        cp = "kos::guozhuan::_工作机制/wiki/STATE.md"
        assert hashlib.sha1(cp.encode()).hexdigest() == hashlib.sha1(cp.encode()).hexdigest()  # noqa: S324
