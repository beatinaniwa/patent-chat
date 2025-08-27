from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader

from app.export import export_pdf


def test_pdf_export_supports_japanese_text():
    title = "日本語タイトル"
    body = "これは日本語の本文です。英数字ABC123も含みます。"

    filename, pdf_bytes = export_pdf(title, body)

    assert filename.endswith(".pdf")
    # Basic smoke: produced some bytes
    assert isinstance(pdf_bytes, (bytes, bytearray)) and len(pdf_bytes) > 100

    # Try to extract text. Even if layout differs, Japanese characters should be present somewhere
    reader = PdfReader(BytesIO(pdf_bytes))
    full_text = "\n".join(page.extract_text() or "" for page in reader.pages)

    # Japanese characters from title and body should appear (not mojibake)
    assert "日本語タイトル" in full_text
    assert "これは日本語の本文です。" in full_text
