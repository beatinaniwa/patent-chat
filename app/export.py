from __future__ import annotations

import re
from dataclasses import dataclass
from io import BytesIO
from typing import List, Tuple

from docx import Document
from docx.shared import Pt
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas


@dataclass
class MarkdownElement:
    """Represents a parsed Markdown element."""

    kind: str
    text: str
    level: int | None = None
    number: int | None = None


def parse_markdown(markdown_text: str) -> List[MarkdownElement]:
    r"""Parse a subset of Markdown into structured elements.

    Supports headings (``#``), unordered lists (``-``/``*``), ordered lists
    (``1.``, ``2.``, ...), blank lines, and regular paragraphs.
    """

    elements: List[MarkdownElement] = []
    for raw_line in markdown_text.splitlines():
        line = raw_line.rstrip()
        if not line:
            elements.append(MarkdownElement("blank", ""))
            continue

        if m := re.match(r"^(#{1,6})\s+(.*)", line):
            elements.append(MarkdownElement("heading", m.group(2).strip(), level=len(m.group(1))))
            continue

        if m := re.match(r"^\s*[-*]\s+(.*)", line):
            elements.append(MarkdownElement("bullet", m.group(1).strip()))
            continue

        if m := re.match(r"^(\d+)\.\s+(.*)", line):
            elements.append(MarkdownElement("number", m.group(2).strip(), number=int(m.group(1))))
            continue

        elements.append(MarkdownElement("paragraph", line))

    return elements


def export_docx(title: str, markdown_text: str) -> Tuple[str, bytes]:
    doc = Document()
    doc.add_heading(title or "特許明細書草案", level=1)
    for element in parse_markdown(markdown_text):
        if element.kind == "blank":
            doc.add_paragraph()
            continue
        if element.kind == "heading":
            level = element.level if element.level is not None else 1
            doc.add_heading(element.text, level=level)
            continue
        if element.kind == "bullet":
            doc.add_paragraph(element.text, style="List Bullet")
            continue
        if element.kind == "number":
            doc.add_paragraph(element.text, style="List Number")
            continue
        p = doc.add_paragraph()
        run = p.add_run(element.text)
        run.font.size = Pt(11)
    buffer = BytesIO()
    doc.save(buffer)
    return (f"{title or 'draft'}.docx", buffer.getvalue())


def export_pdf(title: str, markdown_text: str) -> Tuple[str, bytes]:
    buffer = BytesIO()

    # Register Japanese-capable CID font (built-in CJK font mapping)
    # HeiseiKakuGo-W5 is a Gothic (sans-serif) font suitable for body text
    try:
        pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
    except Exception:
        # Registration is idempotent; ignore if already registered or unavailable
        pass

    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 40
    # Use Japanese-capable font
    c.setFont("HeiseiKakuGo-W5", 16)
    c.drawString(40, y, title or "特許明細書草案")
    y -= 30
    c.setFont("HeiseiKakuGo-W5", 10)
    for element in parse_markdown(markdown_text):
        if y < 40:
            c.showPage()
            y = height - 40
            c.setFont("HeiseiKakuGo-W5", 10)

        if element.kind == "blank":
            y -= 14
            continue

        if element.kind == "heading":
            size_map = {1: 14, 2: 12, 3: 11}
            size = size_map.get(element.level or 1, 10)
            c.setFont("HeiseiKakuGo-W5", size)
            c.drawString(40, y, element.text)
            y -= size + 4
            c.setFont("HeiseiKakuGo-W5", 10)
            continue

        if element.kind == "bullet":
            c.drawString(60, y, f"• {element.text}")
            y -= 14
            continue

        if element.kind == "number":
            c.drawString(60, y, f"{element.number}. {element.text}")
            y -= 14
            continue

        c.drawString(40, y, element.text)
        y -= 14
    c.showPage()
    c.save()
    return (f"{title or 'draft'}.pdf", buffer.getvalue())
