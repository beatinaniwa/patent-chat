import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestPromptNoPreface:
    @patch("app.llm._get_client")
    def test_bootstrap_spec_prompt_contains_no_preface_instruction(self, mock_client):
        from app.llm import bootstrap_spec

        # Mock API response to avoid errors
        mock_response = MagicMock()
        mock_response.text = "# 特許明細書"
        mock_client.return_value.models.generate_content.return_value = mock_response

        bootstrap_spec(sample_manual_md="指示", idea_description="アイデア")

        # Inspect prompt passed to API
        call_args = mock_client.return_value.models.generate_content.call_args
        contents = call_args[1]["contents"]
        assert "前置きや挨拶は不要" in contents

    @patch("app.llm._get_client")
    def test_regenerate_spec_prompt_contains_no_preface_instruction(self, mock_client):
        from app.llm import regenerate_spec

        mock_response = MagicMock()
        mock_response.text = "# 特許明細書"
        mock_client.return_value.models.generate_content.return_value = mock_response

        regenerate_spec(instruction_md="指示", idea_description="アイデア", transcript=[])

        call_args = mock_client.return_value.models.generate_content.call_args
        contents = call_args[1]["contents"]
        assert "前置きや挨拶は不要" in contents

    @patch("app.llm._get_client")
    def test_refine_spec_prompt_contains_no_preface_instruction(self, mock_client):
        from app.llm import refine_spec

        mock_response = MagicMock()
        mock_response.text = "# 更新後の特許明細書"
        mock_client.return_value.models.generate_content.return_value = mock_response

        refine_spec(sample_manual_md="指示", transcript=[], current_spec_md="# 現行")

        call_args = mock_client.return_value.models.generate_content.call_args
        contents = call_args[1]["contents"]
        assert "前置きや挨拶は不要" in contents
