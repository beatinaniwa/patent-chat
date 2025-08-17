"""Tests for hearing improvements: count display and default answer selection."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.state import Idea


class TestHearingCount:
    """Test cases for hearing count display."""

    def test_calculate_hearing_round(self):
        """Test that hearing round equals draft version."""
        idea = Idea(
            id="test",
            title="Test",
            category="test",
            description="test",
            draft_version=2,  # Second version
            messages=[
                {"role": "assistant", "content": "質問1？"},
                {"role": "user", "content": "はい"},
                {"role": "assistant", "content": "質問2？"},
                {"role": "user", "content": "いいえ"},
                {"role": "assistant", "content": "質問3？"},
            ],
        )

        # Hearing round should equal draft version
        hearing_round = idea.draft_version
        assert hearing_round == 2, "Should be 2nd hearing round for version 2"

    def test_hearing_round_with_no_messages(self):
        """Test hearing round when no messages exist."""
        idea = Idea(
            id="test",
            title="Test",
            category="test",
            description="test",
            draft_version=1,  # First version
            messages=[],
        )

        hearing_round = idea.draft_version
        assert hearing_round == 1, "Should be 1st hearing round"

    def test_hearing_round_with_only_assistant_messages(self):
        """Test hearing round when only assistant messages exist."""
        idea = Idea(
            id="test",
            title="Test",
            category="test",
            description="test",
            draft_version=1,  # First version
            messages=[
                {"role": "assistant", "content": "質問1？"},
                {"role": "assistant", "content": "質問2？"},
            ],
        )

        hearing_round = idea.draft_version
        assert hearing_round == 1, "Should be 1st hearing round"

    @patch("app.main.st")
    def test_hearing_count_displayed_in_ui(self, mock_st):
        """Test that hearing count is displayed in the UI."""
        from app.main import _render_hearing_section

        idea = Idea(
            id="test",
            title="Test",
            category="test",
            description="test",
            draft_spec_markdown="draft",
            draft_version=3,  # Third version
            messages=[
                {"role": "assistant", "content": "質問1？"},
                {"role": "user", "content": "はい"},
                {"role": "assistant", "content": "質問2？"},
                {"role": "user", "content": "いいえ"},
                {"role": "assistant", "content": "質問3？"},
            ],
        )

        # Mock form context manager
        mock_form = MagicMock()
        mock_form.__enter__ = MagicMock(return_value=mock_form)
        mock_form.__exit__ = MagicMock(return_value=None)
        mock_st.form.return_value = mock_form
        mock_st.form_submit_button.return_value = False

        _render_hearing_section(idea, "manual_md", show_questions_first=False)

        # Check if hearing round is displayed in subheader
        subheader_calls = [str(call) for call in mock_st.subheader.call_args_list]
        # Should display "AI ヒアリング（第3回）" or similar
        assert any(
            "第3回" in call for call in subheader_calls
        ), "Hearing count should be displayed as '第3回'"


class TestQAHistoryFormat:
    """Test cases for Q&A history display format."""

    @patch("app.main.st")
    def test_qa_history_format(self, mock_st):
        """Test that Q&A history is displayed in correct format."""
        from app.main import _render_hearing_section

        idea = Idea(
            id="test",
            title="Test",
            category="test",
            description="test",
            draft_spec_markdown="draft",
            draft_version=2,
            messages=[
                {"role": "assistant", "content": "質問1ですか？"},
                {"role": "user", "content": "はい"},
                {"role": "assistant", "content": "質問2ですか？"},
                {"role": "user", "content": "いいえ"},
                {"role": "assistant", "content": "質問3ですか？"},  # Unanswered
            ],
        )

        # Mock form context manager
        mock_form = MagicMock()
        mock_form.__enter__ = MagicMock(return_value=mock_form)
        mock_form.__exit__ = MagicMock(return_value=None)
        mock_st.form.return_value = mock_form
        mock_st.form_submit_button.return_value = False

        _render_hearing_section(idea, "manual_md", show_questions_first=False)

        # Check markdown calls for Q&A history
        markdown_calls = [str(call) for call in mock_st.markdown.call_args_list]

        # Should show question and answer on same line without "AI:" or "ユーザー:"
        assert any(
            "質問1ですか？: はい" in call for call in markdown_calls
        ), "Q&A should be displayed as 'Question: Answer' format"
        assert any(
            "質問2ですか？: いいえ" in call for call in markdown_calls
        ), "Q&A should be displayed as 'Question: Answer' format"

        # Should not have "AI:" or "ユーザー:" prefixes
        assert not any(
            "AI:" in call or "ユーザー:" in call for call in markdown_calls
        ), "Should not display 'AI:' or 'ユーザー:' prefixes"


class TestDefaultAnswerSelection:
    """Test cases for default answer selection in radio buttons."""

    @patch("app.main.st")
    def test_default_answer_is_wakaranai(self, mock_st):
        """Test that default answer is always 'わからない' (index=2)."""
        from app.main import _render_pending_questions

        idea = Idea(
            id="test",
            title="Test",
            category="test",
            description="test",
            messages=[],
        )

        pending_questions = ["質問1？", "質問2？", "質問3？"]

        # Mock form context manager
        mock_form = MagicMock()
        mock_form.__enter__ = MagicMock(return_value=mock_form)
        mock_form.__exit__ = MagicMock(return_value=None)
        mock_st.form.return_value = mock_form
        mock_st.form_submit_button.return_value = False

        _render_pending_questions(idea, pending_questions, "manual_md")

        # Check all radio button calls
        radio_calls = mock_st.radio.call_args_list
        assert len(radio_calls) == 3, "Should have 3 radio buttons"

        for call in radio_calls:
            # Check that index=2 (わからない) is used
            assert call.kwargs.get("index") == 2, "Default should be 'わからない' (index=2)"

    @patch("app.main.st")
    def test_unique_keys_for_radio_buttons(self, mock_st):
        """Test that each radio button has a unique key to prevent state persistence."""
        from app.main import _render_pending_questions

        idea = Idea(
            id="test-id",
            title="Test",
            category="test",
            description="test",
            messages=[],
        )

        pending_questions = ["質問1？", "質問2？"]

        # Mock form context manager
        mock_form = MagicMock()
        mock_form.__enter__ = MagicMock(return_value=mock_form)
        mock_form.__exit__ = MagicMock(return_value=None)
        mock_st.form.return_value = mock_form
        mock_st.form_submit_button.return_value = False

        _render_pending_questions(idea, pending_questions, "manual_md")

        # Check that keys are unique
        radio_calls = mock_st.radio.call_args_list
        keys = [call.kwargs.get("key") for call in radio_calls]

        assert len(keys) == len(set(keys)), "All radio button keys should be unique"
        # Keys should include idea ID and version for uniqueness
        assert all(
            "ans-test-id-v" in key for key in keys
        ), "Keys should include idea ID and version"

    @patch("app.main.st")
    def test_radio_buttons_reset_between_rounds(self, mock_st):
        """Test that radio buttons don't retain previous selections."""
        from app.main import _render_pending_questions

        idea = Idea(
            id="test",
            title="Test",
            category="test",
            description="test",
            draft_version=2,  # Simulate second version
            messages=[
                {"role": "assistant", "content": "前の質問1？"},
                {"role": "user", "content": "はい"},  # Previous answer
                {"role": "assistant", "content": "前の質問2？"},
                {"role": "user", "content": "いいえ"},  # Previous answer
            ],
        )

        # New questions
        pending_questions = ["新しい質問1？", "新しい質問2？"]

        # Mock form context manager
        mock_form = MagicMock()
        mock_form.__enter__ = MagicMock(return_value=mock_form)
        mock_form.__exit__ = MagicMock(return_value=None)
        mock_st.form.return_value = mock_form
        mock_st.form_submit_button.return_value = False

        _render_pending_questions(idea, pending_questions, "manual_md")

        # Check that all new radio buttons have index=2 (わからない)
        radio_calls = mock_st.radio.call_args_list
        for call in radio_calls:
            assert call.kwargs.get("index") == 2, "New questions should default to 'わからない'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
