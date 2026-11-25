import io
import re
import zipfile

import docx
import pymupdf

MAX_TEXT_CHARS = 60_000
MAX_PDF_PAGES = 15
MAX_DOCX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
MIN_TEXT_CHARS = 50


class ResumeParseError(Exception):
    """Raised with a user-safe message when a resume cannot be read."""


def _normalize(text: str) -> str:
    text = text.replace("\x00", "")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _parse_pdf(data: bytes) -> tuple[str, int, list[str]]:
    if not data.startswith(b"%PDF-"):
        raise ResumeParseError("File content is not a valid PDF")
    warnings: list[str] = []
    try:
        document = pymupdf.open(stream=data, filetype="pdf")
    except Exception:
        raise ResumeParseError("The PDF could not be read; it may be corrupted")
    with document:
        if document.needs_pass:
            raise ResumeParseError("Password-protected PDFs are not supported")
        page_count = document.page_count
        pages = min(page_count, MAX_PDF_PAGES)
        if page_count > MAX_PDF_PAGES:
            warnings.append(f"Only the first {MAX_PDF_PAGES} pages were read")
        text = "\n".join(document[i].get_text("text") for i in range(pages))
    return text, page_count, warnings


def _parse_docx(data: bytes) -> tuple[str, int, list[str]]:
    buffer = io.BytesIO(data)
    if not zipfile.is_zipfile(buffer):
        raise ResumeParseError("File content is not a valid DOCX")
    with zipfile.ZipFile(buffer) as archive:
        if "word/document.xml" not in archive.namelist():
            raise ResumeParseError("File content is not a valid DOCX")
        if sum(info.file_size for info in archive.infolist()) > MAX_DOCX_UNCOMPRESSED_BYTES:
            raise ResumeParseError("The DOCX file expands to an unsafe size")
    try:
        document = docx.Document(io.BytesIO(data))
    except Exception:
        raise ResumeParseError("The DOCX could not be read; it may be corrupted")

    parts: list[str] = []
    for section in document.sections:
        parts.extend(p.text for p in section.header.paragraphs if p.text.strip())
    parts.extend(p.text for p in document.paragraphs)
    for table in document.tables:
        for row in table.rows:
            cells: list[str] = []
            for cell in row.cells:
                value = cell.text.strip()
                if value and (not cells or cells[-1] != value):
                    cells.append(value)
            if cells:
                parts.append(" | ".join(cells))
    return "\n".join(parts), 0, []


def parse_resume(data: bytes, file_type: str) -> dict:
    if file_type == "pdf":
        text, page_count, warnings = _parse_pdf(data)
    elif file_type == "docx":
        text, page_count, warnings = _parse_docx(data)
    else:
        raise ResumeParseError("Unsupported file type")

    text = _normalize(text)
    if len(text) < MIN_TEXT_CHARS:
        raise ResumeParseError(
            "No readable text was found. Scanned or image-only resumes are not supported "
            "(OCR is not available). Please upload a text-based PDF or DOCX."
        )
    if len(text) > MAX_TEXT_CHARS:
        text = text[:MAX_TEXT_CHARS]
        warnings.append("Resume text was truncated to 60,000 characters")
    return {"text": text, "page_count": page_count, "warnings": warnings}
