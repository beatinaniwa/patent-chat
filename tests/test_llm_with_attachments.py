"""Tests for LLM integration with attachments."""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.llm import bootstrap_spec, next_questions, regenerate_spec
from app.state import Attachment


class TestBootstrapWithAttachments:
    """Test cases for initial spec generation with attachments."""

    @patch("app.llm._get_client")
    def test_bootstrap_spec_with_attachments(self, mock_client):
        """Test generating initial spec with attachment content."""
        # Mock API response
        mock_response = MagicMock()
        mock_response.text = "# 特許明細書\n添付ファイルの内容を反映"
        mock_client.return_value.models.generate_content.return_value = mock_response

        attachments = [
            {
                "filename": "diagram.png",
                "extracted_text": "図面：製品の構造を示す",
                "comment": "製品の全体構造図",
            },
            {
                "filename": "spec.txt",
                "extracted_text": "技術仕様：耐熱温度100度",
                "comment": "技術仕様書",
            },
        ]

        result, error = bootstrap_spec(
            sample_manual_md="指示書",
            idea_description="防災用品のアイデア",
            attachments=attachments,
        )

        assert error is None
        assert "特許明細書" in result

        # Check that attachments are included in prompt
        call_args = mock_client.return_value.models.generate_content.call_args
        prompt = call_args[1]["contents"]
        assert "製品の全体構造図" in prompt
        assert "図面：製品の構造を示す" in prompt
        assert "技術仕様書" in prompt
        assert "技術仕様：耐熱温度100度" in prompt

    @patch("app.llm._get_client")
    def test_bootstrap_spec_without_attachments(self, mock_client):
        """Test that bootstrap works normally without attachments."""
        mock_response = MagicMock()
        mock_response.text = "# 特許明細書\n通常の内容"
        mock_client.return_value.models.generate_content.return_value = mock_response

        result, error = bootstrap_spec(
            sample_manual_md="指示書",
            idea_description="アイデアの説明",
            attachments=None,
        )

        assert error is None
        assert "特許明細書" in result

        # Check that no attachment section is in prompt
        call_args = mock_client.return_value.models.generate_content.call_args
        prompt = call_args[1]["contents"]
        assert "[添付ファイル情報]" not in prompt

    @patch("app.llm._get_client")
    def test_bootstrap_spec_with_empty_attachments(self, mock_client):
        """Test bootstrap with empty attachments list."""
        mock_response = MagicMock()
        mock_response.text = "# 特許明細書"
        mock_client.return_value.models.generate_content.return_value = mock_response

        result, error = bootstrap_spec(
            sample_manual_md="指示書",
            idea_description="アイデア",
            attachments=[],
        )

        assert error is None

        # Should not include attachment section for empty list
        call_args = mock_client.return_value.models.generate_content.call_args
        prompt = call_args[1]["contents"]
        assert "[添付ファイル情報]" not in prompt


