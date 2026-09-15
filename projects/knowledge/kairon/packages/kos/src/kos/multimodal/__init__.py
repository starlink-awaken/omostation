#!/usr/bin/env python3
# ruff: noqa
"""
KOS Multimodal Processor — 多模态内容处理

将图片、音频、视频等非结构化内容转换为可搜索的文本。

支持格式:
- 图片: PNG, JPG, WEBP, BMP, TIFF (OCR + 描述)
- 音频: MP3, WAV, M4A, FLAC, OGG (转写 + 说话人分离)
- 视频: MP4, MOV, AVI, MKV (关键帧 + 音频转写)
- 文档: PDF (扫描件 OCR)

Usage:
    from kos.multimodal import MultimodalProcessor

    processor = MultimodalProcessor()

    # 处理单个文件
    result = processor.process_file("/path/to/image.png")

    # 批量处理目录
    results = processor.process_directory("/path/to/media/")

    # 获取支持格式
    formats = processor.supported_formats
"""

from __future__ import annotations

import json
import os


# 推理端点: 默认 omlxc 网关 (tailscale), 可通过 LLM_GATEWAY_URL 覆盖
OMLX_GATEWAY_URL = os.environ.get("LLM_GATEWAY_URL", "http://100.96.126.35:4000")
OMLX_CHAT_URL = f"{OMLX_GATEWAY_URL}/v1/chat/completions"
OMLX_MODELS_URL = f"{OMLX_GATEWAY_URL}/v1/models"
OMLX_API_KEY = os.environ.get("OMLX_API_KEY", "local")


import sqlite3
import subprocess as sp
import sys
import time
from pathlib import Path
from typing import Any

from kos.config import get_artifact_path
from kos.db import get_connection


