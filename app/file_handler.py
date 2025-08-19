"""File handling utilities for attachments."""

import base64
import io
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from PIL import Image
from pypdf import PdfReader

# Logger
logger = logging.getLogger("patent_chat.file_handler")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False

# Constants
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
SUPPORTED_TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".json",
    ".csv",
    ".xml",
    ".html",
    ".css",
    ".js",
    ".py",
    ".java",
    ".cpp",
    ".c",
    ".h",
}
SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp"}
SUPPORTED_PDF_EXTENSIONS = {".pdf"}
MAX_TEXT_LENGTH = 4000  # Maximum characters to extract from a file


def validate_file_size(file) -> bool:
    """Validate that file size is within limits.

    Args:
        file: Streamlit UploadedFile object

    Returns:
        True if file size is valid

    Raises:
        ValueError: If file size exceeds limit
    """
    if file.size > MAX_FILE_SIZE:
        raise ValueError(f"ファイルサイズが10MBを超えています（{file.size / 1024 / 1024:.1f}MB）")
    return True


def validate_file_type(filename: str) -> bool:
    """Validate that file type is supported.

    Args:
        filename: Name of the file

    Returns:
        True if file type is supported

    Raises:
        ValueError: If file type is not supported
    """
    ext = "".join(filename.split(".")[-1:])
    if ext:
        ext = f".{ext.lower()}"
    else:
        raise ValueError("ファイル拡張子が不明です")

    all_supported = (
        SUPPORTED_TEXT_EXTENSIONS | SUPPORTED_IMAGE_EXTENSIONS | SUPPORTED_PDF_EXTENSIONS
    )
    if ext not in all_supported:
        raise ValueError(f"サポートされていないファイル形式です: {ext}")
    return True


def extract_text_from_file(file_bytes: bytes, filename: str) -> str:
    """Extract text content from file bytes.

    Args:
        file_bytes: Raw file content
        filename: Name of the file

    Returns:
        Extracted text content or description
    """
    ext = "".join(filename.split(".")[-1:])
    if ext:
        ext = f".{ext.lower()}"

    # Text files
    if ext in SUPPORTED_TEXT_EXTENSIONS:
        try:
            text = file_bytes.decode("utf-8")
            if len(text) > MAX_TEXT_LENGTH:
                return text[:MAX_TEXT_LENGTH] + "\n... (以下省略)"
            return text
        except UnicodeDecodeError:
            # Try with shift-jis for Japanese files
            try:
                text = file_bytes.decode("shift-jis")
                if len(text) > MAX_TEXT_LENGTH:
                    return text[:MAX_TEXT_LENGTH] + "\n... (以下省略)"
                return text
            except Exception:
                logger.warning(f"Failed to decode text file: {filename}")
                return "テキストファイルの読み取りに失敗しました"

    # PDF files
    elif ext in SUPPORTED_PDF_EXTENSIONS:
        return extract_text_from_pdf(file_bytes)

    # Image files
    elif ext in SUPPORTED_IMAGE_EXTENSIONS:
        return extract_text_from_image(file_bytes)

    # Unsupported
    else:
        return ""


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract text from PDF bytes.

    Args:
        pdf_bytes: PDF file content

    Returns:
        Extracted text from PDF
    """
    try:
        pdf_file = io.BytesIO(pdf_bytes)
        reader = PdfReader(pdf_file)

        text_parts = []
        for i, page in enumerate(reader.pages):
            if i >= 10:  # Limit to first 10 pages
                text_parts.append("... (以降のページは省略)")
                break

            page_text = page.extract_text()
            if page_text:
                text_parts.append(f"[Page {i+1}]\n{page_text}")

        if not text_parts:
            return "PDFからテキストを抽出できませんでした"

        full_text = "\n\n".join(text_parts)
        if len(full_text) > MAX_TEXT_LENGTH:
            return full_text[:MAX_TEXT_LENGTH] + "\n... (以下省略)"
        return full_text

    except Exception as e:
        logger.error(f"PDF extraction error: {e}")
        return "PDFの読み取りに失敗しました"


def extract_text_from_image(image_bytes: bytes) -> str:
    """Extract description from image bytes.

    Note: This creates a basic description. For OCR, additional libraries would be needed.

    Args:
        image_bytes: Image file content

    Returns:
        Description of the image
    """
    try:
        image = Image.open(io.BytesIO(image_bytes))

        # Get image properties
        width, height = image.size
        mode = image.mode
        format_name = image.format if image.format else "不明"

        description = (
            f"画像ファイル（{format_name}形式、{width}x{height}ピクセル、カラーモード: {mode}）"
        )

        # Add more details if needed
        if width > 2000 or height > 2000:
            description += "\n高解像度画像"

        return description

    except Exception as e:
        logger.error(f"Image extraction error: {e}")
        return "画像の読み取りに失敗しました"


def process_uploaded_file(file, comment: str) -> Dict[str, Any]:
    """Process an uploaded file and prepare it for storage.

    Args:
        file: Streamlit UploadedFile object
        comment: User's comment about the file

    Returns:
        Dictionary with file information ready for storage

    Raises:
        ValueError: If file validation fails
    """
    # Validate file
    validate_file_size(file)
    validate_file_type(file.name)

    # Read file content
    file_bytes = file.read()

    # Extract text content
    extracted_text = extract_text_from_file(file_bytes, file.name)

    # Encode to base64 for storage
    content_base64 = base64.b64encode(file_bytes).decode("utf-8")

    return {
        "filename": file.name,
        "content_base64": content_base64,
        "comment": comment,
        "file_type": file.type,
        "extracted_text": extracted_text,
        "upload_time": datetime.now(),
    }


def _format_attachments_for_prompt(attachments: Optional[list]) -> str:
    """Format attachments for LLM prompt.

    Args:
        attachments: List of attachment dictionaries

    Returns:
        Formatted string for inclusion in LLM prompt
    """
    if not attachments:
        return ""

    parts = []
    for i, att in enumerate(attachments, 1):
        filename = att.get("filename", "不明なファイル")
        comment = att.get("comment", "")
        extracted_text = att.get("extracted_text", "")

        # Truncate very long text
        if extracted_text and len(extracted_text) > 2000:
            extracted_text = extracted_text[:2000] + "\n... (省略)"

        part = f"[添付ファイル{i}]\n"
        part += f"ファイル名: {filename}\n"
        if comment:
            part += f"コメント: {comment}\n"
        if extracted_text:
            part += f"内容:\n{extracted_text}\n"

        parts.append(part)

    if parts:
        return "\n".join(parts)
    return ""
