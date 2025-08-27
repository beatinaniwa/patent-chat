"""Tests for Gemini Files API integration."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.file_handler import (
    extract_with_gemini,
    upload_to_gemini,
)


class TestGeminiFileUpload:
    """Test cases for Gemini Files API upload functionality."""

    @patch("app.file_handler._get_client")
    def test_upload_pdf_to_gemini(self, mock_get_client):
        """Test uploading PDF file to Gemini Files API."""
        # Mock Gemini client and file response
        mock_client = MagicMock()
        mock_file = MagicMock()
        mock_file.id = "file-abc123"
        mock_file.name = "test.pdf"
        mock_file.mime_type = "application/pdf"
        mock_client.files.upload.return_value = mock_file
        mock_get_client.return_value = mock_client

        # Test data
        pdf_bytes = b"fake pdf content"
        filename = "test.pdf"

        # Upload file
        file_id, mime_type = upload_to_gemini(pdf_bytes, filename, "application/pdf")

        # Verify
        assert file_id == "file-abc123"
        assert mime_type == "application/pdf"
        mock_client.files.upload.assert_called_once()
        call_kwargs = mock_client.files.upload.call_args[1]
        assert call_kwargs["config"]["mime_type"] == "application/pdf"

    @patch("app.file_handler._get_client")
    def test_upload_image_to_gemini(self, mock_get_client):
        """Test uploading image file to Gemini Files API."""
        # Mock Gemini client and file response
        mock_client = MagicMock()
        mock_file = MagicMock()
        mock_file.id = "file-img456"
        mock_file.name = "image.png"
        mock_file.mime_type = "image/png"
        mock_client.files.upload.return_value = mock_file
        mock_get_client.return_value = mock_client

        # Test data
        image_bytes = b"fake image content"
        filename = "image.png"

        # Upload file
        file_id, mime_type = upload_to_gemini(image_bytes, filename, "image/png")

        # Verify
        assert file_id == "file-img456"
        assert mime_type == "image/png"
        mock_client.files.upload.assert_called_once()

    @patch("app.file_handler._get_client")
    def test_upload_file_size_limit(self, mock_get_client):
        """Test that files over 20MB are rejected."""
        # Create fake file over 20MB
        large_file = b"x" * (21 * 1024 * 1024)  # 21MB

        with pytest.raises(ValueError, match="ファイルサイズが20MBを超えています"):
            upload_to_gemini(large_file, "large.pdf", "application/pdf")

    @patch("app.file_handler._get_client")
    def test_upload_with_no_client(self, mock_get_client):
        """Test upload behavior when client is not available."""
        mock_get_client.return_value = None

        file_id, mime_type = upload_to_gemini(b"content", "test.pdf", "application/pdf")

        assert file_id is None
        assert mime_type == "application/pdf"

    @patch("app.file_handler._get_client")
    def test_upload_with_api_error(self, mock_get_client):
        """Test upload behavior when API raises an error."""
        mock_client = MagicMock()
        mock_client.files.upload.side_effect = Exception("API Error")
        mock_get_client.return_value = mock_client

        file_id, mime_type = upload_to_gemini(b"content", "test.pdf", "application/pdf")

        assert file_id is None
        assert mime_type == "application/pdf"


class TestGeminiContentExtraction:
    """Test cases for content extraction using Gemini."""

    @patch("app.file_handler._get_client")
    def test_extract_pdf_content_with_gemini(self, mock_get_client):
        """Test extracting content from PDF using Gemini."""
        # Mock Gemini client
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "This PDF contains technical specifications for a new device."
        mock_client.models.generate_content.return_value = mock_response
        mock_get_client.return_value = mock_client

        # Mock file object
        mock_file = MagicMock()
        mock_file.id = "file-pdf789"
        mock_file.mime_type = "application/pdf"

        # Extract content
        content = extract_with_gemini(mock_file, "Extract key information from this PDF")

        # Verify
        assert "technical specifications" in content
        mock_client.models.generate_content.assert_called_once()

    @patch("app.file_handler._get_client")
    def test_extract_image_content_with_gemini(self, mock_get_client):
        """Test extracting content from image using Gemini."""
        # Mock Gemini client
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "This image shows a flowchart of the system architecture."
        mock_client.models.generate_content.return_value = mock_response
        mock_get_client.return_value = mock_client

        # Mock file object
        mock_file = MagicMock()
        mock_file.id = "file-img999"
        mock_file.mime_type = "image/png"

        # Extract content
        content = extract_with_gemini(mock_file, "Describe this image")

        # Verify
        assert "flowchart" in content
        assert "system architecture" in content

    @patch("app.file_handler._get_client")
    def test_extract_with_custom_prompt(self, mock_get_client):
        """Test extraction with custom prompt."""
        # Mock Gemini client
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "主要な技術的特徴：1. 防水性能 2. 軽量設計"
        mock_client.models.generate_content.return_value = mock_response
        mock_get_client.return_value = mock_client

        # Mock file object
        mock_file = MagicMock()

        # Extract with Japanese prompt
        content = extract_with_gemini(mock_file, "このドキュメントから技術的特徴を抽出してください")

        # Verify
        assert "防水性能" in content
        assert "軽量設計" in content

    @patch("app.file_handler._get_client")
    def test_extract_with_no_client(self, mock_get_client):
        """Test extraction when client is not available."""
        mock_get_client.return_value = None
        mock_file = MagicMock()

        content = extract_with_gemini(mock_file, "Extract content")

        assert content == ""

    @patch("app.file_handler._get_client")
    def test_extract_with_api_error(self, mock_get_client):
        """Test extraction when API raises an error."""
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception("API Error")
        mock_get_client.return_value = mock_client
        mock_file = MagicMock()

        content = extract_with_gemini(mock_file, "Extract content")

        assert content == "ファイルの内容を解析できませんでした"


class TestProcessUploadedFileWithGemini:
    """Test cases for complete file processing with Gemini."""

    @patch("app.file_handler.upload_to_gemini")
    @patch("app.file_handler.extract_with_gemini")
    @patch("app.file_handler._get_client")
    def test_process_pdf_with_gemini(self, mock_get_client, mock_extract, mock_upload):
        """Test processing PDF file with Gemini integration."""
        # Setup mocks
        mock_client = MagicMock()
        mock_file = MagicMock()
        mock_file.id = "file-123"
        mock_file.mime_type = "application/pdf"
        mock_get_client.return_value = mock_client

        mock_upload.return_value = ("file-123", "application/pdf")
        mock_extract.return_value = "Extracted PDF content with diagrams"

        # Create mock uploaded file
        from app.file_handler import process_uploaded_file_with_gemini

        file_mock = MagicMock()
        file_mock.name = "test.pdf"
        file_mock.type = "application/pdf"
        file_mock.size = 1024 * 1024  # 1MB
        file_mock.read.return_value = b"pdf content"

        # Process file
        result = process_uploaded_file_with_gemini(file_mock, "Technical document")

        # Verify
        assert result["filename"] == "test.pdf"
        assert result["gemini_file_id"] == "file-123"
        assert result["gemini_mime_type"] == "application/pdf"
        assert result["extracted_text"] == "Extracted PDF content with diagrams"
        assert result["comment"] == "Technical document"

    @patch("app.file_handler.upload_to_gemini")
    @patch("app.file_handler.extract_with_gemini")
    def test_process_text_file_without_gemini(self, mock_extract, mock_upload):
        """Test that text files are processed locally without Gemini."""
        from app.file_handler import process_uploaded_file_with_gemini

        file_mock = MagicMock()
        file_mock.name = "test.txt"
        file_mock.type = "text/plain"
        file_mock.size = 100
        file_mock.read.return_value = b"Plain text content"

        # Process file
        result = process_uploaded_file_with_gemini(file_mock, "Text file")

        # Verify Gemini APIs were not called for text file
        mock_upload.assert_not_called()
        mock_extract.assert_not_called()

        # Text should be extracted locally
        assert result["filename"] == "test.txt"
        assert result["gemini_file_id"] is None
        assert result["extracted_text"] == "Plain text content"

    @patch("app.file_handler.upload_to_gemini")
    def test_process_file_upload_failure(self, mock_upload):
        """Test handling of upload failure."""
        from app.file_handler import process_uploaded_file_with_gemini

        # Mock upload failure
        mock_upload.return_value = (None, "application/pdf")

        file_mock = MagicMock()
        file_mock.name = "test.pdf"
        file_mock.type = "application/pdf"
        file_mock.size = 1024
        file_mock.read.return_value = b"pdf content"

        # Process file - should fall back to local processing
        result = process_uploaded_file_with_gemini(file_mock, "Failed upload")

        # Verify fallback behavior
        assert result["filename"] == "test.pdf"
        assert result["gemini_file_id"] is None
        # Should have some extracted text from fallback processing
        assert "extracted_text" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
