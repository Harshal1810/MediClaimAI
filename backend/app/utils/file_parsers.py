from __future__ import annotations

import re
import zipfile
from pathlib import Path


def extract_text_from_pdf(file_path: str) -> str:
    parts: list[str] = []

    # 1) Prefer pypdf when available (fast for text PDFs).
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(file_path)
        for page in reader.pages:
            txt = page.extract_text() or ""
            if txt.strip():
                parts.append(txt)
        out = "\n\n".join(parts).strip()
        if out:
            return out
    except Exception:
        parts = []

    # 2) Fallback to pypdfium2 (commonly available; works well on Windows).
    try:
        import pypdfium2 as pdfium  # type: ignore

        doc = pdfium.PdfDocument(file_path)
        for i in range(len(doc)):
            page = doc[i]
            try:
                textpage = page.get_textpage()
                try:
                    txt = textpage.get_text_range() or ""
                finally:
                    # pypdfium2 text/page objects expose close() in recent versions
                    if hasattr(textpage, "close"):
                        textpage.close()
                if txt.strip():
                    parts.append(txt)
            finally:
                if hasattr(page, "close"):
                    page.close()
        out = "\n\n".join(parts).strip()
        if out:
            return out
    except Exception:
        parts = []

    # 3) Optional fallback to PyMuPDF (fitz) when installed.
    try:
        import fitz  # type: ignore

        doc = fitz.open(file_path)
        for page in doc:
            txt = page.get_text() or ""
            if txt.strip():
                parts.append(txt)
        out = "\n\n".join(parts).strip()
        if out:
            return out
    except Exception:
        return ""

    return ""


def extract_text_from_docx(file_path: str) -> str:
    """
    Minimal .docx text extraction without external dependencies.
    """
    try:
        path = Path(file_path)
        if path.suffix.lower() != ".docx":
            return ""
        with zipfile.ZipFile(path, "r") as z:
            xml = z.read("word/document.xml").decode("utf-8", errors="ignore")
        # strip tags and collapse whitespace
        text = re.sub(r"<[^>]+>", " ", xml)
        text = re.sub(r"\s+", " ", text)
        return text.strip()
    except Exception:
        return ""
