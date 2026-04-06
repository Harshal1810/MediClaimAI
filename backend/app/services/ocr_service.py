from __future__ import annotations

from pathlib import Path


class OCRService:
    def extract_text(self, file_path: str) -> str:
        try:
            resolved = self._resolve_path(file_path)
            lower = (resolved or "").lower()
            if lower.endswith(".pdf"):
                from app.utils.file_parsers import extract_text_from_pdf

                return extract_text_from_pdf(resolved)
            if lower.endswith(".docx"):
                from app.utils.file_parsers import extract_text_from_docx

                return extract_text_from_docx(resolved)

            from PIL import Image  # type: ignore
            import pytesseract  # type: ignore

            image = Image.open(resolved)
            return pytesseract.image_to_string(image)
        except Exception:
            return ""

    def _resolve_path(self, file_path: str) -> str:
        """
        Resolve a document path robustly.

        Older DB rows may contain relative paths (e.g. "uploads/...") which break when
        the server is started from a different working directory.
        """
        p = Path(file_path or "")
        if not file_path:
            return ""
        if p.is_absolute() and p.exists():
            return str(p)

        candidates: list[Path] = []
        # Current working directory
        candidates.append(Path.cwd() / p)
        # backend/ root (…/backend)
        backend_root = Path(__file__).resolve().parents[2]
        candidates.append(backend_root / p)
        # repo root (…/MediClaimAI)
        repo_root = Path(__file__).resolve().parents[3]
        candidates.append(repo_root / p)

        for c in candidates:
            if c.exists():
                return str(c.resolve())

        # Fall back to original string (it will fail and be handled upstream).
        return str(p)
