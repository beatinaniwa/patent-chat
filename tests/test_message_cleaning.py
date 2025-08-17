"""Tests for AI message cleaning functions."""

import sys
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestMessageCleaning:
    """Test AI message cleaning functionality."""

    def test_clean_ai_message_removes_common_intros(self):
        """一般的な導入部分が除外されることを確認."""
        from app.main import _clean_ai_message

        # Test cases with various intro patterns
        test_cases = [
            (
                "承知いたしました。それでは質問させていただきます。\nこの発明は防災用ですか？",
                "この発明は防災用ですか？",
            ),
            (
                "了解しました。確認させてください。\n既存技術の改良ですか？",
                "既存技術の改良ですか？",
            ),
            (
                "わかりました。次の点について教えてください。\n図面は必要ですか？",
                "図面は必要ですか？",
            ),
            (
                "ありがとうございます。追加で確認です。\n実施例は複数ありますか？",
                "実施例は複数ありますか？",
            ),
            (
                "確認させていただきます。\n定量的な効果はありますか？",
                "定量的な効果はありますか？",
            ),
            (
                "それでは、以下の点を確認させてください。\n緊急時に使用されますか？",
                "緊急時に使用されますか？",
            ),
        ]

        for input_text, expected in test_cases:
            result = _clean_ai_message(input_text)
            assert result == expected, f"Failed for input: {input_text}"

    def test_clean_ai_message_preserves_questions_without_intro(self):
        """導入部分がない質問はそのまま保持されることを確認."""
        from app.main import _clean_ai_message

        test_cases = [
            "この発明は防災用ですか？（はい/いいえ）",
            "既存技術を改良したものですか？",
            "図面の添付は必要ですか？",
            "実施例は複数のバリエーションがありますか？",
            "発明の効果に定量的根拠はありますか？",
        ]

        for text in test_cases:
            result = _clean_ai_message(text)
            assert result == text, f"Text was modified unexpectedly: {text}"

    def test_clean_ai_message_handles_multiline_questions(self):
        """複数行の質問で導入部分のみ除外されることを確認."""
        from app.main import _clean_ai_message

        input_text = """承知いたしました。以下について確認させてください。

1. この発明は防災用ですか？
2. 既存技術の改良ですか？
3. 図面は必要ですか？"""

        expected = """1. この発明は防災用ですか？
2. 既存技術の改良ですか？
3. 図面は必要ですか？"""

        result = _clean_ai_message(input_text)
        assert result == expected

    def test_clean_ai_message_handles_empty_and_none(self):
        """空文字列やNoneが適切に処理されることを確認."""
        from app.main import _clean_ai_message

        assert _clean_ai_message("") == ""
        assert _clean_ai_message("   ") == ""
        assert _clean_ai_message(None) == ""

    def test_clean_ai_message_removes_multiple_intro_patterns(self):
        """複数の導入パターンが混在する場合も除外されることを確認."""
        from app.main import _clean_ai_message

        input_text = (
            "承知いたしました。ありがとうございます。"
            "それでは確認させてください。この技術は新規性がありますか？"
        )
        expected = "この技術は新規性がありますか？"

        result = _clean_ai_message(input_text)
        assert result == expected


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
