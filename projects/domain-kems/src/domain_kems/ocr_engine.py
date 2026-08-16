#!/usr/bin/env python3
"""
OCR Engine — 统一 OCR 引擎
从各域 _control/tools/ 下沉，复用 PyMuPDF + tesseract。
支持批量处理、损坏文件跳过、已处理文件跳过。
"""

import fitz
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional


class OCREngine:
    """统一 OCR 引擎"""

    def __init__(self, domain_root: Path, dpi: int = 200, lang: str = "chi_sim+eng"):
        self.domain_root = Path(domain_root)
        self.dpi = dpi
        self.lang = lang
        self.ocr_dir = self.domain_root / "_ocr_text"
        self.ocr_dir.mkdir(exist_ok=True)

    def process_pdf(self, pdf_path: Path) -> dict:
        """处理单个 PDF"""
        name = pdf_path.stem[:60].replace("/", "_").replace(" ", "_")[:80]
        out_file = self.ocr_dir / f"{name}.txt"
        if out_file.exists():
            return {"file": name, "status": "skipped"}

        try:
            doc = fitz.open(str(pdf_path))
            all_text = []
            for pn in range(len(doc)):
                page = doc[pn]
                mat = fitz.Matrix(self.dpi / 72, self.dpi / 72)
                pix = page.get_pixmap(matrix=mat)
                img = self.ocr_dir / f"_tmp_{name}_{pn}.png"
                pix.save(str(img))
                try:
                    r = subprocess.run(
                        ["tesseract", str(img), "-", "-l", self.lang, "--psm", "6"],
                        capture_output=True, text=True, timeout=120
                    )
                    t = r.stdout.strip()
                    if t:
                        all_text.append(f"\n--- Page {pn+1} ---\n{t}")
                except Exception:
                    pass
                img.unlink(missing_ok=True)
            doc.close()

            text = "\n".join(all_text)
            if text.strip():
                out_file.write_text(text, encoding="utf-8")
                return {"file": name, "pages": len(doc), "chars": len(text), "status": "done"}
            return {"file": name, "status": "empty"}
        except Exception as e:
            return {"file": name, "error": str(e), "status": "error"}

    def batch_process(self, domain_id: Optional[str] = None) -> List[dict]:
        """批量处理域内所有 PDF"""
        results = []
        pdfs = sorted(self.domain_root.rglob("*.pdf"))
        for i, pdf_path in enumerate(pdfs, 1):
            result = self.process_pdf(pdf_path)
            result["index"] = i
            result["total"] = len(pdfs)
            results.append(result)
            if result["status"] == "done":
                print(f"  [{i}/{len(pdfs)}] {result['file'][:50]} ({result.get('chars', 0)} chars)")
            elif result["status"] == "error":
                print(f"  [{i}/{len(pdfs)}] ERROR {result['file'][:50]}: {result.get('error', '?')}")
        return results

    def get_stats(self) -> dict:
        """获取 OCR 统计"""
        txt_files = list(self.ocr_dir.glob("*.txt"))
        pdf_files = list(self.domain_root.rglob("*.pdf"))
        return {
            "domain": self.domain_root.name,
            "pdf_count": len(pdf_files),
            "ocr_count": len(txt_files),
            "pending": len(pdf_files) - len(txt_files),
        }


if __name__ == "__main__":
    import sys

    domain = sys.argv[1] if len(sys.argv) > 1 else "卫健委"
    root = Path("/Users/xiamingxing/Documents/@工作文档") / domain
    engine = OCREngine(root)
    print(f"OCR: {domain}")
    results = engine.batch_process()
    done = sum(1 for r in results if r["status"] == "done")
    print(f"完成: {done}/{len(results)}")
