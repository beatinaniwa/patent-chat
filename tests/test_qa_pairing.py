"""Tests for Q&A pairing logic in batch format."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.llm import regenerate_spec


class TestQAPairing:
    """Test cases for Q&A pairing in batch format."""

    @patch("app.llm._get_client")
    def test_batch_qa_pairing(self, mock_client):
        """Test that batch Q&A format is correctly paired."""
        # Mock API response
        mock_response = MagicMock()
        mock_response.text = "# 特許明細書"
        mock_client.return_value.models.generate_content.return_value = mock_response

        # Batch format: 5 questions then 5 answers
        transcript = [
            {"role": "assistant", "content": "質問1？"},
            {"role": "assistant", "content": "質問2？"},
            {"role": "assistant", "content": "質問3？"},
            {"role": "assistant", "content": "質問4？"},
            {"role": "assistant", "content": "質問5？"},
            {"role": "user", "content": "回答1"},
            {"role": "user", "content": "回答2"},
            {"role": "user", "content": "回答3"},
            {"role": "user", "content": "回答4"},
            {"role": "user", "content": "回答5"},
        ]

        regenerate_spec(
            instruction_md="指示書",
            idea_description="アイデア",
            transcript=transcript,
        )

        # Check the prompt contains correctly paired Q&A
        call_args = mock_client.return_value.models.generate_content.call_args
        prompt = call_args[1]["contents"]

        # All Q&A pairs should be present
        assert "Q: 質問1？\nA: 回答1" in prompt
        assert "Q: 質問2？\nA: 回答2" in prompt
        assert "Q: 質問3？\nA: 回答3" in prompt
        assert "Q: 質問4？\nA: 回答4" in prompt
        assert "Q: 質問5？\nA: 回答5" in prompt

        # Wrong pairings should NOT exist
        assert "Q: 質問1？\nA: 未回答" not in prompt
        assert "Q: 質問1？\nA: 回答2" not in prompt

    @patch("app.llm._get_client")
    def test_multiple_rounds_qa_pairing(self, mock_client):
        """Test pairing with multiple rounds of Q&A."""
        # Mock API response
        mock_response = MagicMock()
        mock_response.text = "# 特許明細書"
        mock_client.return_value.models.generate_content.return_value = mock_response

        # Two rounds of Q&A
        transcript = [
            # Round 1: 3 questions
            {"role": "assistant", "content": "Q1-1"},
            {"role": "assistant", "content": "Q1-2"},
            {"role": "assistant", "content": "Q1-3"},
            # Round 1: 3 answers
            {"role": "user", "content": "A1-1"},
            {"role": "user", "content": "A1-2"},
            {"role": "user", "content": "A1-3"},
            # Round 2: 2 questions
            {"role": "assistant", "content": "Q2-1"},
            {"role": "assistant", "content": "Q2-2"},
            # Round 2: 2 answers
            {"role": "user", "content": "A2-1"},
            {"role": "user", "content": "A2-2"},
        ]

        regenerate_spec(
            instruction_md="指示書",
            idea_description="アイデア",
            transcript=transcript,
        )

        # Check the prompt
        call_args = mock_client.return_value.models.generate_content.call_args
        prompt = call_args[1]["contents"]

        # Round 1 pairs
        assert "Q: Q1-1\nA: A1-1" in prompt
        assert "Q: Q1-2\nA: A1-2" in prompt
        assert "Q: Q1-3\nA: A1-3" in prompt

        # Round 2 pairs
        assert "Q: Q2-1\nA: A2-1" in prompt
        assert "Q: Q2-2\nA: A2-2" in prompt

    @patch("app.llm._get_client")
    def test_unanswered_questions_handling(self, mock_client):
        """Test handling of unanswered questions at the end."""
        # Mock API response
        mock_response = MagicMock()
        mock_response.text = "# 特許明細書"
        mock_client.return_value.models.generate_content.return_value = mock_response

        # Questions without corresponding answers
        transcript = [
            # Round 1
            {"role": "assistant", "content": "Q1"},
            {"role": "assistant", "content": "Q2"},
            {"role": "user", "content": "A1"},
            {"role": "user", "content": "A2"},
            # Round 2 (unanswered)
            {"role": "assistant", "content": "Q3"},
            {"role": "assistant", "content": "Q4"},
        ]

        regenerate_spec(
            instruction_md="指示書",
            idea_description="アイデア",
            transcript=transcript,
        )

        # Check the prompt
        call_args = mock_client.return_value.models.generate_content.call_args
        prompt = call_args[1]["contents"]

        # Answered questions
        assert "Q: Q1\nA: A1" in prompt
        assert "Q: Q2\nA: A2" in prompt

        # Unanswered questions
        assert "Q: Q3\nA: 未回答" in prompt
        assert "Q: Q4\nA: 未回答" in prompt

    @patch("app.llm._get_client")
    def test_improved_prompt_no_instruction_text(self, mock_client):
        """Test that improved prompt doesn't include instruction text verbatim."""
        # Mock API response
        mock_response = MagicMock()
        mock_response.text = "# 特許明細書"
        mock_client.return_value.models.generate_content.return_value = mock_response

        transcript = []

        regenerate_spec(
            instruction_md="指示書の内容",
            idea_description="アイデア",
            transcript=transcript,
        )

        # Check the prompt structure
        call_args = mock_client.return_value.models.generate_content.call_args
        prompt = call_args[1]["contents"]

        # Should have clear instructions not to include instruction text
        assert "指示書は作成の指針として参照し、指示書の文章そのものは出力に含めないこと" in prompt
        assert "指示書のタイトルや本文をそのまま含めないこと" in prompt

        # Should specify what sections to include
        assert "発明の名称" in prompt
        assert "技術分野" in prompt
        assert "背景技術" in prompt
        assert "発明が解決しようとする課題" in prompt

    @patch("app.llm.logger")
    @patch("app.llm._get_client")
    def test_qa_pairing_logging(self, mock_client, mock_logger):
        """Test that Q&A pairing is logged for debugging."""
        # Mock API response
        mock_response = MagicMock()
        mock_response.text = "# 特許明細書"
        mock_client.return_value.models.generate_content.return_value = mock_response

        transcript = [
            {"role": "assistant", "content": "Q1"},
            {"role": "assistant", "content": "Q2"},
            {"role": "user", "content": "A1"},
        ]

        regenerate_spec(
            instruction_md="指示書",
            idea_description="アイデア",
            transcript=transcript,
        )

        # Check that pairing was logged
        # With the new logic, answers are padded to match questions
        mock_logger.info.assert_any_call(
            "regenerate_spec: Q&A pairing - questions=%d, answers=%d, pairs=%d",
            2,  # 2 questions
            2,  # 2 answers (one is "未回答")
            2,  # 2 pairs
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
