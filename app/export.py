from __future__ import annotations

from io import BytesIO
from typing import Tuple

from docx import Document
from docx.shared import Pt
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas


def export_docx(title: str, markdown_text: str) -> Tuple[str, bytes]:
    doc = Document()
    doc.add_heading(title or "特許明細書草案", level=1)
    for line in markdown_text.splitlines():
        p = doc.add_paragraph()
        run = p.add_run(line)
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
    for line in markdown_text.splitlines():
        if y < 40:
            c.showPage()
            y = height - 40
            c.setFont("HeiseiKakuGo-W5", 10)
        c.drawString(40, y, line)
        y -= 14
    c.showPage()
    c.save()
    return (f"{title or 'draft'}.pdf", buffer.getvalue())