class TestRegenerateWithAttachments:
    """Test cases for spec regeneration with attachments."""

    @patch("app.llm._get_client")
    def test_regenerate_spec_with_attachments(self, mock_client):
        """Test regenerating spec with attachment content."""
        mock_response = MagicMock()
        mock_response.text = "# 改良版特許明細書\n添付ファイル反映済み"
        mock_client.return_value.models.generate_content.return_value = mock_response

        transcript = [
            {"role": "assistant", "content": "防災用ですか？"},
            {"role": "user", "content": "はい"},
        ]

        attachments = [
            {
                "filename": "test_results.pdf",
                "extracted_text": "耐久テスト結果：1000時間動作確認",
                "comment": "耐久性テストの結果",
            }
        ]

        result, error = regenerate_spec(
            instruction_md="指示書",
            idea_description="防災用品",
            transcript=transcript,
            attachments=attachments,
        )

        assert error is None
        assert "改良版特許明細書" in result

        # Check that attachments are included
        call_args = mock_client.return_value.models.generate_content.call_args
        prompt = call_args[1]["contents"]
        assert "耐久性テストの結果" in prompt
        assert "耐久テスト結果：1000時間動作確認" in prompt

    @patch("app.llm._get_client")
    def test_regenerate_spec_multiple_attachments(self, mock_client):
        """Test regenerating with multiple attachments."""
        mock_response = MagicMock()
        mock_response.text = "# 特許明細書"
        mock_client.return_value.models.generate_content.return_value = mock_response

        attachments = [
            {
                "filename": "file1.txt",
                "extracted_text": "内容1",
                "comment": "コメント1",
            },
            {
                "filename": "file2.pdf",
                "extracted_text": "内容2",
                "comment": "コメント2",
            },
            {
                "filename": "image.png",
                "extracted_text": "画像説明",
                "comment": "図面",
            },
        ]

        regenerate_spec(
            instruction_md="指示書",
            idea_description="アイデア",
            transcript=[],
            attachments=attachments,
        )

        # Check all attachments are included
        call_args = mock_client.return_value.models.generate_content.call_args
        prompt = call_args[1]["contents"]
        assert "コメント1" in prompt
        assert "コメント2" in prompt
        assert "図面" in prompt
        assert "内容1" in prompt
        assert "内容2" in prompt
        assert "画像説明" in prompt


class TestNextQuestionsWithAttachments:
    """Test cases for question generation with attachments."""

    @patch("app.llm._get_client")
    def test_next_questions_with_attachments(self, mock_client):
        """Test generating questions considering attachment content."""
        mock_response = MagicMock()
        mock_response.text = (
            "図面の詳細について確認させてください。寸法は正確ですか？（はい/いいえ）\n"
            "テスト結果は第三者機関によるものですか？（はい/いいえ）\n"
            "添付の仕様書以外に関連文書はありますか？（はい/いいえ）"
        )
        mock_client.return_value.models.generate_content.return_value = mock_response

        attachments = [
            {
                "filename": "drawing.pdf",
                "extracted_text": "製品図面",
                "comment": "設計図",
            }
        ]

        questions, error = next_questions(
            instruction_md="指示書",
            transcript=[],
            current_spec_md="現在の明細書",
            attachments=attachments,
            num_questions=3,
        )

        assert error is None
        assert len(questions) == 3
        assert "寸法は正確ですか" in questions[0]

        # Check that attachments are considered
        call_args = mock_client.return_value.models.generate_content.call_args
        prompt = call_args[1]["contents"]
        assert "設計図" in prompt or "製品図面" in prompt

    @patch("app.llm._get_client")
    def test_next_questions_without_attachments(self, mock_client):
        """Test that question generation works without attachments."""
        mock_response = MagicMock()
        mock_response.text = (
            "製品の用途は明確ですか？（はい/いいえ）\n" "競合製品はありますか？（はい/いいえ）"
        )
        mock_client.return_value.models.generate_content.return_value = mock_response

        questions, error = next_questions(
            instruction_md="指示書",
            transcript=[],
            current_spec_md="明細書",
            attachments=None,
            num_questions=2,
        )

        assert error is None
        assert len(questions) == 2

        # Should not have attachment section
        call_args = mock_client.return_value.models.generate_content.call_args
        prompt = call_args[1]["contents"]
        assert "[添付ファイル]" not in prompt


