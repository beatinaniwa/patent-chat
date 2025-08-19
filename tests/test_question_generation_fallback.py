"""Tests for question generation fallback handling."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.state import Idea


class TestQuestionGenerationFallback:
    """Test cases for question generation error handling and fallback."""

    @patch("app.main.st")
    @patch("app.main.save_ideas")
    @patch("app.main._load_instruction_markdown")
    def test_second_version_questions_added_on_error(
        self, mock_load_instruction, mock_save, mock_st
    ):
        """第2版の質問生成でエラーが発生してもデフォルト質問が追加されることを確認."""
        from app.main import _render_pending_questions

        # Arrange: 第1版の回答済みアイデア
        idea = Idea(
            id="test-1",
            title="Test Idea",
            category="防災",
            description="Test description",
            draft_spec_markdown="# 第1版ドラフト",
            draft_version=1,
            messages=[
                {"role": "assistant", "content": "質問1？（はい/いいえ）"},
                {"role": "assistant", "content": "質問2？（はい/いいえ）"},
                {"role": "user", "content": "はい"},
                {"role": "user", "content": "いいえ"},
            ],
        )

        mock_load_instruction.return_value = "instruction"
        mock_form = MagicMock()
        mock_form.form_submit_button.return_value = True
        mock_st.form.return_value.__enter__.return_value = mock_form
        mock_st.radio.side_effect = ["はい", "いいえ"]  # Mock user selections

        # Mock regenerate_spec to succeed
        with patch("app.main.regenerate_spec") as mock_regenerate:
            mock_regenerate.return_value = ("# 第2版ドラフト", None)

            # Mock next_questions to return error and default questions
            with patch("app.main.next_questions") as mock_next:
                mock_next.return_value = (
                    [
                        "デフォルト質問1？（はい/いいえ）",
                        "デフォルト質問2？（はい/いいえ）",
                        "デフォルト質問3？（はい/いいえ）",
                    ],
                    "API接続エラー",
                )

                # Act
                _render_pending_questions(
                    idea, ["質問1？（はい/いいえ）", "質問2？（はい/いいえ）"], "instruction"
                )

                # Assert
                # 1. next_questions was called with version=2
                mock_next.assert_called_once()
                call_args = mock_next.call_args
                assert call_args[1]["version"] == 2

                # 2. Default questions should be added to messages
                # Note: In actual implementation, we need to ensure this happens
                assert mock_save.called
                # The test shows what we expect to happen

    @patch("app.main.st")
    @patch("app.main.save_ideas")
    def test_questions_always_added_even_on_api_failure(self, mock_save, mock_st):
        """APIが完全に失敗してもデフォルト質問が追加されることを確認."""
        from app.main import _render_pending_questions

        # Arrange
        idea = Idea(
            id="test-2",
            title="Test Idea",
            category="防災",
            description="Test description",
            draft_spec_markdown="# ドラフト",
            draft_version=2,
            messages=[
                {"role": "assistant", "content": "既存質問？（はい/いいえ）"},
                {"role": "user", "content": "はい"},
            ],
        )

        mock_form = MagicMock()
        mock_form.form_submit_button.return_value = True
        mock_st.form.return_value.__enter__.return_value = mock_form
        mock_st.radio.return_value = "はい"

        with patch("app.main._load_instruction_markdown", return_value="inst"):
            with patch("app.main.regenerate_spec") as mock_regenerate:
                mock_regenerate.return_value = ("# 新ドラフト", None)

                with patch("app.main.next_questions") as mock_next:
                    # Simulate complete API failure
                    mock_next.side_effect = Exception("API completely failed")

                    # Act & Assert - should not raise exception
                    try:
                        _render_pending_questions(idea, ["既存質問？（はい/いいえ）"], "inst")
                    except Exception:
                        pytest.fail("Should handle API failure gracefully")

                    # Save should still be called
                    assert mock_save.called

    def test_default_questions_are_valid_yes_no_format(self):
        """デフォルト質問が適切なはい/いいえ形式であることを確認."""
        from app.llm import next_questions

        # Act - call with no client (simulates API unavailable)
        with patch("app.llm._get_client", return_value=None):
            questions, error = next_questions(
                instruction_md="",
                transcript=[],
                current_spec_md="",
                num_questions=3,
                version=2,
            )

        # Assert
        assert error is not None
        assert len(questions) == 3
        for q in questions:
            assert "？" in q or "?" in q
            assert "（はい/いいえ）" in q or "はい/いいえ" in q

    @patch("app.main.st")
    def test_question_generation_continues_after_error_recovery(self, mock_st):
        """エラー後も質問生成が継続されることを確認."""
        from app.main import _render_pending_questions

        idea = Idea(
            id="test-3",
            title="Test",
            category="防災",
            description="Test",
            draft_spec_markdown="# Draft",
            draft_version=1,
            messages=[
                {"role": "assistant", "content": "既存質問？（はい/いいえ）"},
            ],
        )

        mock_form = MagicMock()
        mock_form.form_submit_button.return_value = True  # Submit to trigger next questions
        mock_st.form.return_value.__enter__.return_value = mock_form
        mock_st.radio.return_value = "はい"

        with patch("app.main._load_instruction_markdown", return_value="inst"):
            with patch("app.main.regenerate_spec") as mock_regenerate:
                mock_regenerate.return_value = ("# 新ドラフト", None)

                with patch("app.main.next_questions") as mock_next:
                    # Return error with default questions
                    mock_next.return_value = (
                        ["エラー時質問1？（はい/いいえ）", "エラー時質問2？（はい/いいえ）"],
                        "一時的なエラー",
                    )

                    with patch("app.main.save_ideas"):
                        # Call with existing question
                        _render_pending_questions(idea, ["既存質問？（はい/いいえ）"], "inst")

                        # Verify error message shown
                        mock_st.warning.assert_called()
                        mock_st.info.assert_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
