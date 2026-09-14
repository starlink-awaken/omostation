"""Tests for KOS Multimodal Processor."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
src_dir = SCRIPT_DIR / "src"
sys.path.insert(0, str(src_dir))

os.environ.setdefault("KOS_HOME", str(SCRIPT_DIR))


class TestMultimodalProcessor(unittest.TestCase):
    """Test the MultimodalProcessor class."""

    def test_import(self):
        from kos.multimodal import MultimodalProcessor

        self.assertTrue(callable(MultimodalProcessor))

    def test_creation(self):
        from kos.multimodal import MultimodalProcessor

        processor = MultimodalProcessor()
        self.assertIsNotNone(processor)

    def test_supported_formats(self):
        from kos.multimodal import MultimodalProcessor

        processor = MultimodalProcessor()
        formats = processor.supported_formats
        self.assertIn("image", formats)
        self.assertIn("audio", formats)
        self.assertIn("video", formats)
        self.assertIn(".png", formats["image"])
        self.assertIn(".mp3", formats["audio"])
        self.assertIn(".mp4", formats["video"])

    def test_process_nonexistent_file(self):
        from kos.multimodal import MultimodalProcessor

        processor = MultimodalProcessor()
        result = processor.process_file("/non/existent/file.png")
        self.assertIn("error", result)

    def test_process_nonexistent_directory(self):
        from kos.multimodal import MultimodalProcessor

        processor = MultimodalProcessor()
        result = processor.process_directory("/non/existent/dir")
        self.assertIn("error", result)

    def test_process_unsupported_format(self):
        from kos.multimodal import MultimodalProcessor

        processor = MultimodalProcessor()
        with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as tmp:
            tmp.write(b"test data")
            tmp.flush()
            result = processor.process_file(tmp.name)
            self.assertIn("error", result)
        os.unlink(tmp.name)

    def test_image_extensions(self):
        from kos.multimodal import MultimodalProcessor

        self.assertIn(".png", MultimodalProcessor.IMAGE_EXTENSIONS)
        self.assertIn(".jpg", MultimodalProcessor.IMAGE_EXTENSIONS)
        self.assertIn(".webp", MultimodalProcessor.IMAGE_EXTENSIONS)

    def test_audio_extensions(self):
        from kos.multimodal import MultimodalProcessor

        self.assertIn(".mp3", MultimodalProcessor.AUDIO_EXTENSIONS)
        self.assertIn(".wav", MultimodalProcessor.AUDIO_EXTENSIONS)
        self.assertIn(".m4a", MultimodalProcessor.AUDIO_EXTENSIONS)

    def test_video_extensions(self):
        from kos.multimodal import MultimodalProcessor

        self.assertIn(".mp4", MultimodalProcessor.VIDEO_EXTENSIONS)
        self.assertIn(".mov", MultimodalProcessor.VIDEO_EXTENSIONS)

    def test_all_extensions_union(self):
        from kos.multimodal import MultimodalProcessor

        expected = (
            MultimodalProcessor.IMAGE_EXTENSIONS
            | MultimodalProcessor.AUDIO_EXTENSIONS
            | MultimodalProcessor.VIDEO_EXTENSIONS
            | MultimodalProcessor.DOCUMENT_EXTENSIONS
        )
        self.assertEqual(MultimodalProcessor.ALL_EXTENSIONS, expected)

    def test_ocr_image_unavailable(self):
        from kos.multimodal import MultimodalProcessor

        processor = MultimodalProcessor()
        # Without tesseract/arkcli, OCR returns empty
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(b"fake png data")
            tmp.flush()
            # Should not crash, just return empty
            result = processor._ocr_image(Path(tmp.name))
            self.assertIsInstance(result, str)
        os.unlink(tmp.name)

    def test_describe_image_no_llm(self):
        from kos.multimodal import MultimodalProcessor

        processor = MultimodalProcessor()
        processor._llm_available = False  # Force unavailable
        result = processor._describe_image(Path("/tmp/fake.png"))
        self.assertEqual(result, "")

    def test_transcribe_unavailable(self):
        from kos.multimodal import MultimodalProcessor

        processor = MultimodalProcessor()
        # Without whisper/arkcli, returns empty
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp.write(b"fake mp3 data")
            tmp.flush()
            result = processor._transcribe_audio(Path(tmp.name))
            self.assertIsInstance(result, str)
        os.unlink(tmp.name)

    def test_check_llm_available(self):
        from kos.multimodal import MultimodalProcessor

        processor = MultimodalProcessor()
        # Should return a boolean
        result = processor._check_llm_available()
        self.assertIsInstance(result, bool)

    def test_process_directory_empty(self):
        from kos.multimodal import MultimodalProcessor

        processor = MultimodalProcessor()
        # Create empty temp directory
        with tempfile.TemporaryDirectory() as tmpdir:
            result = processor.process_directory(tmpdir)
            self.assertEqual(result["total_files"], 0)
            self.assertEqual(result["processed"], 0)


if __name__ == "__main__":
    unittest.main()
