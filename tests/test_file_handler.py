"""Tests for file handling functionality."""

import base64
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.file_handler import (
    MAX_FILE_SIZE,
    extract_text_from_file,
    process_uploaded_file_with_gemini,
    validate_file_size,
    validate_file_type,
)


class TestFileValidation:
    """Test cases for file validation functions."""

    def test_validate_file_size_under_limit(self):
        """Test file size validation for file under limit."""
        # Create mock file object
        file_mock = MagicMock()
        file_mock.size = 5 * 1024 * 1024  # 5MB

        result = validate_file_size(file_mock)
        assert result is True

    def test_validate_file_size_at_limit(self):
        """Test file size validation for file at exact limit."""
        file_mock = MagicMock()
        file_mock.size = MAX_FILE_SIZE  # Exactly 10MB

        result = validate_file_size(file_mock)
        assert result is True

    def test_validate_file_size_over_limit(self):
        """Test file size validation for file over limit."""
        file_mock = MagicMock()
        file_mock.size = 11 * 1024 * 1024  # 11MB

        with pytest.raises(ValueError, match="ファイルサイズが10MBを超えています"):
            validate_file_size(file_mock)

    def test_validate_file_type_text(self):
        """Test file type validation for text files."""
        assert validate_file_type("document.txt") is True
        assert validate_file_type("README.md") is True
        assert validate_file_type("config.json") is True
        assert validate_file_type("style.css") is True

    def test_validate_file_type_pdf(self):
        """Test file type validation for PDF files."""
        assert validate_file_type("report.pdf") is True
        assert validate_file_type("REPORT.PDF") is True

    def test_validate_file_type_image(self):
        """Test file type validation for image files."""
        assert validate_file_type("photo.jpg") is True
        assert validate_file_type("diagram.png") is True
        assert validate_file_type("scan.jpeg") is True
        assert validate_file_type("chart.gif") is True
        assert validate_file_type("drawing.bmp") is True

    def test_validate_file_type_invalid(self):
        """Test file type validation for unsupported files."""
        with pytest.raises(ValueError, match="サポートされていないファイル形式"):
            validate_file_type("program.exe")

        with pytest.raises(ValueError, match="サポートされていないファイル形式"):
            validate_file_type("video.mp4")

        with pytest.raises(ValueError, match="サポートされていないファイル形式"):
            validate_file_type("archive.zip")


class TestTextExtraction:
    """Test cases for text extraction from files."""

    def test_extract_text_from_txt_file(self):
        """Test extracting text from plain text file."""
        content = "This is a test document.\nWith multiple lines."
        file_bytes = content.encode("utf-8")

        result = extract_text_from_file(file_bytes, "test.txt")

        assert result == content

    def test_extract_text_from_markdown_file(self):
        """Test extracting text from markdown file."""
        content = "# Title\n\nThis is **markdown** content."
        file_bytes = content.encode("utf-8")

        result = extract_text_from_file(file_bytes, "document.md")

        assert result == content

    def test_extract_text_from_json_file(self):
        """Test extracting text from JSON file."""
        content = '{"key": "value", "number": 42}'
        file_bytes = content.encode("utf-8")

        result = extract_text_from_file(file_bytes, "data.json")

        assert result == content

    @patch("app.file_handler.extract_text_from_pdf")
    def test_extract_text_from_pdf_file(self, mock_pdf_extract):
        """Test extracting text from PDF file."""
        mock_pdf_extract.return_value = "Extracted PDF content"
        file_bytes = b"fake pdf content"

        result = extract_text_from_file(file_bytes, "document.pdf")

        assert result == "Extracted PDF content"
        mock_pdf_extract.assert_called_once_with(file_bytes)

    @patch("app.file_handler.extract_text_from_image")
    def test_extract_text_from_image_file(self, mock_image_extract):
        """Test extracting text from image file."""
        mock_image_extract.return_value = "Text from image"
        file_bytes = b"fake image content"

        result = extract_text_from_file(file_bytes, "diagram.png")

        assert result == "Text from image"
        mock_image_extract.assert_called_once_with(file_bytes)

    def test_extract_text_from_unsupported_file(self):
        """Test extracting text from unsupported file type."""
        file_bytes = b"binary content"

        result = extract_text_from_file(file_bytes, "program.exe")

        assert result == ""


