"""Tests for Q&A history collapsed display."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.state import Idea


class TestQAHistoryCollapsed:
    """Test cases for Q&A history collapsed display functionality."""

    @patch("app.main.st")
    def test_qa_history_in_expander_for_version_2_plus(self, mock_st):
        """バージョン2以降でQ&A履歴がexpanderで折りたたまれることを確認."""
        from app.main import _render_hearing_section

        # Arrange: Version 2 with answered questions
        idea = Idea(
            id="test-1",
            title="Test Idea",
            category="防災",
            description="Test description",
            draft_spec_markdown="# 第2版ドラフト",
            draft_version=2,
            messages=[
                {"role": "assistant", "content": "質問1？（はい/いいえ）"},
                {"role": "assistant", "content": "質問2？（はい/いいえ）"},
                {"role": "user", "content": "はい"},
                {"role": "user", "content": "いいえ"},
                {"role": "assistant", "content": "新質問1？（はい/いいえ）"},
                {"role": "assistant", "content": "新質問2？（はい/いいえ）"},
            ],
        )

        # Mock expander
        mock_expander = MagicMock()
        mock_expander.__enter__ = MagicMock(return_value=mock_expander)
        mock_expander.__exit__ = MagicMock(return_value=None)
        mock_st.expander.return_value = mock_expander

        # Act
        _render_hearing_section(idea, "instruction", show_questions_first=True)

        # Assert
        # Check that expander was called for Q&A history
        expander_calls = [call for call in mock_st.expander.call_args_list]
        assert any(
            "これまでの質問と回答" in str(call) or "Q&A履歴" in str(call) for call in expander_calls
        ), "Q&A履歴がexpanderで表示されていない"

    @patch("app.main.st")
    def test_pending_questions_not_in_expander(self, mock_st):
        """未回答の質問はexpanderに入らず直接表示されることを確認."""
        from app.main import _render_hearing_section

        # Arrange: Pending questions
        idea = Idea(
            id="test-2",
            title="Test Idea",
            category="防災",
            description="Test description",
            draft_spec_markdown="# ドラフト",
            draft_version=2,
            messages=[
                {"role": "assistant", "content": "回答済み質問？（はい/いいえ）"},
                {"role": "user", "content": "はい"},
                {"role": "assistant", "content": "未回答質問1？（はい/いいえ）"},
                {"role": "assistant", "content": "未回答質問2？（はい/いいえ）"},
            ],
        )

        # Mock form for pending questions
        mock_form = MagicMock()
        mock_st.form.return_value.__enter__.return_value = mock_form

        # Act
        _render_hearing_section(idea, "instruction", show_questions_first=True)

        # Assert
        # Pending questions should be in a form, not in expander
        mock_st.form.assert_called()
        form_calls = mock_st.form.call_args_list
        assert any("qa-form" in str(call) for call in form_calls)

    @patch("app.main.st")
    def test_qa_history_content_displayed_correctly(self, mock_st):
        """Q&A履歴の内容が正しく表示されることを確認."""
        from app.main import _render_hearing_section

        # Arrange
        idea = Idea(
            id="test-3",
            title="Test Idea",
            category="防災",
            description="Test description",
            draft_spec_markdown="# ドラフト",
            draft_version=3,
            messages=[
                {
                    "role": "assistant",
                    "content": "承知しました。確認させていただきます。質問1？（はい/いいえ）",
                },
                {"role": "assistant", "content": "質問2？（はい/いいえ）"},
                {"role": "assistant", "content": "質問3？（はい/いいえ）"},
                {"role": "user", "content": "はい"},
                {"role": "user", "content": "いいえ"},
                {"role": "user", "content": "わからない"},
            ],
        )

        # Mock expander
        mock_expander = MagicMock()
        mock_expander.__enter__ = MagicMock(return_value=mock_expander)
        mock_expander.__exit__ = MagicMock(return_value=None)
        mock_st.expander.return_value = mock_expander

        # Act
        _render_hearing_section(idea, "instruction", show_questions_first=True)

        # Assert
        # Check that cleaned questions and answers are displayed
        markdown_calls = [call for call in mock_st.markdown.call_args_list]

        # Should display Q&A pairs (cleaned questions without intro)
        displayed_content = " ".join(str(call) for call in markdown_calls)
        assert "質問1" in displayed_content
        assert "はい" in displayed_content
        assert "いいえ" in displayed_content
        assert "わからない" in displayed_content
        # Intro phrases should be cleaned
        assert (
            "承知しました" not in displayed_content
            or "確認させていただきます" not in displayed_content
        )

    @patch("app.main.st")
    def test_version_1_no_expander_for_history(self, mock_st):
        """バージョン1ではQ&A履歴にexpanderを使わないことを確認."""
        from app.main import _render_hearing_section

        # Arrange: Version 1
        idea = Idea(
            id="test-4",
            title="Test Idea",
            category="防災",
            description="Test description",
            draft_spec_markdown="# 第1版ドラフト",
            draft_version=1,
            messages=[
                {"role": "assistant", "content": "質問1？（はい/いいえ）"},
            ],
        )

        # Act
        _render_hearing_section(idea, "instruction", show_questions_first=False)

        # Assert
        # Version 1 should not use expander for Q&A history
        expander_calls = mock_st.expander.call_args_list
        assert not any(
            "これまでの質問と回答" in str(call) or "Q&A履歴" in str(call) for call in expander_calls
        ), "バージョン1でQ&A履歴がexpanderで表示されている"

    @patch("app.main.st")
    def test_empty_qa_history_not_shown(self, mock_st):
        """Q&A履歴が空の場合はexpanderを表示しないことを確認."""
        from app.main import _render_hearing_section

        # Arrange: No answered questions yet
        idea = Idea(
            id="test-5",
            title="Test Idea",
            category="防災",
            description="Test description",
            draft_spec_markdown="# ドラフト",
            draft_version=2,
            messages=[
                {"role": "assistant", "content": "未回答質問？（はい/いいえ）"},
            ],
        )

        # Act
        _render_hearing_section(idea, "instruction", show_questions_first=True)

        # Assert
        # Should not create expander for empty history
        expander_calls = mock_st.expander.call_args_list
        assert not any(
            "これまでの質問と回答" in str(call) or "Q&A履歴" in str(call) for call in expander_calls
        ), "空のQ&A履歴でexpanderが作成されている"

    @patch("app.main.st")
    def test_qa_pairs_displayed_on_same_line(self, mock_st):
        """質問と回答が同じ行に表示されることを確認."""
        from app.main import _render_hearing_section

        # Arrange
        idea = Idea(
            id="test-6",
            title="Test Idea",
            category="防災",
            description="Test description",
            draft_spec_markdown="# ドラフト",
            draft_version=2,
            messages=[
                {"role": "assistant", "content": "防災用ですか？（はい/いいえ）"},
                {"role": "user", "content": "はい"},
                {"role": "assistant", "content": "既存技術の改良ですか？（はい/いいえ）"},
                {"role": "user", "content": "いいえ"},
            ],
        )

        # Mock expander
        mock_expander = MagicMock()
        mock_expander.__enter__ = MagicMock(return_value=mock_expander)
        mock_expander.__exit__ = MagicMock(return_value=None)
        mock_st.expander.return_value = mock_expander

        # Act
        _render_hearing_section(idea, "instruction", show_questions_first=True)

        # Assert
        markdown_calls = [str(call) for call in mock_st.markdown.call_args_list]

        # Check for Q: A format on same line
        qa_format_found = any(
            ("防災用ですか" in call and "はい" in call)
            or ("既存技術の改良ですか" in call and "いいえ" in call)
            for call in markdown_calls
        )
        assert qa_format_found, "Q&Aが同じ行に表示されていない"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