class TestAttachmentFormatting:
    """Test cases for attachment content formatting."""

    def test_format_attachments_for_prompt(self):
        """Test formatting attachments for LLM prompt."""
        from app.llm import _format_attachments_for_prompt

        attachments = [
            {
                "filename": "doc1.txt",
                "extracted_text": "Document content",
                "comment": "Important document",
            },
            {
                "filename": "image.png",
                "extracted_text": "Image description",
                "comment": "Product photo",
            },
        ]

        formatted = _format_attachments_for_prompt(attachments)

        assert "Important document" in formatted
        assert "doc1.txt" in formatted
        assert "Document content" in formatted
        assert "Product photo" in formatted
        assert "image.png" in formatted
        assert "Image description" in formatted

    def test_format_empty_attachments(self):
        """Test formatting empty attachments list."""
        from app.llm import _format_attachments_for_prompt

        formatted = _format_attachments_for_prompt([])
        assert formatted == ""

    def test_format_none_attachments(self):
        """Test formatting None attachments."""
        from app.llm import _format_attachments_for_prompt

        formatted = _format_attachments_for_prompt(None)
        assert formatted == ""

    def test_format_attachment_with_long_text(self):
        """Test formatting attachment with long extracted text."""
        from app.llm import _format_attachments_for_prompt

        long_text = "A" * 5000  # 5000 characters
        attachments = [
            {
                "filename": "long.txt",
                "extracted_text": long_text,
                "comment": "Long document",
            }
        ]

        formatted = _format_attachments_for_prompt(attachments)

        # Should truncate long text
        assert len(formatted) < 5000
        assert "..." in formatted or "省略" in formatted

    def test_format_attachment_missing_fields(self):
        """Test formatting attachment with missing fields."""
        from app.llm import _format_attachments_for_prompt

        attachments = [
            {
                "filename": "test.txt",
                # Missing extracted_text
                "comment": "Test file",
            },
            {
                "filename": "test2.txt",
                "extracted_text": "Content",
                # Missing comment
            },
        ]

        formatted = _format_attachments_for_prompt(attachments)

        # Should handle missing fields gracefully
        assert "test.txt" in formatted
        assert "test2.txt" in formatted
        assert "Content" in formatted


class TestAttachmentIntegration:
    """Integration tests for attachment handling in LLM calls."""

    @patch("app.llm._get_client")
    def test_full_workflow_with_attachments(self, mock_client):
        """Test complete workflow with attachments."""
        # Mock responses for each LLM call
        mock_response_bootstrap = MagicMock()
        mock_response_bootstrap.text = "# 初期明細書\n添付ファイル参照"

        mock_response_questions = MagicMock()
        mock_response_questions.text = "添付図面は完成版ですか？（はい/いいえ）"

        mock_response_regenerate = MagicMock()
        mock_response_regenerate.text = "# 更新版明細書\n図面確認済み"

        mock_client.return_value.models.generate_content.side_effect = [
            mock_response_bootstrap,
            mock_response_questions,
            mock_response_regenerate,
        ]

        attachments = [
            {
                "filename": "design.pdf",
                "extracted_text": "設計図面の詳細",
                "comment": "最終設計図",
            }
        ]

        # Step 1: Bootstrap
        spec1, error1 = bootstrap_spec(
            "指示書",
            "製品アイデア",
            attachments=attachments,
        )
        assert "初期明細書" in spec1

        # Step 2: Generate questions
        questions, error2 = next_questions(
            "指示書",
            [],
            spec1,
            attachments=attachments,
            num_questions=1,
        )
        assert "添付図面は完成版ですか" in questions[0]

        # Step 3: Regenerate with answer
        transcript = [
            {"role": "assistant", "content": questions[0]},
            {"role": "user", "content": "はい"},
        ]
        spec2, error3 = regenerate_spec(
            "指示書",
            "製品アイデア",
            transcript,
            attachments=attachments,
        )
        assert "更新版明細書" in spec2

    def test_attachment_model_integration(self):
        """Test Attachment model integration with LLM functions."""
        attachment = Attachment(
            filename="test.pdf",
            content_base64="dGVzdA==",
            comment="Test PDF",
            file_type="application/pdf",
            upload_time=datetime.now(),
        )

        # Convert to dict format expected by LLM functions
        attachment_dict = {
            "filename": attachment.filename,
            "extracted_text": "Extracted content",
            "comment": attachment.comment,
        }

        # This should be the format passed to LLM functions
        assert attachment_dict["filename"] == "test.pdf"
        assert attachment_dict["comment"] == "Test PDF"
        assert "extracted_text" in attachment_dict


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
