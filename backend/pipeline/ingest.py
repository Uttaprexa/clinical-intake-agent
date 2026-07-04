"""
Step 1 of the pipeline: ingest raw uploaded files (PDF or plain text)
into a single normalized text string for the extraction stage.
"""
from pathlib import Path

import pdfplumber


class IngestError(Exception):
    pass


def ingest_file(file_path: str) -> str:
    """Extracts raw text from an uploaded intake form (.pdf or .txt)."""
    path = Path(file_path)
    if not path.exists():
        raise IngestError(f"File not found: {file_path}")

    suffix = path.suffix.lower()
    if suffix == ".txt":
        return path.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".pdf":
        return _ingest_pdf(path)
    raise IngestError(f"Unsupported file type: {suffix}")


def _ingest_pdf(path: Path) -> str:
    pages = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            pages.append(text)

    full_text = "\n".join(pages).strip()
    if not full_text:
        raise IngestError(
            "No extractable text found in PDF. Scanned/image-only PDFs "
            "would need an OCR step (e.g. Tesseract) added here."
        )
    return full_text
