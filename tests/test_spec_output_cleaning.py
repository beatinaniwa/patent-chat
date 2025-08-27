import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestSpecOutputCleaning:
    @patch("app.llm._get_client")
    def test_bootstrap_spec_removes_intro_phrases(self, mock_client):
        from app.llm import bootstrap_spec

        # Mock API response that includes polite intro
        mock_response = MagicMock()
        mock_response.text = (
            "はい、承知いたしました。以下にドラフトを示します。\n# 特許明細書\n本文..."
        )
        mock_client.return_value.models.generate_content.return_value = mock_response

        text, err = bootstrap_spec(sample_manual_md="指示", idea_description="アイデア")

        assert err is None
        assert text.startswith("# 特許明細書"), "前置きが除去されていません"
        assert "承知" not in text.splitlines()[0], "前置き語が残っています"

    @patch("app.llm._get_client")
    def test_regenerate_spec_removes_intro_phrases(self, mock_client):
        from app.llm import regenerate_spec

        # Mock API response that includes polite intro
        mock_response = MagicMock()
        mock_response.text = (
            "了解しました。では完全版を作成します。\n# 特許明細書\n\n## 発明の名称\n..."
        )
        mock_client.return_value.models.generate_content.return_value = mock_response

        text, err = regenerate_spec(
            instruction_md="指示", idea_description="アイデア", transcript=[]
        )

        assert err is None
        assert text.lstrip().startswith("# 特許明細書"), "前置きが除去されていません"
        assert "了解" not in text.splitlines()[0], "前置き語が残っています"