class TestFileProcessing:
    """Test cases for complete file processing."""

    @patch("app.file_handler.validate_file_size")
    @patch("app.file_handler.validate_file_type")
    def test_process_uploaded_file_text(self, mock_validate_type, mock_validate_size):
        """Test processing an uploaded text file."""
        mock_validate_size.return_value = True
        mock_validate_type.return_value = True

        # Create mock uploaded file
        content = "Test file content"
        file_mock = MagicMock()
        file_mock.name = "test.txt"
        file_mock.type = "text/plain"
        file_mock.read.return_value = content.encode("utf-8")
        file_mock.size = len(content)

        # Text files should not use Gemini, so no additional mocking needed
        result = process_uploaded_file_with_gemini(file_mock, "This is a test file")

        assert result["filename"] == "test.txt"
        assert result["file_type"] == "text/plain"
        assert result["comment"] == "This is a test file"
        assert base64.b64decode(result["content_base64"]).decode("utf-8") == content
        assert result["extracted_text"] == content
        assert "upload_time" in result
        assert result["gemini_file_id"] is None  # Text files don't use Gemini

    @patch("app.file_handler.validate_file_size")
    @patch("app.file_handler.validate_file_type")
    @patch("app.file_handler.extract_text_from_pdf")
    def test_process_uploaded_file_pdf(
        self, mock_pdf_extract, mock_validate_type, mock_validate_size
    ):
        """Test processing an uploaded PDF file."""
        mock_validate_size.return_value = True
        mock_validate_type.return_value = True
        mock_pdf_extract.return_value = "Extracted PDF text"

        # Create mock uploaded file
        pdf_content = b"fake pdf bytes"
        file_mock = MagicMock()
        file_mock.name = "document.pdf"
        file_mock.type = "application/pdf"
        file_mock.read.return_value = pdf_content
        file_mock.size = len(pdf_content)

        # Mock Gemini upload for PDF (which will fail, triggering fallback)
        result = process_uploaded_file_with_gemini(file_mock, "Technical specification")

        assert result["filename"] == "document.pdf"
        assert result["file_type"] == "application/pdf"
        assert result["comment"] == "Technical specification"
        assert base64.b64decode(result["content_base64"]) == pdf_content
        assert result["extracted_text"] == "Extracted PDF text"

    @patch("app.file_handler.validate_file_size")
    @patch("app.file_handler.validate_file_type")
    @patch("app.file_handler.extract_text_from_image")
    def test_process_uploaded_file_image(
        self, mock_image_extract, mock_validate_type, mock_validate_size
    ):
        """Test processing an uploaded image file."""
        mock_validate_size.return_value = True
        mock_validate_type.return_value = True
        mock_image_extract.return_value = "Diagram description"

        # Create mock uploaded file
        image_content = b"fake image bytes"
        file_mock = MagicMock()
        file_mock.name = "diagram.png"
        file_mock.type = "image/png"
        file_mock.read.return_value = image_content
        file_mock.size = len(image_content)

        # Mock Gemini upload for image (which will fail, triggering fallback)
        result = process_uploaded_file_with_gemini(file_mock, "System architecture")

        assert result["filename"] == "diagram.png"
        assert result["file_type"] == "image/png"
        assert result["comment"] == "System architecture"
        assert base64.b64decode(result["content_base64"]) == image_content
        assert result["extracted_text"] == "Diagram description"

    @patch("app.file_handler.validate_file_size")
    def test_process_uploaded_file_size_error(self, mock_validate_size):
        """Test processing file that exceeds size limit."""
        mock_validate_size.side_effect = ValueError("ファイルサイズが10MBを超えています")

        file_mock = MagicMock()
        file_mock.name = "large.pdf"
        file_mock.size = 15 * 1024 * 1024

        with pytest.raises(ValueError, match="ファイルサイズが10MBを超えています"):
            process_uploaded_file_with_gemini(file_mock, "Large file")

    @patch("app.file_handler.validate_file_size")
    @patch("app.file_handler.validate_file_type")
    def test_process_uploaded_file_type_error(self, mock_validate_type, mock_validate_size):
        """Test processing file with unsupported type."""
        mock_validate_size.return_value = True
        mock_validate_type.side_effect = ValueError("サポートされていないファイル形式")

        file_mock = MagicMock()
        file_mock.name = "program.exe"
        file_mock.type = "application/x-msdownload"

        with pytest.raises(ValueError, match="サポートされていないファイル形式"):
            process_uploaded_file_with_gemini(file_mock, "Executable file")

    @patch("app.file_handler.validate_file_size")
    @patch("app.file_handler.validate_file_type")
    def test_process_uploaded_file_with_utf8_error(self, mock_validate_type, mock_validate_size):
        """Test processing text file with encoding issues."""
        mock_validate_size.return_value = True
        mock_validate_type.return_value = True

        # Create mock file with non-UTF8 content
        file_mock = MagicMock()
        file_mock.name = "test.txt"
        file_mock.type = "text/plain"
        # Shift-JIS encoded Japanese text
        file_mock.read.return_value = b"\x82\xa0\x82\xa2\x82\xa4"
        file_mock.size = 6

        result = process_uploaded_file_with_gemini(file_mock, "Japanese text file")

        # Should handle encoding gracefully
        assert result["filename"] == "test.txt"
        assert result["extracted_text"] != ""  # Should have some fallback