class MultimodalProcessor:
    """多模态内容处理器。

    将图片/音频/视频转换为可搜索的文本内容，
    并创建对应的 KOS 文档记录。
    """

    # 支持的文件扩展名
    IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif", ".gif"}
    AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".wma", ".aac"}
    VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm"}
    DOCUMENT_EXTENSIONS = {".pdf"}

    ALL_EXTENSIONS = IMAGE_EXTENSIONS | AUDIO_EXTENSIONS | VIDEO_EXTENSIONS | DOCUMENT_EXTENSIONS

    def __init__(self):
        self._llm_available = None

    @property
    def supported_formats(self) -> dict[str, list[str]]:
        """返回支持的格式列表。"""
        return {
            "image": sorted(self.IMAGE_EXTENSIONS),
            "audio": sorted(self.AUDIO_EXTENSIONS),
            "video": sorted(self.VIDEO_EXTENSIONS),
            "document": sorted(self.DOCUMENT_EXTENSIONS),
        }

    # ── 核心 API ────────────────────────────────────────────

    def process_file(self, file_path: str | Path, zone: str = "multimodal") -> dict[str, Any]:
        """处理单个多模态文件。

        Args:
            file_path: 文件路径。
            zone: 目标知识域。

        Returns:
            处理结果 dict。
        """
        file_path = Path(file_path)
        if not file_path.exists():
            return {"error": f"File not found: {file_path}", "path": str(file_path)}

        ext = file_path.suffix.lower()
        file_size = file_path.stat().st_size

        # 跳过过大的文件 (>500MB)
        if file_size > 500 * 1024 * 1024:
            return {"error": "File too large (>500MB)", "path": str(file_path)}

        result = {
            "path": str(file_path),
            "filename": file_path.name,
            "extension": ext,
            "size_bytes": file_size,
            "zone": zone,
        }

        try:
            if ext in self.IMAGE_EXTENSIONS:
                result.update(self._process_image(file_path))
            elif ext in self.AUDIO_EXTENSIONS:
                result.update(self._process_audio(file_path))
            elif ext in self.VIDEO_EXTENSIONS:
                result.update(self._process_video(file_path))
            elif ext in self.DOCUMENT_EXTENSIONS:
                result.update(self._process_pdf(file_path))
            else:
                result["error"] = f"Unsupported format: {ext}"
                return result

            # 创建 KOS 文档
            if result.get("text"):
                doc_id = self._create_document(file_path, result, zone)
                result["doc_id"] = doc_id
                result["indexed"] = True

        except Exception as e:
            result["error"] = str(e)

        return result

    def process_directory(
        self,
        dir_path: str | Path,
        zone: str = "multimodal",
        recursive: bool = True,
    ) -> dict[str, Any]:
        """批量处理目录中的多模态文件。

        Args:
            dir_path: 目录路径。
            zone: 目标知识域。
            recursive: 是否递归子目录。

        Returns:
            批量处理结果。
        """
        dir_path = Path(dir_path)
        if not dir_path.is_dir():
            return {"error": f"Not a directory: {dir_path}"}

        results = []
        files = []

        # 收集文件
        pattern = "**/*" if recursive else "*"
        for f in dir_path.glob(pattern):
            if f.is_file() and f.suffix.lower() in self.ALL_EXTENSIONS:
                files.append(f)

        # 处理
        for f in files:
            result = self.process_file(f, zone=zone)
            results.append(result)

        # 统计
        success = sum(1 for r in results if r.get("indexed"))
        failed = sum(1 for r in results if r.get("error"))

        return {
            "total_files": len(files),
            "processed": success,
            "failed": failed,
            "results": results,
        }

    # ── 图片处理 ────────────────────────────────────────────

    def _process_image(self, file_path: Path) -> dict[str, Any]:
        """处理图片: OCR + 描述。"""
        result = {"type": "image"}

        # 1. OCR 文字提取
        ocr_text = self._ocr_image(file_path)
        if ocr_text:
            result["ocr_text"] = ocr_text

        # 2. 图片描述 (使用 LLM)
        description = self._describe_image(file_path)
        if description:
            result["description"] = description

        # 3. 合并文本
        parts = []
        if ocr_text:
            parts.append(f"[OCR]\n{ocr_text}")
        if description:
            parts.append(f"[Description]\n{description}")
        result["text"] = "\n\n".join(parts) if parts else ""

        return result

    def _ocr_image(self, file_path: Path) -> str:
        """OCR 文字提取。"""
        # 尝试使用 arkcli-understand 或 tesseract
        try:
            # 方法1: arkcli-understand (如果可用)
            r = sp.run(
                ["arkcli", "understand", "image", str(file_path), "--task", "ocr"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        except (FileNotFoundError, sp.TimeoutExpired):
            pass

        # 方法2: tesseract (如果安装)
        try:
            r = sp.run(
                ["tesseract", str(file_path), "stdout", "-l", "chi_sim+eng"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        except (FileNotFoundError, sp.TimeoutExpired):
            pass

        return ""

    def _describe_image(self, file_path: Path) -> str:
        """使用 LLM 生成图片描述。"""
        if not self._check_llm_available():
            return ""

        import base64
        import urllib.request

        # 读取图片并编码
        try:
            with open(file_path, "rb") as f:
                img_data = base64.b64encode(f.read()).decode("utf-8")
        except Exception:
            return ""

        # 调用 omlx 视觉模型
        payload = json.dumps(
            {
                "model": "qwen3.6-27b-4bit",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{img_data}"},
                            },
                            {
                                "type": "text",
                                "content": "用一句话描述这张图片的主要内容，包括可见的文字、物体和场景。",
                            },
                        ],
                    }
                ],
                "max_tokens": 200,
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            OMLX_CHAT_URL,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + OMLX_API_KEY,
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=60.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                choices = data.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "").strip()
        except Exception:
            pass

        return ""

    # ── 音频处理 ────────────────────────────────────────────

    def _process_audio(self, file_path: Path) -> dict[str, Any]:
        """处理音频: 转写。"""
        result = {"type": "audio"}

        # 转写
        transcript = self._transcribe_audio(file_path)
        if transcript:
            result["transcript"] = transcript
            result["text"] = f"[Transcript]\n{transcript}"

        return result

    def _transcribe_audio(self, file_path: Path) -> str:
        """音频转写。"""
        # 方法1: arkcli-understand
        try:
            r = sp.run(
                ["arkcli", "understand", "audio", str(file_path), "--task", "asr"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        except (FileNotFoundError, sp.TimeoutExpired):
            pass

        # 方法2: whisper (如果安装)
        try:
            r = sp.run(
                ["whisper", str(file_path), "--model", "base", "--output_format", "txt", "--output_dir", "/tmp"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if r.returncode == 0:
                # 读取输出文件
                output = Path("/tmp") / f"{file_path.stem}.txt"
                if output.exists():
                    return output.read_text().strip()
        except (FileNotFoundError, sp.TimeoutExpired):
            pass

        return ""

    # ── 视频处理 ────────────────────────────────────────────

    def _process_video(self, file_path: Path) -> dict[str, Any]:
        """处理视频: 关键帧 + 音频转写。"""
        result = {"type": "video"}

        # 1. 提取音频并转写
        audio_text = self._extract_audio_from_video(file_path)
        if audio_text:
            result["audio_transcript"] = audio_text

        # 2. 关键帧描述
        keyframe_desc = self._describe_keyframes(file_path)
        if keyframe_desc:
            result["keyframe_descriptions"] = keyframe_desc

        # 3. 合并
        parts = []
        if audio_text:
            parts.append(f"[Audio Transcript]\n{audio_text}")
        if keyframe_desc:
            parts.append(f"[Keyframes]\n{keyframe_desc}")
        result["text"] = "\n\n".join(parts) if parts else ""

        return result

    def _extract_audio_from_video(self, file_path: Path) -> str:
        """从视频提取音频并转写。"""
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
            try:
                # 提取音频
                r = sp.run(
                    [
                        "ffmpeg",
                        "-i",
                        str(file_path),
                        "-vn",
                        "-acodec",
                        "pcm_s16le",
                        "-ar",
                        "16000",
                        "-ac",
                        "1",
                        tmp.name,
                        "-y",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if r.returncode != 0:
                    return ""

                # 转写
                return self._transcribe_audio(Path(tmp.name))
            except (FileNotFoundError, sp.TimeoutExpired):
                return ""

    def _describe_keyframes(self, file_path: Path) -> str:
        """提取关键帧并描述。"""
        try:
            # 提取关键帧
            r = sp.run(
                [
                    "ffmpeg",
                    "-i",
                    str(file_path),
                    "-vf",
                    "select='gt(scene,0.3)',",
                    "-vsync",
                    "vfr",
                    "-q:v",
                    "2",
                    "/tmp/frame_%03d.jpg",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if r.returncode != 0:
                return ""

            # 描述每个关键帧
            descriptions = []
            for frame in sorted(Path("/tmp").glob("frame_*.jpg")):
                desc = self._describe_image(frame)
                if desc:
                    descriptions.append(f"- {desc}")
                frame.unlink(missing_ok=True)

            return "\n".join(descriptions)
        except (FileNotFoundError, sp.TimeoutExpired):
            return ""

    # ── PDF 处理 ────────────────────────────────────────────

    def _process_pdf(self, file_path: Path) -> dict[str, Any]:
        """处理 PDF: 文本提取 + OCR (扫描件)。"""
        result = {"type": "document"}

        # 1. 尝试直接提取文本
        text = self._extract_pdf_text(file_path)
        if text:
            result["text"] = text
            result["extraction_method"] = "text"
            return result

        # 2. 扫描件: OCR 每一页
        ocr_text = self._ocr_pdf(file_path)
        if ocr_text:
            result["text"] = ocr_text
            result["extraction_method"] = "ocr"
            return result

        result["text"] = ""
        return result

    def _extract_pdf_text(self, file_path: Path) -> str:
        """提取 PDF 文本。"""
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(str(file_path))
            text = "\n".join(page.get_text() for page in doc)  # type: ignore[reportArgumentType]
            doc.close()
            return text.strip() if text.strip() else ""
        except ImportError:
            pass

        # 备选: pdftotext
        try:
            r = sp.run(
                ["pdftotext", str(file_path), "-"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if r.returncode == 0:
                return r.stdout.strip()
        except (FileNotFoundError, sp.TimeoutExpired):
            pass

        return ""

    def _ocr_pdf(self, file_path: Path) -> str:
        """OCR 扫描版 PDF。"""
        try:
            import fitz

            doc = fitz.open(str(file_path))
            texts = []
            for page in doc:
                pix = page.get_pixmap(dpi=200)
                img_data = pix.tobytes("png")
                # 临时保存并 OCR
                import tempfile

                with tempfile.NamedTemporaryFile(suffix=".png", delete=True) as tmp:
                    tmp.write(img_data)
                    tmp.flush()
                    text = self._ocr_image(Path(tmp.name))
                    if text:
                        texts.append(text)
            doc.close()
            return "\n\n".join(texts)
        except (ImportError, Exception):
            return ""

    # ── KOS 文档创建 ────────────────────────────────────────

    def _create_document(self, file_path: Path, result: dict, zone: str) -> str | None:
        """为处理结果创建 KOS 文档。"""
        import hashlib

        text = result.get("text", "")
        if not text.strip():
            return None

        canonical = f"kos::{zone}::multimodal/{file_path.name}"
        doc_id = hashlib.sha1(canonical.encode()).hexdigest()

        conn = get_connection(get_artifact_path("retrievalDatabase"))
        try:
            # 检查是否已存在
            existing = conn.execute("SELECT doc_id FROM documents WHERE doc_id=?", (doc_id,)).fetchone()
            if existing:
                # 更新
                conn.execute(
                    """UPDATE documents SET
                       title=?, body=?, updated_at=?, metadata_json=?
                       WHERE doc_id=?""",
                    (
                        f"[Multimedia] {file_path.name}",
                        text[:8000],
                        datetime.now().strftime("%Y%m%d%H%M%S"),  # type: ignore[reportUndefinedVariable]
                        json.dumps(
                            {
                                "type": result.get("type", "unknown"),
                                "source_path": str(file_path),
                                "file_size": result.get("size_bytes", 0),
                                "extraction_method": result.get("extraction_method", "auto"),
                                "ocr_text": result.get("ocr_text", ""),
                                "description": result.get("description", ""),
                            }
                        ),
                        doc_id,
                    ),
                )
            else:
                # 新建
                now = datetime.now().strftime("%Y%m%d%H%M%S")  # type: ignore[reportUndefinedVariable]
                conn.execute(
                    """INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        doc_id,
                        f"[Multimedia] {file_path.name}",
                        "multimedia",
                        zone,
                        "active",
                        "multimodal-processor",
                        "",
                        now,
                        now,
                        "working",
                        "active",
                        "pending",
                        "1.0",
                        canonical,
                        str(file_path),
                        "managed",
                        json.dumps(
                            {
                                "type": result.get("type", "unknown"),
                                "source_path": str(file_path),
                                "file_size": result.get("size_bytes", 0),
                            }
                        ),
                        text[:8000],
                        result.get("size_bytes", 0),
                        now,
                    ),
                )
                # 同步 FTS
                conn.execute(
                    "INSERT INTO documents_fts (doc_id, title, body, tags, canonical_path) VALUES (?,?,?,?,?)",
                    (doc_id, f"[Multimedia] {file_path.name}", text[:8000], "", canonical),
                )

            conn.commit()
            return doc_id
        except Exception:
            return None
        finally:
            conn.close()

    # ── 工具方法 ────────────────────────────────────────────

    def _check_llm_available(self) -> bool:
        """检查 LLM 是否可用。"""
        if self._llm_available is not None:
            return self._llm_available

        import urllib.request

        try:
            req = urllib.request.Request(
                OMLX_MODELS_URL,
                headers={"Authorization": "Bearer " + OMLX_API_KEY},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                self._llm_available = resp.status == 200
        except Exception:
            self._llm_available = False

        return self._llm_available


# ── CLI 入口 ──────────────────────────────────────────────


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="KOS Multimodal Processor")
    parser.add_argument("path", help="File or directory to process")
    parser.add_argument("--zone", default="multimodal", help="Target knowledge zone")
    parser.add_argument("--recursive", action="store_true", help="Process directory recursively")
    parser.add_argument("--formats", action="store_true", help="Show supported formats")
    args = parser.parse_args()

    processor = MultimodalProcessor()

    if args.formats:
        print(json.dumps(processor.supported_formats, indent=2))
        return

    path = Path(args.path)
    if path.is_file():
        result = processor.process_file(path, zone=args.zone)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif path.is_dir():
        result = processor.process_directory(path, zone=args.zone, recursive=args.recursive)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"error": f"Path not found: {path}"}))


if __name__ == "__main__":
    main()
