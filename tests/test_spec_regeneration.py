"""Tests for specification regeneration logic."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.llm import regenerate_spec


class TestSpecRegeneration:
    """Test cases for complete specification regeneration."""

    @patch("app.llm._get_client")
    def test_regenerate_with_no_qa(self, mock_client):
        """Test regeneration with no Q&A history (similar to bootstrap)."""
        # Mock API response
        mock_response = MagicMock()
        mock_response.text = "# 特許明細書\n## 発明の名称\nテスト発明"
        mock_client.return_value.models.generate_content.return_value = mock_response

        result = regenerate_spec(
            instruction_md="指示書内容",
            idea_description="アイデアの説明",
            transcript=[],
        )

        # Should return the generated text
        assert "特許明細書" in result
        assert "テスト発明" in result

        # Check that the prompt includes idea description
        call_args = mock_client.return_value.models.generate_content.call_args
        prompt = call_args[1]["contents"]
        assert "アイデアの説明" in prompt
        assert "（質疑応答なし）" in prompt

    @patch("app.llm._get_client")
    def test_regenerate_with_qa_history(self, mock_client):
        """Test regeneration with Q&A history integrated."""
        # Mock API response
        mock_response = MagicMock()
        mock_response.text = "# 特許明細書\n## 発明の名称\n改良版発明"
        mock_client.return_value.models.generate_content.return_value = mock_response

        transcript = [
            {"role": "assistant", "content": "防災用ですか？"},
            {"role": "user", "content": "はい"},
            {"role": "assistant", "content": "既存技術の改良ですか？"},
            {"role": "user", "content": "いいえ"},
        ]

        result = regenerate_spec(
            instruction_md="指示書内容",
            idea_description="アイデアの説明",
            transcript=transcript,
        )

        # Should return the generated text
        assert "特許明細書" in result
        assert "改良版発明" in result

        # Check that the prompt includes Q&A pairs
        call_args = mock_client.return_value.models.generate_content.call_args
        prompt = call_args[1]["contents"]
        assert "防災用ですか？" in prompt
        assert "はい" in prompt
        assert "既存技術の改良ですか？" in prompt
        assert "いいえ" in prompt

    @patch("app.llm._get_client")
    def test_regenerate_with_unanswered_questions(self, mock_client):
        """Test regeneration with some unanswered questions."""
        # Mock API response
        mock_response = MagicMock()
        mock_response.text = "# 特許明細書\n## 内容"
        mock_client.return_value.models.generate_content.return_value = mock_response

        transcript = [
            {"role": "assistant", "content": "質問1？"},
            {"role": "user", "content": "回答1"},
            {"role": "assistant", "content": "質問2？"},
            {"role": "assistant", "content": "質問3？"},  # Unanswered
        ]

        regenerate_spec(
            instruction_md="指示書",
            idea_description="アイデア",
            transcript=transcript,
        )

        # Check that unanswered questions are marked
        call_args = mock_client.return_value.models.generate_content.call_args
        prompt = call_args[1]["contents"]
        assert "質問1？" in prompt
        assert "回答1" in prompt
        assert "質問3？" in prompt
        assert "未回答" in prompt

    @patch("app.llm._get_client")
    def test_regenerate_preserves_all_information(self, mock_client):
        """Test that regeneration includes all components."""
        # Mock API response
        mock_response = MagicMock()
        mock_response.text = "# Complete Patent Specification"
        mock_client.return_value.models.generate_content.return_value = mock_response

        instruction = "詳細な指示書の内容..."
        idea = "革新的なアイデアの説明..."
        transcript = [
            {"role": "assistant", "content": "技術的な質問？"},
            {"role": "user", "content": "技術的な回答"},
        ]

        regenerate_spec(
            instruction_md=instruction,
            idea_description=idea,
            transcript=transcript,
        )

        # Verify all components are in the prompt
        call_args = mock_client.return_value.models.generate_content.call_args
        prompt = call_args[1]["contents"]

        # Should include all three components
        assert instruction in prompt
        assert idea in prompt
        assert "技術的な質問？" in prompt
        assert "技術的な回答" in prompt

        # Should have proper sections
        assert "[指示書]" in prompt
        assert "[アイデア概要]" in prompt
        assert "[質疑応答による追加情報]" in prompt

    @patch("app.llm._get_client")
    def test_regenerate_fallback_on_error(self, mock_client):
        """Test fallback behavior when API fails."""
        # Mock API error
        mock_client.return_value.models.generate_content.side_effect = Exception("API Error")

        result = regenerate_spec(
            instruction_md="指示書",
            idea_description="アイデア説明",
            transcript=[],
        )

        # Should return fallback skeleton
        assert "特許明細書草案" in result
        assert "アイデア概要" in result
        assert "未記載" in result

    @patch("app.llm._get_client")
    def test_regenerate_empty_response_fallback(self, mock_client):
        """Test fallback when API returns empty response."""
        # Mock empty response
        mock_response = MagicMock()
        mock_response.text = ""
        mock_client.return_value.models.generate_content.return_value = mock_response

        result = regenerate_spec(
            instruction_md="指示書",
            idea_description="アイデア",
            transcript=[],
        )

        # Should return fallback skeleton
        assert "特許明細書草案" in result
        assert "未記載" in result

    def test_regenerate_no_client_fallback(self):
        """Test fallback when no client is available."""
        with patch("app.llm._get_client", return_value=None):
            result = regenerate_spec(
                instruction_md="指示書",
                idea_description="アイデア",
                transcript=[],
            )

            # Should return fallback skeleton
            assert "特許明細書草案" in result
            assert "未記載" in result

    @patch("app.llm._get_client")
    def test_regenerate_complex_qa_parsing(self, mock_client):
        """Test Q&A parsing with complex message patterns."""
        # Mock API response
        mock_response = MagicMock()
        mock_response.text = "# Patent"
        mock_client.return_value.models.generate_content.return_value = mock_response

        # Complex pattern with consecutive questions and answers
        transcript = [
            {"role": "assistant", "content": "Q1?"},
            {"role": "assistant", "content": "Q2?"},
            {"role": "user", "content": "A1"},
            {"role": "user", "content": "A2"},
            {"role": "assistant", "content": "Q3?"},
            {"role": "user", "content": "A3"},
            {"role": "assistant", "content": "Q4?"},  # Unanswered
        ]

        regenerate_spec(
            instruction_md="inst",
            idea_description="idea",
            transcript=transcript,
        )

        # Check Q&A parsing
        call_args = mock_client.return_value.models.generate_content.call_args
        prompt = call_args[1]["contents"]

        # Should properly pair questions and answers
        assert "Q1?" in prompt
        assert "Q4?" in prompt
        assert "未回答" in prompt  # Q4 should be marked as unanswered


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
