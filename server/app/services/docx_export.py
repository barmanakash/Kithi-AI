"""Word (.docx) export for generated resumes and cover letters. Built locally with python-docx."""
import re
from io import BytesIO

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt

from app.agents.resume_generation import format_period

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _c(value) -> str:
    """python-docx rejects XML-invalid control characters, so strip them."""
    return _CONTROL.sub("", "" if value is None else str(value))


def _new_document() -> Document:
    doc = Document()
    for section in doc.sections:
        section.left_margin = section.right_margin = Inches(0.8)
        section.top_margin = section.bottom_margin = Inches(0.7)
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(10.5)
    return doc


def _heading(doc: Document, text: str) -> None:
    paragraph = doc.add_paragraph()
    paragraph.paragraph_format.space_before = Pt(10)
    paragraph.paragraph_format.space_after = Pt(2)
    run = paragraph.add_run(_c(text).upper())
    run.bold = True
    run.font.size = Pt(11)


def _to_bytes(doc: Document) -> bytes:
    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def resume_docx(content: dict) -> bytes:
    doc = _new_document()
    header = content.get("header", {})

    name = doc.add_paragraph()
    name.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = name.add_run(_c(header.get("name")))
    run.bold = True
    run.font.size = Pt(18)

    contact = [header.get("email"), header.get("phone"), header.get("location"), *header.get("links", [])]
    contact_line = " | ".join(_c(c) for c in contact if c)
    if contact_line:
        paragraph = doc.add_paragraph(contact_line)
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if content.get("headline"):
        paragraph = doc.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.add_run(_c(content["headline"])).italic = True

    if content.get("summary"):
        _heading(doc, "Summary")
        doc.add_paragraph(_c(content["summary"]))

    if content.get("skills") or content.get("soft_skills"):
        _heading(doc, "Skills")
        if content.get("skills"):
            doc.add_paragraph(_c(", ".join(content["skills"])))
        if content.get("soft_skills"):
            paragraph = doc.add_paragraph()
            paragraph.add_run("Soft skills: ").bold = True
            paragraph.add_run(_c(", ".join(content["soft_skills"])))

    if content.get("experience"):
        _heading(doc, "Experience")
        for role in content["experience"]:
            paragraph = doc.add_paragraph()
            paragraph.paragraph_format.space_before = Pt(4)
            paragraph.paragraph_format.space_after = Pt(0)
            paragraph.add_run(_c(role.get("title"))).bold = True
            paragraph.add_run(_c(f" - {role.get('company', '')}"))
            period = format_period(role.get("start_date"), role.get("end_date"), role.get("current", False))
            if period:
                paragraph.add_run(_c(f"  ({period})")).italic = True
            for bullet in role.get("bullets", []):
                doc.add_paragraph(_c(bullet), style="List Bullet")

    if content.get("projects"):
        _heading(doc, "Projects")
        for project in content["projects"]:
            paragraph = doc.add_paragraph()
            paragraph.paragraph_format.space_after = Pt(0)
            paragraph.add_run(_c(project.get("name"))).bold = True
            if project.get("technologies"):
                paragraph.add_run(_c(f"  [{', '.join(project['technologies'])}]"))
            if project.get("description"):
                doc.add_paragraph(_c(project["description"]), style="List Bullet")

    if content.get("education"):
        _heading(doc, "Education")
        for edu in content["education"]:
            parts = [edu.get("degree") or "", edu.get("field_of_study") or ""]
            years = " - ".join(str(y) for y in (edu.get("start_year"), edu.get("end_year")) if y)
            line = f"{', '.join(p for p in parts if p)} - {edu.get('institution', '')}"
            doc.add_paragraph(_c(line + (f" ({years})" if years else "")))

    if content.get("certifications"):
        _heading(doc, "Certifications")
        for cert in content["certifications"]:
            extra = ", ".join(str(x) for x in (cert.get("issuer"), cert.get("year")) if x)
            doc.add_paragraph(_c(cert.get("name", "") + (f" ({extra})" if extra else "")))

    return _to_bytes(doc)


def letter_docx(text: str) -> bytes:
    doc = _new_document()
    blocks = [block for block in re.split(r"\n\s*\n", text or "") if block.strip()]
    for block in blocks:
        lines = [_c(line) for line in block.strip().splitlines()]
        paragraph = doc.add_paragraph()
        paragraph.paragraph_format.space_after = Pt(8)
        for i, line in enumerate(lines):
            run = paragraph.add_run(line)
            if i < len(lines) - 1:
                run.add_break()
    return _to_bytes(doc)