class TestPDFExtraction:
    """Test cases for PDF text extraction."""

    @patch("app.file_handler.PdfReader")
    def test_extract_text_from_pdf_success(self, mock_pdf_reader_class):
        """Test successful PDF text extraction."""
        # Mock PDF reader
        mock_pdf_reader = MagicMock()
        mock_page1 = MagicMock()
        mock_page1.extract_text.return_value = "Page 1 content"
        mock_page2 = MagicMock()
        mock_page2.extract_text.return_value = "Page 2 content"
        mock_pdf_reader.pages = [mock_page1, mock_page2]
        mock_pdf_reader_class.return_value = mock_pdf_reader

        from app.file_handler import extract_text_from_pdf

        pdf_bytes = b"fake pdf content"
        result = extract_text_from_pdf(pdf_bytes)

        assert "Page 1 content" in result
        assert "Page 2 content" in result

    @patch("app.file_handler.PdfReader")
    def test_extract_text_from_pdf_empty(self, mock_pdf_reader_class):
        """Test PDF extraction with empty content."""
        mock_pdf_reader = MagicMock()
        mock_pdf_reader.pages = []
        mock_pdf_reader_class.return_value = mock_pdf_reader

        from app.file_handler import extract_text_from_pdf

        pdf_bytes = b"fake pdf content"
        result = extract_text_from_pdf(pdf_bytes)

        assert result == "PDFからテキストを抽出できませんでした"

    @patch("app.file_handler.PdfReader")
    def test_extract_text_from_pdf_error(self, mock_pdf_reader_class):
        """Test PDF extraction with error."""
        mock_pdf_reader_class.side_effect = Exception("PDF parsing error")

        from app.file_handler import extract_text_from_pdf

        pdf_bytes = b"corrupted pdf content"
        result = extract_text_from_pdf(pdf_bytes)

        assert result == "PDFの読み取りに失敗しました"


class TestImageExtraction:
    """Test cases for image text extraction."""

    @patch("app.file_handler.Image.open")
    def test_extract_text_from_image_success(self, mock_image_open):
        """Test successful image description generation."""
        # Mock image
        mock_image = MagicMock()
        mock_image.size = (800, 600)
        mock_image.mode = "RGB"
        mock_image_open.return_value = mock_image

        from app.file_handler import extract_text_from_image

        image_bytes = b"fake image content"
        result = extract_text_from_image(image_bytes)

        assert "画像ファイル" in result
        assert "800x600" in result
        assert "RGB" in result

    @patch("app.file_handler.Image.open")
    def test_extract_text_from_image_error(self, mock_image_open):
        """Test image extraction with error."""
        mock_image_open.side_effect = Exception("Invalid image")

        from app.file_handler import extract_text_from_image

        image_bytes = b"corrupted image"
        result = extract_text_from_image(image_bytes)

        assert result == "画像の読み取りに失敗しました"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
