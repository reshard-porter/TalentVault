"""Turns a downloaded resume into a PDF in the PDF folder, whatever format it was uploaded in."""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

CONVERTIBLE = {".doc", ".docx", ".odt", ".rtf", ".txt"}


class ConversionError(Exception):
    pass


def safe_filename(*parts: str) -> str:
    text = "_".join(p.strip() for p in parts if p and p.strip())
    text = re.sub(r"[^\w\-]+", "_", text, flags=re.UNICODE)
    return re.sub(r"_+", "_", text).strip("_") or "candidate"


def is_pdf(path: Path) -> bool:
    with open(path, "rb") as fh:
        return fh.read(5) == b"%PDF-"


def save_as_pdf(downloaded: Path, original_name: str, target: Path) -> Path:
    """Copy (if already a PDF) or convert the download to `target` (.pdf)."""
    target.parent.mkdir(parents=True, exist_ok=True)
    if is_pdf(downloaded):
        shutil.copyfile(downloaded, target)
        return target

    suffix = Path(original_name).suffix.lower()
    if suffix not in CONVERTIBLE:
        raise ConversionError(f"Unsupported resume format '{suffix or 'unknown'}'")

    office = shutil.which("soffice") or shutil.which("libreoffice")
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / f"resume{suffix}"
        shutil.copyfile(downloaded, src)
        if office:
            subprocess.run([office, "--headless", "--convert-to", "pdf", "--outdir", tmp, str(src)],
                           check=True, capture_output=True, timeout=120)
            produced = Path(tmp) / "resume.pdf"
            if not produced.exists():
                raise ConversionError("LibreOffice did not produce a PDF")
            shutil.copyfile(produced, target)
        elif suffix == ".docx":
            _docx_to_pdf_basic(src, target)
        else:
            raise ConversionError(f"Install LibreOffice to convert {suffix} resumes to PDF")
    return target


def _docx_to_pdf_basic(src: Path, target: Path) -> None:
    """Text-only fallback when LibreOffice is not installed."""
    from docx import Document
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate
    from xml.sax.saxutils import escape

    styles = getSampleStyleSheet()
    story = [Paragraph(escape(p.text) or "&nbsp;", styles["Normal"]) for p in Document(src).paragraphs]
    SimpleDocTemplate(str(target), pagesize=LETTER).build(story)
