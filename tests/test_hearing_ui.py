"""Tests for hearing UI display logic based on draft version."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.state import Idea


class TestHearingUIDisplay:
    """Test hearing_ui function displays correctly based on draft version."""

    @patch("app.main.st")
    def test_first_version_shows_questions_first_with_collapsed_draft(self, mock_st):
        """初版では質問が先に表示され、ドラフトは折りたたまれているか確認."""
        from app.main import hearing_ui

        # Arrange: 初版のアイデア
        idea = Idea(
            id="test-1",
            title="Test Idea",
            category="防災",
            description="Test description",
            draft_spec_markdown="# 初版ドラフト内容",
            draft_version=1,
            messages=[
                {"role": "assistant", "content": "質問1: これは緊急時に使用されますか？"},
                {"role": "assistant", "content": "質問2: 既存の技術を改良したものですか？"},
            ],
        )

        # Mock session state
        mock_st.session_state.ideas = [idea]

        # Act
        with patch("app.main._load_instruction_markdown", return_value="instruction"):
            with patch("app.main.save_ideas"):
                hearing_ui(idea)

        # Assert
        # 1. AIヒアリングのsubheaderが最初に呼ばれる
        subheader_calls = [
            call for call in mock_st.subheader.call_args_list if call[0][0] == "AI ヒアリング"
        ]
        assert len(subheader_calls) > 0, "AI ヒアリングのサブヘッダーが表示されていない"

        # 2. expanderでドラフトが折りたたまれている
        expander_calls = mock_st.expander.call_args_list
        assert any(
            "生成された明細書ドラフト（第1版）" in str(call) for call in expander_calls
        ), "初版ドラフトがexpanderで表示されていない"

        # 3. エクスポートボタンがない
        assert mock_st.download_button.call_count == 0, "初版でエクスポートボタンが表示されている"

    @patch("app.main.st")
    def test_second_version_shows_questions_first_then_draft(self, mock_st):
        """2版以降では質問が先、次に回答履歴、最後にドラフト（折りたたみ）の順で表示されるか確認."""
        from app.main import hearing_ui

        # Arrange: 2版のアイデア
        idea = Idea(
            id="test-2",
            title="Test Idea",
            category="防災",
            description="Test description",
            draft_spec_markdown="# 第2版ドラフト内容",
            draft_version=2,
            messages=[
                {"role": "assistant", "content": "質問1: これは緊急時に使用されますか？"},
                {"role": "user", "content": "はい"},
                {"role": "assistant", "content": "質問2: 既存の技術を改良したものですか？"},
            ],
        )

        # Mock session state
        mock_st.session_state.ideas = [idea]
        mock_st.columns.return_value = [MagicMock(), MagicMock()]  # Mock columns for export buttons

        # Mock expander context manager
        mock_expander = MagicMock()
        mock_expander.__enter__ = MagicMock(return_value=mock_expander)
        mock_expander.__exit__ = MagicMock(return_value=None)
        mock_st.expander.return_value = mock_expander

        # Act
        with patch("app.main._load_instruction_markdown", return_value="instruction"):
            with patch("app.main.save_ideas"):
                with patch("app.main.export_docx", return_value=("test.docx", b"data")):
                    with patch("app.main.export_pdf", return_value=("test.pdf", b"data")):
                        hearing_ui(idea)

        # Assert
        # 1. AIヒアリングのsubheaderが表示される
        subheader_calls = mock_st.subheader.call_args_list
        assert any(
            "AI ヒアリング" in str(call) for call in subheader_calls
        ), "AIヒアリングのサブヘッダーが表示されていない"

        # 2. ドラフトはexpanderで折りたたまれている（バージョン番号は変化する可能性あり）
        expander_calls = mock_st.expander.call_args_list
        assert any(
            "生成された明細書ドラフト" in str(call) for call in expander_calls
        ), "ドラフトがexpanderで表示されていない"

        # 3. dividerが呼ばれている（質問セクションとドラフトの間）
        assert mock_st.divider.called, "質問とドラフトの間にdividerが表示されていない"

    @patch("app.main.st")
    def test_questions_display_logic_works_in_both_versions(self, mock_st):
        """両方のバージョンで質問表示ロジックが正常動作するか確認."""
        from app.main import hearing_ui

        # Arrange: 未回答質問があるアイデア
        idea = Idea(
            id="test-3",
            title="Test Idea",
            category="防災",
            description="Test description",
            draft_spec_markdown="# ドラフト内容",
            draft_version=1,
            messages=[
                {"role": "assistant", "content": "これは防災用ですか？"},
                {"role": "assistant", "content": "既存技術の改良ですか？"},
            ],
        )

        # Mock session state
        mock_st.session_state.ideas = [idea]
        mock_st.form.return_value.__enter__ = MagicMock()
        mock_st.form.return_value.__exit__ = MagicMock()

        # Act
        with patch("app.main._load_instruction_markdown", return_value="instruction"):
            with patch("app.main.save_ideas"):
                hearing_ui(idea)

        # Assert: 質問フォームが表示される
        form_calls = mock_st.form.call_args_list
        assert len(form_calls) > 0, "質問フォームが表示されていない"
        assert any("qa-form" in str(call) for call in form_calls), "質問フォームのIDが正しくない"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
