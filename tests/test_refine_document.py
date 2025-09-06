import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestRefineDocument:
    @patch("app.llm._get_client")
    def test_refine_document_prompt_contains_body_only_instruction(self, mock_client):
        from app.llm import refine_document

        # Mock API response
        mock_response = MagicMock()
        mock_response.text = "# 修正後"
        mock_client.return_value.models.generate_content.return_value = mock_response

        refine_document(original="# 原稿", feedback="用語を統一", doc_type="spec")

        call_args = mock_client.return_value.models.generate_content.call_args
        contents = call_args[1]["contents"]
        assert "本文のみ" in contents
        assert "フル再出力" in contents or "フル再出力" in contents

    def test_unified_markdown_diff_outputs_diff(self):
        from app.diff_utils import unified_markdown_diff

        a = "# A\n行1\n行2"
        b = "# A\n行1\n行2修正"
        diff = unified_markdown_diff(a, b, fromfile="old", tofile="new")
        assert isinstance(diff, str)
        assert "--- old" in diff
        assert "+++ new" in diff
        assert "-行2" in diff and "+行2修正" in diff
