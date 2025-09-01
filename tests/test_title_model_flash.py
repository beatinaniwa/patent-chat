import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import llm


def test_title_model_ignores_env(monkeypatch):
    """GEMINI_TITLE_MODELを設定してもフラッシュが返る"""
    monkeypatch.setenv("GEMINI_TITLE_MODEL", "gemini-2.5-pro")
    assert llm._title_model_name() == "gemini-2.5-flash"
