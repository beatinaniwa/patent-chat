"""Tests for attachment data model."""

import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.state import Attachment, Idea


class TestAttachmentModel:
    """Test cases for Attachment dataclass."""

    def test_attachment_creation(self):
        """Test creating an attachment with all fields."""
        attachment = Attachment(
            filename="test.pdf",
            content_base64="dGVzdCBjb250ZW50",
            comment="This is a test PDF file",
            file_type="application/pdf",
            upload_time=datetime(2024, 1, 1, 12, 0, 0),
        )

        assert attachment.filename == "test.pdf"
        assert attachment.content_base64 == "dGVzdCBjb250ZW50"
        assert attachment.comment == "This is a test PDF file"
        assert attachment.file_type == "application/pdf"
        assert attachment.upload_time == datetime(2024, 1, 1, 12, 0, 0)

    def test_attachment_to_dict(self):
        """Test converting attachment to dictionary for JSON serialization."""
        attachment = Attachment(
            filename="image.png",
            content_base64="aW1hZ2VfZGF0YQ==",
            comment="Product diagram",
            file_type="image/png",
            upload_time=datetime(2024, 1, 1, 12, 0, 0),
        )

        attachment_dict = asdict(attachment)

        assert attachment_dict["filename"] == "image.png"
        assert attachment_dict["content_base64"] == "aW1hZ2VfZGF0YQ=="
        assert attachment_dict["comment"] == "Product diagram"
        assert attachment_dict["file_type"] == "image/png"
        # datetime should be converted to ISO format string
        assert isinstance(attachment_dict["upload_time"], datetime)

    def test_attachment_from_dict(self):
        """Test creating attachment from dictionary (for JSON deserialization)."""
        data = {
            "filename": "document.txt",
            "content_base64": "ZG9jdW1lbnQ=",
            "comment": "Technical specification",
            "file_type": "text/plain",
            "upload_time": "2024-01-01T12:00:00",
        }

        # Convert string to datetime for the test
        data["upload_time"] = datetime.fromisoformat(data["upload_time"])
        attachment = Attachment(**data)

        assert attachment.filename == "document.txt"
        assert attachment.content_base64 == "ZG9jdW1lbnQ="
        assert attachment.comment == "Technical specification"
        assert attachment.file_type == "text/plain"
        assert attachment.upload_time == datetime(2024, 1, 1, 12, 0, 0)

    def test_attachment_default_upload_time(self):
        """Test that upload_time defaults to current time if not provided."""
        attachment = Attachment(
            filename="test.txt",
            content_base64="dGVzdA==",
            comment="Test file",
            file_type="text/plain",
        )

        # Check that upload_time is set and is recent
        assert attachment.upload_time is not None
        assert isinstance(attachment.upload_time, datetime)
        # Should be within the last minute
        time_diff = datetime.now() - attachment.upload_time
        assert time_diff.total_seconds() < 60


class TestIdeaWithAttachments:
    """Test cases for Idea dataclass with attachments."""

    def test_idea_with_empty_attachments(self):
        """Test that Idea has empty attachments list by default."""
        idea = Idea(
            id="test-id",
            title="Test Idea",
            category="防災",
            description="Test description",
        )

        assert hasattr(idea, "attachments")
        assert idea.attachments == []

    def test_idea_with_attachments(self):
        """Test creating Idea with attachments."""
        attachment1 = Attachment(
            filename="file1.pdf",
            content_base64="ZmlsZTE=",
            comment="First file",
            file_type="application/pdf",
        )
        attachment2 = Attachment(
            filename="file2.txt",
            content_base64="ZmlsZTI=",
            comment="Second file",
            file_type="text/plain",
        )

        idea = Idea(
            id="test-id",
            title="Test Idea",
            category="防災",
            description="Test description",
            attachments=[attachment1, attachment2],
        )

        assert len(idea.attachments) == 2
        assert idea.attachments[0].filename == "file1.pdf"
        assert idea.attachments[1].filename == "file2.txt"

    def test_idea_to_dict_with_attachments(self):
        """Test converting Idea with attachments to dictionary."""
        attachment = Attachment(
            filename="test.pdf",
            content_base64="dGVzdA==",
            comment="Test PDF",
            file_type="application/pdf",
            upload_time=datetime(2024, 1, 1, 12, 0, 0),
        )

        idea = Idea(
            id="test-id",
            title="Test Idea",
            category="防災",
            description="Test description",
            attachments=[attachment],
        )

        idea_dict = asdict(idea)

        assert "attachments" in idea_dict
        assert len(idea_dict["attachments"]) == 1
        assert idea_dict["attachments"][0]["filename"] == "test.pdf"

    def test_add_attachment_to_idea(self):
        """Test adding attachment to existing idea."""
        idea = Idea(
            id="test-id",
            title="Test Idea",
            category="防災",
            description="Test description",
        )

        attachment = Attachment(
            filename="new_file.pdf",
            content_base64="bmV3X2ZpbGU=",
            comment="New attachment",
            file_type="application/pdf",
        )

        idea.attachments.append(attachment)

        assert len(idea.attachments) == 1
        assert idea.attachments[0].filename == "new_file.pdf"

    def test_remove_attachment_from_idea(self):
        """Test removing attachment from idea."""
        attachment1 = Attachment(
            filename="file1.pdf",
            content_base64="ZmlsZTE=",
            comment="First file",
            file_type="application/pdf",
        )
        attachment2 = Attachment(
            filename="file2.txt",
            content_base64="ZmlsZTI=",
            comment="Second file",
            file_type="text/plain",
        )

        idea = Idea(
            id="test-id",
            title="Test Idea",
            category="防災",
            description="Test description",
            attachments=[attachment1, attachment2],
        )

        # Remove first attachment
        idea.attachments = [a for a in idea.attachments if a.filename != "file1.pdf"]

        assert len(idea.attachments) == 1
        assert idea.attachments[0].filename == "file2.txt"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
