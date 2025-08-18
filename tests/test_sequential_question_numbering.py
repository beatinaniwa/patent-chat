"""Tests for sequential question numbering across versions."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.state import Idea


class TestSequentialQuestionNumbering:
    """Test cases for sequential question numbering (1-5, 6-10, 11-15, etc.)."""

    @patch("app.main.st")
    def test_first_version_questions_numbered_1_to_5(self, mock_st):
        """第1版の質問が1〜5番で表示されることを確認."""
        from app.main import _render_pending_questions

        # Arrange: Version 1 with 5 questions
        idea = Idea(
            id="test-1",
            title="Test Idea",
            category="防災",
            description="Test description",
            draft_spec_markdown="# ドラフト",
            draft_version=1,
            messages=[
                {"role": "assistant", "content": "質問1？（はい/いいえ）"},
                {"role": "assistant", "content": "質問2？（はい/いいえ）"},
                {"role": "assistant", "content": "質問3？（はい/いいえ）"},
                {"role": "assistant", "content": "質問4？（はい/いいえ）"},
                {"role": "assistant", "content": "質問5？（はい/いいえ）"},
            ],
        )

        # Mock form
        mock_form = MagicMock()
        mock_form.form_submit_button.return_value = False
        mock_st.form.return_value.__enter__.return_value = mock_form

        # Act
        questions = ["質問1？（はい/いいえ）", "質問2？（はい/いいえ）", "質問3？（はい/いいえ）"]
        _render_pending_questions(idea, questions, "instruction")

        # Assert: Check that Q1, Q2, Q3 are displayed
        markdown_calls = [str(call) for call in mock_st.markdown.call_args_list]
        assert any("Q1:" in call for call in markdown_calls), "Q1 should be displayed"
        assert any("Q2:" in call for call in markdown_calls), "Q2 should be displayed"
        assert any("Q3:" in call for call in markdown_calls), "Q3 should be displayed"

    @patch("app.main.st")
    def test_second_version_questions_numbered_6_to_10(self, mock_st):
        """第2版の質問が6〜10番で表示されることを確認."""
        from app.main import _render_pending_questions

        # Arrange: Version 2 with new questions after 5 answered ones
        idea = Idea(
            id="test-2",
            title="Test Idea",
            category="防災",
            description="Test description",
            draft_spec_markdown="# ドラフト",
            draft_version=2,
            messages=[
                # First 5 questions (answered)
                {"role": "assistant", "content": "質問1？（はい/いいえ）"},
                {"role": "assistant", "content": "質問2？（はい/いいえ）"},
                {"role": "assistant", "content": "質問3？（はい/いいえ）"},
                {"role": "assistant", "content": "質問4？（はい/いいえ）"},
                {"role": "assistant", "content": "質問5？（はい/いいえ）"},
                {"role": "user", "content": "はい"},
                {"role": "user", "content": "いいえ"},
                {"role": "user", "content": "はい"},
                {"role": "user", "content": "いいえ"},
                {"role": "user", "content": "わからない"},
                # Second 5 questions (pending)
                {"role": "assistant", "content": "質問6？（はい/いいえ）"},
                {"role": "assistant", "content": "質問7？（はい/いいえ）"},
                {"role": "assistant", "content": "質問8？（はい/いいえ）"},
            ],
        )

        # Mock form
        mock_form = MagicMock()
        mock_form.form_submit_button.return_value = False
        mock_st.form.return_value.__enter__.return_value = mock_form

        # Act
        _render_pending_questions(
            idea,
            ["質問6？（はい/いいえ）", "質問7？（はい/いいえ）", "質問8？（はい/いいえ）"],
            "instruction",
        )

        # Assert: Check that Q6, Q7, Q8 are displayed (not Q1, Q2, Q3)
        markdown_calls = [str(call) for call in mock_st.markdown.call_args_list]
        assert any("Q6:" in call for call in markdown_calls), "Q6 should be displayed"
        assert any("Q7:" in call for call in markdown_calls), "Q7 should be displayed"
        assert any("Q8:" in call for call in markdown_calls), "Q8 should be displayed"
        assert not any("Q1:" in call for call in markdown_calls), "Q1 should NOT be displayed"
        assert not any("Q2:" in call for call in markdown_calls), "Q2 should NOT be displayed"

    @patch("app.main.st")
    def test_third_version_questions_numbered_11_to_15(self, mock_st):
        """第3版の質問が11〜15番で表示されることを確認."""
        from app.main import _render_pending_questions

        # Arrange: Version 3 with questions after 10 answered ones
        idea = Idea(
            id="test-3",
            title="Test Idea",
            category="防災",
            description="Test description",
            draft_spec_markdown="# ドラフト",
            draft_version=3,
            messages=[
                # Previous messages (10 questions, 10 answers)
                *[{"role": "assistant", "content": f"質問{i}？"} for i in range(1, 11)],
                *[{"role": "user", "content": "はい"} for _ in range(10)],
                # Third round questions
                {"role": "assistant", "content": "質問11？（はい/いいえ）"},
                {"role": "assistant", "content": "質問12？（はい/いいえ）"},
            ],
        )

        # Mock form
        mock_form = MagicMock()
        mock_form.form_submit_button.return_value = False
        mock_st.form.return_value.__enter__.return_value = mock_form

        # Act
        _render_pending_questions(
            idea, ["質問11？（はい/いいえ）", "質問12？（はい/いいえ）"], "instruction"
        )

        # Assert: Check that Q11, Q12 are displayed
        markdown_calls = [str(call) for call in mock_st.markdown.call_args_list]
        assert any("Q11:" in call for call in markdown_calls), "Q11 should be displayed"
        assert any("Q12:" in call for call in markdown_calls), "Q12 should be displayed"

    @patch("app.main.st")
    def test_question_numbering_with_variable_question_counts(self, mock_st):
        """各版で質問数が異なる場合でも正しく番号付けされることを確認."""
        from app.main import _render_pending_questions

        # Arrange: Version 2 with only 3 questions in first round and 2 in second
        idea = Idea(
            id="test-4",
            title="Test Idea",
            category="防災",
            description="Test description",
            draft_spec_markdown="# ドラフト",
            draft_version=2,
            messages=[
                # First round: 3 questions
                {"role": "assistant", "content": "質問1？"},
                {"role": "assistant", "content": "質問2？"},
                {"role": "assistant", "content": "質問3？"},
                {"role": "user", "content": "はい"},
                {"role": "user", "content": "いいえ"},
                {"role": "user", "content": "わからない"},
                # Second round: 2 questions
                {"role": "assistant", "content": "質問4？"},
                {"role": "assistant", "content": "質問5？"},
            ],
        )

        # Mock form
        mock_form = MagicMock()
        mock_form.form_submit_button.return_value = False
        mock_st.form.return_value.__enter__.return_value = mock_form

        # Act
        _render_pending_questions(idea, ["質問4？", "質問5？"], "instruction")

        # Assert: Should count actual questions, not assume 5 per round
        markdown_calls = [str(call) for call in mock_st.markdown.call_args_list]
        # With actual counting: 3 questions answered, so next should be Q4, Q5
        assert any("Q4:" in call for call in markdown_calls), "Q4 should be displayed"
        assert any("Q5:" in call for call in markdown_calls), "Q5 should be displayed"

    def test_calculate_question_start_number(self):
        """質問開始番号の計算ロジックをテスト."""
        from app.main import _calculate_question_start_number

        # Test cases
        idea1 = Idea(
            id="test",
            title="Test",
            category="防災",
            description="Test",
            draft_version=1,
            messages=[],
        )
        assert _calculate_question_start_number(idea1) == 1

        idea2 = Idea(
            id="test",
            title="Test",
            category="防災",
            description="Test",
            draft_version=2,
            messages=[
                {"role": "assistant", "content": "Q1？"},
                {"role": "assistant", "content": "Q2？"},
                {"role": "assistant", "content": "Q3？"},
                {"role": "assistant", "content": "Q4？"},
                {"role": "assistant", "content": "Q5？"},
                {"role": "user", "content": "A1"},
                {"role": "user", "content": "A2"},
                {"role": "user", "content": "A3"},
                {"role": "user", "content": "A4"},
                {"role": "user", "content": "A5"},
            ],
        )
        assert _calculate_question_start_number(idea2) == 6

        idea3 = Idea(
            id="test",
            title="Test",
            category="防災",
            description="Test",
            draft_version=3,
            messages=[
                # 10 questions and answers
                *[{"role": "assistant", "content": f"Q{i}？"} for i in range(1, 11)],
                *[{"role": "user", "content": f"A{i}"} for i in range(1, 11)],
            ],
        )
        assert _calculate_question_start_number(idea3) == 11


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
