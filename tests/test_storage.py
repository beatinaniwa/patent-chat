from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.state import Attachment, Idea
from app.storage import load_ideas, save_ideas


def test_save_ideas_with_datetime_attachment():
    """Test that ideas with datetime in attachments can be saved to JSON"""

    # Create a temporary file to use as IDEAS_PATH
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
        tmp_path = Path(tmp.name)

    # Patch IDEAS_PATH to use our temporary file
    with patch('app.storage.IDEAS_PATH', tmp_path), patch('app.storage.DATA_DIR', tmp_path.parent):
        # Create an idea with an attachment that has datetime
        attachment = Attachment(
            filename="test.pdf",
            content_base64="base64content",
            comment="Test PDF",
            file_type="application/pdf",
            upload_time=datetime.now(),
            gemini_file_id="test_id",
            gemini_mime_type="application/pdf",
        )

        idea = Idea(
            id="test-1",
            title="Test Idea",
            category="発明",
            description="Test description",
            attachments=[attachment],
        )

        # After the fix, this should NOT raise an error
        save_ideas([idea])

        # Verify the file was created and contains valid JSON
        assert tmp_path.exists()
        content = json.loads(tmp_path.read_text(encoding="utf-8"))
        assert "ideas" in content
        assert len(content["ideas"]) == 1

    # Clean up
    tmp_path.unlink(missing_ok=True)


def test_save_and_load_ideas_with_datetime_fix():
    """Test that ideas with datetime can be saved and loaded after fix"""

    # This test will pass after we implement the fix
    # For now, it's expected to fail

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
        tmp_path = Path(tmp.name)

    with patch('app.storage.IDEAS_PATH', tmp_path), patch('app.storage.DATA_DIR', tmp_path.parent):
        attachment = Attachment(
            filename="test.pdf",
            content_base64="base64content",
            comment="Test PDF",
            file_type="application/pdf",
            upload_time=datetime(2025, 8, 27, 9, 13, 54),
            gemini_file_id="test_id",
            gemini_mime_type="application/pdf",
        )

        idea = Idea(
            id="test-1",
            title="Test Idea",
            category="発明",
            description="Test description",
            attachments=[attachment],
        )

        # Save and load should work after fix
        save_ideas([idea])
        loaded_ideas = load_ideas()

        assert len(loaded_ideas) == 1
        assert loaded_ideas[0].id == "test-1"
        assert len(loaded_ideas[0].attachments) == 1
        assert loaded_ideas[0].attachments[0].filename == "test.pdf"

    tmp_path.unlink(missing_ok=True)


def test_load_ideas_with_null_attachments():
    """load_ideas should handle null attachments gracefully"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
        tmp.write(
            json.dumps(
                {
                    "ideas": [
                        {
                            "id": "null-1",
                            "title": "t",
                            "category": "c",
                            "description": "d",
                            "attachments": None,
                        }
                    ]
                },
                ensure_ascii=False,
            )
        )
        tmp_path = Path(tmp.name)

    with patch("app.storage.IDEAS_PATH", tmp_path), patch("app.storage.DATA_DIR", tmp_path.parent):
        ideas = load_ideas()
        assert len(ideas) == 1
        assert ideas[0].attachments == []

    tmp_path.unlink(missing_ok=True)
